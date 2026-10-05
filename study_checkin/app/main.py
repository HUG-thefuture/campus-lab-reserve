# -*- coding: utf-8 -*-
"""自习打卡统计接口 —— FastAPI 应用入口（端口 8011）。

简历承诺对应：
  - 提供打卡记录、连续天数统计与排行榜查询接口
  - FastAPI + MySQL：唯一约束、聚合查询与分页
  - /docs 自动生成 OpenAPI 文档；统一错误返回 {detail} + 正确状态码

启动：python -m uvicorn study_checkin.app.main:app --host 127.0.0.1 --port 8011
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
from .routers import checkins, stats, users

logger = logging.getLogger("study_checkin")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="自习打卡统计接口",
        version="1.0.0",
        description="打卡（唯一约束每日一次）/ 连续天数统计 / 排行榜（GROUP BY + COUNT + ORDER BY）/ 我的记录分页。",
        lifespan=lifespan,
    )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        """业务错误统一转 {"detail": ...} + 正确状态码（400/401/403/404/409）。"""
        detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        return JSONResponse(status_code=exc.status_code, content={"detail": detail})

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        """Pydantic 校验失败：FastAPI 自动 422，这里统一格式。"""
        errors = [
            {"loc": ".".join(str(loc) for loc in err.get("loc", [])), "msg": err.get("msg", "参数校验失败")}
            for err in exc.errors()
        ]
        return JSONResponse(status_code=422, content={"detail": errors})

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("未处理异常: %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": "服务器内部错误"})

    app.include_router(users.router)
    app.include_router(checkins.router)
    app.include_router(stats.router)

    @app.get("/health", tags=["运维"], summary="健康检查")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "study_checkin"}

    @app.get("/", tags=["运维"], summary="服务信息")
    def root() -> dict[str, str]:
        return {"service": "自习打卡统计接口", "docs": "/docs"}

    return app


app = create_app()
