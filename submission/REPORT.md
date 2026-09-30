# Báo cáo cá nhân — K4-L3B Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Khi dẫn evidence, dùng đường dẫn tương đối, ví dụ `evidence/07-trace-waterfall.png`.

## 1. Thông tin học viên

- **Họ và tên:** Nguyễn Minh Ngọc
- **MSSV:** 2A202602530
- **Lớp:** K4-L3B
- **Repository URL:** https://github.com/nguyenminhngoc234it-gif/K4-L3-DAY13-NguyenMinhNgoc-2A202602530-Monitoring-LLMOps
- **Commit SHA cuối:**
- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1`
- **Tên project Langfuse cá nhân:** `day13-k4-l3b-2A202602530`

## 2. Evidence index

Điền đúng đường dẫn tới evidence thực tế. Có thể đổi tên hoặc dùng nhiều ảnh nếu cần.

| Evidence            | Đường dẫn                             |
| ------------------- | ------------------------------------- |
| Pytest cuối         | `evidence/01-pytest.png`              |
| Log validator       | `evidence/02-log-validator.png`       |
| Dashboard validator | `evidence/03-dashboard-validator.png` |
| Structured log      | `evidence/04-structured-log.png`      |
| PII redaction       | `evidence/05-pii-redaction.png`       |
| Trace list          | `evidence/06-trace-list.png`          |
| Trace waterfall     | `evidence/07-trace-waterfall.png`     |
| Trace metadata      | `evidence/08-trace-metadata.png`      |
| Prompt versions     | `evidence/09-prompt-versions.png`     |
| Prompt rollback     | `evidence/10-prompt-rollback.png`     |
| Dashboard runtime   | `evidence/11-dashboard-overview.png`  |
| Incident metric     | `evidence/12-incident-metric.png`     |
| Incident log        | `evidence/13-incident-log.png`        |
| Incident trace      | `evidence/14-incident-trace.png`      |

## 3. Kết quả kỹ thuật

| Nội dung                | Baseline  | Kết quả cuối    | Nhận xét                          |
| ----------------------- | --------- | --------------- | --------------------------------- |
| `validate_logs.py`      | 30/100    | 100/100         | Đạt CP1                           |
| `validate_dashboard.py` | 6/6       | 6/6             | Đạt CP2                           |
| `pytest`                | 22 passed | 27 passed       | Đạt                               |
| Số traces hợp lệ        |           | 10              | Đủ cây agent/retrieval/generation |
| Số PII leak             | Chưa đo   | 0               | Đạt                               |
| Latency P95 / TTFT P95  |           | 1414 ms / 52 ms | Cửa sổ dashboard 60 phút          |
| Retrieval success rate  |           | 100%            | 10 request CP2 sạch               |

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:** Middleware xóa context cũ ở đầu request, nhận header hợp lệ theo mẫu `req-<8-hex>` hoặc sinh ID mới từ UUID, bind vào `structlog.contextvars`, gán vào `request.state` và trả lại trong header `x-request-id`.
- **Các metadata được ghi vào structured log:** `user_id_hash` (SHA-256 rút gọn), `session_id`, `feature`, `model`, `env` và `correlation_id`; log kết quả còn có latency, TTFT, token, cost và quality score.
- **Cách bảo đảm PII được scrub trước khi ghi:** Processor `scrub_event` duyệt đệ quy toàn bộ event sau bước tạo exception/stack data và trước `JsonlFileProcessor`/`JSONRenderer`, che email, số điện thoại Việt Nam, CCCD và số thẻ.
- **Cách kiểm chứng kết quả:** Test unit và tích hợp gửi đủ bốn loại PII, kiểm tra response header/correlation ID/enrichment; `python scripts/validate_logs.py` đạt 100/100 với 0 PII leak. Baseline cũ được giữ cục bộ tại `data/logs.cp1-baseline.jsonl` và log sạch được tạo lại trước khi đo.

## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:** Chạy 10 request sạch với `user_id=cp2-student`, session `cp2-session-01..10`, sau đó kiểm tra Observations API v2 trong project cá nhân; cả 10 trace đều có đủ ba observation.
- **Cấu trúc root/retrieval/generation observations:** `lab-agent-run` (agent) có hai child là `retrieval` (retriever, preview đã scrub, document count) và `generation` (model, prompt link, token usage, cost, TTFT và preview đã scrub).
- **Cách nối trace với log:** `correlation_id` được ghi trong structured log và metadata của root, retrieval và generation để lọc đúng cùng một request.
- **Prompt name:** `day13-chat`
- **Version/label baseline:** v1 — `baseline`, `production` (trạng thái cuối sau rollback).
- **Version/label candidate:** v2 — `candidate`.
- **Trace ID của mỗi version:** baseline v1 `fba2008ad3292b50dc61bf81e828ca3f`; candidate v2 `ad2e3fe59bea7b85b5846a1704096bd9`; production khi promote v2 `46df7495d42e758c341cd91ecc740891`.
- **Cách promote và rollback `production`:** Chuyển `production` sang v2, chạy một request để ghi trace dùng v2, sau đó chuyển `production` về v1. API kiểm tra cuối trả `production=1`, `candidate=2`.

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:** Dashboard lấy `data/logs.jsonl`, cửa sổ 60 phút, refresh 30 giây và đúng sáu panel Latency, Traffic, Errors/Retrieval, Cost, Tokens, Quality. Evidence runtime: `evidence/11-dashboard-overview.svg`.
- **SLO và lý do chọn:** 99.5% request phải thành công và có latency tối đa 3000 ms trong cửa sổ 28 ngày; ngưỡng này bảo vệ trải nghiệm chờ và khớp threshold của panel latency.
- **Cách tính error budget:** 100% - 99.5% = 0.5%. Với 10,000 request, tối đa 50 request được phép lỗi hoặc chậm hơn 3000 ms.
- **Ba alert và runbook tương ứng:** `HighLatencyP95` (>3000 ms/5m), `HighErrorRate` (>2%/5m), `LowRetrievalSuccess` (<90%/5m); cả ba gửi Slack `#k4-l3b-alerts`, có severity, owner và runbook tại `docs/alerts.md`.

> Ví dụ cách viết error budget: "SLO 99.5% trong 28 ngày nghĩa là error budget 0.5%. Nếu workload có 10,000 request thì tối đa 50 request được phép lỗi hoặc chậm hơn ngưỡng SLO."

## 7. Điều tra challenge

- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1`.
- **Khoảng thời gian điều tra:** request challenge từ `2026-09-30T05:18:17Z` đến `2026-09-30T05:18:32Z` (12:18:17–12:18:32 ICT); cửa sổ response dùng trong evidence metric là `05:18:22.031862Z`–`05:18:32.680789Z`.
- **Triệu chứng từ metrics:** 5/5 request trả HTTP 200 và retrieval success 100%, nhưng latency server-side có P50 `2654 ms`, P95/P99 `4072 ms`, trung bình `2937.8 ms`. P95 vượt cả ngưỡng challenge `2000 ms` lẫn ngưỡng dashboard/SLO `3000 ms`; so với baseline CP2 P95 `478 ms`, độ trễ tăng khoảng `8.5x`. Evidence: `evidence/12-incident-metric.png`.
- **Log line và correlation ID liên quan:** `data/logs.jsonl:72`, event `response_sent`, `correlation_id=req-8112ed89`, session `k4-l3b-challenge-s02`, feature `monitoring`, `latency_ms=4072`, `ttft_ms=50`, `tool_name=retrieval`, `tool_success=true`. Đây là request có latency server-side cao nhất trong run. Evidence: `evidence/13-incident-log.png`.
- **Trace ID và span gây ảnh hưởng:** trace `3fd3f266763efe4978fbb5b256373371` có root `lab-agent-run=4.073 s`; span `retrieval=2.502 s` chiếm phần lớn thời gian, trong khi `generation=0.151 s`. Trace được truy vấn từ project Langfuse cá nhân qua Observations API v2 và nối với log bằng cùng session/correlation ID. Evidence: `evidence/14-incident-trace.png`.
- **Root cause:** incident `rag_slow` làm tầng retrieval chờ thêm `2.5 s` (`time.sleep(2.5)` trong `app/mock_rag.py`). Metric cho thấy latency tăng nhưng không tăng lỗi; log khoanh đúng request chậm; trace xác nhận retrieval là span bất thường còn generation vẫn nhanh. Ba nguồn evidence cùng chỉ về retrieval latency.
- **Fix action:** đã chạy `python scripts/inject_incident.py --disable`, xác nhận `/health` trả `rag_slow=false`, rồi chạy lại cùng challenge. Lượt warm-cache cuối có 5 latency server-side `153, 153, 153, 153, 156 ms`, P95 `156 ms`, thấp hơn ngưỡng challenge `2000 ms`.
- **Preventive measure:** giữ alert `HighLatencyP95`, bổ sung span-level alert cho retrieval > `2000 ms`, timeout/circuit breaker cho vector store, theo dõi riêng cold prompt fetch, và thêm regression test bật/tắt `rag_slow` để xác nhận retrieval latency trở về baseline sau mitigation.

> Gợi ý cách viết ngắn, không thay cho evidence thực tế: "Metric cho thấy `[latency/error/cost/quality]` bất thường trong `[khoảng thời gian]`. Log line `[event]` có `correlation_id=[...]` đại diện cho request bị ảnh hưởng. Trace cùng `correlation_id` cho thấy span `[retrieval/generation/prompt/tool]` có dấu hiệu `[chậm/lỗi/token tăng]`. Root cause là `[nguyên nhân suy ra từ evidence]`. Fix action là `[hành động khôi phục]`; preventive measure là `[alert/runbook/test/guardrail để ngăn tái diễn]`."

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:** chọn request có latency cao nhất trong đúng cửa sổ challenge làm mẫu điều tra, thay vì mở trace ngẫu nhiên; cách này giữ chuỗi bằng chứng có thể tái lập.
- **Một lỗi/blocker đã gặp:** Traces API legacy trả HTTP 410 vì organization mới; ảnh giao diện Langfuse cũng không thể chụp tự động do browser surface của môi trường không khả dụng.
- **Cách tìm nguyên nhân và xử lý:** chuyển sang Observations API v2 chính thức của SDK Langfuse 4.15.6, lọc theo session của log đã chọn, rồi kết xuất waterfall từ observation thật; evidence ghi rõ nguồn API, project và không chứa secret.
- **Cách hiểu luồng Metrics → Logs → Traces:** metrics phát hiện P95 vượt ngưỡng và xác định cửa sổ; logs chọn request `req-8112ed89`; trace tương ứng phân rã thời gian và chỉ ra retrieval 2.502 s là span gây ảnh hưởng.
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:** SLO biến latency thành điều kiện pass/fail; trace giúp tách retrieval delay khỏi generation/prompt; rollback hoặc disable chỉ được chọn sau khi evidence xác nhận đúng thành phần gây lỗi.
- **Điều quan trọng nhất đã học:** HTTP 200 và retrieval success 100% không đồng nghĩa hệ thống khỏe; tail latency vẫn có thể phá SLO và cần metric, log, trace để chứng minh nguyên nhân.
- **Hạn chế hoặc phần chưa hoàn thành, nếu có:** evidence trace được lấy từ project cá nhân qua Langfuse Observations API v2 và trình bày thành waterfall cục bộ; chưa có screenshot trực tiếp từ Langfuse UI do trình duyệt tích hợp không khả dụng trong phiên chạy.

## 9. Checklist trước khi nộp

- [x] Kết quả và evidence thuộc commit SHA cuối.
- [x] Tất cả ảnh/output mở được bằng đường dẫn tương đối.
- [x] Incident evidence nối đúng metric → log → trace.
- [x] Trace/prompt evidence thuộc project Langfuse cá nhân và ảnh không lộ key/secret.
- [x] Repository chạy lại được theo README.
- [x] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác.
- [x] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs.
