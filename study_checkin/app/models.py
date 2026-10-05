# -*- coding: utf-8 -*-
"""ORM 模型：用户 / 打卡记录。

简历承诺：唯一约束 UniqueConstraint(user_id, checkin_date) 保证每天只能打卡一次。
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="student")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)

    checkins: Mapped[list["Checkin"]] = relationship(back_populates="user")


class Checkin(Base):
    __tablename__ = "checkins"
    # 简历承诺：唯一约束保证“每天一次打卡”，重复打卡由应用层转 409 "今日已打卡"
    __table_args__ = (
        UniqueConstraint("user_id", "checkin_date", name="uq_user_checkin_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    checkin_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)

    user: Mapped["User"] = relationship(back_populates="checkins")
