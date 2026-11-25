# Benchmark & Observability Report — Day 14

> Mọi con số lấy từ report JSON / CSV thật trong `reports/` và `benchmark-results/` (không ước lượng).
> Mục 1–3: CP7 (đo local, `develop/`). Mục 4–6: CP8 (stack Docker đầy đủ, `production/`).
> Ảnh bằng chứng: `screenshots/`.

**Họ tên:** Đỗ Hoàng Minh (2A202603507)
**Ngày chạy:** 25/11/2026
**Môi trường:** Windows 11 + WSL2 Ubuntu (Python 3.14, Docker Engine 29.9.3), agent `develop/` chạy local bằng `uvicorn` 1 worker, mock LLM `mock-llm-small`.
**Môi trường CP8:** Docker Compose (`k5-day14-observability`): Nginx 1.28-alpine → agent (FastAPI + OpenTelemetry) ×1–3, Prometheus v3.16.0, Grafana 13.2.4, Jaeger 2.23.0, Locust 2.47.0.

---

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng này |
|---|---|---|
| p95 latency `/ask` | ≤ 500 ms | Mock LLM có latency nền ~150–200 ms; 500 ms chừa biên cho jitter nhưng vẫn bắt được tail latency (>1 s) |
| Error rate `/ask` | ≤ 2% | `MOCK_ERROR_RATE=0.01` mô phỏng lỗi upstream ~1%; ngưỡng 2% để không báo động vì lỗi ngẫu nhiên |
| Accuracy trên golden dataset | ≥ 100% (quality gate) | Golden dataset cố định 23 câu, có `expected_keywords` → 100% là mục tiêu kiểm chứng tự động; dưới 100% = regression so với baseline |

---

## 2. Benchmark hiện năng (develop, `load_test.py`)

### 2.1 Concurrency vs latency (agent v2)

Mỗi mức: 300 request, `MOCK_SLOW_RATE=0.03` (mặc định) — file `reports/load_v2_c*.json`.

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---|---|---|---|---|---|---|
| 1 | 4.36 | 190.2 | 221.1 | 1697.1 | 0.33% | ✅ PASS |
| 10 | 43.38 | 189.6 | 218.7 | 1696.3 | 0.67% | ✅ PASS |
| 50 | 109.63 | 202.9 | 280.5 | 1721.0 | 1.33% | ✅ PASS |
| 100 | 54.87 | 882.3 | 4322.1 | 4801.6 | 1.00% | ❌ FAIL (p95 vượt 500 ms) |

**Nhận xét:** RPS **không** tăng tuyến tính. Từ c=1 → c=50 throughput tăng 4,36 → 109,63 req/s (≈25×), nhưng từ c=50 → c=100 RPS **giảm** còn 54,87 req/s và p95 nhảy từ 280 ms lên 4.322 ms (vượt SLO, exit code 1). Lý do: agent `develop/` chạy **1 worker uvicorn** trên máy lab, mỗi request đều chờ `await asyncio.sleep()` mô phỏng LLM; khi concurrency vượt khả năng xử lý của event loop, request phải xếp hàng → độ trễ tích tụ (queuing delay), RPS bị giới hạn bởi worker. Muốn tuyến tính cần scale **ngang** (nhiều instance/container) — đó là lý do Part 7 Bước 2 scale 1 → 3 instance qua Nginx. p50 gần như không đổi (190 → 203 ms) cho tới c=50, chỉ khi quá tải mới tăng mạnh: dấu hiệu hàng đợi, không phải code chậm.

### 2.2 Tail latency

Cùng cấu hình: 300 request, concurrency 20 — file `reports/load_v2_slow_*.json`.

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|
| 0 | 191.2 | 219.3 | 236.2 |
| 0.03 (mặc định) | 214.8 | 229.8 | 1658.3 |
| 0.1 | 318.7 | 1693.9 | 1713.0 |

**Nhận xét:** `avg` tăng rất nhẹ (191 → 319 ms, +67%) trong khi **p99 tăng vọt** (236 → 1.713 ms, +625%) và p95 ở mức 0,1 đã vượt SLO (1.693 ms > 500 ms → FAIL). Nguyên nhân: request chậm chỉ chiếm 3–10% tổng số nên kéo nhẹ phép tính trung bình, nhưng percentile p95/p99 xếp theo thứ tự nên phản ánh trực tiếp "người dùng tệ nhất chờ bao lâu". Vì vậy **SLO phải đặt theo percentile (p95/p99), không theo average** — nếu đặt theo avg, agent vẫn "xanh" trong khi 1 người trong 100 chờ gần 2 giây.

---

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

Golden dataset 23 câu (`eval/golden_dataset.jsonl`), điều kiện đúng: câu trả lời chứa ≥ 60% `expected_keywords`.

| Chỉ số | Agent v1 | Agent v2 | Agent v2 (sau khi sửa KB) |
|---|---|---|---|
| Accuracy | 4.3% (1/23) | 91.3% (21/23) | **100% (23/23)** |
| Avg tokens / câu | 56.5 | 108.8 | 117.3 |
| Tổng cost (USD) | 0.000396 | 0.000758 | 0.000822 |
| Cost / câu đúng (USD) | 0.00039615 | 0.00003607 | **0.00003573** |
| p50 / p95 latency (ms) | 155.1 / 185.4 | 189.1 / 214.6 | 187.4 / 216.6 |
| Quality gate | ❌ FAIL (≥80%) | ✅ PASS (≥80%) | ✅ PASS (≥100%, 0 regression) |

**Những câu v2 trả lời sai ban đầu và cách bạn sửa:**

| ID | Keyword bị thiếu | Bạn đã sửa gì |
|---|---|---|
| `scaling-03` | `cpu`, `memory`, `custom metrics` | Thêm entry `["hpa","kubernetes","autoscal","horizontal pod","k8s"]` vào `KNOWLEDGE_BASE` trong `develop/utils/mock_llm.py`: HPA scale số Pod dựa trên cpu/memory/custom metrics (request/s từ Prometheus Adapter) |
| `security-02` | `token`, `hết hạn`, `chữ ký` | Thêm entry `["jwt","json web token"]`: JWT là token có chữ ký số, xác minh không cần DB, có thời gian hết hạn (`exp`) khác API key. **Lưu ý:** phải viết đúng dấu tiếng Việt (`hết hạn`, `chữ ký`) — bản đầu viết không dấu nên chỉ khớp 1/3 keyword (score 0.33) |

**Nhận xét về trade-off chất lượng / chi phí / latency giữa v1 và v2:**
v2 có retrieval nên accuracy nhảy từ 4,3% → 91,3% (không có regression), nhưng đổi lại token/câu gần gấp đôi (56,5 → 108,8) và latency p95 tăng ~30 ms (185,4 → 214,6 ms) do thêm bước tìm tài liệu + prompt dài hơn. Về **chi phí**, `cost / câu đúng` của v2 thấp hơn v1 khoảng **11×** (0,00003607 vs 0,00039615 USD) — dù tổng cost tăng, mỗi câu trả lời đúng vẫn rẻ hơn nhiều, nên đây là đánh đổi có lợi. Sau khi bổ sung KB, v2 đạt 100% và cost/câu đúng còn giảm nhẹ (0,00003573 USD).

**Quality gate trong CI:** `run_eval.py` trả **exit code 1** khi accuracy < `--min-accuracy` hoặc có câu regression (baseline đúng → hiện tại sai). Job `.github/workflows/eval.yml` chạy eval trên mỗi Pull Request với `--min-accuracy 0.85`: exit code ≠ 0 ⇒ job fail ⇒ **PR không merge được**. File: `.github/workflows/eval.yml`.

---

## 4. Observability stack (production)

**Cách chạy (đã thực hiện):**

```bash
cd 06-lab-complete/benchmark-observability/production
docker compose -p k5-day14-observability up -d --build --scale agent=1
docker compose -p k5-day14-observability up -d --scale agent=3      # scale ngang
```

| Service | URL | Ghi chú thực tế |
|---|---|---|
| Agent (qua Nginx) | http://localhost:8080 | Header `X-API-Key: day14-lab-key`; `X-Served-By` cho biết instance phục vụ |
| Grafana | http://localhost:3000 | Dashboard "Day 14 — AI Agent Overview" (admin/admin) |
| Prometheus | http://localhost:9090 | *Status → Target health*, *Alerts* |
| Jaeger | http://localhost:16686 | Service `observable-agent` |
| Locust | http://localhost:8089 | Web UI; phần benchmark dùng chế độ headless để ghi CSV |

> **Lưu ý sửa lỗi:** Dockerfile gốc của `production/` cài package bằng `pip install --user` vào `/home/agent/.local`, nhưng user `agent` có home `/app` và `PYTHONPATH=/app` nên Python **không tìm thấy site-packages** → container restart liên tục với `ModuleNotFoundError: No module named 'uvicorn'`. Đã đổi sang pattern venv (`/opt/venv`) giống Dockerfile của `06-lab-complete/`.

### 4.1 Screenshot

| Ảnh | Nội dung thực tế |
|---|---|
| [`screenshots/grafana-dashboard.png`](screenshots/grafana-dashboard.png) | Dashboard khi **scale 3 instance đang có tải**: Traffic **31,3 req/s**, Error rate **1,12%**, p95 **293,66 ms**, In-flight **10**, Instances up **3**, Cost **$2,5027/h**; hàng "Instances": req/s theo từng instance (12,49 / 12,33 / 12,47), Model `mock-llm-small`, Agent version `v2` |
| [`screenshots/jaeger-slow-trace.png`](screenshots/jaeger-slow-trace.png) | Trace chậm `5c7037095de1df7e78b73db9bee68124`: `POST /ask` **1,7 s** → `agent.run` 1.725,8 ms → `agent.retrieve_context` **26,9 ms** + `chat mock-llm-small` **1.698,6 ms (98,2%)** |
| [`screenshots/jaeger-error-trace.png`](screenshots/jaeger-error-trace.png) | Trace lỗi `c739e067d2c92d08ade9b254b07b4ac8`: `POST /ask` → **503**, span `chat mock-llm-small` có tag `error=true` + event `exception` (`exception.type`, `exception.message`) |
| [`screenshots/prometheus-alert-firing.png`](screenshots/prometheus-alert-firing.png) | Trang **Alerts** của Prometheus: **3 alert đang FIRING** — `AgentHighErrorRate`, `AgentHighLatencyP95`, `LLMCostBurnRateHigh` (`AgentInstanceDown` = INACTIVE) |

Ảnh phụ trợ: `grafana-chaos.png` (lúc lỗi + chậm), `grafana-v1-no-alert.png` (thí nghiệm E), `prometheus-alert-instance-down.png` (thí nghiệm D), `prometheus-targets.png`, `jaeger-longest-first.png`.

### 4.2 Thí nghiệm "phá hệ thống"

Đổi cấu hình qua file `.env` trong `production/` rồi `docker compose -p k5-day14-observability up -d`; trong suốt các thí nghiệm giữ Locust chạy ~30 user.

| # | Thay đổi | Alert nào firing | Thời gian từ lúc đổi → firing | Panel nào phản ánh rõ nhất | Số liệu quan sát |
|---|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` | `AgentHighErrorRate` (critical) | **86 s** (rule có `for: 1m`) | Golden Signals → **Error rate** | Error rate **20,64%** (SLO < 5%), kèm trace lỗi trong Jaeger |
| B | thêm `MOCK_SLOW_RATE=0.3` | `AgentHighLatencyP95` (warning) | **144 s** (rule có `for: 2m`) | Latency & Traffic → **p95/p99** | p95 **1,907 s** (SLO < 1 s) |
| C | `LLM_MODEL=mock-llm-large` | `LLMCostBurnRateHigh` (warning) | đã **firing sẵn** ở cấu hình mặc định; sau khi đổi model: cost **$4,38/h → $17,59/h**, LLM p95 **0,198 s → 0,484 s** | 🤖 LLM → **Cost burn rate** | Giá `mock-llm-large` đắt **16,7×** và latency chậm **2,5×** so với `mock-llm-small` |
| D | `docker pause` agent-1 | `AgentInstanceDown` (critical) | **46 s** (rule có `for: 30s`) | 🧩 Instances → **Instances up** | `up{job="agent"}` của instance bị pause = 0; sau `docker unpause` → 1 lại (Prometheus tự hồi phục) |
| E | `AGENT_VERSION=v1` | **Không có alert nào firing** (API trả về `0` alert active) | — | 🧩 Instances → bảng **Agent version** đổi `v2 → v1` | Token/request rơi từ **92** (v2, có retrieval) xuống **37** (v1); câu hỏi "Kubernetes HPA scale dựa trên chỉ số nào?" v1 trả lời **sai** ("Đây là câu trả lời từ AI agent (mock)…") trong khi metric hạ tầng vẫn xanh |

**Vì sao `docker pause` mà không `docker stop`?** Prometheus tìm agent bằng DNS (`dns_sd_configs`). Container bị `stop` sẽ **biến mất khỏi DNS** → Prometheus coi như target không còn tồn tại (không phải "down") → `up` không bao giờ bằng 0 → **không có alert**. Container bị `pause` vẫn còn trong DNS nhưng không trả lời → `up == 0` → alert bắn. (Đã kiểm chứng: sau `docker unpause`, `up` trở lại 1 trong ~15 s.)

**Thí nghiệm E không làm alert nào firing. Bạn sẽ phát hiện loại sự cố này trong production bằng cách nào?**
Đây là **sự cố chất lượng**, không phải sự cố hạ tầng: metric latency/error/cost đều bình thường nhưng câu trả lời sai. Cách phát hiện:
1. **Eval/quality monitoring định kỳ** (đúng những gì đã làm ở CP7): chạy `eval/run_eval.py` trên golden dataset → accuracy 23/23; đưa vào CI (`.github/workflows/eval.yml`) để chặn merge, và chạy định kỳ (cron) trên production để phát hiện regression của model/KB.
2. **Metric chất lượng nghiệp vụ** export ra Prometheus: `answer_quality_score` (LLM-as-judge / groundedness), `refusal_rate`, `retrieval_hit_ratio`, `tokens_per_request` bất thường. Ở thí nghiệm E, `tokens_per_request` giảm từ 92 → 37 và `retrieval hit ratio` về 0 → đó là tín hiệu **hậu quả** có thể cảnh báo (agent không còn dùng KB).
3. **Canary + phản hồi người dùng**: traffic 5% trên model mới, so sánh điểm chất lượng và tỉ lệ like/dislike, CSAT theo phiên bản; alert khi điểm giảm quá ngưỡng.
4. **Synthetic check định kỳ** (giống `/health` nhưng hỏi câu có đáp án biết) → phát hiện sớm KB/model bị đổi nhầm.

### 4.3 Debug bằng trace

**Trace chậm** (`screenshots/jaeger-slow-trace.png`):

- `trace_id`: `5c7037095de1df7e78b73db9bee68124`
- Tổng thời gian: **1.729,3 ms** (span `POST /ask` trong Jaeger; log `http_request` ghi `ms = 1728.6`, status 200) — waterfall hiển thị 1,7 s
- Phân rã span (tính từ `reports/jaeger/trace_slow.json`):

  | Span | Thời gian | Tỉ lệ |
  |---|---|---|
  | `POST /ask` | 1.729,3 ms | 100% |
  | `agent.run` | 1.725,8 ms | 99,8% |
  | **`chat mock-llm-small`** | **1.698,6 ms** | **98,2%** |
  | `agent.retrieve_context` | 26,9 ms | 1,6% |

  → **Bottleneck nằm ở lời gọi LLM, không phải code của mình** (đúng như `MOCK_SLOW_RATE` mô phỏng "slow upstream")
- Dòng log tương ứng (grep theo `trace_id`):

```json
{"ts": "2026-11-25T15:07:27.733424+00:00", "level": "INFO", "service": "observable-agent", "instance": "ab234c7cd5b2", "event": "llm_call", "trace_id": "5c7037095de1df7e78b73db9bee68124", "span_id": "57dba2d6b67d8aa4", "request_id": "fa5baabf1950", "model": "mock-llm-small", "agent_version": "v2", "input_tokens": 95, "output_tokens": 55, "cost_usd": 0.000047, "llm_ms": 1697.6}
{"ts": "2026-11-25T15:07:27.733915+00:00", "level": "INFO", "service": "observable-agent", "instance": "ab234c7cd5b2", "event": "http_request", "trace_id": "5c7037095de1df7e78b73db9bee68124", "span_id": "57dba2d6b67d8aa4", "request_id": "fa5baabf1950", "method": "POST", "route": "/ask", "status": 200, "ms": 1728.6}
```

**Trace lỗi** (`screenshots/jaeger-error-trace.png`):

- `trace_id`: `c739e067d2c92d08ade9b254b07b4ac8`
- Tổng thời gian: **100,7 ms** (span `POST /ask`, `otel.status_code = ERROR`; log `http_request` ghi `ms = 100.1`, status **503**)
- Span lỗi: **`chat mock-llm-small` = 83,0 ms (82,5%)** với tag `error = true`, `otel.status_code = ERROR`, `error.type = upstream_unavailable`; event `exception` gồm `exception.type = utils.mock_llm.LLMError` và `exception.message = Upstream LLM error: 503 Service Unavailable (mock)` + stack trace trỏ đúng `/app/utils/mock_llm.py:199`
- Span `agent.retrieve_context` chỉ 15,2 ms → lỗi xuất phát từ **upstream LLM**, không phải từ retrieval
- Log tương ứng:

```json
{"ts": "2026-11-25T15:08:04.057890+00:00", "level": "INFO", "service": "observable-agent", "instance": "68d682b289f7", "event": "llm_error", "trace_id": "c739e067d2c92d08ade9b254b07b4ac8", "span_id": "0e26b49b4f97e5ce", "request_id": "f9b62dd3943b", "error": "Upstream LLM error: 503 Service Unavailable (mock)"}
```

> Nhờ `trace_id` có trong **mọi** dòng log JSON, ta đi từ log → Jaeger để tìm trace, và từ trace → log để đọc nguyên nhân — hai chiều đều khớp `trace_id`.

**Bằng chứng máy:** `reports/jaeger/trace_summary.json`, `reports/jaeger/trace_slow.json`, `reports/jaeger/trace_error.json`, `reports/jaeger/agent_logs.jsonl` (log JSON thật của agent trong stack production).

### 4.4 Đọc dashboard Grafana (Exercise 7.4)

| Câu hỏi | Trả lời (số liệu thật lúc scale 3, đang tải) |
|---|---|
| **p95 vs avg** | avg **236,9 ms**, p50 **180,6 ms**, p95 **297,1 ms**, p99 **1.820 s**. p99 gấp ~7,7× avg → phần lớn request rất nhanh, một nhóm nhỏ (3% `MOCK_SLOW_RATE`) kéo p99 lên ~1,8 s. Nếu chỉ nhìn avg sẽ tưởng hệ thống rất ổn. |
| **req/s theo instance** | 12,49 / 12,33 / 12,47 req/s cho 3 instance (tổng 37,3 req/s) → Nginx chia tải gần như **đều tuyệt đối** (lệch < 1,5%). Header `X-Served-By` trả về IP instance đã phục vụ, ví dụ `172.20.0.2:8000`. |
| **input vs output token/s** | input **2.945 token/s**, output **1.580 token/s** (tỉ lệ ~1,87). Input lớn hơn vì prompt của v2 có thêm **context truy xuất từ KB** (95 input token/câu so với 37 của v1). Tổng token/s ≈ 4.525 → ở 37,3 req/s là ~121 token/request. |
| **Vì sao `/metrics` trả 404?** | Nginx có `location = /metrics { return 404; }` → endpoint metrics **không public ra ngoài** vì lộ thông tin hệ thống (route, lưu lượng, số instance). Prometheus scrape **trực tiếp trong mạng nội bộ** (`agent:8000/metrics` qua DNS service discovery) nên vẫn lấy được: kiểm chứng `curl localhost:8080/metrics → 404` còn `GET http://localhost:8000/metrics` trong container agent → **200**. |

### 4.5 Dữ liệu CSV gốc của các lần chạy chaos

Lưu ý: mỗi lần chạy Locust chaos **kéo dài qua lúc đổi cấu hình**, nên CSV chứa cả giai đoạn trước/sau thay đổi — số liệu chuẩn để kết luận là **ảnh chụp Prometheus theo thời điểm** ở bảng mục 4.2. CSV ở đây để đối chiếu/tái lập.

| File | Kịch bản | `/ask` requests | Failures | p50 | avg | p95 | p99 | max |
|---|---|---|---|---|---|---|---|---|
| `benchmark-results/scale_1_stats.csv` | scale 1, cấu hình mặc định | 6.968 | 72 (1,03%) | 200 ms | 271,1 ms | 620 ms | 1.700 ms | 2.464,8 ms |
| `benchmark-results/scale_3_stats.csv` | scale 3, cấu hình mặc định | 7.068 | 83 (1,17%) | 190 ms | 246,1 ms | 280 ms | 1.700 ms | 2.162,7 ms |
| `benchmark-results/chaos_run_stats.csv` | A+B: error 20% + slow 30% | 21.167 | 2.063 (9,75%) | 190 ms | 314,9 ms | 1.700 ms | 1.700 ms | 3.183,7 ms |
| `benchmark-results/chaosD_run_stats.csv` | D: `docker pause` 1/3 instance | 16.679 | 815 (4,89%) | 180 ms | 241,0 ms | 1.700 ms | **10.000 ms** | **10.004,2 ms** |
| `benchmark-results/cpu_1_stats.csv` | đo CPU khi scale 1 | 3.309 | 27 | 190 ms | 245,6 ms | 1.700 ms | 1.700 ms | 1.730,1 ms |
| `benchmark-results/cpu_3_stats.csv` | đo CPU khi scale 3 | 3.302 | 25 | 190 ms | 226,9 ms | 1.700 ms | 1.700 ms | 1.733,2 ms |

**Điểm đáng chú ý của kịch bản D:** pause 1 trong 3 instance khiến **p99 của `/ask` nhảy lên 10 s** và `/health` có request treo tới **53,9 s** (Nginx vẫn định tuyến tới instance bị pause cho tới khi hết timeout) → đây chính là loại sự cố "một replica chết" mà `AgentInstanceDown` bắt được, và cho thấy **Nginx cần retry/timeout ngắn hơn** nếu muốn che giấu sự cố một replica.

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

Lệnh (chạy trong `production/`, CSV ghi vào `benchmark-results/`):

```bash
docker compose -p k5-day14-observability up -d --scale agent=1
docker compose -p k5-day14-observability run --rm --no-deps locust \
  -f /mnt/locust/locustfile.py --host http://nginx \
  --headless -u 100 -r 10 -t 2m --csv /mnt/results/scale_1

docker compose -p k5-day14-observability up -d --scale agent=3     # chờ ~20s cho DNS/Nginx/Prometheus thấy instance mới
docker compose -p k5-day14-observability run --rm --no-deps locust \
  -f /mnt/locust/locustfile.py --host http://nginx \
  --headless -u 100 -r 10 -t 2m --csv /mnt/results/scale_3
```

Số liệu lấy từ `benchmark-results/scale_1_stats.csv` và `scale_3_stats.csv` (dòng `POST /ask`):

| Số instance | Request | RPS | p50 (ms) | avg (ms) | p95 (ms) | p99 (ms) | max (ms) | Failures | Error rate |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 6.968 | **58,62** | 200 | 271,1 | **620** | 1700 | 2464,8 | 72 | 1,03% |
| 3 | 7.068 | **59,55** | 190 | 246,1 | **280** | 1700 | 2162,7 | 83 | 1,17% |

*(Tổng cả `/ask` + `/health`: RPS 64,41 → 65,52; Locust trả exit code 1 do có lỗi 503 — đây là lỗi mô phỏng `MOCK_ERROR_RATE=0.01`, không phải lỗi hệ thống.)*

**Giải thích kết quả: scale có cải thiện p95 không? Nút thắt nằm ở đâu?**

- **p95 cải thiện rõ**: 620 ms → 280 ms (**−55%**), p50 200 → 190 ms, avg 271 → 246 ms. Lý do: chia 3 instance ⇒ mỗi instance phục vụ ~1/3 số request ⇒ **độ dài hàng đợi trong hàng đợi của từng instance giảm**, latency phục vụ giảm.
- **RPS gần như không đổi**: 58,62 → 59,55 req/s (**+1,6%**). Đây **không phải** vì server quá tải, mà vì **Locust là mô hình closed-loop**: mỗi user chờ `response + wait_time (0,5–2 s, trung bình 1,25 s)` rồi mới gọi lần sau. Với 100 user, throughput tối đa ≈ `100 / (latency + 1,25 s)` ≈ 64–67 req/s — đúng bằng RPS đo được (64,4 và 65,5). Muốn đo năng lực tối đa của server phải dùng **open-loop** (rate cố định) hoặc tăng số user.
- **Server không phải nút thắt**: `docker stats` lúc scale=1 cho thấy agent dùng **7,5% CPU** (giới hạn của container là 0,5 CPU), scale=3 mỗi instance ~6–7% (một mẫu đầu ngắn 33%), RAM ~55–64 MB / 256 MB. Còn rất nhiều headroom → scale thêm không tăng throughput.
- **p99 không đổi (1700 ms cả 2 lần)**: p99 đến từ **slow path của mock LLM** (`MOCK_SLOW_RATE` → ngủ 1,5 s cố định), **không phải** do xếp hàng. Đây là ví dụ điển hình: scale giải quyết được phần đuôi do *queueing* nhưng không giải quyết được phần đuôi do *upstream dependency* → muốn cải thiện p99 phải xử lý phía LLM (timeout, retry, cache, model nhẹ hơn).
- **Error rate gần như không đổi** (1,03% → 1,17%, khác biệt nằm trong nhiễu) và khớp đúng `MOCK_ERROR_RATE=0.01` ⇒ scale không làm tăng lỗi.

---

## 6. Kết luận

**3 điều học được về benchmark & observability:**

1. **SLO phải đặt theo percentile, không theo average.** avg 236,9 ms nhìn có vẻ đẹp, nhưng p99 là 1.820 s (7,7× avg) và p95 ở mức `MOCK_SLOW_RATE=0.1` là 1.694 s — người dùng tệ nhất chờ gần 2 giây trong khi đồng thời "trung bình" vẫn xanh. Tương tự, alert error rate dùng `for: 1m`/`for: 2m` để lọc spike ngắn, và chính thời gian đó (86 s cho error alert, 144 s cho latency alert) là độ trễ có chủ đích của hệ thống cảnh báo.
2. **Tracing trả lời được câu hỏi "chậm ở đâu" mà metric không trả lời được.** Metric cho biết p95 = 1,7 s; trace cho biết **span `chat mock-llm-small` chiếm 98,2%** trong khi `agent.retrieve_context` chỉ 26,9 ms → biết ngay đừng tối ưu code, hãy xử lý upstream. Kết hợp với log JSON có `trace_id` là điều kiện tối thiểu để điều tra sự cố từ "người dùng báo chậm" đến tận dòng log cụ thể.
3. **Benchmark phải biết mình đang đo gì, và observability hạ tầng không phát hiện được lỗi chất lượng.** Scale 3 instance không làm tăng RPS vì tải bị giới hạn bởi mô hình user closed-loop của Locust (không phải bởi server) — nếu không kiểm tra CPU ta sẽ kết luận sai là "scale không ăn". Ngược lại, thí nghiệm E (`AGENT_VERSION=v1`) cho thấy câu trả lời sai hoàn toàn mà **mọi metric hạ tầng vẫn xanh** → cần thêm lớp eval/quality monitoring, không thể chỉ dựa vào dashboard.

**Nếu đưa agent này lên production thật, sẽ thêm metric / alert nào nữa?**

| Metric / Alert | Vì sao |
|---|---|
| `llm_upstream_timeout_total`, `llm_upstream_retries_total` + alert khi retry > 5% | Lỗi LLM upstream là nguyên nhân gốc của trace lỗi (503); cần biết lỗi đến từ timeout, 5xx hay circuit breaker |
| `llm_cost_usd_total` theo **user/tenant** + alert `cost_per_user` vượt hạn mức | `LLMCostBurnRateHigh` chỉ nhìn tổng; một user gọi vòng lặp cũng làm cháy budget chung |
| `answer_quality_score` (LLM-as-judge), `refusal_rate`, `groundedness` | Bắt lỗi chất lượng mà metric hạ tầng không thấy (thí nghiệm E) |
| `retrieval_hit_ratio`, `tokens_per_request` + alert khi đột biến | Phát hiện KB bị hỏng / model đổi nhầm (v1: 37 token/câu vs v2: 92) |
| `http_request_duration_seconds` **theo tenant** (cardinality thấp, whitelist) | Theo dõi SLO từng khách hàng lớn, nhưng phải giới hạn số label để không bùng nổ |
| `queue_depth` / `in_flight_requests` + alert khi vượt ngưỡng | Báo hiệu sắp quá tải **trước khi** p95 vượt SLO |
| Synthetic check từ bên ngoài (không đi qua LB) + alert | Bắt được lỗi 504 do Nginx/LB mà metric của agent không đếm (như README mục 2.6 nhận xét) |
| `database_pool_size` / `redis_latency_seconds` | SLO phụ thuộc Redis (rate limit, cost guard) — Redis chậm sẽ kéo latency toàn hệ thống |
| SLO burn-rate alert (`error_budget_burn_rate`) | Cảnh báo theo tốc độ tiêu hết error budget thay vì ngưỡng tức thời — phù hợp hơn cho on-call |
| `trace_sampling_rate` + metric đếm số trace bị drop | Trace 100% rất tốn; cần biết mình đang bỏ sót bao nhiêu trace |
