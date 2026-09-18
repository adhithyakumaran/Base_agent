"""P10.1 — warm-server authentication, CORS, and security helpers."""

from __future__ import annotations

import json
import os
import sys
import threading
from typing import Any

MAX_BODY_BYTES = int(os.environ.get("SCOUT_MAX_BODY_BYTES", "2097152"))
_MAX_CONCURRENT = int(os.environ.get("SCOUT_MAX_CONCURRENT_REQUESTS", "32"))
_concurrency = threading.Semaphore(_MAX_CONCURRENT)


def scout_env() -> str:
    return (os.environ.get("SCOUT_ENV") or os.environ.get("NODE_ENV") or "development").strip().lower()


def is_production() -> bool:
    return scout_env() == "production"


def allow_insecure_local() -> bool:
    if is_production():
        return False
    return os.environ.get("SCOUT_ALLOW_INSECURE_LOCAL", "true").strip().lower() in {"1", "true", "yes", "on"}


def internal_api_token() -> str | None:
    token = (os.environ.get("SCOUT_INTERNAL_API_TOKEN") or os.environ.get("SCOUT_API_TOKEN") or "").strip()
    return token or None


def auth_configuration_error() -> str | None:
    if is_production() and not internal_api_token():
        return "SCOUT_INTERNAL_API_TOKEN required in production"
    return None


def allowed_origin() -> str:
    explicit = (os.environ.get("SCOUT_ALLOWED_ORIGIN") or "").strip()
    if explicit:
        return explicit
    return "http://127.0.0.1:43123"


def bind_host_default() -> str:
    return (os.environ.get("SCOUT_AGENT_BIND_HOST") or "127.0.0.1").strip() or "127.0.0.1"


def assert_bind_host(host: str) -> None:
    if host in {"127.0.0.1", "localhost", "::1"}:
        return
    if os.environ.get("SCOUT_ALLOW_EXTERNAL_BIND", "").strip().lower() in {"1", "true", "yes", "on"}:
        return
    raise SystemExit(
        f"Refusing to bind {host!r} without SCOUT_ALLOW_EXTERNAL_BIND=true (default loopback only)"
    )


def extract_bearer(header_value: str | None) -> str | None:
    if not header_value:
        return None
    value = header_value.strip()
    if value.lower().startswith("bearer "):
        return value[7:].strip()
    return value


def is_authenticated(headers: Any) -> bool:
    err = auth_configuration_error()
    if err:
        return False
    expected = internal_api_token()
    if not expected:
        return allow_insecure_local()
    provided = extract_bearer(headers.get("Authorization") or headers.get("authorization"))
    if provided == expected:
        return True
    alt = headers.get("X-Scout-Internal-Token") or headers.get("x-scout-internal-token")
    if alt and str(alt).strip() == expected:
        return True
    return False


def security_log(event: str, **fields: Any) -> None:
    payload = {"security_event": event, **fields}
    sys.stderr.write(json.dumps(payload, default=str) + "\n")


def log_auth_rejection(path: str, reason: str) -> None:
    security_log("auth_rejected", path=path, reason=reason)


def cors_headers(origin_header: str | None) -> dict[str, str]:
    allowed = allowed_origin()
    if is_production() and origin_header and origin_header != allowed:
        return {}
    if origin_header and origin_header != allowed:
        if not allow_insecure_local():
            return {}
    return {
        "Access-Control-Allow-Origin": allowed if is_production() else (origin_header or allowed),
        "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Scout-Internal-Token",
        "Vary": "Origin",
    }


def acquire_concurrency() -> bool:
    return _concurrency.acquire(blocking=False)


def release_concurrency() -> None:
    _concurrency.release()


def validate_body_size(length: int) -> bool:
    return 0 <= length <= MAX_BODY_BYTES
