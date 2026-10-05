# -*- coding: utf-8 -*-
"""应用配置：数据库连接、JWT 密钥与有效期。"""
from __future__ import annotations

import os
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent  # lab_reserve/

# 简历承诺：默认 SQLite（零依赖即可跑），通过环境变量 DATABASE_URL 可切 MySQL。
# MySQL 示例：mysql+pymysql://root:root@127.0.0.1:3306/lab_reserve?charset=utf8mb4
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    f"sqlite:///{(APP_DIR / 'lab_reserve.db').as_posix()}",
)

# JWT 密钥：生产环境应从环境变量/密钥管理服务注入，这里给默认值便于本地一键启动
SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "dev-secret-lab-reserve-change-me")
JWT_ALGORITHM = "HS256"
# 简历承诺：JWT 有效期 12 小时
ACCESS_TOKEN_EXPIRE_HOURS = 12
