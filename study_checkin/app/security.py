# -*- coding: utf-8 -*-
"""安全模块：PBKDF2 口令哈希 + JWT 签发/校验（与项目一同一套实现）。

口令哈希说明：使用标准库 hashlib.pbkdf2_hmac（随机盐 + 10 万次迭代），避免重依赖；
生产环境建议替换为 BCrypt 或 argon2。
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from .config import ACCESS_TOKEN_EXPIRE_HOURS, JWT_ALGORITHM, SECRET_KEY

_ITERATIONS = 100_000
_SALT_BYTES = 16


def hash_password(password: str) -> str:
    salt = secrets.token_hex(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), _ITERATIONS)
    return f"pbkdf2_sha256${_ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _scheme, iterations, salt, expected_hex = stored.split("$")
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt), int(iterations)
        )
        return hmac.compare_digest(digest.hex(), expected_hex)
    except (ValueError, TypeError):
        return False


def create_access_token(user_id: int, role: str) -> str:
    """签发 JWT：payload 含 sub（用户 id）与 role，12 小时后过期。"""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "role": role,
        "iat": int(now.timestamp()),
        "exp": now + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    """校验并解码 JWT；失败时抛 HTTPException(401)。"""
    from fastapi import HTTPException

    try:
        payload: dict[str, Any] = jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="无效的登录凭证")
    sub = payload.get("sub")
    if sub is None or not str(sub).isdigit():
        raise HTTPException(status_code=401, detail="无效的登录凭证")
    return payload
