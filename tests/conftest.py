# -*- coding: utf-8 -*-
"""pytest 夹具：每个用例启动“真实 uvicorn 子进程 + 全新临时 SQLite 文件”。

验证方式（与简历口径一致）：
  - pytest + requests 打真实 HTTP（127.0.0.1:80xx），不是 TestClient 内存模拟；
  - 每个用例（test function）拿到独立的临时 SQLite 数据库文件，
    数据库随用例创建、随用例销毁 —— 天然实现“每用例重置”；
  - 服务端口优先使用简历口径的 8010/8011，被占用时自动退回随机空闲端口，
    避免与本机已手工启动的服务冲突。
"""
from __future__ import annotations

import os
import socket
import sqlite3
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent   # project/
VENDOR_DIR = PROJECT_DIR / "vendor"                    # 离线依赖目录

# 直接 `python -m pytest`（未经过 run_tests.sh 设置 PYTHONPATH）时也能从 vendor 导入。
# 注意：必须在 import pytest / requests 之前插入 vendor 到 sys.path，
# 否则这两条 import 会先于 vendor 生效而直接 ImportError。
if VENDOR_DIR.is_dir() and str(VENDOR_DIR) not in sys.path:
    sys.path.insert(0, str(VENDOR_DIR))

import pytest
import requests


# ------------------------------------------------------------------ 基础设施
def _pick_port(preferred: int) -> int:
    """优先用简历口径端口；被占用则退回随机空闲端口。"""
    for port in (preferred, 0):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port if port != 0 else s.getsockname()[1]
    raise RuntimeError("无法获取可用端口")


def _wait_health(base: str, timeout: float = 30.0) -> None:
    """轮询 /health 直到 200（等待 uvicorn 完成冷启动与建表）。"""
    deadline = time.time() + timeout
    last_err: object = None
    while time.time() < deadline:
        try:
            if requests.get(base + "/health", timeout=2).status_code == 200:
                return
        except requests.RequestException as exc:  # 连接拒绝属正常，继续等
            last_err = exc
        time.sleep(0.15)
    raise RuntimeError(f"服务未就绪：{base}（最后错误：{last_err}）")


class Service:
    """一个被测服务的封装：HTTP 根地址 + SQLite 文件路径 + uvicorn 子进程。"""

    def __init__(self, app_module: str, preferred_port: int, tmp_dir: Path):
        port = _pick_port(preferred_port)
        self.base = f"http://127.0.0.1:{port}"
        self.db_path = tmp_dir / f"{app_module.replace('.', '_')}.db"

        env = os.environ.copy()
        env["DATABASE_URL"] = f"sqlite:///{self.db_path.as_posix()}"  # 每用例全新库
        env["PYTHONIOENCODING"] = "utf-8"
        parts = [str(PROJECT_DIR)]
        if VENDOR_DIR.is_dir():
            parts.append(str(VENDOR_DIR))
        env["PYTHONPATH"] = os.pathsep.join(parts)

        self._proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", f"{app_module}.app.main:app",
             "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"],
            cwd=str(PROJECT_DIR), env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
        try:
            _wait_health(self.base)
        except Exception:
            self.stop()
            output = b""
            if self._proc.stdout is not None:
                try:
                    output = self._proc.stdout.read() or b""
                except Exception:
                    pass
            raise RuntimeError(
                f"{app_module} 启动失败，子进程输出：\n{output.decode('utf-8', 'replace')}"
            )

    def stop(self) -> None:
        if self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._proc.kill()
                self._proc.wait(timeout=5)

    # ---------------------------------------------------------- HTTP 快捷方法
    def _req(self, method: str, path: str, token: str | None = None, **kwargs) -> requests.Response:
        headers = kwargs.pop("headers", {})
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return requests.request(method, self.base + path, headers=headers, timeout=10, **kwargs)

    def get(self, path: str, token: str | None = None, **kwargs) -> requests.Response:
        return self._req("GET", path, token, **kwargs)

    def post(self, path: str, token: str | None = None, **kwargs) -> requests.Response:
        return self._req("POST", path, token, **kwargs)

    # ---------------------------------------------------------- 常用业务步骤
    def register(self, username: str, password: str = "pass123", role: str = "student",
                 expect: int = 201) -> dict:
        r = self.post("/api/register", json={"username": username, "password": password, "role": role})
        assert r.status_code == expect, f"注册 {username} 期望 {expect} 实际 {r.status_code}: {r.text}"
        return r.json()

    def login(self, username: str, password: str = "pass123", expect: int = 200) -> dict:
        r = self.post("/api/login", json={"username": username, "password": password})
        assert r.status_code == expect, f"登录 {username} 期望 {expect} 实际 {r.status_code}: {r.text}"
        return r.json()

    def token(self, username: str, password: str = "pass123") -> str:
        return self.login(username, password)["access_token"]

    def make_user(self, username: str, role: str = "student", password: str = "pass123") -> str:
        """注册 + 登录，直接返回可用 token（测试常用前置步骤）。"""
        self.register(username, password, role)
        return self.token(username, password)

    # ---------------------------------------------------------- 测试数据构造
    def seed_checkins(self, user_id: int, dates: list[date]) -> None:
        """绕过 HTTP 直接向 SQLite 写历史打卡（连续天数/排行榜场景需要过去日期，
        而打卡接口只允许打当天；直连同一个 SQLite 文件写入是构造数据的最简方式）。
        注意 created_at 是 Python 侧默认值，直插 SQL 必须显式提供。"""
        conn = sqlite3.connect(self.db_path, timeout=10)
        try:
            conn.executemany(
                "INSERT INTO checkins (user_id, checkin_date, created_at) VALUES (?, ?, ?)",
                [(user_id, d.isoformat(), d.isoformat() + " 08:30:00") for d in dates],
            )
            conn.commit()
        finally:
            conn.close()


# ------------------------------------------------------------------ 夹具
@pytest.fixture()
def lab(tmp_path: Path):
    """项目一：实验室设备预约系统后端（每用例全新 SQLite + 真实 uvicorn 子进程）。"""
    svc = Service("lab_reserve", 8010, tmp_path)
    yield svc
    svc.stop()


@pytest.fixture()
def study(tmp_path: Path):
    """项目二：自习打卡统计接口（每用例全新 SQLite + 真实 uvicorn 子进程）。"""
    svc = Service("study_checkin", 8011, tmp_path)
    yield svc
    svc.stop()
