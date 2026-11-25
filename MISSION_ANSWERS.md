#  Delivery Checklist — Day 14 Lab Submission

> **Student Name:** Đỗ Hoàng Minh


> **Student ID:** 2A202603507 

> **Date:** 25/11/2026

---

##  Submission Requirements

Submit a **GitHub repository** containing:

### 1. Mission Answers (40 points)

Create a file `MISSION_ANSWERS.md` with your answers to all exercises:

```markdown
# Day 14 Lab - Mission Answers

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns found
1. Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic.
2. Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé.
3. Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận.
...

{"question":"Hello","answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé.","model":"gpt-4o-mini"}

### Exercise 1.3: Comparison table
| Feature | Develop | Production | Why Important? |
|---|---|---|---|
| Config & secret | Hardcode key, DB URL (`app.py:17–18`); `localhost:8000`, `DEBUG=True` | Đọc env qua `config.py` (`HOST`, `PORT`, `OPENAI_API_KEY`, `AGENT_API_KEY`); có `.env.example` | Đổi config không rebuild; không lộ secret; chạy được trong container |
| Request / Response | Query `?question=Hello` → `{"answer": "..."}` | JSON body → `{"question", "answer", "model": "gpt-4o-mini"}` | Response có thông tin model, dễ trace và debug |
| Logging | `print()`, thậm chí log cả key (`app.py:33–34`) | `logger.info(json.dumps(...))`, không log secret | Log máy đọc được, an toàn khi up cloud |
| Health & shutdown | Không có endpoint, tắt đột ngột | `/health`, `/ready` (503), `SIGTERM` + `lifespan` | Nền tảng restart đúng lúc, không cắt ngang request |

## Part 2: Docker

### Exercise 2.1: Dockerfile questions
1. Base image: `python:3.11` (develop; production dùng `python:3.11-slim`).
2. Working directory: `/app`.
3. `COPY requirements.txt` trước `COPY . .` để tận dụng layer cache: đổi source code thì không phải cài lại dependencies → build nhanh hơn.
4. `CMD` là lệnh mặc định, bị override khi `docker run <image> <lệnh khác>`; `ENTRYPOINT` là lệnh cố định, chỉ đổi được bằng `--entrypoint`. Dùng cả hai: entrypoint cố định, cmd truyền args mặc định.

### Exercise 2.2: Build & run container

    docker build -f 02-docker/develop/Dockerfile -t my-agent:develop .   # build từ gốc repo
    docker run --rm -p 8000:8000 my-agent:develop
    curl -X POST "http://localhost:8000/ask?question=What is Docker?"

Kết quả: `HTTP 200`, `{"answer":"..."}`. Develop nhận `question` qua **query string** (gửi JSON → 422).

### Exercise 2.3: Multi-stage build & image size
- Stage 1 `builder`: cài dependencies (`python:3.11-slim`).
- Stage 2 `runtime`: chỉ copy artifact từ builder, tạo user non-root, có `HEALTHCHECK` → bỏ được compiler/cache pip nên image nhỏ hơn.
- Develop: **1,710 MB (~1.67 GB)** · Production: **240 MB** · Chênh lệch: **85.96%** (đo bằng `docker images`, không chép README).

### Exercise 2.4: Docker Compose stack
Sơ đồ service (network `internal`, chỉ nginx public):

    Client ──▶ nginx (:8080 → :80) ──▶ agent (:8000)
                                     ├── redis  (:6379)
                                     └── qdrant (:6333)

    touch 02-docker/production/.env.local
    docker compose -p k5-day14-docker up -d --build
    docker compose -p k5-day14-docker ps
    curl http://localhost:8080/health
    curl -X POST http://localhost:8080/ask -H "Content-Type: application/json" -d '{"question":"Explain microservices"}'
    docker compose -p k5-day14-docker logs agent
    docker compose -p k5-day14-docker down

Kết quả test qua Nginx:
- `GET /health` → `HTTP 200` · `{"status":"ok","version":"2.0.0",...}`
- `POST /ask` (JSON body) → `HTTP 200` · `{"answer":"Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic."}`
- `docker compose logs agent` thấy JSON log `{"event":"request","q_len":21}` và access log `POST /ask HTTP/1.1 200 OK`.



## Part 3: Cloud Deployment

### Exercise 3.1: Railway deployment (nền tảng chính)
- **Platform:** Railway · **Source deploy:** agent Part 6 trong `06-lab-complete/` (config: `06-lab-complete/railway.toml`, builder `DOCKERFILE`, healthcheck `/health`).
- **URL:** `https://<your-app>.railway.app` ← điền sau khi chạy `railway domain`.
- **Các bước:** `railway login --browserless` → `cd 06-lab-complete && railway init` → `railway variables set AGENT_API_KEY=… REDIS_URL=… RATE_LIMIT_PER_MINUTE=10 DAILY_BUDGET_USD=10 ENVIRONMENT=production` → `railway up` → `railway domain`.
- **Redis:** tạo Redis (plugin) trong project Railway, lấy URL dạng `redis://default:pass@host:port` rồi đặt vào `REDIS_URL`; phải đảm bảo `/ready` trả 200 trước khi chụp ảnh.
- **Screenshot:** [dashboard](screenshots/dashboard.png) · [running](screenshots/running.png) · [test](screenshots/test.png).

Tự kiểm tra (4 lệnh, mỗi lệnh chỉ in mã HTTP → không lộ key):

    BASE=https://<your-app>.railway.app
    AGENT_API_KEY=<key-đã-đặt>
    curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/health"     # 200
    curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ready"      # 200
    curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
      -H 'Content-Type: application/json' -d '{"question":"Hello"}'   # 401
    curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
      -H 'Content-Type: application/json' -H "X-API-Key: $AGENT_API_KEY" \
      -d '{"question":"Hello"}'                                        # 200

### So sánh `railway.toml` với `render.yaml`
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
Pipeline CI/CD trong `cloudbuild.yaml` (trigger khi push `main`): **test** (`pytest`, fail thì dừng) → **build** image Docker tag theo `$COMMIT_SHA` + `latest` và dùng layer cache → **push** lên Container Registry (`gcr.io/$PROJECT_ID/ai-agent`) → **deploy** Cloud Run `gcloud run deploy` với `--image` theo commit, `--allow-unauthenticated`, `--min-instances=1 --max-instances=10`, secret lấy từ Secret Manager. File `service.yaml` mô tả service (Knative): scale `minScale=1`/`maxScale=10`, `containerConcurrency=80`, `timeoutSeconds=60`, env `ENVIRONMENT/PORT`, secret `OPENAI_API_KEY` + `AGENT_API_KEY` từ Secret Manager, liveness probe `/health` và startup probe `/ready`.

## Part 4: API Security

### Exercise 4.1: API key authentication (develop)
Key được kiểm tra trong dependency `verify_api_key()` (`APIKeyHeader(name="X-API-Key", auto_error=False)`) inject vào `POST /ask` qua `Depends`. Thiếu key → **401**, sai key → **403**; rotate key bằng cách đổi env `AGENT_API_KEY` (không sửa code).

Không có key → 401:
    curl -i -X POST http://localhost:8000/ask -H "Content-Type: application/json" -d '{"question":"Hello"}'
    HTTP/1.1 401 Unauthorized
    {"detail":"Missing API key. Include header: X-API-Key: <your-key>"}

Có key → 200:
    curl -i -X POST http://localhost:8000/ask -H "X-API-Key: secret-key-123" \
      -H "Content-Type: application/json" -d '{"question":"Hello"}'
    HTTP/1.1 200 OK
    {"question":"Hello","answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé."}

### Exercise 4.2: JWT authentication (production)
Flow: `POST /auth/token` (student / demo123) → JWT hết hạn sau 60 phút → gửi trong header `Authorization: Bearer <token>`; server verify chữ ký HS256, không cần tra DB mỗi request. Token sai → `{"detail":"Invalid token."}`. Dùng token trong 4.3.

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

### Exercise 4.3: Rate limiting
Thuật toán **Sliding Window Counter** bằng `deque` timestamp trong 60 giây; user `student` giới hạn **10 request/phút**, admin (`teacher`) dùng bucket riêng **100 request/phút**. Vượt giới hạn → **429** kèm `Retry-After`. Tự chạy 15 request:

    TOKEN="<token lấy ở 4.2>"
    for i in $(seq 1 15); do
      curl -s -o /dev/null -w "$i -> %{http_code}\n" -X POST http://localhost:8000/ask \
        -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
        -d "{\"question\":\"Test $i\"}"
    done
    1 -> 200  ...  10 -> 200
    11 -> 429  12 -> 429  13 -> 429  14 -> 429  15 -> 429

### Exercise 4.4: Cost guard implementation
`check_budget()` chạy **trước** khi gọi LLM, `record_usage()` ghi token **sau** khi trả lời: `cost = input/1000 × $0.00015 + output/1000 × $0.0006`. Giới hạn **$1/ngày/user** và **$10/ngày toàn hệ thống**; vượt → **402** (global → 503), cảnh báo ở 80% budget. Production lưu số liệu trong **Redis** theo key ngày để chạy nhiều instance/restart không mất state (bản demo dùng dict RAM).

**Vì sao cần cả hai:** rate limit bảo vệ **tốc độ** (chống spam/DoS, quá tải hệ thống), cost guard bảo vệ **tiền** (ngay cả request hợp lệ, đều đặn cũng có thể tiêu sạch budget). Limit 10 req/phút mà mỗi req đắt thì vẫn cháy tiền; ngược lại budget còn nhưng burst 1000 req vẫn làm sập service.

## Part 5: Scaling & Reliability

### Exercise 5.1: Health checks — liveness vs readiness

- **Liveness `/health`**: kiểm tra process còn sống. Trong bản develop, endpoint trả `status`, `uptime_seconds`, `version`, `environment` và kiểm tra RAM qua `psutil`; RAM trên 90% thì `status=degraded`. Trong bản production, endpoint kiểm tra `redis.ping()`, trả HTTP **200** khi process sống (`status` có thể là `degraded` nếu Redis lỗi). Nếu liveness trả lỗi, Docker/Kubernetes có thể restart container.
- **Readiness `/ready`**: kiểm tra instance đã sẵn sàng nhận traffic hay chưa. Bản develop trả **503** trong lúc startup/shutdown; bản production gọi `redis.ping()` và trả **503 `Redis not available`** nếu Redis không kết nối được. Load balancer chỉ route traffic tới instance readiness trả 200.
- **Tách hai probe để tránh restart loop**: nếu `/health` phụ thuộc Redis, chỉ cần Redis lỗi cũng làm container bị restart liên tục dù ứng dụng vẫn hoạt động. `/health` đánh giá process; `/ready` đánh giá dependency và khả năng phục vụ traffic.

Kết quả thực tế trên stack 3 instance:

    $ curl -i http://localhost:8080/health
    HTTP/1.1 200 OK
    X-Served-By: 172.19.0.3:8000
    {"status":"ok","instance_id":"instance-ee1e3b","uptime_seconds":68.6,"storage":"redis","redis_connected":true}

    $ curl -i http://localhost:8080/ready
    HTTP/1.1 200 OK
    X-Served-By: 172.19.0.4:8000
    {"ready":true,"instance":"instance-d56414"}

### Exercise 5.2: Graceful shutdown

Bản develop đăng ký `signal.signal(signal.SIGTERM, handle_sigterm)` và `SIGINT`. Khi nhận `SIGTERM`, uvicorn ngừng nhận request mới, middleware đếm `_in_flight_requests`, còn `lifespan` chờ các request đang chạy hoàn thành tối đa **30 giây** trước khi đóng kết nối và thoát (`timeout_graceful_shutdown=30`). Vì vậy request đang xử lý không bị cắt ngang khi deploy, restart hoặc scale-down.

Test thực tế bằng `docker stop` (gửi `SIGTERM`):

    $ docker stop -t 10 k5-day14-scaling-agent-2
    agent-2  | INFO:     Shutting down
    agent-2  | INFO:     Waiting for application shutdown.
    agent-2  | INFO:app:Instance instance-465eab shutting down
    agent-2  | INFO:     Application shutdown complete.
    agent-2  | INFO:     Finished server process [1]

### Exercise 5.3: Stateless design

Bản production không lưu conversation trong RAM. `save_session()` dùng `_redis.setex(f"session:{session_id}", 3600, json_data)` để lưu session/history trong Redis với TTL 1 giờ; `load_session()` đọc lại từ Redis, nên mọi agent instance đều thấy cùng trạng thái. `history` được giới hạn 20 message (10 lượt). Chỉ khi Redis không kết nối được mới fallback sang dict trong RAM — trường hợp này **không scale-safe** và được log cảnh báo.

Anti-pattern khi lưu state trong RAM: request của user có thể rơi vào instance A rồi instance B; instance B không có `history` của user. Giải pháp Redis giữ state ở ngoài process, nhờ vậy request có thể phục vụ bởi bất kỳ instance nào và state còn nguyên sau restart.

Bằng chứng state thực sự nằm trong Redis:

    $ docker compose -p k5-day14-scaling exec redis redis-cli --scan --pattern 'session:*'
    session:1fe1901a-41ea-4e81-9a33-53b4c499e962
    session:9f276698-266a-431a-96b2-2d684185a0eb
    session:demo

### Exercise 5.4: Load balancing với 3 instance

    touch 05-scaling-reliability/production/.env.local
    cd 05-scaling-reliability/production
    docker compose -p k5-day14-scaling up -d --build --scale agent=3
    docker compose -p k5-day14-scaling ps

Kết quả:

    NAME                       STATUS                   PORTS
    k5-day14-scaling-agent-1   Up ... (healthy)         8000/tcp
    k5-day14-scaling-agent-2   Up ... (healthy)         8000/tcp
    k5-day14-scaling-agent-3   Up ... (healthy)         8000/tcp
    k5-day14-scaling-nginx-1   Up ...                   0.0.0.0:8080->80/tcp
    k5-day14-scaling-redis-1   Up ... (healthy)         6379/tcp

Luồng request: client → **Nginx :8080** → `upstream agent_cluster` → 3 agent `:8000`. Docker DNS (`127.0.0.11`) trả về các IP của service `agent`; Nginx phân tán round-robin. Header `X-Served-By` cho biết instance đã xử lý, còn trường `served_by` trong JSON response là ID logic của instance.

    $ curl -i -X POST http://localhost:8080/chat \
        -H "Content-Type: application/json" \
        -d '{"question":"Request 1","session_id":"demo"}'
    HTTP/1.1 200 OK
    X-Served-By: 172.19.0.4:8000
    {"session_id":"demo","question":"Request 1","answer":"Đây là câu trả lời từ AI agent (mock)...","turn":3,"served_by":"instance-d56414","storage":"redis"}

Gửi 10 request cùng session để kiểm tra phân tán tải:

    Request  1 -> HTTP 200, served_by=instance-ee1e3b
    Request  2 -> HTTP 200, served_by=instance-d56414
    Request  3 -> HTTP 200, served_by=instance-ee1e3b
    Request  4 -> HTTP 200, served_by=instance-4a2803
    Request  5 -> HTTP 200, served_by=instance-d56414
    Request  6 -> HTTP 200, served_by=instance-ee1e3b
    Request  7 -> HTTP 200, served_by=instance-4a2803
    Request  8 -> HTTP 200, served_by=instance-d56414
    Request  9 -> HTTP 200, served_by=instance-ee1e3b
    Request 10 -> HTTP 200, served_by=instance-4a2803
    Instances used: {'instance-ee1e3b', 'instance-4a2803', 'instance-d56414'}

**Failover test:** dừng `agent-2`, request tiếp vẫn trả **HTTP 200** và được instance khác phục vụ (`served_by=instance-ee1e3b`). Nginx tự thử upstream tiếp theo nhờ `proxy_next_upstream error timeout http_503`; history của cùng session vẫn còn đủ **12 message** trong Redis. Như vậy khi một instance ngừng hoạt động, service không bị gián đoạn và không mất state.

### Exercise 5.5: Test stateless

    cd 05-scaling-reliability/production
    python test_stateless.py

> Trên Windows PowerShell, dùng `New-Item -ItemType File .env.local -Force` thay cho `touch`, và đặt `$env:PYTHONIOENCODING='utf-8'` trước khi chạy script để in được tiếng Việt.

Kết quả thực tế:

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

**Kết luận:** 5 request được load balance qua 3 agent khác nhau nhưng vẫn có đủ 10 message (5 câu hỏi + 5 câu trả lời) vì state nằm trong Redis, không nằm trong RAM của từng container. Sau failover, cùng session vẫn có 12 message. Đây là bằng chứng ứng dụng **stateless** và có thể scale ngang an toàn.

Dọn stack sau khi test:

    docker compose -p k5-day14-scaling down
```

---

### 2. Full Source Code - Lab 06 Complete (60 points)

Your final production-ready agent, built from the skeleton in `06-lab-complete/` (xem mục **Hợp đồng** trong [06-lab-complete/README.md](06-lab-complete/README.md)):

```
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

**Requirements:**
-  **`python check_production_ready.py` báo `PASS 12/12`** (chạy đầy đủ, có Docker) — dán phần "📋 Checklist Deliverable" của output vào `MISSION_ANSWERS.md`
-  All code runs without errors
-  Multi-stage Dockerfile (image < 500 MB)
-  API key authentication
-  Rate limiting (10 req/min)
-  Cost guard ($10/month)
-  Health + readiness checks
-  Graceful shutdown
-  Stateless design (Redis)
-  No hardcoded secrets

---

### 3. Service Domain Link

Create a file `DEPLOYMENT.md` with your deployed service information:

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

---

### 4. Benchmark & Observability Report — Part 7 (20 points)

Copy [06-lab-complete/benchmark-observability/BENCHMARK_REPORT_TEMPLATE.md](06-lab-complete/benchmark-observability/BENCHMARK_REPORT_TEMPLATE.md) thành `BENCHMARK_REPORT.md` và điền đầy đủ, kèm các file bằng chứng:

```
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

**Requirements:**
-  Load test ở 4 mức concurrency, có p50/p95/p99 và đối chiếu SLO
-  Eval v1 vs v2, sửa knowledge base để v2 đạt 100% không regression
-  Dashboard Grafana có tải, 1 trace chậm + 1 trace lỗi trong Jaeger
-  Ít nhất 2 alert firing, ghi lại thời gian phát hiện
-  Số liệu trong report khớp với file JSON/CSV

> **Cách tính điểm:** tổng thô 120 (40 + 60 + 20), quy đổi về thang 100.

---

## Part 6: Final Project — output `check_production_ready.py`

> **Trạng thái:** đã hoàn thiện agent trong `06-lab-complete/` (config từ env, `/health` + `/ready`, API key 401, rate limit 429, cost guard 402, log JSON, SIGTERM, Dockerfile multi-stage, compose + Redis, `railway.toml`).
> **Việc còn lại:** chạy bản đầy đủ (cần Docker) rồi dán output vào đây:

    cd 06-lab-complete
    python check_production_ready.py
    # Kết quả mong đợi: PASS 12/12

*(Phần "📋 Checklist Deliverable" của output sẽ được dán vào đây sau khi chạy bản đầy đủ.)*

---

## Part 7: Benchmark & Observability — Bước 1 (local)

Báo cáo đầy đủ: **[`BENCHMARK_REPORT.md`](BENCHMARK_REPORT.md)** · Dữ liệu gốc: `reports/` (10 file JSON).

### 7.1 Đọc metrics của agent
- **Counter** (chỉ tăng): `http_requests_total{method="POST",route="/ask",status="200"}`, `llm_tokens_total{model="mock-llm-small",type="input"}`, `llm_cost_usd_total{...}`.
- **Gauge** (lên xuống): `agent_in_flight_requests` (số request đang xử lý), `agent_info{version="v2",model="mock-llm-small"}`.
- **Histogram** (chia bucket để tính percentile): `http_request_duration_seconds_bucket{le="0.2",...}`, `llm_request_duration_seconds_bucket`.
- **Vì sao label `route` dùng `route.path` (template) chứ không dùng URL thật?** Nếu dùng `request.url.path`, bot quét `/wp-admin`, `/.env`, `/a1b2c3`… sẽ tạo hàng nghìn time series → cardinality bùng nổ, Prometheus hết RAM. Dùng template + `unmatched` giữ số series ổn định.
- **Metric thêm (nhiệm vụ):** `agent_question_length_chars` (Histogram, buckets 20/50/100/200/500/1000/2000) đo phân bố độ dài câu hỏi. Dùng Histogram chứ không label `length=...` vì độ dài có vô số giá trị → cardinality bùng nổ.

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

- **2 câu sai ban đầu của v2:** `scaling-03` (thiếu `cpu`, `memory`, `custom metrics`) và `security-02` (thiếu `token`, `hết hạn`, `chữ ký`) → đã thêm entry HPA + JWT vào `KNOWLEDGE_BASE` trong `develop/utils/mock_llm.py`. Lưu ý: keyword có dấu (`hết hạn`, `chữ ký`) phải viết đúng dấu, nếu không chỉ khớp 1/3 keyword.
- **Cost/câu đúng** của v2 thấp hơn v1 ~11× dù tổng cost cao hơn → đánh đổi chất lượng/cost có lợi; đổi lại token/câu gần gấp đôi và p95 latency +30 ms (thêm bước retrieval).
- **Quality gate chặn merge:** `run_eval.py` trả **exit code 1** khi accuracy < `--min-accuracy` hoặc có regression. Job `.github/workflows/eval.yml` chạy eval mỗi Pull Request với `--min-accuracy 0.85` → exit ≠ 0 ⇒ job fail ⇒ PR không merge được.

### 7.4–7.7 Observability stack (CP8)
> ⚠️ **Chưa làm — cần Docker:** Grafana/Jaeger/Prometheus/Locust, ảnh trace chậm + trace lỗi + alert firing, và benchmark scale 1 vs 3 instance. Chi tiết bước làm: `STEP.md` mục CP8.

---

## AI log / Ghi chú

| Mốc | Việc đã làm | Ghi chú |
|---|---|---|
| CP0–CP1 | Setup WSL2 + Docker, chạy develop/production Part 1 | Bản develop nhận `question` qua **query**, production nhận JSON |
| CP2 | Build image, đo size, bật Compose stack | Docker Hub trả 429 → lấy `python:3.11-slim` từ mirror ECR; cổng 80 bị chiếm → dùng `8080:80` |
| CP3 | Test 401 / 200 / 429 + giải thích cost guard | Token JWT đã che trước khi dán |
| CP4 | Health/readiness, stateless, scale 3 instance, `test_stateless.py` | Dùng `-p k5-day14-scaling` để không trùng project |
| CP5 | Sửa TODO trong `06-lab-complete/` | Chạy `check_production_ready.py` tới `PASS 12/12` (cần Docker) |
| CP6 | `railway.toml` + `DEPLOYMENT.md` + Part 3 (so sánh Railway/Render, Cloud Run) | Chưa deploy — cần `railway login` bằng tài khoản của bạn |
| CP7 | Load test 4 mức + 3 mức `MOCK_SLOW_RATE`, eval v1/v2/v2-fixed (23/23), metric `agent_question_length_chars`, CI `eval.yml` | Chạy trong WSL2 với `.venv` Python 3.14 |
| CP8 | Observability stack + ảnh + nộp | **Còn lại** — cần Docker chạy được |

---

##  Pre-Submission Checklist

- [ ] Repository is public (or instructor has access)
- [ ] `MISSION_ANSWERS.md` completed with all exercises
- [ ] `DEPLOYMENT.md` has working public URL
- [ ] All source code in `app/` directory
- [ ] `README.md` has clear setup instructions
- [ ] No `.env` file committed (only `.env.example`)
- [ ] No hardcoded secrets in code
- [ ] Public URL is accessible and working
- [ ] Screenshots included in `screenshots/` folder
- [ ] Repository has clear commit history
- [ ] `python check_production_ready.py` → `PASS 12/12`
- [ ] `BENCHMARK_REPORT.md` điền đủ, có `reports/`, `benchmark-results/` và screenshot Part 7

---

##  Self-Test

Before submitting, verify your deployment:

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

---

##  Submission

**Submit your GitHub repository URL:**

```
https://github.com/your-username/day14-agent-deployment
```

---

##  Quick Tips

1.  Test your public URL from a different device
2.  Make sure repository is public or instructor has access
3.  Include screenshots of working deployment
4.  Write clear commit messages
5.  Test all commands in DEPLOYMENT.md work
6.  No secrets in code or commit history

---

##  Need Help?

- Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- Review [CODE_LAB.md](CODE_LAB.md)
- Ask in office hours
- Post in discussion forum

---

**Good luck! **
