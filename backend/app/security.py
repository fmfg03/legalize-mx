from __future__ import annotations

import hashlib
import secrets


API_KEY_PREFIX_LENGTH = 12
API_KEY_TOKEN_BYTES = 24


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def generate_api_key() -> tuple[str, str, str]:
    secret = secrets.token_urlsafe(API_KEY_TOKEN_BYTES)
    raw_key = f"lmx_{secret}"
    prefix = raw_key[:API_KEY_PREFIX_LENGTH]
    return raw_key, prefix, hash_api_key(raw_key)
