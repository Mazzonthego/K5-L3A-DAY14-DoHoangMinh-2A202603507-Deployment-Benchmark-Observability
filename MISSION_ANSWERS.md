# Day 14 Lab — Mission Answers

> **Học viên:** Đỗ Hoàng Minh · **MSSV:** 2A202603507 · **Ngày chạy:** 25/11/2026
> **Báo cáo Part 7 đầy đủ:** [`BENCHMARK_REPORT.md`](BENCHMARK_REPORT.md) · **Thông tin deploy:** [`DEPLOYMENT.md`](DEPLOYMENT.md)

| Part | Nội dung | File bằng chứng |
|---|---|---|
| 1 | Localhost vs Production | — |
| 2 | Docker | `02-docker/` |
| 3 | Cloud Deployment (Railway) | `06-lab-complete/railway.toml`, `DEPLOYMENT.md` |
| 4 | API Security | `03-api-security/` |
| 5 | Scaling & Reliability | `05-scaling-reliability/` |
| 6 | Final Project — `check_production_ready.py` | `06-lab-complete/` |
| 7 | Benchmark & Observability | `BENCHMARK_REPORT.md`, `reports/`, `benchmark-results/`, `screenshots/` |

---

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns tìm được trong bản develop

Ba câu trả lời lặp lại y hệt nhau với mọi câu hỏi — dấu hiệu app chưa gọi LLM thật:

1. `Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic.`
2. `Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé.`
3. `Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận.`

Response thực tế trả về:

```json
{"question":"Hello","answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé.","model":"gpt-4o-mini"}
```

### Exercise 1.3: So sánh Develop vs Production

| Hạng mục | Develop | Production | Vì sao quan trọng |
|---|---|---|---|
| Config & secret | Hardcode key, DB URL (`app.py:17–18`); `localhost:8000`, `DEBUG=True` | Đọc env qua `config.py` (`HOST`, `PORT`, `OPENAI_API_KEY`, `AGENT_API_KEY`); có `.env.example` | Đổi config không rebuild; không lộ secret; chạy được trong container |
| Request / Response | Query `?question=Hello` → `{"answer": "..."}` | JSON body → `{"question", "answer", "model": "gpt-4o-mini"}` | Response có thông tin model, dễ trace và debug |
| Logging | `print()`, thậm chí log cả key (`app.py:33–34`) | `logger.info(json.dumps(...))`, không log secret | Log máy đọc được, an toàn khi up cloud |
| Health & shutdown | Không có endpoint, tắt đột ngột | `/health`, `/ready` (503), `SIGTERM` + `lifespan` | Nền tảng restart đúng lúc, không cắt ngang request |

---

## Part 2: Docker

### Exercise 2.1: Dockerfile questions

| # | Câu hỏi | Trả lời |
|---|---|---|
| 1 | Base image | `python:3.11` (develop; production dùng `python:3.11-slim`) |
| 2 | Working directory | `/app` |
| 3 | Vì sao `COPY requirements.txt` trước `COPY . .` | Tận dụng layer cache: đổi source code thì không phải cài lại dependencies → build nhanh hơn |
| 4 | `CMD` vs `ENTRYPOINT` | `CMD` là lệnh mặc định, bị override khi `docker run <image> <lệnh khác>`; `ENTRYPOINT` là lệnh cố định, chỉ đổi được bằng `--entrypoint`. Dùng cả hai: entrypoint cố định, cmd truyền args mặc định |

### Exercise 2.2: Build & run container

```bash
docker build -f 02-docker/develop/Dockerfile -t my-agent:develop .   # build từ gốc repo
docker run --rm -p 8000:8000 my-agent:develop
curl -X POST "http://localhost:8000/ask?question=What is Docker?"
```

| Test | Kết quả |
|---|---|
| `POST /ask?question=...` | `HTTP 200`, `{"answer":"..."}` |
| `POST /ask` gửi JSON body | **422** — develop nhận `question` qua **query string** |

### Exercise 2.3: Multi-stage build & image size

| Stage | Nội dung |
|---|---|
| `builder` | Cài dependencies (`python:3.11-slim`) |
| `runtime` | Chỉ copy artifact từ builder, tạo user non-root, có `HEALTHCHECK` → bỏ được compiler/cache pip nên image nhỏ hơn |

| Image | Kích thước |
|---|---|
| Develop | **1.710 MB (~1.67 GB)** |
| Production | **240 MB** |
| Chênh lệch | **85.96%** (đo bằng `docker images`, không chép README) |

### Exercise 2.4: Docker Compose stack

Sơ đồ service (network `internal`, chỉ nginx public):

```text
Client ──▶ nginx (:8080 → :80) ──▶ agent (:8000)
                                     ├── redis  (:6379)
                                     └── qdrant (:6333)
```

```bash
touch 02-docker/production/.env.local
docker compose -p k5-day14-docker up -d --build
docker compose -p k5-day14-docker ps
curl http://localhost:8080/health
curl -X POST http://localhost:8080/ask -H "Content-Type: application/json" -d '{"question":"Explain microservices"}'
docker compose -p k5-day14-docker logs agent
docker compose -p k5-day14-docker down
```

| Test qua Nginx | Kết quả |
|---|---|
| `GET /health` | `HTTP 200` · `{"status":"ok","version":"2.0.0",...}` |
| `POST /ask` (JSON body) | `HTTP 200` · `{"answer":"Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic."}` |
| `docker compose logs agent` | JSON log `{"event":"request","q_len":21}` + access log `POST /ask HTTP/1.1 200 OK` |

---

## Part 3: Cloud Deployment

### Exercise 3.1: Railway deployment (nền tảng chính)

| Hạng mục | Nội dung |
|---|---|
| Platform | Railway |
| Source deploy | Agent Part 6 trong `06-lab-complete/` (config: `06-lab-complete/railway.toml`, builder `DOCKERFILE`, healthcheck `/health`) |
| URL | `https://<your-app>.railway.app` ← **điền sau khi chạy `railway domain`** |
| Redis | Tạo Redis (plugin) trong project Railway, lấy URL dạng `redis://default:pass@host:port` rồi đặt vào `REDIS_URL`; phải đảm bảo `/ready` trả 200 trước khi chụp ảnh |
| Screenshot | [dashboard](screenshots/dashboard.png) · [running](screenshots/running.png) · [test](screenshots/test.png) |

Các bước deploy:

```bash
railway login --browserless
cd 06-lab-complete && railway init
railway variables set AGENT_API_KEY=… REDIS_URL=… RATE_LIMIT_PER_MINUTE=10 DAILY_BUDGET_USD=10 ENVIRONMENT=production
railway up
railway domain
```

Tự kiểm tra (4 lệnh, mỗi lệnh chỉ in mã HTTP → không lộ key):

```bash
BASE=https://<your-app>.railway.app
AGENT_API_KEY=<key-đã-đặt>
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/health"     # 200
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ready"      # 200
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H 'Content-Type: application/json' -d '{"question":"Hello"}'   # 401
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H 'Content-Type: application/json' -H "X-API-Key: $AGENT_API_KEY" \
  -d '{"question":"Hello"}'                                        # 200
```

### Exercise 3.2: So sánh `railway.toml` với `render.yaml`

| Tiêu chí | Railway (`railway.toml`) | Render (`render.yaml`) |
|---|---|---|
| Định dạng | TOML, phẳng: `[build]`, `[deploy]` | YAML, danh sách `services:` |
| Cách build | `builder = "DOCKERFILE"` (file mình dùng) hoặc `NIXPACKS` tự detect | `runtime: python` + `buildCommand`, hoặc `runtime: docker` |
| Lệnh start | `startCommand` ngay trong `[deploy]` | `startCommand` thuộc từng service |
| Health check | `healthcheckPath = "/health"` | `healthCheckPath: /health` |
| Secret | Đặt riêng qua CLI/Dashboard (`railway variables set`) | `sync: false` (tự nhập) hoặc `generateValue: true` (Render tự sinh) |
| Redis | Plugin Database → copy `REDIS_URL` | Khai báo thêm service `type: redis` trong blueprint |
| Deploy | CLI (`railway up`) hoặc GitHub integration | Dashboard → New → Blueprint → connect repo, `autoDeploy` khi push |

→ Railway đơn giản hơn cho CLI-first (1 file, deploy bằng lệnh); Render mạnh hơn ở IaC khai báo sẵn nhiều service (web + Redis) và tự sinh secret, nhưng phải thao tác qua web UI.

### Exercise 3.3: GCP Cloud Run — đọc `cloudbuild.yaml` + `service.yaml` (không cần deploy)

| Giai đoạn | Nội dung |
|---|---|
| Trigger | Push lên `main` |
| `test` | `pytest`, fail thì dừng |
| `build` | Build image Docker tag theo `$COMMIT_SHA` + `latest`, dùng layer cache |
| `push` | Container Registry (`gcr.io/$PROJECT_ID/ai-agent`) |
| `deploy` | Cloud Run `gcloud run deploy` với `--image` theo commit, `--allow-unauthenticated`, `--min-instances=1 --max-instances=10`, secret lấy từ Secret Manager |

| `service.yaml` (Knative) | Nội dung |
|---|---|
| Scale | `minScale=1` / `maxScale=10` |
| Traffic | `containerConcurrency=80`, `timeoutSeconds=60` |
| Env | `ENVIRONMENT`, `PORT` |
| Secret | `OPENAI_API_KEY`, `AGENT_API_KEY` từ Secret Manager |
| Probe | Liveness `/health`, startup `/ready` |

---

## Part 4: API Security

### Exercise 4.1: API key authentication (develop)

Key được kiểm tra trong dependency `verify_api_key()` (`APIKeyHeader(name="X-API-Key", auto_error=False)`) inject vào `POST /ask` qua `Depends`.

| Tình huống | HTTP | Body trả về |
|---|---|---|
| Thiếu key | **401** | `{"detail":"Missing API key. Include header: X-API-Key: <your-key>"}` |
| Sai key | **403** | — |
| Đúng key | **200** | `{"question":"Hello","answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé."}` |

Rotate key bằng cách đổi env `AGENT_API_KEY` (không sửa code).

```bash
# Không có key → 401
curl -i -X POST http://localhost:8000/ask -H "Content-Type: application/json" -d '{"question":"Hello"}'
HTTP/1.1 401 Unauthorized
{"detail":"Missing API key. Include header: X-API-Key: <your-key>"}

# Có key → 200
curl -i -X POST http://localhost:8000/ask -H "X-API-Key: secret-key-123" \
  -H "Content-Type: application/json" -d '{"question":"Hello"}'
HTTP/1.1 200 OK
{"question":"Hello","answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé."}
```

### Exercise 4.2: JWT authentication (production)

Flow: `POST /auth/token` (student / demo123) → JWT hết hạn sau 60 phút → gửi trong header `Authorization: Bearer <token>`; server verify chữ ký HS256, không cần tra DB mỗi request. Token sai → `{"detail":"Invalid token."}`. Dùng token trong 4.3.

```bash
curl -i -s -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/json" -d '{"username":"student","password":"demo123"}'
HTTP/1.1 200 OK
{"access_token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...<đã che>",
 "token_type":"bearer","expires_in_minutes":60}

curl -i -X POST http://localhost:8000/ask -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"question":"Explain JWT"}'
HTTP/1.1 200 OK
{"question":"Explain JWT","answer":"...",
 "usage":{"requests_remaining":9,"budget_remaining_usd":2.1e-05}}
```

### Exercise 4.3: Rate limiting

| Hạng mục | Giá trị |
|---|---|
| Thuật toán | **Sliding Window Counter** bằng `deque` timestamp trong 60 giây |
| User `student` | **10 request/phút** |
| Admin (`teacher`) | **100 request/phút** (bucket riêng) |
| Vượt giới hạn | **429** kèm `Retry-After` |

Tự chạy 15 request:

```bash
TOKEN="<token lấy ở 4.2>"
for i in $(seq 1 15); do
  curl -s -o /dev/null -w "$i -> %{http_code}\n" -X POST http://localhost:8000/ask \
    -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
    -d "{\"question\":\"Test $i\"}"
done
1 -> 200  ...  10 -> 200
11 -> 429  12 -> 429  13 -> 429  14 -> 429  15 -> 429
```

### Exercise 4.4: Cost guard implementation

`check_budget()` chạy **trước** khi gọi LLM, `record_usage()` ghi token **sau** khi trả lời: `cost = input/1000 × $0.00015 + output/1000 × $0.0006`.

| Hạng mục | Giá trị |
|---|---|
| Giới hạn mỗi user | **$1/ngày** |
| Giới hạn toàn hệ thống | **$10/ngày** |
| Khi vượt | **402** (global → 503) |
| Cảnh báo | ở 80% budget |
| Lưu state | Production lưu trong **Redis** theo key ngày → chạy nhiều instance/restart không mất state (bản demo dùng dict RAM) |

**Vì sao cần cả hai:**

| | Rate limit | Cost guard |
|---|---|---|
| Bảo vệ | **Tốc độ** (chống spam/DoS, quá tải hệ thống) | **Tiền** (request hợp lệ, đều đặn cũng có thể tiêu sạch budget) |
| Kịch bản vẫn lộ | Limit 10 req/phút mà mỗi req đắt thì vẫn cháy tiền | Budget còn nhưng burst 1000 req vẫn làm sập service |

---

## Part 5: Scaling & Reliability

### Exercise 5.1: Health checks — liveness vs readiness

| Probe | Kiểm tra gì | Develop | Production |
|---|---|---|---|
| **Liveness `/health`** | Process còn sống | Trả `status`, `uptime_seconds`, `version`, `environment`; kiểm tra RAM qua `psutil`, RAM > 90% thì `status=degraded` | Kiểm tra `redis.ping()`, trả HTTP **200** khi process sống (`status` có thể là `degraded` nếu Redis lỗi) |
| **Readiness `/ready`** | Instance đã sẵn sàng nhận traffic | Trả **503** trong lúc startup/shutdown | Gọi `redis.ping()`, trả **503 `Redis not available`** nếu Redis không kết nối được |

| Vì sao phải tách hai probe | |
|---|---|
| Tránh restart loop | Nếu `/health` phụ thuộc Redis thì chỉ cần Redis lỗi cũng làm container restart liên tục dù ứng dụng vẫn hoạt động |
| Vai trò | `/health` đánh giá process; `/ready` đánh giá dependency và khả năng phục vụ traffic — load balancer chỉ route traffic tới instance readiness trả 200 |
| Hệ quả | Nếu liveness trả lỗi, Docker/Kubernetes có thể restart container |

Kết quả thực tế trên stack 3 instance:

```bash
$ curl -i http://localhost:8080/health
HTTP/1.1 200 OK
X-Served-By: 172.19.0.3:8000
{"status":"ok","instance_id":"instance-ee1e3b","uptime_seconds":68.6,"storage":"redis","redis_connected":true}

$ curl -i http://localhost:8080/ready
HTTP/1.1 200 OK
X-Served-By: 172.19.0.4:8000
{"ready":true,"instance":"instance-d56414"}
```

### Exercise 5.2: Graceful shutdown

Bản develop đăng ký `signal.signal(signal.SIGTERM, handle_sigterm)` và `SIGINT`. Khi nhận `SIGTERM`:

1. Uvicorn ngừng nhận request mới, middleware đếm `_in_flight_requests`.
2. `lifespan` chờ các request đang chạy hoàn thành tối đa **30 giây** trước khi đóng kết nối và thoát (`timeout_graceful_shutdown=30`).

Nhờ vậy request đang xử lý không bị cắt ngang khi deploy, restart hoặc scale-down.

Test thực tế bằng `docker stop` (gửi `SIGTERM`):

```bash
$ docker stop -t 10 k5-day14-scaling-agent-2
agent-2  | INFO:     Shutting down
agent-2  | INFO:     Waiting for application shutdown.
agent-2  | INFO:app:Instance instance-465eab shutting down
agent-2  | INFO:     Application shutdown complete.
agent-2  | INFO:     Finished server process [1]
```

### Exercise 5.3: Stateless design

Bản production không lưu conversation trong RAM:

| Cơ chế | Chi tiết |
|---|---|
| Ghi session | `save_session()` → `_redis.setex(f"session:{session_id}", 3600, json_data)`, TTL 1 giờ |
| Đọc session | `load_session()` đọc lại từ Redis → mọi agent instance thấy cùng trạng thái |
| Giới hạn history | 20 message (10 lượt) |
| Khi Redis lỗi | Fallback sang dict trong RAM — **không scale-safe**, có log cảnh báo |

**Anti-pattern khi lưu state trong RAM:** request của user có thể rơi vào instance A rồi instance B; instance B không có `history` của user. Giải pháp Redis giữ state ở ngoài process, nhờ vậy request có thể phục vụ bởi bất kỳ instance nào và state còn nguyên sau restart.

Bằng chứng state thực sự nằm trong Redis:

```bash
$ docker compose -p k5-day14-scaling exec redis redis-cli --scan --pattern 'session:*'
session:1fe1901a-41ea-4e81-9a33-53b4c499e962
session:9f276698-266a-431a-96b2-2d684185a0eb
session:demo
```

### Exercise 5.4: Load balancing với 3 instance

```bash
touch 05-scaling-reliability/production/.env.local
cd 05-scaling-reliability/production
docker compose -p k5-day14-scaling up -d --build --scale agent=3
docker compose -p k5-day14-scaling ps
```

Kết quả:

```text
NAME                       STATUS                   PORTS
k5-day14-scaling-agent-1   Up ... (healthy)         8000/tcp
k5-day14-scaling-agent-2   Up ... (healthy)         8000/tcp
k5-day14-scaling-agent-3   Up ... (healthy)         8000/tcp
k5-day14-scaling-nginx-1   Up ...                   0.0.0.0:8080->80/tcp
k5-day14-scaling-redis-1   Up ... (healthy)         6379/tcp
```

**Luồng request:**

```text
client → Nginx :8080 → upstream agent_cluster → 3 agent :8000
```

| Chi tiết | Ghi chú |
|---|---|
| DNS nội bộ | Docker DNS (`127.0.0.11`) trả về các IP của service `agent` |
| Cân bằng tải | Nginx phân tán round-robin |
| Header `X-Served-By` | Cho biết instance đã xử lý |
| Trường `served_by` trong JSON | ID logic của instance |

```bash
$ curl -i -X POST http://localhost:8080/chat \
    -H "Content-Type: application/json" \
    -d '{"question":"Request 1","session_id":"demo"}'
HTTP/1.1 200 OK
X-Served-By: 172.19.0.4:8000
{"session_id":"demo","question":"Request 1","answer":"Đây là câu trả lời từ AI agent (mock)...","turn":3,"served_by":"instance-d56414","storage":"redis"}
```

Gửi 10 request cùng session để kiểm tra phân tán tải:

| Request | HTTP | `served_by` | | Request | HTTP | `served_by` |
|---|---|---|---|---|---|---|
| 1 | 200 | `instance-ee1e3b` | | 6 | 200 | `instance-ee1e3b` |
| 2 | 200 | `instance-d56414` | | 7 | 200 | `instance-4a2803` |
| 3 | 200 | `instance-ee1e3b` | | 8 | 200 | `instance-d56414` |
| 4 | 200 | `instance-4a2803` | | 9 | 200 | `instance-ee1e3b` |
| 5 | 200 | `instance-d56414` | | 10 | 200 | `instance-4a2803` |

Instances used: `{'instance-ee1e3b', 'instance-4a2803', 'instance-d56414'}`

**Failover test:** dừng `agent-2`, request tiếp vẫn trả **HTTP 200** và được instance khác phục vụ (`served_by=instance-ee1e3b`). Nginx tự thử upstream tiếp theo nhờ `proxy_next_upstream error timeout http_503`; history của cùng session vẫn còn đủ **12 message** trong Redis. Như vậy khi một instance ngừng hoạt động, service không bị gián đoạn và không mất state.### Exercise 5.5: Test stateless

```bash
cd 05-scaling-reliability/production
python test_stateless.py
```

> Trên Windows PowerShell, dùng `New-Item -ItemType File .env.local -Force` thay cho `touch`, và đặt `$env:PYTHONIOENCODING='utf-8'` trước khi chạy script để in được tiếng Việt.

Kết quả thực tế:

```text
============================================================
Stateless Scaling Demo
============================================================

Session ID: 9f276698-266a-431a-96b2-2d684185a0eb

Request 1: [instance-465eab]
Request 2: [instance-ee1e3b]
Request 3: [instance-d56414]
Request 4: [instance-465eab]
Request 5: [instance-ee1e3b]

Total requests: 5
Instances used: {'instance-ee1e3b', 'instance-465eab', 'instance-d56414'}
✅ All requests served despite different instances!

--- Conversation History ---
Total messages: 10
  [user]: What is Docker?...
  [assistant]: Container là cách đóng gói app để chạy ở mọi nơi...
  [user]: Why do we need containers?...
  [assistant]: Agent đang hoạt động tốt! (mock response)...
  [user]: What is Kubernetes?...
  [assistant]: Đây là câu trả lời từ AI agent (mock)...
  [user]: How does load balancing work?...
  [assistant]: Agent đang hoạt động tốt! (mock response)...
  [user]: What is Redis used for?...
  [assistant]: Agent đang hoạt động tốt! (mock response)...

✅ Session history preserved across all instances via Redis!
```

**Kết luận:**

| Bằng chứng | Kết quả |
|---|---|
| 5 request qua 3 agent khác nhau | Vẫn đủ **10 message** (5 câu hỏi + 5 câu trả lời) vì state nằm trong Redis, không nằm trong RAM của từng container |
| Sau failover | Cùng session vẫn có **12 message** |

→ Đây là bằng chứng ứng dụng **stateless** và có thể scale ngang an toàn.

Dọn stack sau khi test:

```bash
docker compose -p k5-day14-scaling down
```

---

## Part 6: Final Project — output `check_production_ready.py`

**Lệnh đã chạy (WSL2 Ubuntu, Docker 29.9.3):**

```bash
cd 06-lab-complete
python check_production_ready.py     # exit code = 0
```

**Output thật (rút gọn phần tiêu chí, giữ nguyên kết quả):**

```text
✅ 1. Dockerfile (multi-stage, < 500 MB)
     ✅ Multi-stage build (≥ 2 lệnh FROM)
     ✅ Base image gọn — stage cuối dùng python:3.11-slim
     ✅ Chạy bằng user non-root
     ✅ Có HEALTHCHECK
     ✅ Docker: build image thành công — 7s
     ✅ Docker: image < 500 MB — 273 MB
     ✅ Docker: container chạy được, GET /health → 200

✅ 2. docker-compose.yml (agent + redis)
     ✅ Có service agent (build từ Dockerfile) + redis — services: agent, redis
     ✅ Service agent kết nối redis (REDIS_URL + depends_on)

✅ 3. .dockerignore
     ✅ Loại trừ .env (secrets), __pycache__, venv

✅ 4. Health check endpoint (GET /health)
     ✅ Khi chạy: GET /health → 200 — uvicorn --workers 2

✅ 5. Readiness endpoint (GET /ready)
     ✅ Khi chạy: GET /ready → 200
     ✅ Khi chạy: Redis mất kết nối → /ready 503 (còn /health vẫn 200)

✅ 6. API Key authentication
     ✅ Khi chạy: thiếu / sai API key → 401
     ✅ Khi chạy: API key đúng → 200

✅ 7. Rate limiting
     ✅ Khi chạy: vượt giới hạn → 429 — 429 sau 5 request thành công (RATE_LIMIT_PER_MINUTE=5)
     ✅ Khi chạy: state nằm trong Redis — restart agent vẫn bị 429

✅ 8. Cost guard
     ✅ Khi chạy: hết budget → 402 — 402 ở request thứ 2

✅ 9. Config từ environment variables
     ✅ app/config.py đọc biến môi trường
     ✅ .env.example liệt kê đủ biến cấu hình · .env nằm trong .gitignore
     ✅ Không hard-code secret trong code
     ✅ Khi chạy: agent dùng AGENT_API_KEY và RATE_LIMIT_PER_MINUTE từ env

✅ 10. Structured logging
     ✅ Code ghi log dạng JSON
     ✅ Khi chạy: mọi dòng log của app là JSON hợp lệ — 12 dòng JSON

✅ 11. Graceful shutdown
     ✅ Code xử lý SIGTERM / lifespan shutdown
     ✅ Khi chạy: SIGTERM lúc đang có request → request vẫn 200, process tự thoát — exit code 0
     ✅ Docker: `docker stop` tắt êm (exit code 0, < 10s) — exit code 0, 1.0s

✅ 12. Public URL ready (Railway / Render config)
     ✅ Có railway.toml (không chỉ toàn comment)
     ✅ railway.toml: builder + healthcheckPath = "/health"
     ✅ App lắng nghe theo biến PORT do platform cấp

================================================================
  📋 Checklist Deliverable
     ✅ Dockerfile (multi-stage, < 500 MB)
     ✅ docker-compose.yml (agent + redis)
     ✅ .dockerignore
     ✅ Health check endpoint (GET /health)
     ✅ Readiness endpoint (GET /ready)
     ✅ API Key authentication
     ✅ Rate limiting
     ✅ Cost guard
     ✅ Config từ environment variables
     ✅ Structured logging
     ✅ Graceful shutdown
     ✅ Public URL ready (Railway / Render config)
----------------------------------------------------------------
  Result: 12/12 tiêu chí đạt · 41/41 checks passed
  🎉 PASS 12/12 — PRODUCTION READY! Deploy nào!
================================================================
```

| Tiêu chí | Kết quả | Bằng chứng đo được |
|---|---|---|
| 1. Dockerfile multi-stage < 500 MB | ✅ | Build 7s, image **273 MB** |
| 2. docker-compose.yml (agent + redis) | ✅ | `services: agent, redis` + `REDIS_URL` + `depends_on` |
| 3. .dockerignore | ✅ | Loại `.env`, `__pycache__`, venv |
| 4. Health `/health` | ✅ | `GET /health → 200`, uvicorn `--workers 2` |
| 5. Readiness `/ready` | ✅ | `200`; mất Redis → `503` còn `/health` vẫn `200` |
| 6. API key auth | ✅ | Thiếu/sai key → `401`; đúng key → `200` |
| 7. Rate limiting | ✅ | `429` sau 5 request (`RATE_LIMIT_PER_MINUTE=5`); state nằm trong Redis, restart vẫn `429` |
| 8. Cost guard | ✅ | Hết budget → `402` ở request thứ 2 |
| 9. Config từ env | ✅ | `app/config.py` đọc env; `.env` nằm trong `.gitignore`; không hard-code secret |
| 10. Structured logging | ✅ | 12 dòng log, tất cả là JSON hợp lệ |
| 11. Graceful shutdown | ✅ | SIGTERM khi đang có request → request vẫn `200`, exit code 0; `docker stop` 1,0s |
| 12. Public URL ready | ✅ | `railway.toml` có builder + `healthcheckPath = "/health"`, app nghe theo `PORT` |

**Ghi chú môi trường (2 điểm cần lưu ý khi chạy lại):**

| Vấn đề | Chi tiết |
|---|---|
| Lần chạy đầu agent không khởi động | `.venv` (WSL) thiếu `redis` → sau khi `pip install redis==5.1.0 psutil==6.0.0` là đạt |
| `pydantic==2.9.0` trong `requirements.txt` | **Không có wheel cho Python 3.14** (chỉ build được từ source → fail). Trên Python 3.11 của Docker image vẫn cài bình thường, nên không sửa file này |

---

## Part 7: Benchmark & Observability

Báo cáo đầy đủ: **[`BENCHMARK_REPORT.md`](BENCHMARK_REPORT.md)** · Dữ liệu gốc: `reports/` (10 file JSON).

### 7.1 Đọc metrics của agent

| Loại metric | Ví dụ | Đặc tính |
|---|---|---|
| **Counter** | `http_requests_total{method="POST",route="/ask",status="200"}`, `llm_tokens_total{model="mock-llm-small",type="input"}`, `llm_cost_usd_total{...}` | Chỉ tăng |
| **Gauge** | `agent_in_flight_requests` (số request đang xử lý), `agent_info{version="v2",model="mock-llm-small"}` | Lên xuống |
| **Histogram** | `http_request_duration_seconds_bucket{le="0.2",...}`, `llm_request_duration_seconds_bucket` | Chia bucket để tính percentile |

| Câu hỏi | Trả lời |
|---|---|
| Vì sao label `route` dùng `route.path` (template) chứ không dùng URL thật? | Nếu dùng `request.url.path`, bot quét `/wp-admin`, `/.env`, `/a1b2c3`… sẽ tạo hàng nghìn time series → cardinality bùng nổ, Prometheus hết RAM. Dùng template + `unmatched` giữ số series ổn định |
| Metric thêm (nhiệm vụ) | `agent_question_length_chars` (Histogram, buckets 20/50/100/200/500/1000/2000) đo phân bố độ dài câu hỏi. Dùng Histogram chứ không label `length=...` vì độ dài có vô số giá trị → cardinality bùng nổ |

### 7.2 Load test & SLO (300 request/mức)

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO p95 ≤ 500 ms |
|---|---|---|---|---|---|---|
| 1 | 4.36 | 190.2 | 221.1 | 1697.1 | 0.33% | ✅ |
| 10 | 43.38 | 189.6 | 218.7 | 1696.3 | 0.67% | ✅ |
| 50 | 109.63 | 202.9 | 280.5 | 1721.0 | 1.33% | ✅ |
| 100 | 54.87 | 882.3 | 4322.1 | 4801.6 | 1.00% | ❌ (exit code 1) |

RPS không tăng tuyến tính (c=50 → 109,63 req/s rồi c=100 **giảm** còn 54,87 req/s, p95 nhảy lên 4.322 ms): agent `develop/` chạy 1 worker uvicorn, request xếp hàng khi quá tải → cần scale **ngang** (nhiều instance) thay vì tăng concurrency.

Tail latency (`MOCK_SLOW_RATE`, concurrency 20):

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|
| 0 | 191.2 | 219.3 | 236.2 |
| 0.03 (mặc định) | 214.8 | 229.8 | 1658.3 |
| 0.1 | 318.7 | 1693.9 | 1713.0 |

avg tăng nhẹ (+67%) còn p99 tăng vọt (+625%) → SLO phải đặt theo **percentile (p95/p99)**, không theo trung bình; nếu theo avg, agent vẫn "xanh" trong khi 1 người trong 100 chờ gần 2 giây.

### 7.3 Eval & quality gate (golden dataset 23 câu)

| Chỉ số | Agent v1 | Agent v2 | Agent v2 (sau khi sửa KB) |
|---|---|---|---|
| Accuracy | 4.3% (1/23) | 91.3% (21/23) | **100% (23/23)** |
| Avg tokens / câu | 56.5 | 108.8 | 117.3 |
| Cost / câu đúng (USD) | 0.00039615 | 0.00003607 | **0.00003573** |
| Quality gate | ❌ FAIL | ✅ PASS | ✅ PASS (0 regression) |

- **2 câu sai ban đầu của v2:** `scaling-03` (thiếu `cpu`, `memory`, `custom metrics`) và `security-02` (thiếu `token`, `hết hạn`, `chữ ký`) → đã thêm entry HPA + JWT vào `KNOWLEDGE_BASE` trong `develop/utils/mock_llm.py`.
  - Lưu ý: keyword có dấu (`hết hạn`, `chữ ký`) phải viết đúng dấu, nếu không chỉ khớp 1/3 keyword.
- **Cost/câu đúng** của v2 thấp hơn v1 ~11× dù tổng cost cao hơn → đánh đổi chất lượng/cost có lợi; đổi lại token/câu gần gấp đôi và p95 latency +30 ms (thêm bước retrieval).
- **Quality gate chặn merge:** `run_eval.py` trả **exit code 1** khi accuracy < `--min-accuracy` hoặc có regression. Job `.github/workflows/eval.yml` chạy eval mỗi Pull Request với `--min-accuracy 0.85` → exit ≠ 0 ⇒ job fail ⇒ PR không merge được.

### 7.4–7.7 Observability stack (CP8) — stack Docker đầy đủ

Báo cáo chi tiết: **[`BENCHMARK_REPORT.md`](BENCHMARK_REPORT.md)** mục 4–6 · Ảnh: [`screenshots/`](screenshots/) · CSV: [`benchmark-results/`](benchmark-results/) · Bằng chứng trace/log: [`reports/jaeger/`](reports/jaeger/)

Stack đã bật thật: `docker compose -p k5-day14-observability up -d --build --scale agent=1` → Nginx :8080 → agent ×N → Jaeger :16686 (OTLP) + Prometheus :9090 (scrape) → Grafana :3000, Locust :8089.

**7.4 — Đọc dashboard Grafana (số liệu lúc scale 3, đang tải):**

| Câu hỏi | Trả lời (số liệu thật) |
|---|---|
| p95 vs avg | avg **236,9 ms**, p50 **180,6 ms**, p95 **297,1 ms**, p99 **1.820 s** → p99 gấp ~7,7× avg. Nhìn avg thì tưởng ổn, thực tế có nhóm 3% request chậm bất thường kéo p99 lên ~1,8 s |
| req/s theo instance | 12,49 / 12,33 / 12,47 req/s (tổng 37,3 req/s) → Nginx chia tải gần như **đều tuyệt đối**; header `X-Served-By` trả IP instance đã phục vụ |
| input vs output token/s | input **2.945 token/s**, output **1.580 token/s** (tỉ lệ 1,87) → input lớn hơn vì prompt v2 có context truy xuất từ KB (95 input token/câu so với 37 của v1) |
| Vì sao `/metrics` 404 | Nginx có `location = /metrics { return 404; }` để **không lộ** metrics ra ngoài. Prometheus scrape **trực tiếp trong mạng nội bộ** (`agent:8000/metrics` qua DNS service discovery) → `curl localhost:8080/metrics → 404` nhưng `GET http://localhost:8000/metrics` trong container agent → **200** |

**7.5 — Tracing (Jaeger):**

| Trace | Tổng thời gian | Phân rã span | Kết luận |
|---|---|---|---|
| Chậm — `5c7037095de1df7e78b73db9bee68124` | `POST /ask` **1.729,3 ms** | `agent.run` 1.725,8 ms → `chat mock-llm-small` **1.698,6 ms (98,2%)**, `agent.retrieve_context` 26,9 ms (1,6%) | Bottleneck ở **LLM upstream**, không phải code của mình (log `llm_call` cùng trace: `llm_ms = 1697.6`) |
| Lỗi — `c739e067d2c92d08ade9b254b07b4ac8` | `POST /ask` **100,7 ms** → HTTP **503** | `chat mock-llm-small` (83,0 ms): tag `error=true`, `otel.status_code=ERROR`, `error.type=upstream_unavailable` | Lỗi xuất phát từ **upstream LLM**, không phải từ retrieval (`agent.retrieve_context` chỉ 15,2 ms) |

Event `exception` của trace lỗi: `exception.type = utils.mock_llm.LLMError`, `exception.message = Upstream LLM error: 503 Service Unavailable (mock)`, stack trace trỏ `utils/mock_llm.py:199`.

Ảnh: `screenshots/jaeger-slow-trace.png` · `screenshots/jaeger-error-trace.png`

**Từ log sang trace:** mọi dòng log JSON đều có `trace_id`, nên đi theo hai chiều:

```bash
docker compose -p k5-day14-observability logs agent | grep llm_error
# → lấy được trace_id của request lỗi, dán vào http://localhost:16686/trace/<trace_id>
```

Bằng chứng máy: `reports/jaeger/trace_summary.json`, `trace_slow.json`, `trace_error.json`, `slow_trace.json`, `error_trace.json`, `agent_logs.jsonl`.

**7.6 — Alerts & chaos (đổi cấu hình qua `.env` trong `production/`):**

| # | Thay đổi | Alert firing | Thời gian đổi → firing | Panel rõ nhất | Số liệu |
|---|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` | `AgentHighErrorRate` | **86 s** (`for: 1m`) | Golden Signals → Error rate | error rate **20,64%** |
| B | `+ MOCK_SLOW_RATE=0.3` | `AgentHighLatencyP95` | **144 s** (`for: 2m`) | Latency & Traffic → p95/p99 | p95 **1,907 s** |
| C | `LLM_MODEL=mock-llm-large` | `LLMCostBurnRateHigh` | đã firing sẵn; sau khi đổi: **$4,38/h → $17,59/h**, LLM p95 0,198 → 0,484 s | 🤖 LLM → Cost burn rate | model large đắt **16,7×**, chậm **2,5×** |
| D | `docker pause` agent-1 | `AgentInstanceDown` | **46 s** (`for: 30s`) | 🧩 Instances → Instances up | `up=0` cho instance bị pause; `unpause` → tự về 1 |
| E | `AGENT_VERSION=v1` | **không alert nào** (0 alert active) | — | bảng Agent version → v1 | token/câu 92 → **37**; câu hỏi HPA trả lời **sai** nhưng metric hạ tầng vẫn xanh |

Ảnh: `screenshots/prometheus-alert-firing.png` (**3 alert cùng FIRING**), `screenshots/prometheus-alert-instance-down.png`, `screenshots/grafana-chaos.png`, `screenshots/grafana-v1-no-alert.png`.

- **Vì sao `docker pause` chứ không `docker stop`?** Prometheus tìm agent bằng DNS.
  - Container bị `stop` **biến mất khỏi DNS** → coi như target không tồn tại (không phải "down") → `up` không bao giờ = 0 → **không alert**.
  - Container bị `pause` vẫn còn trong DNS nhưng không trả lời → `up == 0` → alert bắn.
- **Thí nghiệm E phát hiện bằng cách nào trong production?** Đây là lỗi **chất lượng**, không phải lỗi hạ tầng. Bốn lớp giám sát bổ sung:

  | Lớp | Cách làm |
  |---|---|
  | 1. Eval / quality monitoring | `eval/run_eval.py` trên golden dataset + CI gate (`.github/workflows/eval.yml`), chạy định kỳ trên production |
  | 2. Metric chất lượng | Export ra Prometheus: `answer_quality_score` (LLM-as-judge/groundedness), `refusal_rate`, `retrieval_hit_ratio`, `tokens_per_request` |
  | 3. Canary + phản hồi người dùng | So sánh điểm chất lượng/CSAT theo phiên bản |
  | 4. Synthetic check định kỳ | Hỏi câu có đáp án biết |

  Tín hiệu cảnh báo được trong thí nghiệm E: `tokens_per_request` 92 → 37 và `retrieval hit ratio` về 0 (agent không còn dùng KB).

**7.7 — Benchmark scaling (Locust headless, 100 user, 2 phút, `--csv`):**

| Số instance | Request | RPS | p50 (ms) | avg (ms) | p95 (ms) | p99 (ms) | Failures | Error rate |
|---|---|---|---|---|---|---|---|---|
| 1 | 6.968 | **58,62** | 200 | 271,1 | **620** | 1700 | 72 | 1,03% |
| 3 | 7.068 | **59,55** | 190 | 246,1 | **280** | 1700 | 83 | 1,17% |

| Câu hỏi | Trả lời |
|---|---|
| Scale có cải thiện p95 không? | Có: p95 **620 → 280 ms (−55%)**, p50 200 → 190, avg 271 → 246 — nhờ chia tải, mỗi instance ít request hơn nên hàng đợi ngắn hơn |
| Vì sao p99 không đổi (1700 ms cả 2 lần)? | Vì nó đến từ **slow path của mock LLM** (`MOCK_SLOW_RATE` → ngủ 1,5 s), không phải do xếp hàng → scale giải quyết được queueing nhưng không giải quyết được phụ thuộc upstream |
| Error rate ~1,1% khớp `MOCK_ERROR_RATE=0.01` | ⇒ scale không làm tăng lỗi |

**Nút thắt ở đâu?** Không phải ở server:

| Bằng chứng | Số đo |
|---|---|
| CPU của agent (`docker stats`) | **7,5%** (giới hạn container 0,5 CPU) → còn nhiều headroom |
| RAM của agent | ~60 MB / 256 MB |
| RPS khi scale 1 → 3 | 58,62 → 59,55 req/s (**+1,6%**) |

Lý do RPS đứng yên là **Locust là closed-loop**: 100 user × (response + wait 0,5–2 s) ⇒ throughput tối đa ≈ 64–67 req/s, đúng bằng số đo (64,41 và 65,52). Muốn đo năng lực tối đa phải dùng **open-loop** (rate cố định) hoặc tăng số user.

**Sửa lỗi phát sinh (2 lỗi, đều đã sửa trong repo):**

| Lỗi | Nguyên nhân | Cách sửa |
|---|---|---|
| Container restart liên tục, `ModuleNotFoundError: No module named 'uvicorn'` | Dockerfile gốc của `production/` cài package bằng `pip install --user` vào `/home/agent/.local`, nhưng user `agent` có home `/app` + `PYTHONPATH=/app` nên Python không thấy site-packages | Đổi sang pattern venv `/opt/venv` giống Dockerfile `06-lab-complete/` |
| Agent trong stack trả lời sai câu HPA/JWT | `production/utils/mock_llm.py` chưa có phần `KNOWLEDGE_BASE` đã sửa ở CP7 | Đồng bộ entry HPA + JWT sang `production/utils/mock_llm.py` → agent trong stack trả lời đúng |

---

## AI log / Ghi chú

| Mốc | Việc đã làm | Ghi chú |
|---|---|---|
| CP0–CP1 | Setup WSL2 + Docker, chạy develop/production Part 1 | Bản develop nhận `question` qua **query**, production nhận JSON |
| CP2 | Build image, đo size, bật Compose stack | Docker Hub trả 429 → lấy `python:3.11-slim` từ mirror ECR; cổng 80 bị chiếm → dùng `8080:80` |
| CP3 | Test 401 / 200 / 429 + giải thích cost guard | Token JWT đã che trước khi dán |
| CP4 | Health/readiness, stateless, scale 3 instance, `test_stateless.py` | Dùng `-p k5-day14-scaling` để không trùng project |
| CP5 | Sửa TODO trong `06-lab-complete/`, chạy `check_production_ready.py` đầy đủ | ✅ **PASS 12/12 · 41/41 checks** (exit 0). Docker image 273 MB, `docker stop` 1.0s |
| CP6 | `railway.toml` + `DEPLOYMENT.md` + Part 3 (so sánh Railway/Render, Cloud Run) | Chưa deploy — cần `railway login` bằng tài khoản của bạn |
| CP7 | Load test 4 mức + 3 mức `MOCK_SLOW_RATE`, eval v1/v2/v2-fixed (23/23), metric `agent_question_length_chars`, CI `eval.yml` | Chạy trong WSL2 với `.venv` Python 3.14 |
| CP8 | Observability stack (Prometheus/Grafana/Jaeger/Locust), 5 thí nghiệm chaos, ảnh, benchmark scale 1 vs 3 | ✅ Xong — 3 alert FIRING, trace chậm + trace lỗi, 9 ảnh trong `screenshots/`, CSV trong `benchmark-results/` |

---

## Phụ lục A — Checklist giao bài & Self-test

> Phần này là checklist gốc của lab, giữ nguyên để đối chiếu khi nộp.

### A.1 Yêu cầu nộp bài

| Mục | Yêu cầu |
|---|---|
| 1. Mission Answers (40 points) | File `MISSION_ANSWERS.md` trả lời toàn bộ exercise |
| 2. Full Source Code (60 points) | Agent production-ready dựng từ skeleton `06-lab-complete/` (xem mục **Hợp đồng** trong [`06-lab-complete/README.md`](06-lab-complete/README.md)) |
| 3. Service Domain Link | File `DEPLOYMENT.md` có URL public, lệnh test, biến môi trường đã đặt |
| 4. Benchmark & Observability (20 points) | `BENCHMARK_REPORT.md` + `reports/`, `benchmark-results/`, `screenshots/` |

> **Cách tính điểm:** tổng thô 120 (40 + 60 + 20), quy đổi về thang 100.

### A.2 Cấu trúc source code Part 6

```text
your-repo/
├── app/
│   ├── main.py              # Main application
│   ├── config.py            # Configuration
│   ├── auth.py              # Authentication
│   ├── rate_limiter.py      # Rate limiting (Redis)
│   ├── cost_guard.py        # Cost protection (Redis)
│   └── redis_client.py      # Redis connection + health
├── utils/
│   └── mock_llm.py          # Mock LLM (provided)
├── check_production_ready.py  # Grading script (provided, do not modify)
├── Dockerfile               # Multi-stage build
├── docker-compose.yml       # Full stack
├── requirements.txt         # Dependencies
├── .env.example             # Environment template
├── .dockerignore            # Docker ignore
├── railway.toml             # Railway config (or render.yaml)
└── README.md                # Setup instructions
```

| Requirement | Trạng thái |
|---|---|
| `python check_production_ready.py` báo `PASS 12/12` (chạy đầy đủ, có Docker) — dán phần "📋 Checklist Deliverable" của output vào `MISSION_ANSWERS.md` | ✅ xem Part 6 |
| All code runs without errors | ✅ |
| Multi-stage Dockerfile (image < 500 MB) | ✅ 273 MB |
| API key authentication | ✅ |
| Rate limiting (10 req/min) | ✅ |
| Cost guard ($10/month) | ✅ |
| Health + readiness checks | ✅ |
| Graceful shutdown | ✅ |
| Stateless design (Redis) | ✅ |
| No hardcoded secrets | ✅ |

### A.3 `DEPLOYMENT.md` — mẫu theo yêu cầu

````markdown
# Deployment Information

## Public URL
https://your-agent.railway.app

## Platform
Railway / Render / Cloud Run

## Test Commands

### Health Check
```bash
curl https://your-agent.railway.app/health
# Expected: {"status": "ok"}
```

### API Test (with authentication)
```bash
curl -X POST https://your-agent.railway.app/ask \
  -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test", "question": "Hello"}'
```

## Environment Variables Set
- PORT
- REDIS_URL
- AGENT_API_KEY
- LOG_LEVEL

## Screenshots
- [Deployment dashboard](screenshots/dashboard.png)
- [Service running](screenshots/running.png)
- [Test results](screenshots/test.png)
````

### A.4 Cấu trúc bằng chứng Part 7

```text
your-repo/
├── BENCHMARK_REPORT.md
├── reports/
│   ├── load_v2_c1.json ... load_v2_c100.json   # load_test.py --out
│   ├── eval_v1.json
│   ├── eval_v2.json
│   └── eval_v2_fixed.json                      # sau khi sửa knowledge base
├── benchmark-results/
│   ├── scale_1_stats.csv                       # Locust headless
│   └── scale_3_stats.csv
└── screenshots/
    ├── grafana-dashboard.png
    ├── jaeger-slow-trace.png
    ├── jaeger-error-trace.png
    └── prometheus-alert-firing.png
```

| Requirement | Trạng thái |
|---|---|
| Load test ở 4 mức concurrency, có p50/p95/p99 và đối chiếu SLO | ✅ mục 7.2 |
| Eval v1 vs v2, sửa knowledge base để v2 đạt 100% không regression | ✅ mục 7.3 |
| Dashboard Grafana có tải, 1 trace chậm + 1 trace lỗi trong Jaeger | ✅ mục 7.4–7.5 |
| Ít nhất 2 alert firing, ghi lại thời gian phát hiện | ✅ 3 alert firing, mục 7.6 |
| Số liệu trong report khớp với file JSON/CSV | ✅ |

### A.5 Pre-Submission Checklist

| Mục | Trạng thái |
|---|---|
| Repository is public (or instructor has access) | ⬜ chưa push repo lên GitHub |
| `MISSION_ANSWERS.md` completed with all exercises | ✅ |
| `DEPLOYMENT.md` has working public URL | ⬜ cần deploy thật lên Railway (xem CP6) |
| All source code in `app/` directory | ✅ `06-lab-complete/app/` |
| `README.md` has clear setup instructions | ✅ |
| No `.env` file committed (only `.env.example`) | ✅ `.env` nằm trong `.gitignore`, không có trong history |
| No hardcoded secrets in code | ✅ |
| Public URL is accessible and working | ⬜ chờ deploy |
| Screenshots included in `screenshots/` folder | ✅ 9 ảnh Part 7 |
| Repository has clear commit history | ✅ |
| `python check_production_ready.py` → `PASS 12/12` | ✅ exit code 0 |
| `BENCHMARK_REPORT.md` điền đủ, có `reports/`, `benchmark-results/` và screenshot Part 7 | ✅ |

### A.6 Self-Test

Trước khi nộp, kiểm tra deployment:

```bash
# 1. Health check
curl https://your-app.railway.app/health

# 2. Authentication required
curl https://your-app.railway.app/ask
# Should return 401

# 3. With API key works
curl -H "X-API-Key: YOUR_KEY" https://your-app.railway.app/ask \
  -X POST -d '{"user_id":"test","question":"Hello"}'
# Should return 200

# 4. Rate limiting
for i in {1..15}; do 
  curl -H "X-API-Key: YOUR_KEY" https://your-app.railway.app/ask \
    -X POST -d '{"user_id":"test","question":"test"}'; 
done
# Should eventually return 429

# 5. Part 7 — eval quality gate (agent v2 đang chạy ở local)
cd 06-lab-complete/benchmark-observability/develop
python eval/run_eval.py --min-accuracy 1.0
# Should print: Quality gate ... ✅ PASS
```

> Lưu ý từ `README.md` mục 8: dùng bản tự kiểm ở CP6, **không dùng mục Self-Test này** — mục này gọi `GET /ask` nên ra 405 thay vì 401.

### A.7 Submission

**Submit your GitHub repository URL:**

```text
https://github.com/Mazzonthego/K5-L3A-DAY14-DoHoangMinh-2A202603507-Deployment-Benchmark-Observability.git
```

### A.8 Quick Tips

1. Test your public URL from a different device
2. Make sure repository is public or instructor has access
3. Include screenshots of working deployment
4. Write clear commit messages
5. Test all commands in DEPLOYMENT.md work
6. No secrets in code or commit history

### A.9 Need Help?

- Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- Review [CODE_LAB.md](CODE_LAB.md)
- Ask in office hours
- Post in discussion forum
