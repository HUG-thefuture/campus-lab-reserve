# -*- coding: utf-8 -*-
"""应用配置：数据库连接、JWT 密钥与有效期（独立应用、独立数据库）。"""
from __future__ import annotations

import os
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent  # study_checkin/

# 默认 SQLite（零依赖即可跑）；环境变量 DATABASE_URL 可切 MySQL：
#   mysql+pymysql://root:root@127.0.0.1:3306/study_checkin?charset=utf8mb4
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    f"sqlite:///{(APP_DIR / 'study_checkin.db').as_posix()}",
)

SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "dev-secret-study-checkin-change-me")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 12  # 与项目一保持一致：JWT 有效期 12h
