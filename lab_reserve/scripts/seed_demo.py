# -*- coding: utf-8 -*-
"""演示种子数据：一键生成可登录账号 + 设备 + 各状态预约，开箱即演。

为什么有这个脚本：此前演示必须先现场注册账号、再手工造设备，
面试/评审环境里既慢又容易卡壳——"能演示"不等于"好演示"。

用法：
  python scripts/seed_demo.py            # 已有数据则跳过（幂等）
  python scripts/seed_demo.py --reset    # 清空三张表后重建（演示库专用，勿对生产库使用）

账号（密码统一 123456，仅演示）：
  admin / teacher01 / student01 / student02 —— 覆盖 admin/teacher/student 三种角色。
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal  # noqa: E402
from app.models import Device, Reservation, User  # noqa: E402
from app.security import hash_password  # noqa: E402

DEVICES = [
    ("数字示波器套件", 2, "100MHz 四通道，含探头与校准记录"),
    ("3D 打印机", 1, "FDM 0.4mm 喷嘴，需预约耗材"),
    ("高性能计算工作站", 4, "128G 内存 + RTX 显卡，深度学习训练用"),
    ("逻辑分析仪", 2, "16 通道，配合示波器做时序调试"),
    ("FPGA 开发板", 3, "Xilinx 系列，含 JTAG 下载器"),
    ("可编程电子负载仪", 1, "300W，电源模块测试用"),
]


def seed(session) -> None:
    users = {
        "admin": User(username="admin", password_hash=hash_password("123456"), role="admin"),
        "teacher01": User(username="teacher01", password_hash=hash_password("123456"), role="teacher"),
        "student01": User(username="student01", password_hash=hash_password("123456"), role="student"),
        "student02": User(username="student02", password_hash=hash_password("123456"), role="student"),
    }
    session.add_all(users.values())
    session.flush()  # 拿到 user.id

    devices = [Device(name=n, capacity=c, description=d) for n, c, d in DEVICES]
    session.add_all(devices)
    session.flush()

    now = datetime.now()
    reservations = [
        # 各状态至少一条：演示状态机流转（PENDING→APPROVED→RETURNED / REJECTED）
        Reservation(user_id=users["student01"].id, device_id=devices[0].id,
                    start_time=now.replace(hour=10, minute=0, second=0, microsecond=0),
                    end_time=now.replace(hour=12, minute=0, second=0, microsecond=0),
                    status="APPROVED"),
        Reservation(user_id=users["student02"].id, device_id=devices[1].id,
                    start_time=(now + timedelta(days=1)).replace(hour=14, minute=0,
                                                                 second=0, microsecond=0),
                    end_time=(now + timedelta(days=1)).replace(hour=16, minute=0,
                                                               second=0, microsecond=0),
                    status="PENDING"),
        Reservation(user_id=users["student01"].id, device_id=devices[2].id,
                    start_time=(now + timedelta(days=2)).replace(hour=9, minute=0,
                                                                 second=0, microsecond=0),
                    end_time=(now + timedelta(days=2)).replace(hour=11, minute=0,
                                                               second=0, microsecond=0),
                    status="PENDING"),
        Reservation(user_id=users["student02"].id, device_id=devices[4].id,
                    start_time=now - timedelta(days=7, hours=2),
                    end_time=now - timedelta(days=7),
                    status="RETURNED"),
        Reservation(user_id=users["student01"].id, device_id=devices[3].id,
                    start_time=now - timedelta(days=1),
                    end_time=now + timedelta(hours=2),
                    status="REJECTED"),
    ]
    session.add_all(reservations)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true", help="清空三张表后重建（演示库专用）")
    args = ap.parse_args()

    with SessionLocal() as session:
        existing = session.query(User).count()
        if existing and not args.reset:
            print(f"seed: 已存在 {existing} 个用户，跳过（--reset 可重建）")
            return 0
        if args.reset:
            session.query(Reservation).delete()
            session.query(Device).delete()
            session.query(User).delete()
            session.commit()
        seed(session)
        session.commit()
        print("seed: 完成 —— admin / teacher01 / student01 / student02（密码均 123456，仅演示）")
        print(f"  设备 {session.query(Device).count()} 台，"
              f"预约 {session.query(Reservation).count()} 条（含各状态）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
