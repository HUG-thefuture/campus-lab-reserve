# -*- coding: utf-8 -*-
"""打卡接口：POST /api/checkin（每日一次）与 GET /api/checkins/me（我的记录，分页）。"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import Checkin, User
from ..schemas import CheckinOut, CheckinPage

router = APIRouter(tags=["打卡"])


@router.post("/api/checkin", response_model=CheckinOut, status_code=status.HTTP_201_CREATED, summary="学生打卡（每天一次）")
def do_checkin(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Checkin:
    """当日打卡；重复打卡 -> 409 "今日已打卡"。

    双重保障（简历承诺：唯一约束）：
      1) 应用层先查一次，返回更友好的 409；
      2) 并发兜底靠 Checkin.__table_args__ 中的 UniqueConstraint(user_id, checkin_date)，
         数据库层拦截 IntegrityError 后同样转 409。
    """
    today = date.today()
    existing = (
        db.query(Checkin)
        .filter(Checkin.user_id == user.id, Checkin.checkin_date == today)
        .first()
    )
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="今日已打卡")

    record = Checkin(user_id=user.id, checkin_date=today)
    db.add(record)
    try:
        db.commit()
    except IntegrityError:
        # 并发兜底：两个请求同时通过应用层检查时，由唯一约束保证数据一致
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="今日已打卡")
    db.refresh(record)
    return record


@router.get("/api/checkins/me", response_model=CheckinPage, summary="我的打卡记录（分页，按日期降序）")
def my_checkins(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CheckinPage:
    q = db.query(Checkin).filter(Checkin.user_id == user.id)
    total = q.count()
    items = q.order_by(Checkin.checkin_date.desc(), Checkin.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return CheckinPage(total=total, page=page, page_size=page_size, items=items)
