"""Receiver-side example: verify raw bytes BEFORE parsing JSON or applying actions."""
import hashlib
import hmac
import time


def verify_signature(secret: str, header: str, body: bytes, *, now: int | None = None, tolerance: int = 300) -> bool:
    try:
        parts = dict(item.split("=", 1) for item in header.split(","))
        timestamp = int(parts["t"])
        if abs((int(time.time()) if now is None else now) - timestamp) > tolerance:
            return False
        expected = hmac.new(secret.encode(), str(timestamp).encode() + b"." + body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(parts["v1"], expected)
    except (ValueError, KeyError, TypeError):
        return False
