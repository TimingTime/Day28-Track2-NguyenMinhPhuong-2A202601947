# Bằng chứng Day 28

Các file dưới đây chứa payload thu từ dịch vụ thật. Kết quả, timestamp, phạm vi
kiểm thử và giới hạn tài nguyên được giải thích trong [REPORT.md](../REPORT.md).
Có **11 file IP cho 10 điểm kết nối**, vì IP09 có hai file.

| Điểm | File | Nguồn và nội dung |
|---|---|---|
| IP01 | [ip01-kafka-consume.json](ip01-kafka-consume.json) | Kafka record của demo cuối: partition, offset, key, headers, payload |
| IP02 | [ip02-airflow-run.json](ip02-airflow-run.json) | Airflow REST: DAG success, task states, asset events |
| IP03 | [ip03-delta-history.json](ip03-delta-history.json) | Delta transaction log, MERGE metrics và time travel |
| IP04 | [ip04-feast-online.json](ip04-feast-online.json) | Online row và PRESENT statuses của entity demo |
| IP05 | [ip05-qdrant-search.json](ip05-qdrant-search.json) | Query thật: collection, document IDs và scores |
| IP06 | [ip06-mlflow-release.json](ip06-mlflow-release.json) | Snapshot J3 promotion/rollback; release đang phục vụ được ghi riêng trong runtime report |
| IP07 | [ip07-vllm-identity.json](ip07-vllm-identity.json) | `/version`, model ID và metric family `vllm:` của server GPU thật |
| IP08 | [ip08-gateway.json](ip08-gateway.json) | HTTP 200/429, request IDs và counter rate limit |
| IP09 | [ip09-prometheus-targets.json](ip09-prometheus-targets.json) | Prometheus targets và rules |
| IP09 | [ip09-grafana-dashboards.json](ip09-grafana-dashboards.json) | Grafana dashboard và datasource đã provision |
| IP10 | [ip10-trace.json](ip10-trace.json) | Trace cuối: 35 spans, đủ 11 tên bắt buộc, 4 service thật và không có error span |

Bằng chứng bổ sung trong [reports/runtime](../reports/runtime/):

- `happy-path.json`, `final-trace.json`: sự kiện, DAG, Delta, release, câu trả lời
  và raw trace. Batch và GPU chạy theo pha để vừa RAM; không tính là full-suite PASS.
- `trace-with-startup-errors.json`, `happy-path-before-clean-trace.json`: giữ
  trace/demo trước có lỗi khởi động; không xóa error span để làm đẹp kết quả.
- `recovery.json`, `kafka-migration.json`: bản tin lỗi/DLQ, replay có hai bản trên
  Kafka nhưng một hàng Delta, và offsets trước/sau chuyển volume bằng nhau.
- `langsmith.json`: project, run IDs đọc từ LangSmith và số span exporter đã gửi.
- `ask-load*.json`, `ask-bottleneck*.json`: phép đo hỏi đáp và audit/trace tương ứng.
  File có `cold-entity` dùng entity chưa có feature, nên response degraded.
- `gitops/`: baseline, drift/self-heal, rollout hai replica và Git revert về một replica.
- `live-suite.*`: 56 test không cần GPU/LangSmith đã đạt; `full-suite*` giữ cả
  lần timeout và lần gián đoạn. Không cộng các lần chạy dở thành kết quả toàn bộ suite.
- `gpu-langsmith-suite.*`: tám test J3/J4 GPU và LangSmith đạt sau bản sửa Envoy;
  `gpu-langsmith-before-gateway-fix.*` giữ lỗi health routing phát hiện trước đó.
- `runtime-final.json`: lần thu snapshot sau demo gặp timeout và Docker Engine
  HTTP 500. Không xác nhận runtime vẫn healthy lúc bàn giao; các IP giữ timestamp
  của lần thu thành công tương ứng.

`integration-report.json` là probe của CLI, không thay thế bằng chứng bên ngoài
process. Điểm probe không phải điểm rubric. Các snapshot có thể thuộc những lần
chạy khác nhau; dùng trace ID, DAG run ID và timestamp để đối chiếu.

Để chạy lại, đọc [cấu hình máy nộp bài](../docs/local-runtime.md), đặt URL bằng
`scripts/local-environment.ps1`, khởi động dịch vụ rồi chạy các kiểm thử gốc.
Thu `lab28 evidence --out .lab28/recollected-evidence` trước khi chọn các snapshot
cần cập nhật; CLI không tự thu được tất cả IP và có thể ghi đè bằng chứng J3/J5
bằng probe ngắn hơn. `.env`, database, model cache và `.lab28/` không được đưa vào Git.
