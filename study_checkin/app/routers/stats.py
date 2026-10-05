# -*- coding: utf-8 -*-
"""统计接口：连续打卡天数（streak）与打卡排行榜（leaderboard）。

简历承诺：连续天数统计与排行榜查询接口；
排行榜使用 SQL 聚合 GROUP BY + COUNT + ORDER BY，并做分页自测。
"""
from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import Checkin, User
from ..schemas import LeaderboardItem, LeaderboardPage, StreakResponse

router = APIRouter(tags=["统计"])


@router.get("/api/stats/streak", response_model=StreakResponse, summary="连续打卡天数")
def get_streak(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> StreakResponse:
    """计算当前用户的连续打卡天数。

    实现思路（简历承诺：按日期降序遍历、比较相邻日期差）：
      1) 取该用户全部打卡日期，按日期降序排列；
      2) 从最新一天开始向后逐个比较相邻两次打卡的日期差：差 1 天则连续 +1，
         一旦断档立即停止；
      3) 若最新一次打卡既不是今天也不是昨天，说明连续性已经中断，直接返回 0
         （宽容策略：昨天打了但今天还没打，连续天数仍然保留）。

    备选方案（数据量大时更优）：SQL 窗口函数 gaps-and-islands（分岛法）——
      用 `checkin_date - INTERVAL ROW_NUMBER() OVER (ORDER BY checkin_date) DAY`
      生成“岛键”，按岛键 GROUP BY 后取包含今天（或昨天）那一组的 COUNT(*)，
      一次查询即可在数据库侧算出最长连续段。SQLite 3.25+/MySQL 8.0 均支持窗口函数。
    """
    dates: list[date] = [
        row[0]
        for row in db.query(Checkin.checkin_date)
        .filter(Checkin.user_id == user.id)
        .order_by(Checkin.checkin_date.desc())
        .all()
    ]
    latest = dates[0] if dates else None

    streak = 0
    if latest is not None:
        today = date.today()
        if latest == today or latest == today - timedelta(days=1):
            # 按日期降序遍历，比较相邻日期差：相差 1 天视为连续，断档即止
            streak = 1
            for prev, cur in zip(dates, dates[1:]):
                if (prev - cur).days == 1:
                    streak += 1
                else:
                    break
    return StreakResponse(user_id=user.id, username=user.username, streak=streak, latest_date=latest)


@router.get("/api/leaderboard", response_model=LeaderboardPage, summary="打卡排行榜（按总天数降序，分页）")
def leaderboard(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LeaderboardPage:
    """排行榜（简历承诺：SQL 聚合查询 GROUP BY + COUNT + ORDER BY）。

    总打卡天数 = 每个用户的打卡记录条数（唯一约束保证一天最多一条，
    所以 COUNT(*) 即打卡天数，无需 COUNT(DISTINCT checkin_date)）。
    排行榜本身也要求登录后查看（演示 JWT 鉴权复用）。
    """
    totals = (
        db.query(Checkin.user_id.label("user_id"), func.count().label("total_days"))
        .group_by(Checkin.user_id)          # GROUP BY：按用户聚合
        .subquery()
    )

    q = (
        db.query(User.id, User.username, totals.c.total_days)
        .join(totals, totals.c.user_id == User.id)
        .order_by(totals.c.total_days.desc(), User.id.asc())  # ORDER BY：天数降序，同数按注册先后
    )
    total = q.count()
    rows = q.offset((page - 1) * page_size).limit(page_size).all()

    items = [
        LeaderboardItem(rank=(page - 1) * page_size + idx + 1, user_id=uid, username=username, total_days=int(days))
        for idx, (uid, username, days) in enumerate(rows)
    ]
    return LeaderboardPage(total=total, page=page, page_size=page_size, items=items)
