# Postman / curl 冒烟请求集（Postman Smoke）

覆盖简历承诺的两个重点场景：**预约时段冲突（409）** 与 **越权访问（403）**。
以下请求可直接复制到终端执行，也可导入 Postman（New Request -> 逐条粘贴 URL/Body；
或使用 Postman 的 Import -> Raw import 粘贴 curl 命令）。

前提：两个服务已启动（见根 README「快速启动」）。

- lab_reserve: `http://127.0.0.1:8010`
- study_checkin: `http://127.0.0.1:8011`

---

## 一、lab_reserve（端口 8010）

### 0. 健康检查

```bash
curl -s http://127.0.0.1:8010/health
```

### 1. 注册三个角色用户（student / 另一 student / teacher）

```bash
curl -s -X POST http://127.0.0.1:8010/api/register \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","password":"pass123","role":"student"}'

curl -s -X POST http://127.0.0.1:8010/api/register \
  -H "Content-Type: application/json" \
  -d '{"username":"bob","password":"pass123","role":"student"}'

curl -s -X POST http://127.0.0.1:8010/api/register \
  -H "Content-Type: application/json" \
  -d '{"username":"mr_tan","password":"pass123","role":"teacher"}'
```

### 2. 登录获取 JWT（有效 12h）

```bash
ALICE=$(curl -s -X POST http://127.0.0.1:8010/api/login \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","password":"pass123"}' | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

BOB=$(curl -s -X POST http://127.0.0.1:8010/api/login \
  -H "Content-Type: application/json" \
  -d '{"username":"bob","password":"pass123"}' | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

TEACHER=$(curl -s -X POST http://127.0.0.1:8010/api/login \
  -H "Content-Type: application/json" \
  -d '{"username":"mr_tan","password":"pass123"}' | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
```

### 3. 教师建设备（越权对照见第 8 步）

```bash
curl -s -X POST http://127.0.0.1:8010/api/devices \
  -H "Authorization: Bearer $TEACHER" -H "Content-Type: application/json" \
  -d '{"name":"示波器","capacity":2,"description":"泰克 4 通道示波器"}'
# 记下返回的设备 id，下面假设为 1
```

### 4. 预约成功（明天 9:00-10:00）

```bash
curl -s -X POST http://127.0.0.1:8010/api/reservations \
  -H "Authorization: Bearer $ALICE" -H "Content-Type: application/json" \
  -d '{"device_id":1,"start_time":"2026-09-08T09:00:00","end_time":"2026-09-08T10:00:00"}'
# 201，记下预约 id（假设为 1）
```

### 5. 【核心冒烟：时段冲突 409】另一学生预约完全重叠时段

```bash
curl -s -w "\nHTTP %{http_code}\n" -X POST http://127.0.0.1:8010/api/reservations \
  -H "Authorization: Bearer $BOB" -H "Content-Type: application/json" \
  -d '{"device_id":1,"start_time":"2026-09-08T09:00:00","end_time":"2026-09-08T10:00:00"}'
# 期望：HTTP 409  {"detail": "该时段已被预约"}
# 部分重叠（9:30-10:30）同样 409；相邻时段（10:00-11:00）则 201 成功
```

### 6. 审核通过（teacher；PENDING -> APPROVED）

```bash
curl -s -X POST http://127.0.0.1:8010/api/reservations/1/status \
  -H "Authorization: Bearer $TEACHER" -H "Content-Type: application/json" \
  -d '{"status":"APPROVED"}'
```

### 7. 归还（本人 student；APPROVED -> RETURNED）

```bash
curl -s -X POST http://127.0.0.1:8010/api/reservations/1/return \
  -H "Authorization: Bearer $ALICE"
# 再次调用会返回 400 {"detail": "当前状态不允许归还"}
```

### 8. 【核心冒烟：越权 403】student 调用审核接口

```bash
curl -s -w "\nHTTP %{http_code}\n" -X POST http://127.0.0.1:8010/api/reservations/1/status \
  -H "Authorization: Bearer $ALICE" -H "Content-Type: application/json" \
  -d '{"status":"APPROVED"}'
# 期望：HTTP 403  {"detail": "无权执行该操作"}
# student 建设备同样 403；无 token 访问 /api/reservations/mine 返回 401
```

---

## 二、study_checkin（端口 8011）

### 9. 注册 + 登录 + 当日打卡

```bash
curl -s -X POST http://127.0.0.1:8011/api/register \
  -H "Content-Type: application/json" \
  -d '{"username":"carol","password":"pass123","role":"student"}'

TOKEN=$(curl -s -X POST http://127.0.0.1:8011/api/login \
  -H "Content-Type: application/json" \
  -d '{"username":"carol","password":"pass123"}' | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

curl -s -X POST http://127.0.0.1:8011/api/checkin -H "Authorization: Bearer $TOKEN"
# 201，返回打卡记录
```

### 10. 【核心冒烟：重复打卡 409】

```bash
curl -s -w "\nHTTP %{http_code}\n" -X POST http://127.0.0.1:8011/api/checkin -H "Authorization: Bearer $TOKEN"
# 期望：HTTP 409  {"detail": "今日已打卡"}
```

### 11. 统计与查询

```bash
curl -s http://127.0.0.1:8011/api/stats/streak -H "Authorization: Bearer $TOKEN"
curl -s "http://127.0.0.1:8011/api/leaderboard?page=1&page_size=10" -H "Authorization: Bearer $TOKEN"
curl -s "http://127.0.0.1:8011/api/checkins/me?page=1&page_size=10" -H "Authorization: Bearer $TOKEN"
```

---

## 附：OpenAPI 接口文档

- lab_reserve Swagger UI: http://127.0.0.1:8010/docs （OpenAPI JSON: `/openapi.json`）
- study_checkin Swagger UI: http://127.0.0.1:8011/docs
- Postman 亦可直接 Import -> 链接粘贴 `http://127.0.0.1:8010/openapi.json` 自动生成集合。
