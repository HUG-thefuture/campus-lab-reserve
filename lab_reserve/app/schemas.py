# -*- coding: utf-8 -*-
"""Pydantic v2 请求/响应模型：强类型参数校验。

简历承诺：Pydantic 统一参数校验 —— 密码>=6 位、角色枚举、时间格式、容量>0 等
约束全部声明在模型上，校验失败由 FastAPI 自动返回 422。
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ---------------------------------------------------------------- 用户
class RegisterRequest(BaseModel):
    """注册请求。"""

    username: str = Field(
        min_length=3, max_length=32, pattern=r"^[\w\u4e00-\u9fa5]+$", description="用户名，3-32 位字母/数字/下划线/中文"
    )
    # 简历承诺：密码 >= 6 位
    password: str = Field(min_length=6, max_length=64, description="密码至少 6 位")
    role: Literal["student", "teacher", "admin"] = Field(description="角色只允许 student/teacher/admin")


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=64)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    role: str


class TokenResponse(BaseModel):
    """登录成功响应（简历承诺：返回 JWT）。"""

    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="有效期（秒），12h = 43200")
    user: UserOut


# ---------------------------------------------------------------- 设备
class DeviceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    # 简历承诺：容量 > 0
    capacity: int = Field(gt=0, description="容量必须大于 0")
    description: str | None = Field(default=None, max_length=500)


class DeviceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    capacity: int
    description: str | None
    status: str
    created_at: datetime


class DevicePage(BaseModel):
    """设备分页响应。"""

    total: int
    page: int
    page_size: int
    items: list[DeviceOut]


# ---------------------------------------------------------------- 预约
class ReservationCreate(BaseModel):
    """创建预约（简历承诺：student 选设备 + start_time + end_time）。"""

    device_id: int = Field(gt=0)
    start_time: datetime = Field(description="开始时间，ISO 8601，如 2026-09-08T09:00:00")
    end_time: datetime = Field(description="结束时间，ISO 8601，须晚于开始时间")

    @field_validator("start_time", "end_time")
    @classmethod
    def normalize_naive(cls, v: datetime) -> datetime:
        """统一按本地墙上时间处理：若客户端带时区，仅保留字面时刻（去掉 tzinfo），
        避免 naive/aware 混用导致数据库比较口径不一致。"""
        if v.tzinfo is not None:
            v = v.replace(tzinfo=None)
        return v

    @model_validator(mode="after")
    def check_order(self) -> "ReservationCreate":
        # 简历承诺：校验“结束 > 开始”
        if self.end_time <= self.start_time:
            raise ValueError("end_time 必须晚于 start_time")
        return self


class ReviewRequest(BaseModel):
    """审核请求（简历承诺：PENDING -> APPROVED 或 PENDING -> REJECTED）。"""

    status: Literal["APPROVED", "REJECTED"]


class ReservationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    device_id: int
    device: DeviceOut
    start_time: datetime
    end_time: datetime
    status: str
    created_at: datetime


class ReservationPage(BaseModel):
    """预约分页响应（GET /api/reservations/mine 使用）。"""

    total: int
    page: int
    page_size: int
    items: list[ReservationOut]
