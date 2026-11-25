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

### Exercise 3.1: Railway deployment
- URL: https://your-app.railway.app
- Screenshot: [Link to screenshot in repo]

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

### Exercise 5.1-5.5: Implementation notes
[Your explanations and test results]
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
