# -*- coding: utf-8 -*-
"""设备模块接口：创建（teacher/admin）/ 分页列表 + 名称搜索 / 详情。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_roles
from ..models import Device, User
from ..schemas import DeviceCreate, DeviceOut, DevicePage

router = APIRouter(prefix="/api/devices", tags=["设备"])


@router.post("", response_model=DeviceOut, status_code=status.HTTP_201_CREATED, summary="新增设备（teacher/admin）")
def create_device(
    payload: DeviceCreate,
    user: User = Depends(require_roles("teacher", "admin")),  # 简历承诺：角色控制，student -> 403
    db: Session = Depends(get_db),
) -> Device:
    device = Device(name=payload.name, capacity=payload.capacity, description=payload.description)
    db.add(device)
    db.commit()
    db.refresh(device)
    return device


@router.get("", response_model=DevicePage, summary="设备列表（分页 + 按名称搜索）")
def list_devices(
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(10, ge=1, le=100, description="每页条数，1-100"),
    name: str | None = Query(None, max_length=100, description="按名称模糊搜索"),
    db: Session = Depends(get_db),
) -> DevicePage:
    q = db.query(Device)
    if name:
        # ilike 在 SQLite 上生成 LIKE，在 MySQL 上生成 LOWER() 比较，均大小写不敏感
        q = q.filter(Device.name.ilike(f"%{name}%"))
    total = q.count()
    items = q.order_by(Device.id).offset((page - 1) * page_size).limit(page_size).all()
    return DevicePage(total=total, page=page, page_size=page_size, items=items)


@router.get("/{device_id}", response_model=DeviceOut, summary="设备详情")
def get_device(device_id: int, db: Session = Depends(get_db)) -> Device:
    device = db.get(Device, device_id)
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="设备不存在")
    return device
