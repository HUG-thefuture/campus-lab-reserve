# -*- coding: utf-8 -*-
"""实验室设备预约系统后端 —— FastAPI 应用入口（端口 8010）。

简历承诺对应：
  - 使用 FastAPI + SQLAlchemy + MySQL 按用户、设备、预约划分模块接口
  - JWT 鉴权与角色控制；Pydantic 统一参数校验与错误返回
  - /docs 自动生成 OpenAPI 接口文档（Swagger UI）
  - 全局异常处理器：业务错误统一转 {"detail": ...} + 正确状态码（400/401/403/404/409）

启动：python -m uvicorn lab_reserve.app.main:app --host 127.0.0.1 --port 8010
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import models  # noqa: F401  导入以注册所有 ORM 模型
from .database import Base, engine
from .routers import devices, reservations, users

logger = logging.getLogger("lab_reserve")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # 启动时自动建表（SQLite/MySQL 通用；MySQL 生产部署也可用 schema.sql 手工建表）
    Base.metadata.create_all(bind=engine)
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="实验室设备预约系统后端",
        version="1.0.0",
        description=(
            "用户 / 设备 / 预约 / 审核 / 归还管理；JWT 鉴权与角色控制；"
            "时段冲突校验（409）；状态流转 PENDING→APPROVED/REJECTED/CANCELED，APPROVED→RETURNED。"
        ),
        lifespan=lifespan,
    )

    # ---- 全局异常处理器（简历承诺：统一错误返回 {detail} + 正确 HTTP 状态码）----

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        """业务错误（HTTPException(detail=...)）统一转 {"detail": ...}。"""
        detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        return JSONResponse(status_code=exc.status_code, content={"detail": detail})

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        """Pydantic 参数校验失败：FastAPI 自动返回 422，这里仅做格式统一（可读的字段路径）。"""
        errors = [
            {
                "loc": ".".join(str(loc) for loc in err.get("loc", [])),
                "msg": err.get("msg", "参数校验失败"),
            }
            for err in exc.errors()
        ]
        return JSONResponse(status_code=422, content={"detail": errors})

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """兜底：未预期异常返回 500，不向前端泄露堆栈。"""
        logger.exception("未处理异常: %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": "服务器内部错误"})

    # ---- 按模块挂载路由：用户 / 设备 / 预约（简历承诺：按模块划分接口）----
    app.include_router(users.router)
    app.include_router(devices.router)
    app.include_router(reservations.router)

    @app.get("/health", tags=["运维"], summary="健康检查")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "lab_reserve"}

    @app.get("/", tags=["运维"], summary="服务信息")
    def root() -> dict[str, str]:
        return {"service": "实验室设备预约系统后端", "docs": "/docs"}

    return app


app = create_app()
