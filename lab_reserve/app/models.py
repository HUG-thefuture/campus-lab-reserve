# -*- coding: utf-8 -*-
"""ORM 模型：用户 / 设备 / 预约（SQLAlchemy 2.0 Mapped 风格）。

简历承诺：实现用户、设备、预约、审核与归还管理，支持状态流转。
状态机：PENDING -> APPROVED | REJECTED | CANCELED；APPROVED -> RETURNED。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class ReservationStatus:
    """预约状态常量（与 schema.sql 中 ENUM 保持一致）。"""

    PENDING = "PENDING"      # 待审核
    APPROVED = "APPROVED"    # 已通过（占用设备）
    REJECTED = "REJECTED"    # 已驳回
    CANCELED = "CANCELED"    # 已取消
    RETURNED = "RETURNED"    # 已归还

    # 参与时段冲突判定的“有效”状态：只有待审核和已通过的预约才占用设备
    BLOCKING = (PENDING, APPROVED)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    # 只存 PBKDF2 哈希（见 security.py），绝不存明文
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    # 角色：student / teacher / admin（简历承诺：JWT 鉴权 + 角色控制）
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="student")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    # 容量（可同时使用人数），Pydantic 侧约束 >0
    capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="AVAILABLE")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)


class Reservation(Base):
    __tablename__ = "reservations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), nullable=False, index=True)
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=ReservationStatus.PENDING)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)

    # 关系：序列化时输出设备/用户信息（查询处用 joinedload 预加载避免 N+1）
    device: Mapped["Device"] = relationship(lazy="joined")
    user: Mapped["User"] = relationship(lazy="joined")
