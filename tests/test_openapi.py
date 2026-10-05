# -*- coding: utf-8 -*-
"""OpenAPI 文档用例（简历承诺：/docs 自动生成 OpenAPI 接口文档）。"""
from __future__ import annotations


def test_lab_openapi_docs(lab):
    assert lab.get("/docs").status_code == 200
    r = lab.get("/openapi.json")
    assert r.status_code == 200
    paths = r.json()["paths"]
    for expected in ("/api/register", "/api/login", "/api/me",
                     "/api/devices", "/api/devices/{device_id}",
                     "/api/reservations", "/api/reservations/mine",
                     "/api/reservations/{reservation_id}/status",
                     "/api/reservations/{reservation_id}/return",
                     "/api/reservations/{reservation_id}/cancel"):
        assert expected in paths, f"OpenAPI 缺少 {expected}"


def test_study_openapi_docs(study):
    assert study.get("/docs").status_code == 200
    r = study.get("/openapi.json")
    assert r.status_code == 200
    paths = r.json()["paths"]
    for expected in ("/api/register", "/api/login", "/api/me",
                     "/api/checkin", "/api/checkins/me",
                     "/api/stats/streak", "/api/leaderboard"):
        assert expected in paths, f"OpenAPI 缺少 {expected}"
