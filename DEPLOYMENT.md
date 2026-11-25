# Deployment Information

> **Student Name:** Đỗ Hoàng Minh
> **Student ID:** 2A202603507
> **Date:** 25/11/2026
> **Platform:** Railway
> **Repo:** https://github.com/Mazzonthego/K5-L3A-DAY14-DoHoangMinh-2A202603507-Deployment-Benchmark-Observability

---

## Public URL

```
https://<your-app>.railway.app        ← điền sau khi chạy `railway domain`
```

## Platform

| Mục | Nội dung |
|---|---|
| Nền tảng | Railway (deploy từ Dockerfile, `builder = "DOCKERFILE"`) |
| File cấu hình | `06-lab-complete/railway.toml` (healthcheck `/health`, app nghe theo `$PORT`) |
| Source deploy | Thư mục `06-lab-complete/` — agent Part 6 (KHÔNG deploy app mẫu `03-cloud-deployment/`) |
| Redis | Railway Redis (plugin) → lấy URL đặt vào biến `REDIS_URL` |
| Region | Singapore (gần nhất) |

---

## Điều kiện trước khi deploy (checklist)

- [ ] Trong `06-lab-complete/`: `python check_production_ready.py` → **`PASS 12/12`** (chạy bản đầy đủ, có Docker).
- [ ] `Dockerfile` có `CMD` nghe theo biến `PORT` (`${PORT:-8000}`) — Railway inject `PORT` tự động.
- [ ] `06-lab-complete/railway.toml` có `healthcheckPath = "/health"` và `builder = "DOCKERFILE"`.
- [ ] `.env` **không** commit; mọi secret đặt qua `railway variables set` hoặc Dashboard.
- [ ] Code đã push lên GitHub (Railway build từ commit đẩy lên).

---

## Các lệnh deploy (chạy trong WSL2)

```bash
# 0) Đảm bảo CLI có trong PATH (đã cài ở máy lab)
export PATH="$HOME/.npm-global/bin:$PATH"

# 1) Đăng nhập (mở trình duyệt, dán mã → không cần nhập tay trong terminal)
railway login --browserless

# 2) Vào thư mục agent Part 6 và tạo project
cd 06-lab-complete
railway init

# 3) Đặt biến môi trường (KHÔNG ghi secret vào code)
railway variables set PORT=8000
railway variables set ENVIRONMENT=production
railway variables set AGENT_API_KEY=<key-tự-tạo>
railway variables set REDIS_URL=redis://<host>:<port>
railway variables set RATE_LIMIT_PER_MINUTE=10
railway variables set DAILY_BUDGET_USD=10

# 4) Deploy và lấy URL public
railway up
railway domain          # in ra https://<app>.railway.app

# 5) (tuỳ chọn) Chấm lại kèm URL đã deploy
python check_production_ready.py --public-url https://<app>.railway.app
```

> Redis trên Railway: mở project → **+ New → Database → Redis** → copy `REDIS_URL` (dạng `redis://default:pass@host:port`) rồi `railway variables set REDIS_URL=...`.
> `/ready` phải trả **200** trước khi chụp ảnh — nếu 503 thì kiểm tra lại `REDIS_URL`.

---

## Test Commands

Chạy 4 lệnh sau với `BASE` = URL public và `AGENT_API_KEY` = key đã đặt trên Railway.
Mỗi lệnh chỉ in mã HTTP → chụp ảnh được mà không lộ key.

```bash
BASE=https://<your-app>.railway.app
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

Kết quả mong đợi: `200` · `200` · `401` · `200`.

---

## Environment Variables Set

| Biến | Giá trị | Nơi đặt |
|---|---|---|
| `PORT` | `8000` | Railway variables |
| `ENVIRONMENT` | `production` | Railway variables |
| `AGENT_API_KEY` | *(giá trị thật, không ghi trong repo)* | Railway variables |
| `REDIS_URL` | `redis://…` (Redis plugin) | Railway variables |
| `RATE_LIMIT_PER_MINUTE` | `10` | Railway variables |
| `DAILY_BUDGET_USD` | `10` | Railway variables |

---

## Screenshots

- [Deployment dashboard](screenshots/dashboard.png) — project Railway, biến môi trường, trạng thái service.
- [Service running](screenshots/running.png) — service `Up`, log khởi động.
- [Test results](screenshots/test.png) — 4 lệnh tự kiểm in ra `200 / 200 / 401 / 200`.
