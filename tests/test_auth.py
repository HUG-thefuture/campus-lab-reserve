# -*- coding: utf-8 -*-
"""认证模块用例（简历承诺：JWT 鉴权；Pydantic 统一校验；401/409/422 状态码）。"""
from __future__ import annotations


# ------------------------------------------------------------- 注册
def test_register_success_201(lab):
    body = lab.register("alice", role="student")
    assert body["id"] > 0
    assert body["username"] == "alice"
    assert body["role"] == "student"
    # 响应不泄露口令哈希
    assert "password" not in body and "password_hash" not in body


def test_register_duplicate_409(lab):
    lab.register("alice")
    r = lab.post("/api/register", json={"username": "alice", "password": "pass123", "role": "student"})
    assert r.status_code == 409
    assert r.json()["detail"] == "用户名已存在"


def test_register_invalid_role_422(lab):
    # 角色只允许 student/teacher/admin（Pydantic Literal 校验）
    r = lab.post("/api/register", json={"username": "eve", "password": "pass123", "role": "root"})
    assert r.status_code == 422


def test_register_validation_422(lab):
    """密码 <6 位、用户名 <3 位均被 Pydantic 拦截。"""
    r1 = lab.post("/api/register", json={"username": "alice", "password": "123", "role": "student"})
    r2 = lab.post("/api/register", json={"username": "ab", "password": "pass123", "role": "student"})
    assert r1.status_code == 422
    assert r2.status_code == 422


# ------------------------------------------------------------- 登录
def test_login_success_returns_jwt(lab):
    lab.register("alice")
    body = lab.login("alice")
    assert body["token_type"] == "bearer"
    assert len(body["access_token"]) > 30          # 形如 JWT 的长字符串
    assert body["expires_in"] == 12 * 3600         # 简历承诺：12h
    assert body["user"]["username"] == "alice"


def test_login_wrong_password_401(lab):
    lab.register("alice")
    r = lab.post("/api/login", json={"username": "alice", "password": "wrong66"})
    assert r.status_code == 401
    assert r.json()["detail"] == "用户名或密码错误"


def test_login_unknown_user_401(lab):
    r = lab.post("/api/login", json={"username": "nobody", "password": "pass123"})
    assert r.status_code == 401


# ------------------------------------------------------------- /api/me
def test_me_with_token_200(lab):
    token = lab.make_user("alice", role="teacher")
    r = lab.get("/api/me", token=token)
    assert r.status_code == 200
    assert r.json() == {"id": 1, "username": "alice", "role": "teacher"}


def test_me_without_token_401(lab):
    r = lab.get("/api/me")
    assert r.status_code == 401


def test_me_with_garbage_token_401(lab):
    r = lab.get("/api/me", token="not.a.jwt")
    assert r.status_code == 401
    r2 = lab.get("/api/me", token="ey123.bad.sig")  # 结构像 JWT 但签名错误
    assert r2.status_code == 401
