# Benchmark & Observability Report — Day 14

> Mọi con số lấy từ report JSON / CSV thật trong `reports/` (không ước lượng).
> Mục 1–3: CP7 (đo local, `develop/`). Mục 4–6: CP8 (stack Docker, `production/`) — **chưa làm, xem ghi chú**.

**Họ tên:** Đỗ Hoàng Minh (2A202603507)
**Ngày chạy:** 25/11/2026
**Môi trường:** Windows 11 + WSL2 Ubuntu (Python 3.14, Docker Engine 29.9.3), agent `develop/` chạy local bằng `uvicorn` 1 worker, mock LLM `mock-llm-small`.

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

> ⚠️ **Chưa làm — làm ở CP8** (cần Docker: `docker compose -p k5-day14-observability up -d --build --scale agent=1`).

### 4.1 Screenshot

- [ ] Dashboard Grafana khi đang có tải (thấy rõ Golden Signals)
- [ ] Một trace chậm trong Jaeger (thấy span nào chiếm thời gian)
- [ ] Một trace lỗi trong Jaeger (có event `exception`)
- [ ] Trang Alerts của Prometheus với **≥ 2 alert đang firing**

### 4.2 Thí nghiệm "phá hệ thống"

| # | Thay đổi | Alert nào firing | Thời gian từ lúc đổi → firing | Panel nào phản ánh rõ nhất |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` | | | |
| B | `MOCK_SLOW_RATE=0.3` | | | |
| C | `LLM_MODEL=mock-llm-large` | | | |
| D | `docker pause` 1 instance | | | |
| E | `AGENT_VERSION=v1` | | | |

**Thí nghiệm E không làm alert nào firing. Bạn sẽ phát hiện loại sự cố này trong production bằng cách nào?**

...

### 4.3 Debug bằng trace

- `trace_id`: ...
- Tổng thời gian: ... ms
- Span chiếm nhiều thời gian nhất: ... (... ms, ...%)
- Dòng log tương ứng (grep theo `trace_id`):

```json

```

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

> ⚠️ **Chưa làm — làm ở CP8.** Kết quả lấy từ `benchmark-results/scale_1_stats.csv` và `scale_3_stats.csv`.

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---|---|---|---|---|
| 1 | | | | | |
| 3 | | | | | |

**Giải thích kết quả:** Scale có cải thiện p95 không? Nút thắt nằm ở đâu?

...

---

## 6. Kết luận

- 3 điều bạn học được về benchmark & observability:
  1. ...
  2. ...
  3. ...
- Nếu đưa agent này lên production thật, bạn sẽ thêm metric / alert nào nữa?

...
