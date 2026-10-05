# -*- coding: utf-8 -*-
"""项目二：打卡 / 连续天数 / 排行榜用例。

简历承诺：
  - 打卡唯一约束 UniqueConstraint(user_id, checkin_date)，重复打卡 409
  - 连续天数统计（按日期降序遍历比较相邻日期差）
  - 排行榜（SQL 聚合 GROUP BY + COUNT + ORDER BY + 分页）
"""
from __future__ import annotations

from datetime import date, timedelta

TODAY = date.today()


def _ago(days: int) -> date:
    return TODAY - timedelta(days=days)


# ------------------------------------------------------------------ 打卡
def test_checkin_success_201(study):
    token = study.make_user("carol")
    r = study.post("/api/checkin", token=token)
    assert r.status_code == 201
    body = r.json()
    assert body["user_id"] == 1 and body["checkin_date"] == TODAY.isoformat()


def test_checkin_without_token_401(study):
    r = study.post("/api/checkin")
    assert r.status_code == 401


def test_duplicate_checkin_409(study):
    """简历承诺核心：同一天重复打卡 -> 409 "今日已打卡"
    （应用层预检 + UniqueConstraint(user_id, checkin_date) 数据库兜底）。"""
    token = study.make_user("carol")
    study.post("/api/checkin", token=token)
    r = study.post("/api/checkin", token=token)
    assert r.status_code == 409
    assert r.json()["detail"] == "今日已打卡"


def test_checkins_me_pagination_desc(study):
    token = study.make_user("carol")
    study.seed_checkins(1, [_ago(1), _ago(2), _ago(3)])
    study.post("/api/checkin", token=token)                # 今天
    r = study.get("/api/checkins/me", token=token, params={"page": 1, "page_size": 2})
    body = r.json()
    assert body["total"] == 4
    assert [i["checkin_date"] for i in body["items"]] == [TODAY.isoformat(), _ago(1).isoformat()]
    assert [i["id"] for i in body["items"]] == [4, 1]      # 日期降序：今天(id=4)、昨天(id=1)


# ------------------------------------------------------------------ 连续天数
def test_streak_never_checked_in(study):
    token = study.make_user("carol")
    r = study.get("/api/stats/streak", token=token)
    assert r.status_code == 200
    body = r.json()
    assert body["streak"] == 0 and body["latest_date"] is None


def test_streak_today_only_1(study):
    token = study.make_user("carol")
    study.post("/api/checkin", token=token)
    assert study.get("/api/stats/streak", token=token).json()["streak"] == 1


def test_streak_today_and_yesterday_2(study):
    token = study.make_user("carol")
    study.seed_checkins(1, [_ago(1)])
    study.post("/api/checkin", token=token)
    assert study.get("/api/stats/streak", token=token).json()["streak"] == 2


def test_streak_five_consecutive(study):
    """昨天往前连续 4 天 + 今天 = 连续 5 天。"""
    token = study.make_user("carol")
    study.seed_checkins(1, [_ago(1), _ago(2), _ago(3), _ago(4)])
    study.post("/api/checkin", token=token)
    body = study.get("/api/stats/streak", token=token).json()
    assert body["streak"] == 5 and body["latest_date"] == TODAY.isoformat()


def test_streak_breaks_on_gap(study):
    """中间断档即止：今天打了，但最近的历史打卡是 3 天前 -> 只有今天算 1 天。"""
    token = study.make_user("carol")
    study.seed_checkins(1, [_ago(3), _ago(4)])
    study.post("/api/checkin", token=token)
    assert study.get("/api/stats/streak", token=token).json()["streak"] == 1


def test_streak_stale_latest_zero(study):
    """最新一次打卡既不是今天也不是昨天 -> 连续性已中断，返回 0。"""
    token = study.make_user("carol")
    study.seed_checkins(1, [_ago(5), _ago(6)])
    body = study.get("/api/stats/streak", token=token).json()
    assert body["streak"] == 0 and body["latest_date"] == _ago(5).isoformat()


# ------------------------------------------------------------------ 排行榜
def test_leaderboard_order_and_rank(study):
    """聚合排序：dave 5 天 > carol 3 天 > bob 1 天；rank 连续。"""
    dave = study.make_user("dave")     # id=1
    carol = study.make_user("carol")   # id=2
    bob = study.make_user("bob")       # id=3
    study.seed_checkins(1, [_ago(1), _ago(2), _ago(3), _ago(4)])
    study.post("/api/checkin", token=dave)                 # dave 1+4=5 天
    study.seed_checkins(2, [_ago(1), _ago(2)])
    study.post("/api/checkin", token=carol)                # carol 1+2=3 天
    study.post("/api/checkin", token=bob)                  # bob 1 天

    body = study.get("/api/leaderboard", token=dave).json()
    assert body["total"] == 3
    assert [(i["rank"], i["username"], i["total_days"]) for i in body["items"]] == [
        (1, "dave", 5), (2, "carol", 3), (3, "bob", 1),
    ]


def test_leaderboard_pagination(study):
    """分页：page_size=2 的第 2 页只有最后一名，rank 全局连续（=3）；
    同天数并列时按注册先后（user_id 升序）稳定排序。"""
    dave = study.make_user("dave")
    carol = study.make_user("carol")
    bob = study.make_user("bob")
    study.seed_checkins(1, [_ago(1)])
    study.post("/api/checkin", token=dave)   # dave 2 天
    study.post("/api/checkin", token=carol)  # carol 1 天
    study.post("/api/checkin", token=bob)    # bob 1 天（与 carol 并列，id 靠前排前）

    body = study.get("/api/leaderboard", token=dave, params={"page": 2, "page_size": 2}).json()
    assert body["total"] == 3 and body["page"] == 2
    assert [(i["rank"], i["username"], i["total_days"]) for i in body["items"]] == [(3, "bob", 1)]


def test_leaderboard_without_token_401(study):
    r = study.get("/api/leaderboard")
    assert r.status_code == 401
