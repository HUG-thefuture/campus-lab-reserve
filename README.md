# 实验室设备预约系统后端 + 自习打卡统计接口

![CI](https://github.com/HUG-thefuture/campus-lab-reserve/actions/workflows/ci.yml/badge.svg)

> Python 后端方向简历项目：**FastAPI + SQLAlchemy 2.0 + Pydantic v2 + JWT**。默认 SQLite 零依赖可跑，`DATABASE_URL` 环境变量一键切 MySQL。全部接口经 pytest（56 例，打真实 uvicorn 子进程）与 curl 冒烟验证。

## 项目构成

| 子项目 | 端口 | 内容 |
|---|---|---|
| `lab_reserve/` | 8010 | 实验室设备预约系统后端：用户/设备/预约/审核/归还，时段冲突校验 + 状态机 + 角色控制 |
| `study_checkin/` | 8011 | 自习打卡统计接口：每日打卡（唯一约束）、连续天数统计、排行榜（聚合+分页） |

## 快速启动（本机已验证）

```bash
# 1. 依赖（离线模式：装到 vendor/，运行时经 PYTHONPATH 提供，免虚拟环境）
pip install -r requirements.txt --target vendor

# 2. 启动两个服务（Git Bash 示例；Windows PowerShell 语法见 run_tests.ps1）
export PYTHONPATH="$(pwd)/vendor"
python -m uvicorn lab_reserve.app.main:app   --port 8010 &
python -m uvicorn study_checkin.app.main:app --port 8011 &

# 3. 入口
#    lab_reserve Swagger:  http://127.0.0.1:8010/docs
#    study_checkin Swagger: http://127.0.0.1:8011/docs
```

测试账号由接口现场注册（`POST /api/register`，角色 student/teacher/admin），无预置账号。

> **2026-10 更新：提供演示种子脚本**（"能演示"≠"好演示"，评审现场不再手工造数据）：
> ```bash
> python lab_reserve/scripts/seed_demo.py          # 幂等；--reset 重建
> ```
> 生成 4 个账号（admin / teacher01 / student01 / student02，密码均 `123456`，**仅演示**，覆盖三种角色）、
> 6 台设备、5 条各状态预约（APPROVED / PENDING×2 / RETURNED / REJECTED），登录走真实 PBKDF2 校验。
> 演示即开：student01 登录 → 建预约 → teacher01 审核；PENDING/APPROVED 占用时段可演示冲突拦截。

## 一分钟冒烟（对应 docs/postman_smoke.md 全集）

```bash
# 注册 + 登录（201 / 200，返回 access_token）
curl -X POST localhost:8010/api/register -H "Content-Type: application/json" \
     -d '{"username":"stu1","password":"pass123","role":"student"}'
curl -X POST localhost:8010/api/login -H "Content-Type: application/json" \
     -d '{"username":"stu1","password":"pass123"}'

# 教师建设备（201）；学生建设备（403 越权）
curl -X POST localhost:8010/api/devices -H "Authorization: Bearer $TEA" \
     -H "Content-Type: application/json" -d '{"name":"示波器","capacity":2}'

# 学生预约（201）→ 部分重叠再约（409 该时段已被预约）
curl -X POST localhost:8010/api/reservations -H "Authorization: Bearer $STU" \
     -H "Content-Type: application/json" \
     -d '{"device_id":1,"start_time":"2030-01-10T09:00:00","end_time":"2030-01-10T10:00:00"}'

# 学生调审核接口（403）→ 教师审核通过（200）→ 学生归还（200）
# 打卡：当日一次（唯一约束），重复打卡 409；连续天数/排行榜见 /docs
```

## 全量回归

```bash
bash run_tests.sh        # 或 PowerShell: .\run_tests.ps1
# 期望：56 passed —— 认证/设备/预约冲突与状态机/越权/打卡/连续天数/排行榜/OpenAPI
```

## 切换 MySQL（可选）

```bash
export DATABASE_URL="mysql+pymysql://root:root@127.0.0.1:3306/lab_reserve?charset=utf8mb4"
# 建库脚本：lab_reserve/schema.sql（含 CREATE DATABASE + USE；中文导入加 --default-character-set=utf8mb4）
```

`docker-compose.yml` 提供 MySQL 8.0 的一键起库（需本机安装 Docker Desktop；`00-init-databases.sql` 自动建 lab_reserve / study_checkin 两库）。

## 目录结构

```
project/
├── lab_reserve/           # 项目一（FastAPI 应用）
│   ├── app/{main,config,database,models,schemas,security,deps}.py
│   ├── app/routers/{users,devices,reservations}.py
│   └── schema.sql
├── study_checkin/         # 项目二（FastAPI 应用）
│   ├── app/...（routers/{users,checkins,stats}.py）
│   └── schema.sql
├── tests/                 # pytest + requests，56 例，打真实 HTTP
├── docs/postman_smoke.md  # Postman/curl 冒烟请求集
├── run_tests.ps1 / .sh    # 一键回归
├── vendor/                # 离线依赖（pip install --target）
└── docker-compose.yml
```

## 真实验证记录（本机）

- `bash run_tests.sh` → **56 passed in ~96s**
- curl 冒烟 12 项全过：注册 201 / 登录 200 / 教师建设备 201 / 学生建设备 403 / 预约 201 / 部分重叠 409 / 学生审核 403 / 教师审核 200 / 归还 200 / 打卡 201 / 重复打卡 409 / 排行榜 200（需登录态）
- 详细学习路线见《从零到可运行教程.md》

---

## 产品视角（面试可讲）

- **目标用户**：实验室学生（预约/归还）与教师/管理员（审核/管理）。
- **解决的问题**：设备预约靠群里喊话，冲突靠人记，归还无人追踪。
- **核心场景**：登录→选设备→约时段（冲突拦截）→教师审核→归还；角色权限贯穿。
- **成功指标（实测）**：56 例 HTTP 回归全绿；`lab_reserve/scripts/seed_demo.py` 一键出可登录演示数据（三角色+各状态预约）。
- **未来计划**：周历视图；预约开始前的提醒通知；打卡服务（study_checkin）看板联动。
