# -*- coding: utf-8 -*-
"""项目一：设备与预约模块用例（简历承诺核心：时段冲突校验 + 状态机 + 角色控制）。

冲突判定口径：把预约视为左闭右开区间 [start, end)，
  重叠充要条件 = existing.start < new.end AND existing.end > new.start，
  覆盖完全重叠 / 部分重叠（头、尾）/ 大区间包住；相邻（前一单 end == 后一单 start）不误伤。
"""
from __future__ import annotations

DAY = "2030-01-10"  # 固定远期日期，避免与“今天”耦合


def _t(hour: int, minute: int = 0) -> str:
    return f"{DAY}T{hour:02d}:{minute:02d}:00"


# ------------------------------------------------------------------ 公共步骤
def _make_device(lab, name: str = "示波器", capacity: int = 2, teacher_token: str | None = None) -> int:
    """teacher 建一台设备并返回 id；teacher_token 缺省时自动注册一个教师。"""
    if teacher_token is None:
        teacher_token = lab.make_user("tea1", role="teacher")
    r = lab.post("/api/devices", token=teacher_token, json={"name": name, "capacity": capacity})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _book(lab, token: str, device_id: int, start: str, end: str, expect: int = 201):
    r = lab.post("/api/reservations", token=token,
                 json={"device_id": device_id, "start_time": start, "end_time": end})
    assert r.status_code == expect, f"期望 {expect} 实际 {r.status_code}: {r.text}"
    return r


def _approved_reservation(lab) -> tuple[int, str, str]:
    """前置：teacher 建设备 + alice 预约 09:00-10:00 + teacher 审核通过。
    返回 (reservation_id, alice_token, teacher_token)。"""
    teacher = lab.make_user("tea1", role="teacher")
    device = _make_device(lab, teacher_token=teacher)
    alice = lab.make_user("alice")
    rid = _book(lab, alice, device, _t(9), _t(10)).json()["id"]
    _review(lab, teacher, rid, "APPROVED")
    return rid, alice, teacher


def _review(lab, token: str, rid: int, status: str, expect: int = 200):
    r = lab.post(f"/api/reservations/{rid}/status", token=token, json={"status": status})
    assert r.status_code == expect, f"期望 {expect} 实际 {r.status_code}: {r.text}"
    return r


# ------------------------------------------------------------------ 设备模块
def test_create_device_by_teacher_201(lab):
    teacher = lab.make_user("tea1", role="teacher")
    r = lab.post("/api/devices", token=teacher, json={"name": "示波器", "capacity": 2, "description": "泰克"})
    assert r.status_code == 201
    body = r.json()
    assert body["id"] == 1 and body["name"] == "示波器" and body["status"] == "AVAILABLE"


def test_create_device_by_student_403(lab):
    alice = lab.make_user("alice")
    r = lab.post("/api/devices", token=alice, json={"name": "hack", "capacity": 1})
    assert r.status_code == 403
    assert r.json()["detail"] == "无权执行该操作"


def test_create_device_without_token_401(lab):
    r = lab.post("/api/devices", json={"name": "x", "capacity": 1})
    assert r.status_code == 401


def test_create_device_capacity_zero_422(lab):
    teacher = lab.make_user("tea1", role="teacher")
    r = lab.post("/api/devices", token=teacher, json={"name": "bad", "capacity": 0})
    assert r.status_code == 422  # 简历承诺：容量 > 0（Pydantic gt=0）


def test_device_list_search_and_pagination(lab):
    teacher = lab.make_user("tea1", role="teacher")
    for name in ("示波器A", "信号发生器A", "信号发生器B"):
        lab.post("/api/devices", token=teacher, json={"name": name, "capacity": 1})
    r = lab.get("/api/devices", params={"name": "发生器"})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2                                   # 名称模糊搜索命中 2 台
    r2 = lab.get("/api/devices", params={"page": 2, "page_size": 1})
    body2 = r2.json()
    assert body2["total"] == 3 and len(body2["items"]) == 1     # 分页
    assert body2["items"][0]["id"] == 2                         # 第 2 页是第 2 条


def test_device_detail_404(lab):
    r = lab.get("/api/devices/999")
    assert r.status_code == 404
    assert r.json()["detail"] == "设备不存在"


# ------------------------------------------------------------------ 创建预约
def test_create_reservation_success_201(lab):
    device = _make_device(lab)
    alice = lab.make_user("alice")
    body = _book(lab, alice, device, _t(9), _t(10)).json()
    assert body["status"] == "PENDING"          # 初始状态：待审核
    assert body["device"]["id"] == device       # 响应带出设备信息
    assert body["start_time"].startswith(DAY)


def test_create_reservation_without_token_401(lab):
    device = _make_device(lab)
    r = lab.post("/api/reservations", json={"device_id": device, "start_time": _t(9), "end_time": _t(10)})
    assert r.status_code == 401


def test_create_reservation_unknown_device_404(lab):
    alice = lab.make_user("alice")
    r = lab.post("/api/reservations", token=alice,
                 json={"device_id": 999, "start_time": _t(9), "end_time": _t(10)})
    assert r.status_code == 404


def test_create_reservation_end_not_after_start_422(lab):
    device = _make_device(lab)
    alice = lab.make_user("alice")
    r = lab.post("/api/reservations", token=alice,
                 json={"device_id": device, "start_time": _t(9), "end_time": _t(9)})
    assert r.status_code == 422  # model_validator：end_time 必须晚于 start_time


# ------------------------------------------------------------------ 冲突判定矩阵
def test_conflict_exact_overlap_409(lab):
    device = _make_device(lab)
    _book(lab, lab.make_user("alice"), device, _t(9), _t(10))
    _book(lab, lab.make_user("bob"), device, _t(9), _t(10), expect=409)


def test_conflict_partial_overlap_tail_409(lab):
    """新预约头部撞进已有预约（09:30-10:30 vs 09:00-10:00）。"""
    device = _make_device(lab)
    _book(lab, lab.make_user("alice"), device, _t(9), _t(10))
    _book(lab, lab.make_user("bob"), device, _t(9, 30), _t(10, 30), expect=409)


def test_conflict_partial_overlap_head_409(lab):
    """新预约尾部撞进已有预约（08:30-09:30 vs 09:00-10:00）。"""
    device = _make_device(lab)
    _book(lab, lab.make_user("alice"), device, _t(9), _t(10))
    _book(lab, lab.make_user("bob"), device, _t(8, 30), _t(9, 30), expect=409)


def test_conflict_enclosing_409(lab):
    """新预约把已有预约整个包住（08:00-11:00 vs 09:00-10:00）。"""
    device = _make_device(lab)
    _book(lab, lab.make_user("alice"), device, _t(9), _t(10))
    _book(lab, lab.make_user("bob"), device, _t(8), _t(11), expect=409)


def test_adjacent_slots_ok_201(lab):
    """相邻不误伤：前一单 09:00-10:00，后一单 10:00-11:00、再一单 08:00-09:00 均成功。"""
    device = _make_device(lab)
    alice = lab.make_user("alice")
    _book(lab, alice, device, _t(9), _t(10))
    _book(lab, lab.make_user("bob"), device, _t(10), _t(11), expect=201)   # 后接
    _book(lab, alice, device, _t(8), _t(9), expect=201)                    # 前接


def test_conflict_not_count_rejected(lab):
    """REJECTED 不占用时段：被驳回后同一时段可再次预约。"""
    teacher = lab.make_user("tea1", role="teacher")
    device = _make_device(lab, teacher_token=teacher)
    alice = lab.make_user("alice")
    rid = _book(lab, alice, device, _t(9), _t(10)).json()["id"]
    _review(lab, teacher, rid, "REJECTED")
    _book(lab, lab.make_user("bob"), device, _t(9), _t(10), expect=201)


def test_conflict_not_count_canceled(lab):
    """CANCELED 不占用时段：取消后同一时段可再次预约。"""
    device = _make_device(lab)
    alice = lab.make_user("alice")
    rid = _book(lab, alice, device, _t(9), _t(10)).json()["id"]
    r = lab.post(f"/api/reservations/{rid}/cancel", token=alice)
    assert r.status_code == 200 and r.json()["status"] == "CANCELED"
    _book(lab, lab.make_user("bob"), device, _t(9), _t(10), expect=201)


def test_conflict_not_count_returned(lab):
    """RETURNED 不占用时段：归还后同一时段可再次预约。"""
    teacher = lab.make_user("tea1", role="teacher")
    device = _make_device(lab, teacher_token=teacher)
    alice = lab.make_user("alice")
    rid = _book(lab, alice, device, _t(9), _t(10)).json()["id"]
    _review(lab, teacher, rid, "APPROVED")
    r = lab.post(f"/api/reservations/{rid}/return", token=alice)
    assert r.status_code == 200 and r.json()["status"] == "RETURNED"
    _book(lab, lab.make_user("bob"), device, _t(9), _t(10), expect=201)


# ------------------------------------------------------------------ 审核流
def test_review_approve_by_teacher(lab):
    teacher = lab.make_user("tea1", role="teacher")
    device = _make_device(lab, teacher_token=teacher)
    alice = lab.make_user("alice")
    rid = _book(lab, alice, device, _t(9), _t(10)).json()["id"]
    body = _review(lab, teacher, rid, "APPROVED").json()
    assert body["status"] == "APPROVED"   # PENDING -> APPROVED


def test_review_reject_by_teacher(lab):
    teacher = lab.make_user("tea1", role="teacher")
    device = _make_device(lab, teacher_token=teacher)
    alice = lab.make_user("alice")
    rid = _book(lab, alice, device, _t(9), _t(10)).json()["id"]
    body = _review(lab, teacher, rid, "REJECTED").json()
    assert body["status"] == "REJECTED"   # PENDING -> REJECTED


def test_review_non_pending_400(lab):
    """非法流转：APPROVED / REJECTED 之后都不允许再审核。"""
    teacher = lab.make_user("tea1", role="teacher")
    device = _make_device(lab, teacher_token=teacher)
    alice = lab.make_user("alice")
    rid = _book(lab, alice, device, _t(9), _t(10)).json()["id"]
    _review(lab, teacher, rid, "APPROVED")
    r = lab.post(f"/api/reservations/{rid}/status", token=teacher, json={"status": "REJECTED"})
    assert r.status_code == 400
    assert r.json()["detail"] == "当前状态不允许审核"


def test_review_by_student_403(lab):
    """简历承诺：student 调用审核接口 -> 403。"""
    device = _make_device(lab)
    alice = lab.make_user("alice")
    rid = _book(lab, alice, device, _t(9), _t(10)).json()["id"]
    r = lab.post(f"/api/reservations/{rid}/status", token=alice, json={"status": "APPROVED"})
    assert r.status_code == 403
    assert r.json()["detail"] == "无权执行该操作"


def test_review_unknown_reservation_404(lab):
    teacher = lab.make_user("tea1", role="teacher")
    r = lab.post("/api/reservations/999/status", token=teacher, json={"status": "APPROVED"})
    assert r.status_code == 404


# ------------------------------------------------------------------ 归还
def test_return_by_owner_then_again_400(lab):
    """APPROVED -> RETURNED（本人操作）；重复归还 -> 400。"""
    rid, alice, _ = _approved_reservation(lab)
    r = lab.post(f"/api/reservations/{rid}/return", token=alice)
    assert r.status_code == 200 and r.json()["status"] == "RETURNED"
    r2 = lab.post(f"/api/reservations/{rid}/return", token=alice)
    assert r2.status_code == 400
    assert r2.json()["detail"] == "当前状态不允许归还"


def test_return_pending_400(lab):
    device = _make_device(lab)
    alice = lab.make_user("alice")
    rid = _book(lab, alice, device, _t(9), _t(10)).json()["id"]
    r = lab.post(f"/api/reservations/{rid}/return", token=alice)
    assert r.status_code == 400  # PENDING 不能直接归还


def test_return_by_other_student_403(lab):
    """越权：别人的预约不能由无关学生归还。"""
    rid, alice, _ = _approved_reservation(lab)
    bob = lab.make_user("bob")
    r = lab.post(f"/api/reservations/{rid}/return", token=bob)
    assert r.status_code == 403


def test_return_by_teacher_ok(lab):
    """teacher/admin 是管理角色，可代为归还他人预约。"""
    rid, _, teacher = _approved_reservation(lab)
    r = lab.post(f"/api/reservations/{rid}/return", token=teacher)
    assert r.status_code == 200 and r.json()["status"] == "RETURNED"


# ------------------------------------------------------------------ 取消
def test_cancel_own_pending_200(lab):
    device = _make_device(lab)
    alice = lab.make_user("alice")
    rid = _book(lab, alice, device, _t(9), _t(10)).json()["id"]
    r = lab.post(f"/api/reservations/{rid}/cancel", token=alice)
    assert r.status_code == 200 and r.json()["status"] == "CANCELED"   # PENDING -> CANCELED


def test_cancel_by_other_403(lab):
    """越权：他人不能取消别人的预约（403 先于状态校验）。"""
    device = _make_device(lab)
    alice = lab.make_user("alice")
    rid = _book(lab, alice, device, _t(9), _t(10)).json()["id"]
    bob = lab.make_user("bob")
    r = lab.post(f"/api/reservations/{rid}/cancel", token=bob)
    assert r.status_code == 403


def test_cancel_after_approved_400(lab):
    """非法流转：APPROVED 不允许取消（须先归还）。"""
    rid, alice, _ = _approved_reservation(lab)
    r = lab.post(f"/api/reservations/{rid}/cancel", token=alice)
    assert r.status_code == 400
    assert r.json()["detail"] == "当前状态不允许取消"


# ------------------------------------------------------------------ 我的预约
def test_mine_pagination_desc_order(lab):
    device = _make_device(lab)
    alice = lab.make_user("alice")
    for h in (9, 10, 11):
        _book(lab, alice, device, _t(h), _t(h + 1))
    r = lab.get("/api/reservations/mine", token=alice, params={"page": 1, "page_size": 2})
    body = r.json()
    assert body["total"] == 3 and body["page"] == 1 and body["page_size"] == 2
    assert [i["id"] for i in body["items"]] == [3, 2]   # 按时间倒序，最新在前
    r2 = lab.get("/api/reservations/mine", token=alice, params={"page": 2, "page_size": 2})
    assert [i["id"] for i in r2.json()["items"]] == [1]
