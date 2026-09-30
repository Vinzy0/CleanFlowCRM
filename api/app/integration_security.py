"""Integration credentials and outbound SSRF boundary. Never log credentials."""
import hashlib
import http.client
import ipaddress
import socket
import ssl
from urllib.parse import urlsplit

from cryptography.fernet import Fernet, InvalidToken
from fastapi import Depends, HTTPException, Request
from fastapi.security import APIKeyHeader
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import ratelimit, settings
from .db import get_db
from .models import IntegrationKey, User, now_utc

SCOPES = {"leads:read", "leads:write"}
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def cipher() -> Fernet:
    try:
        return Fernet((settings.env("INTEGRATION_ENCRYPTION_KEY", "") or "").encode())
    except (ValueError, TypeError):
        raise HTTPException(503, "Integration encryption is not configured") from None


def encrypt(value: str) -> str:
    return cipher().encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    try:
        return cipher().decrypt(value.encode()).decode()
    except InvalidToken:
        raise HTTPException(503, "Integration configuration cannot be decrypted") from None


def owner_only(user: User) -> None:
    if user.is_demo or settings.flag("DEMO_MODE"):
        raise HTTPException(403, "Integrations are disabled in the demo workspace")


def external_key(request: Request, raw: str | None = Depends(api_key_header), db: Session = Depends(get_db)) -> IntegrationKey:
    ratelimit.enforce("integration", request)
    if settings.flag("DEMO_MODE"):
        raise HTTPException(403, "External integrations are disabled in demo mode")
    raw = raw or ""
    if not raw.startswith("tavo_") or len(raw) > 120:
        raise HTTPException(401, "Invalid API key")
    key = db.scalar(select(IntegrationKey).where(IntegrationKey.digest == hashlib.sha256(raw.encode()).hexdigest()))
    if key is None or key.revoked_at is not None:
        raise HTTPException(401, "Invalid API key")
    user = db.get(User, key.owner_id)
    if user is None or user.is_demo:
        raise HTTPException(403, "Integration owner is unavailable")
    key.last_used_at = now_utc()
    db.commit()
    return key


def require_scope(key: IntegrationKey, scope: str) -> None:
    if scope not in key.scopes:
        raise HTTPException(403, "API key does not permit this operation")


def validate_url(value: str) -> str:
    try:
        parts = urlsplit(value)
        if (parts.scheme != "https" or not parts.hostname or parts.username or parts.password
                or parts.port not in (None, 443) or parts.fragment
                or any(ord(c) <= 32 or ord(c) == 127 for c in value) or "\\" in value):
            raise ValueError()
        host = parts.hostname.encode("idna").decode()
        if len(host) > 253:
            raise ValueError()
        return host
    except (ValueError, UnicodeError):
        raise ValueError("Use a public HTTPS URL on port 443 without credentials or fragments") from None


def public_addresses(host: str) -> list[str]:
    addresses = list(dict.fromkeys(info[4][0] for info in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)))
    if not addresses:
        raise ValueError("Destination DNS returned no addresses")
    # Reject a mixed public/private answer too. Validate again on every attempt.
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if not ip.is_global or ip.is_multicast or ip.is_reserved or getattr(ip, "ipv4_mapped", None) is not None:
            raise ValueError("Destination must resolve only to public addresses")
    return addresses


class PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host: str, address: str):
        super().__init__(host, 443, timeout=10, context=ssl.create_default_context())
        self.address = address

    def connect(self):
        # Pin the vetted address while retaining original-host TLS verification/SNI.
        sock = socket.create_connection((self.address, 443), self.timeout)
        try:
            self.sock = self._context.wrap_socket(sock, server_hostname=self.host)
        except BaseException:
            sock.close()
            raise


def send_webhook(url: str, body: bytes, headers: dict[str, str]) -> int:
    host = validate_url(url)
    address = public_addresses(host)[0]
    parts = urlsplit(url)
    path = parts.path or "/"
    if parts.query:
        path += "?" + parts.query
    connection = PinnedHTTPSConnection(host, address)
    try:
        connection.request("POST", path, body=body, headers=headers)
        response = connection.getresponse()
        # Status only: do not persist arbitrary receiver bodies or follow redirects.
        return response.status
    finally:
        connection.close()


def get_webhook_sender():
    return send_webhook
