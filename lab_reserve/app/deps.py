# -*- coding: utf-8 -*-
"""鉴权依赖：从请求头解析 JWT 并加载当前用户；角色控制依赖工厂。

简历承诺：使用 JWT 实现鉴权与角色控制。
- get_current_user：无 token / token 无效 / 用户不存在 -> 401
- require_roles(...)?：角色不符 -> 403 "无权执行该操作"
"""
from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .database import get_db
from .models import User
from .security import decode_token

# auto_error=False：缺少 Authorization 头时不由 FastAPI 抛 403，而是交给我们统一抛 401
_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    """解析 Bearer Token 并返回当前用户。"""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录，请先携带 Bearer Token")
    payload = decode_token(credentials.credentials)  # 内部校验失败 -> 401
    user = db.get(User, int(payload["sub"]))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在或已被删除")
    return user


def require_roles(*allowed_roles: str) -> Callable[..., User]:
    """角色控制依赖工厂：require_roles("teacher", "admin") 生成校验依赖。"""

    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed_roles:
            # 简历承诺/测试场景：student 调用审核接口 -> 403 "无权执行该操作"
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权执行该操作")
        return user

    return checker
