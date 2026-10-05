# -*- coding: utf-8 -*-
"""Pydantic v2 请求/响应模型（study_checkin）。"""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RegisterRequest(BaseModel):
    username: str = Field(
        min_length=3, max_length=32, pattern=r"^[\w\u4e00-\u9fa5]+$", description="用户名，3-32 位字母/数字/下划线/中文"
    )
    password: str = Field(min_length=6, max_length=64, description="密码至少 6 位")
    role: Literal["student", "teacher", "admin"]


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=64)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    role: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="有效期（秒），12h = 43200")
    user: UserOut


class CheckinOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    checkin_date: date
    created_at: datetime


class CheckinPage(BaseModel):
    """我的打卡记录（分页）。"""

    total: int
    page: int
    page_size: int
    items: list[CheckinOut]


class LeaderboardItem(BaseModel):
    rank: int = Field(description="名次（按总打卡天数降序）")
    user_id: int
    username: str
    total_days: int


class LeaderboardPage(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[LeaderboardItem]


class StreakResponse(BaseModel):
    user_id: int
    username: str
    streak: int
    latest_date: date | None = Field(description="最近一次打卡日期，从未打卡为 null")
