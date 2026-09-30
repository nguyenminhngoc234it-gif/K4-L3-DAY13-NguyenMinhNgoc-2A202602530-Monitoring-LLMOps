# Alert và Runbook

Mỗi alert phải dựa trên triệu chứng người dùng hoặc SLO, không dựa trực tiếp vào tên implementation nội bộ.

## Alert mẫu để tham khảo

Ví dụ dưới đây minh họa mức độ cụ thể cần có. Học viên không cần copy nguyên, nhưng ba alert trong bài nộp nên rõ ràng tương tự: điều kiện là gì, kéo dài bao lâu, ảnh hưởng tới user ra sao và người trực cần kiểm tra gì trước.

- Tên: `HighLatencyP95`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: latency P95 của `response_sent.latency_ms`
- Điều kiện và thời gian duy trì: `p95(latency_ms) > 3000ms` trong 5 phút
- Ảnh hưởng tới người dùng: người dùng phải chờ lâu hơn trước khi nhận câu trả lời
- Ba bước kiểm tra đầu tiên:
  1. Mở dashboard latency để xác nhận P95/P99 và khoảng thời gian tăng.
  2. Lọc `data/logs.jsonl` trong khoảng đó, lấy một `correlation_id` có `latency_ms` cao.
  3. Mở trace cùng `correlation_id` trên Langfuse, so sánh các span chính để xác định bước nào bất thường.
- Mitigation tạm thời: dựa trên evidence thực tế để rollback prompt, khôi phục cấu hình liên quan, tắt practice scenario hoặc giảm tải khi demo.
- Owner: `student-<MSSV>`

## Alert 1: High Latency P95

- Tên: `HighLatencyP95`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: P95 của `response_sent.latency_ms`; ngưỡng SLO là 3000 ms.
- Điều kiện và thời gian duy trì: `p95(latency_ms) > 3000ms` liên tục 5 phút.
- Ảnh hưởng tới người dùng: nhóm request chậm phải chờ quá lâu mới nhận được câu trả lời.
- Ba bước kiểm tra đầu tiên:
  1. Xác nhận P50/P95/P99 và TTFT P95 trên panel Latency trong đúng khoảng cảnh báo.
  2. Lọc các event `response_sent` có `latency_ms > 3000`, rồi chọn một `correlation_id` đại diện.
  3. Mở trace cùng `correlation_id`, so sánh thời gian của `retrieval` và `generation` để xác định bước chậm.
- Mitigation tạm thời: rollback prompt nếu regression gắn với version mới; nếu retrieval chậm thì khôi phục cấu hình hoặc dependency retrieval, đồng thời giảm tải nếu cần.
- Owner: `student-2A202602530`

## Alert 2: High Error Rate

- Tên: `HighErrorRate`
- Severity: `critical`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: tỷ lệ `request_failed / request_received`; guardrail tối đa 2%.
- Điều kiện và thời gian duy trì: error rate lớn hơn 2% liên tục 5 phút.
- Ảnh hưởng tới người dùng: request không trả được câu trả lời thành công.
- Ba bước kiểm tra đầu tiên:
  1. Xác nhận error rate và breakdown `error_type` trên panel Errors.
  2. Lọc event `request_failed`, nhóm theo `error_type` và lấy một `correlation_id` đại diện.
  3. Mở trace tương ứng, kiểm tra observation lỗi và trạng thái dependency tại bước đó.
- Mitigation tạm thời: tắt practice incident nếu đang bật; rollback thay đổi gần nhất hoặc chuyển về dependency/cấu hình ổn định dựa trên span lỗi.
- Owner: `student-2A202602530`

## Alert 3: Low Retrieval Success

- Tên: `LowRetrievalSuccess`
- Severity: `critical`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: tỷ lệ thành công của tool `retrieval`; guardrail tối thiểu 90%.
- Điều kiện và thời gian duy trì: retrieval success dưới 90% liên tục 5 phút.
- Ảnh hưởng tới người dùng: câu trả lời thiếu context hoặc request thất bại do không lấy được tài liệu.
- Ba bước kiểm tra đầu tiên:
  1. Xác nhận retrieval success và error breakdown trên panel Errors.
  2. Lọc log có `tool_name="retrieval"` và `tool_success=false`, rồi lấy một `correlation_id`.
  3. Mở trace tương ứng để kiểm tra observation `retrieval`, thời lượng, lỗi và số tài liệu trả về.
- Mitigation tạm thời: khôi phục vector store/cấu hình retrieval ổn định; nếu hệ thống cho phép thì dùng fallback an toàn và thông báo câu trả lời có thể thiếu context.
- Owner: `student-2A202602530`
