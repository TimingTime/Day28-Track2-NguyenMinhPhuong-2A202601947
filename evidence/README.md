# Danh mục bằng chứng thực tế

Thư mục này chỉ chứa dữ liệu thực sự thu được từ các dịch vụ. Bản hiện tại chưa
có đủ bằng chứng live; trạng thái tổng hợp nằm trong [REPORT.md](../REPORT.md).

| Điểm | File theo integration matrix | Nguồn cần thu |
|---|---|---|
| IP01 | `ip01-kafka-consume.json` | J1: consume sự kiện và Kafka headers |
| IP02 | `ip02-airflow-run.json` | J1: DAG run, task states và asset event |
| IP03 | `ip03-delta-history.json` | CLI evidence: lịch sử commit và time travel |
| IP04 | `ip04-feast-online.json` | J1: online entity có dữ liệu sau materialization |
| IP05 | `ip05-qdrant-search.json` | CLI evidence: truy vấn vector có ID và score |
| IP06 | `ip06-mlflow-release.json` | J3: phiên bản, provenance và alias |
| IP07 | `ip07-vllm-identity.json` | `/version`, `/v1/models`, metrics của vLLM thật |
| IP08 | `ip08-gateway.json` | Gateway rate-limit test: response và request ID |
| IP09 | `ip09-prometheus-targets.json` | Targets, rules và alerts từ Prometheus |
| IP09 | `ip09-grafana-dashboards.json` | Dashboard đã được provision trong Grafana |
| IP10 | `ip10-trace.json` | Backend trace: trace ID và các span cần có |

Có 10 điểm kết nối nhưng **11 tên file IP** vì IP09 yêu cầu hai file.
`.gitignore` cho phép các file này được đưa vào Git sau khi rà nội dung.
Không thêm file giả hoặc chỉ có trạng thái `PASS` thay cho payload thực tế.

## Trình tự tiếp tục khi stack sẵn sàng

Trên máy nộp bài, trước tiên đặt các biến cổng/URL trong
[REPORT.md](../REPORT.md) để tránh các stack khác đang dùng cổng mặc định.

```text
docker compose --parallel 1 --env-file ports.template --profile full up -d --build --wait
docker compose --env-file ports.template --profile full ps
uv run lab28 topics
uv run lab28 index --source file
uv run lab28 release
uv run lab28 seed --via-gateway
uv run lab28 inspect
uv run lab28 ready
uv run pytest integration-tests/test_j1_golden_path.py -m "not gpu and not langsmith" -q
uv run pytest integration-tests/test_j2_idempotent_replay.py -q
uv run pytest integration-tests -m "not gpu and not langsmith" -q
uv run lab28 evidence
uv run lab28 integration
uv run python load-tests/run_profile.py --url http://localhost:18080 --requests 200 --workers 8
```

`lab28 evidence` không tự thu được mọi điểm; các integration test tạo những file
cần quan sát từ ngoài ứng dụng. CLI có thể ghi kết quả probe thất bại; nội dung
file phải được kiểm tra trước khi ghi nhận điểm kết nối là đã đạt.

Chỉ chạy các test GPU khi vLLM thật đã sẵn sàng. Theo runbook, cần thêm tải
`/api/v1/ask` có warm-up/corpus/concurrency và hồ sơ sự cố/phục hồi để hoàn thành
demo. Lệnh load profile có sẵn chỉ đo `/ready`.
