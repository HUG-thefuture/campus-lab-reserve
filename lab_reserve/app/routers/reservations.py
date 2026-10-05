# -*- coding: utf-8 -*-
"""预约模块接口：创建 / 审核流 / 归还 / 取消 / 我的预约。

简历承诺：实现预约、审核与归还管理，支持时段冲突校验和状态流转。
状态机：PENDING -> APPROVED | REJECTED | CANCELED；APPROVED -> RETURNED。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..deps import get_current_user, require_roles
from ..models import Device, Reservation, ReservationStatus, User
from ..schemas import ReservationCreate, ReservationOut, ReservationPage, ReviewRequest

router = APIRouter(prefix="/api/reservations", tags=["预约"])


def _get_reservation_or_404(db: Session, reservation_id: int) -> Reservation:
    reservation = (
        db.query(Reservation)
        .options(joinedload(Reservation.device), joinedload(Reservation.user))
        .filter(Reservation.id == reservation_id)
        .first()
    )
    if reservation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="预约不存在")
    return reservation


@router.post("", response_model=ReservationOut, status_code=status.HTTP_201_CREATED, summary="创建预约")
def create_reservation(
    payload: ReservationCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Reservation:
    """创建预约（登录用户均可，典型场景为学生选设备）。

    校验顺序：
      1) 结束 > 开始       -> Pydantic model_validator，失败 422
      2) 设备存在          -> 404 设备不存在
      3) 时段冲突          -> 409 该时段已被预约
    """
    device = db.get(Device, payload.device_id)
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="设备不存在")

    # ---- 时段冲突校验（简历承诺：支持时段冲突校验）----
    # 重叠判定 SQL 条件：existing.start_time < new.end_time AND existing.end_time > new.start_time
    #
    # 为什么这样写：把每个预约视为左闭右开时间区间 [start, end)，两个区间相交的充要条件是
    #   “对方的开始早于我的结束” 且 “对方的结束晚于我的开始”。
    # 该条件一条 SQL 同时覆盖三种冲突形态：完全重叠、部分交叠、大区间包住小区间；
    # 且相邻时段（前一单 end == 后一单 start）因等号不成立被自然放行，不需要额外边界分支。
    # 只与“有效预约”（PENDING / APPROVED）比较：REJECTED/CANCELED/RETURNED 不占用设备。
    conflict = (
        db.query(Reservation)
        .filter(
            Reservation.device_id == payload.device_id,
            Reservation.status.in_(ReservationStatus.BLOCKING),
            Reservation.start_time < payload.end_time,
            Reservation.end_time > payload.start_time,
        )
        .first()
    )
    if conflict is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该时段已被预约")

    reservation = Reservation(
        user_id=user.id,
        device_id=payload.device_id,
        start_time=payload.start_time,
        end_time=payload.end_time,
        status=ReservationStatus.PENDING,
    )
    db.add(reservation)
    db.commit()
    # 重新带出关联对象，保证响应模型可完整序列化
    return db.get(Reservation, reservation.id, options=[joinedload(Reservation.device), joinedload(Reservation.user)])


@router.get("/mine", response_model=ReservationPage, summary="我的预约（分页）")
def my_reservations(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    user: User = Depends(get_current_user),  # 无 token / 无效 token -> 401
    db: Session = Depends(get_db),
) -> ReservationPage:
    q = (
        db.query(Reservation)
        .options(joinedload(Reservation.device), joinedload(Reservation.user))
        .filter(Reservation.user_id == user.id)
    )
    total = q.count()
    items = q.order_by(Reservation.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return ReservationPage(total=total, page=page, page_size=page_size, items=items)


@router.post("/{reservation_id}/status", response_model=ReservationOut, summary="审核预约（teacher/admin）")
def review_reservation(
    reservation_id: int,
    payload: ReviewRequest,
    user: User = Depends(require_roles("teacher", "admin")),  # student 调用 -> 403 "无权执行该操作"
    db: Session = Depends(get_db),
) -> Reservation:
    """审核流（简历承诺）：只允许 PENDING -> APPROVED / PENDING -> REJECTED。"""
    reservation = _get_reservation_or_404(db, reservation_id)
    if reservation.status != ReservationStatus.PENDING:
        # 状态流转约束：非 PENDING 一律拒绝（非法状态流转 -> 400）
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前状态不允许审核")
    reservation.status = payload.status
    db.commit()
    # 提交后按主键带关联重查一次，保证响应模型能完整序列化（与 create 保持同一模式）
    return _get_reservation_or_404(db, reservation_id)


@router.post("/{reservation_id}/return", response_model=ReservationOut, summary="归还设备")
def return_reservation(
    reservation_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Reservation:
    """归还（简历承诺）：student 本人或 teacher/admin 可操作；APPROVED -> RETURNED。"""
    reservation = _get_reservation_or_404(db, reservation_id)
    is_owner = reservation.user_id == user.id
    is_staff = user.role in ("teacher", "admin")
    if not (is_owner or is_staff):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权执行该操作")
    if reservation.status != ReservationStatus.APPROVED:
        # 只有“已通过”的预约才能归还，其余状态一律 400（简历承诺文案）
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前状态不允许归还")
    reservation.status = ReservationStatus.RETURNED
    db.commit()
    return _get_reservation_or_404(db, reservation_id)


@router.post("/{reservation_id}/cancel", response_model=ReservationOut, summary="取消预约（本人）")
def cancel_reservation(
    reservation_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Reservation:
    """取消（简历承诺）：仅本人可取消自己的 PENDING 预约 -> CANCELED。"""
    reservation = _get_reservation_or_404(db, reservation_id)
    if reservation.user_id != user.id:
        # 越权场景：他人（含 teacher）取消别人的预约 -> 403
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权执行该操作")
    if reservation.status != ReservationStatus.PENDING:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前状态不允许取消")
    reservation.status = ReservationStatus.CANCELED
    db.commit()
    return _get_reservation_or_404(db, reservation_id)
