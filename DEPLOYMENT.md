# Deployment Information

> **Student Name:** Đỗ Hoàng Minh
> **Student ID:** 2A202603507
> **Date:** 25/11/2026
> **Platform:** Railway
> **Repo:** https://github.com/Mazzonthego/K5-L3A-DAY14-DoHoangMinh-2A202603507-Deployment-Benchmark-Observability

---

## Public URL

```
https://agent-production-6f62b355.up.railway.app
```

> Domain trên Railway được tạo tự động bằng `railway domain` (trạng thái `ACTIVE`).
> Đây là URL public thật của agent Part 6 — đã trả `200` cho `/health`, `/ready` và `/ask` (có API key).

---

## Platform

| Mục | Nội dung |
|---|---|
| Nền tảng | Railway (deploy từ Dockerfile, `builder = "DOCKERFILE"`) |
| File cấu hình | `06-lab-complete/railway.toml` (healthcheck `/health`, app nghe theo `$PORT`) |
| Source deploy | Thư mục `06-lab-complete/` — agent Part 6 (KHÔNG deploy app mẫu `03-cloud-deployment/`) |
| Workspace | `DoHoangMinhh's Projects` (id `a899c199-b413-42f7-b850-ab4e407aa43a`) |
| Project | `k5-day14-agent` (id `f2b55e96-3367-4d40-abac-0ff3bbea8e3a`) |
| Environment | `production` (id `dbe86aab-9d22-4e40-8f23-91f4c7826746`) |
| Service (app) | `agent` (id `aba15d8d-5e9f-4c32-986d-da7924b265f7`) |
| Service (Redis) | `Redis` — plugin `redis:8.2` (id `a6336084-5326-4814-bf52-31a47c2ca337`), volume `redis-volume` mount `/data` (32,7 MB / 500 MB) |
| Deployment | `4dc13a95-1f2c-446d-b6f5-c71a53213728` — trạng thái **SUCCESS**, 25/11/2026 17:50 UTC |
| Replicas | 1 running / 1 configured (cả `agent` và `Redis`) |
| Region | Service được cấu hình region `iad`; request public đi qua edge `sin1` (Singapore) — header `x-railway-edge: sin1` |
| Server | `server: railway-hikari` (reverse proxy của Railway) |
| `PORT` | **Do Railway tự inject** (không set thủ công) — log khởi động: `Uvicorn running on http://0.0.0.0:8080` |

---

## Điều kiện trước khi deploy (checklist)

- [x] Trong `06-lab-complete/`: `python check_production_ready.py` → **`PASS 12/12`** (chạy bản đầy đủ, có Docker).
- [x] `Dockerfile` có `CMD` nghe theo biến `PORT` (`${PORT:-8000}`) — Railway inject `PORT` tự động (thực tế = 8080).
- [x] `06-lab-complete/railway.toml` có `healthcheckPath = "/health"` và `builder = "DOCKERFILE"`.
- [x] `.env` **không** commit; mọi secret đặt qua `railway variables set` hoặc Dashboard.
- [x] Code đã push lên GitHub (Railway build từ thư mục deploy upload lên).

---

## Các lệnh deploy (đã chạy thật trong WSL2 Ubuntu)

```bash
# 0) Đảm bảo CLI có trong PATH (đã cài ở máy lab)
export PATH="$HOME/.npm-global/bin:$PATH"

# 1) Đăng nhập (mở trình duyệt → bấm Approve; không cần nhập tay trong terminal)
railway login
#    hoặc: railway login --browserless  → in ra link + mã ghép nối (mã hết hạn sau vài phút)

# 2) Tạo project + Redis plugin
cd 06-lab-complete
railway init --name k5-day14-agent
railway add --database redis          # tự sinh REDIS_URL cho service Redis

# 3) Tạo service app (không set source; deploy bằng CLI)
railway add --service agent

# 4) Đặt biến môi trường (KHÔNG ghi secret vào code)
railway variable set AGENT_API_KEY=<key-tự-tạo>        --service agent --skip-deploys
railway variable set REDIS_URL=redis://default:...@redis.railway.internal:6379 --service agent --skip-deploys
railway variable set ENVIRONMENT=production             --service agent --skip-deploys
railway variable set RATE_LIMIT_PER_MINUTE=10           --service agent --skip-deploys
railway variable set DAILY_BUDGET_USD=10                --service agent --skip-deploys
railway variable set MONTHLY_BUDGET_USD=100             --service agent --skip-deploys
railway variable set LOG_LEVEL=INFO                     --service agent --skip-deploys

# 5) Deploy + lấy URL public
railway up --service agent --detach -y
railway domain --service agent
#   -> https://agent-production-6f62b355.up.railway.app

# 6) Kiểm tra lại
railway service status --service agent
railway logs --service agent --deployment <deployment-id>
```

> **Lưu ý cú pháp `railway variable set`:** phải truyền **một** đối số dạng `"KEY=VALUE"`.
> Nếu truyền hai đối số (`"KEY=VALUE" ""`) thì CLI sẽ **nối thêm dấu `=` vào cuối value**
> (giá trị bị sai → `/ask` trả 401 dù có key đúng).

> **Redis trên Railway:** tạo bằng `railway add --database redis`, copy `REDIS_URL`
> (dạng `redis://default:pass@redis.railway.internal:6379`) rồi set cho service `agent`.
> `/ready` phải trả **200** trước khi chụp ảnh — nếu 503 thì kiểm tra lại `REDIS_URL`.

---

## Test Commands (đã chạy thật)

Chạy 4 lệnh sau với `BASE` = URL public và `AGENT_API_KEY` = key đã đặt trên Railway.
Mỗi lệnh chỉ in mã HTTP → chụp ảnh được mà không lộ key.

```bash
BASE=https://agent-production-6f62b355.up.railway.app
AGENT_API_KEY=<key-đã-đặt>

# 1. Health check → 200
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/health"

# 2. Readiness (Redis OK) → 200
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ready"

# 3. /ask không có key → 401
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H 'Content-Type: application/json' -d '{"question":"Hello"}'

# 4. /ask có key → 200
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H 'Content-Type: application/json' -H "X-API-Key: $AGENT_API_KEY" \
  -d '{"question":"Hello"}'
```

**Kết quả thật trên Railway:**

| # | Lệnh | Kết quả | Response |
|---|---|---|---|
| 1 | `GET /health` | **200** | `{"status":"ok"}` |
| 2 | `GET /ready` | **200** | `{"status":"ready","redis":"ok"}` ← Redis đã kết nối |
| 3 | `POST /ask` (thiếu key) | **401** | `{"detail":"Invalid or missing API key"}` |
| 4 | `POST /ask` (có key) | **200** | `{"question":"Hello","answer":"Tôi là AI agent được deploy lên cloud...","usage":{"input_tokens":2,"output_tokens":17,"cost_usd":1.05e-05}}` |

Header xác nhận đang chạy trên Railway: `server: railway-hikari`, `x-railway-edge: sin1`,
`x-railway-request-id: gKo79Q3OTwicYSVOqmzx2A`.

> `/health` trả `{"status":"ok"}` — đúng theo bản production trong `06-lab-complete/app/main.py`
> (bản develop trả thêm `uptime_seconds`, `instance_id`, `storage`, `redis_connected`).

---

## Environment Variables Set

| Biến | Giá trị | Nơi đặt |
|---|---|---|
| `AGENT_API_KEY` | *(giá trị thật, không ghi trong repo)* | Railway variables (`--service agent`) |
| `REDIS_URL` | `redis://default:…@redis.railway.internal:6379` *(che giá trị)* | Railway variables (lấy từ service Redis) |
| `ENVIRONMENT` | `production` | Railway variables |
| `RATE_LIMIT_PER_MINUTE` | `10` | Railway variables |
| `DAILY_BUDGET_USD` | `10` | Railway variables |
| `MONTHLY_BUDGET_USD` | `100` | Railway variables |
| `LOG_LEVEL` | `INFO` | Railway variables |
| `PORT` | *(do Railway tự inject — 8080)* | Railway platform |
| `RAILWAY_*` | project / environment / service id, public domain… | Railway platform (tự động) |

---

## Chi phí (billing period 25/11/2026 → 27/11/2026)

| Khoản | USD |
|---|---|
| CPU | 0,0094 |
| Memory | 0,0872 |
| Egress | 0,0001 |
| Volume (Redis) | 0,0003 |
| **Tổng** | **0,0970** |

---

## Screenshots

- [Deployment dashboard](screenshots/dashboard.png) — project `k5-day14-agent`, environment `production`,
  service `agent` + `Redis` (đều `SUCCESS`), biến môi trường (giá trị secret đã che), runtime logs,
  domain `ACTIVE`, chi phí hiện tại. *Dữ liệu lấy từ `railway service list / variable list / domain list / usage / logs --json`.*
- [Service running](screenshots/running.png) — log runtime thật của service `agent`: `Booting VM for replica 1`
  → `Uvicorn running on http://0.0.0.0:8080` → `Application startup complete` → các request `/health` `/ready` `/ask` trả 200/401.
- [Test results](screenshots/test.png) — 4 lệnh tự kiểm in ra `200 · 200 · 401 · 200` (đúng kỳ vọng).

---

## Lỗi gặp phải khi deploy (đã khắc phục)

### 1. Build fail: `header key "exclude-patterns" contains value with non-printable ASCII characters`

Railway CLI gửi danh sách pattern exclude lên build daemon qua **HTTP header**, mà header chỉ nhận
ASCII in được. Repo clone trên Windows (`core.autocrlf=true`) làm `.gitignore` / `.dockerignore` bị
**CRLF** (`\r` = control char) và các ký tự vẽ khung Unicode (`─`, U+2500) trong comment → build fail.

**Cách sửa (đã áp dụng):**

1. Chuyển `.gitignore` / `.dockerignore` về **LF** và **ASCII thuần** (thay ký tự `─` bằng `-`).
2. Thêm `.gitattributes` ở gốc repo để giữ nguyên LF trên mọi OS:

   ```gitattributes
   .gitattributes        text eol=lf
   .gitignore            text eol=lf
   .dockerignore        text eol=lf
   ```

### 2. Vẫn fail khi deploy trực tiếp từ trong repo

Đã sửa line-ending nhưng build vẫn lỗi vì CLI còn gom pattern exclude từ các file ignore nằm rải rác
trong cây repo (kể cả trong `.venv/`) → **deploy từ thư mục staging sạch ngoài repo** là cách chắc chắn:

```bash
# staging = chỉ những file thật sự cần cho Docker build
STAGE=/tmp/k5-deploy
rm -rf $STAGE && mkdir -p $STAGE
cp -r 06-lab-complete/app 06-lab-complete/utils $STAGE/
cp 06-lab-complete/Dockerfile 06-lab-complete/requirements.txt \
   06-lab-complete/railway.toml 06-lab-complete/.dockerignore $STAGE/
find $STAGE -type d -name "__pycache__" -exec rm -rf {} +
find $STAGE -type f -exec sed -i 's/\r$//' {} +      # ép LF

cd $STAGE
railway up --project f2b55e96-3367-4d40-abac-0ff3bbea8e3a \
           --service aba15d8d-5e9f-4c32-986d-da7924b265f7 \
           --environment production --detach -y
```

Kết quả: build **SUCCESS** (image `python:3.11-slim` multi-stage), service `SUCCESS`.

### 3. `Free plan resource provision limit exceeded`

Khi `railway up` tạo **service mới** trên gói Free mà tài khoản đã chạm giới hạn resource → lỗi này.
Cách xử lý: deploy vào **service đã có sẵn** (`--service agent`) thay vì để CLI tự tạo, và xoá
project rỗng do Railway tự sinh lúc đăng nhập (`unique-inspiration`, 0 service).

### 4. Cảnh báo `Config as Code (railway.json / railway.toml) is deprecated`

Railway đã chuyển sang `.railway/railway.ts` (Infrastructure as Code). `railway.toml` **vẫn chạy được
đến 01/12/2026** nên bài này giữ nguyên `railway.toml` (đúng checklist của lớp K5). Khi lên production
thật nên chạy `railway config migrate` để chuyển sang định dạng mới.

---

## Tóm tắt cho Lab Coach

| Hạng mục | Trạng thái |
|---|---|
| Deploy thật lên Railway | ✅ project `k5-day14-agent`, service `agent` trạng thái **SUCCESS** |
| Public URL | ✅ `https://agent-production-6f62b355.up.railway.app` |
| Health check | ✅ `/health` → 200, `/ready` → 200 (Redis OK) |
| Auth | ✅ `/ask` thiếu key → 401, có key → 200 |
| Redis | ✅ plugin `redis:8.2`, dùng chung qua `redis.railway.internal:6379` |
| Secret | ✅ không có secret nào trong repo (kiểm tra bằng `git log --all --oneline -- '*.env' '.env'` → rỗng) |
| Ảnh bằng chứng | ✅ `screenshots/dashboard.png`, `screenshots/running.png`, `screenshots/test.png` |
