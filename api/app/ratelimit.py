"""Fixed-window rate limiting for the public demo.

Counters live in process memory, which is enough for a single-process portfolio
demo. A multi-instance deployment would need a shared store (Redis or similar);
that limitation is documented in the README rather than guessed at here.
"""

import threading
import time

from fastapi import HTTPException, Request

from . import settings

# bucket -> (default limit, default window in seconds, when to retry text)
BUCKETS: dict[str, tuple[int, int, str]] = {
    "integration": (120, 60, "integration requests"),
    "inquiry": (20, 3600, "public inquiry submissions"),
    "simulate": (5, 600, "simulated demo inquiries"),
    "classify": (10, 3600, "AI analyses"),
    "draft": (10, 3600, "draft replies"),
    "email": (5, 3600, "emails"),
    "login": (10, 300, "sign-in attempts"),
    "reset": (3, 3600, "demo data resets"),
}

_windows: dict[tuple[str, str], tuple[float, int]] = {}
_lock = threading.Lock()


def _now() -> float:
    return time.monotonic()


def _limit(bucket: str) -> tuple[int, int]:
    default_limit, default_window, _ = BUCKETS[bucket]
    return (
        settings.number(f"RATE_LIMIT_{bucket.upper()}", default_limit),
        settings.number(f"RATE_LIMIT_{bucket.upper()}_WINDOW_SECONDS", default_window),
    )


def identity(request: Request) -> str:
    """Identify a caller. Forwarded headers are trusted only when asked for."""
    if settings.flag("TRUST_PROXY_HEADERS"):
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded.strip():
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def reset() -> None:
    """Clear every counter (tests, and the demo reset path)."""
    with _lock:
        _windows.clear()


def enforce(bucket: str, request: Request) -> None:
    """Count one use of ``bucket`` for this caller, raising 429 when over limit."""
    limit, window = _limit(bucket)
    if limit <= 0:
        return
    key = (bucket, identity(request))
    now = _now()
    with _lock:
        started, count = _windows.get(key, (now, 0))
        if now - started >= window:
            started, count = now, 0
        if count >= limit:
            retry_after = max(1, int(round(window - (now - started))))
            _windows[key] = (started, count)
            raise HTTPException(
                status_code=429,
                detail=_message(bucket, retry_after),
                headers={"Retry-After": str(retry_after)},
            )
        _windows[key] = (started, count + 1)


def _message(bucket: str, retry_after: int) -> str:
    _, _, label = BUCKETS[bucket]
    wait = _humanize(retry_after)
    return f"Too many {label} from this address. Please try again in {wait}."
    

def _humanize(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds} second{'s' if seconds != 1 else ''}"
    minutes = int(round(seconds / 60))
    if minutes < 60:
        return f"about {minutes} minute{'s' if minutes != 1 else ''}"
    hours = int(round(minutes / 60))
    return f"about {hours} hour{'s' if hours != 1 else ''}"
