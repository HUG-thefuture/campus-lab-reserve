# -*- coding: utf-8 -*-
"""用户模块接口：注册 / 登录（简历承诺：JWT 鉴权入口）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import ACCESS_TOKEN_EXPIRE_HOURS
from ..database import get_db
from ..deps import get_current_user
from ..models import User
from ..schemas import LoginRequest, RegisterRequest, TokenResponse, UserOut
from ..security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/api", tags=["用户"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED, summary="注册用户")
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> User:
    """注册（角色只允许 student/teacher/admin，由 Pydantic Literal 校验，非法值 -> 422）。"""
    if db.query(User).filter(User.username == payload.username).first() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="用户名已存在")
    user = User(username=payload.username, password_hash=hash_password(payload.password), role=payload.role)
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        # 并发兜底：users.username 唯一约束
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="用户名已存在")
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse, summary="登录获取 JWT")
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """登录成功返回 JWT（payload 含 sub/role，有效期 12h；简历承诺）。"""
    user = db.query(User).filter(User.username == payload.username).first()
    # 用户不存在与密码错误返回同一提示，避免枚举用户名
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    token = create_access_token(user.id, user.role)
    return TokenResponse(access_token=token, expires_in=ACCESS_TOKEN_EXPIRE_HOURS * 3600, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut, summary="查看当前用户信息")
def me(user: User = Depends(get_current_user)) -> User:
    """需要携带有效 JWT；无 token/无效 token -> 401。"""
    return user
