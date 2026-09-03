# Báo cáo Day 28 — Track 2

- Người nộp: **Nguyễn Minh Phương — 2A202601947**.
- Ngày thực hiện: **03/09/2026**.
- Hình thức: cá nhân, có hỗ trợ AI khi triển khai, kiểm tra và soạn tài liệu.
- Kết luận hiện tại: **hoàn thành phần mã và kiểm tra cục bộ; phần demo hệ thống
  thật đang chờ khởi động các dịch vụ Docker. Chưa xác nhận hoàn thành toàn bộ DoD.**

## 1. Phạm vi đã hoàn thành

| Hàm | Điểm kết nối | Kết quả triển khai |
|---|---|---|
| `event_headers` | IP01, IP10 | Luôn gửi khóa chống trùng dạng bytes; chỉ gửi trace khi có giá trị |
| `dedupe_latest` | IP03 | Một lần duyệt, một bản mới nhất mỗi khóa, tie-break bằng Event ID, sắp xếp khóa |
| `feast_online_request` | IP04 | Entity và bốn feature đúng contract; sao chép `FEATURE_REFS` thành list |
| `readiness_status` | IP07, IP08 | Lỗi bắt buộc ưu tiên hơn lỗi tùy chọn; hỗ trợ probe generator |

Các hàm nằm trong [integration_tasks.py](src/lab28_platform/integration_tasks.py).
Giữ nguyên các kiểm thử của khung bài và thêm sáu trường hợp kiểm tra biên trong
[test_integration_edge_cases.py](tests/test_integration_edge_cases.py).
Sửa thêm lỗi CLI xuất JSON bị cắt dở khi stdout dùng CP1252 trên Windows;
Unicode được escape trong JSON và được giữ nguyên khi đọc lại. Có một regression
test dùng đúng encoding này trong [test_cli_json_output.py](tests/test_cli_json_output.py).

## 2. Kết quả kiểm tra đã thực hiện

Output được thu bằng [collect_local_checks.py](scripts/collect_local_checks.py),
có mã thoát, thời gian chạy và timestamp trong
[summary.json](reports/local-checks/summary.json).

| Kiểm tra | Kết quả | Bằng chứng |
|---|---|---|
| Starter tests và fast suite | **94 passed** | [fast-suite.txt](reports/local-checks/fast-suite.txt) |
| Ruff | **PASS** | [ruff.txt](reports/local-checks/ruff.txt) |
| Ma trận IP01–IP10 | **245 checks passed** | [integration-matrix.txt](reports/local-checks/integration-matrix.txt) |
| Portability | **PASS** | [portability.txt](reports/local-checks/portability.txt) |
| Kubernetes/GitOps manifests | **PASS — kiểm tra tĩnh** | [manifests.txt](reports/local-checks/manifests.txt) |
| Integration test đánh dấu `offline` | **1 passed, 71 deselected** | [offline-integration.txt](reports/local-checks/offline-integration.txt) |
| Compose cơ bản và full | **PASS — kiểm tra cấu hình** | [basic](reports/local-checks/compose-basic.txt), [full](reports/local-checks/compose-full.txt) |
| Preflight | **local-standard** | [preflight.txt](reports/local-checks/preflight.txt) |

`offline` chỉ chọn một kiểm tra cấu hình; 71 test không được chọn không được
tính là đã đạt. Preflight xác nhận điều kiện máy và Docker, không chứng minh
các dịch vụ hoặc luồng dữ liệu đang hoạt động.

## 3. Môi trường và sự cố quan sát được

- Windows, Python **3.11.16**, uv **0.12.9**.
- Máy có 16 logical CPU, khoảng 15.3 GiB RAM; Docker nhận khoảng 7.4 GiB RAM.
- GPU phát hiện: NVIDIA GeForce RTX 4060 Laptop GPU, khoảng 8 GiB VRAM.
- Docker Engine **28.1.1**, Docker Compose **v2.35.1-desktop.1**.
- Docker Desktop ban đầu chưa chạy; đã khởi động và kiểm tra daemon thành công.
- Compose gặp `fatal error: concurrent map writes` khi tải đồng thời các image.
  Đã thử lại với `--parallel 1` và tải các image bằng lệnh Docker độc lập.
- Lần thử tiếp theo gặp `failed to read expected number of bytes: unexpected EOF`.
  Retry riêng Qdrant thành công; container Qdrant đã **healthy**. Các image còn
  lại và build API/Feast/Airflow vẫn đang được thực hiện ở snapshot này.
- Phát hiện các stack khác chiếm cổng 5000/8000/8080 và khoảng 4.5 GiB trong
  7.4 GiB RAM Docker. Day 28 dùng MLflow **15000**, API **18000**, gateway **18080**;
  không dùng kết quả health của ứng dụng khác làm bằng chứng cho lab.
- Kiểm thử gặp xung đột quyền thư mục tạm giữa các tài khoản Windows. Trình thu
  báo cáo dùng thư mục tạm mới trong `.lab28/test-runs/` cho từng lần chạy;
  kết quả cuối cùng là 94 test đạt.

## 4. Trạng thái các yêu cầu demo

| Yêu cầu | Trạng thái xác minh hiện tại |
|---|---|
| IP01: HTTP → Kafka | Contract/unit tests đạt; chưa có bản tin live được thu |
| IP02: Kafka → Airflow | Chưa có DAG run và asset event live |
| IP03: Spark → Delta | Logic chống trùng đạt; chưa có lịch sử MERGE/time travel live |
| IP04: Delta → Feast | Request contract đạt; chưa có online row được materialize live |
| IP05: Delta → Qdrant | Kiểm thử ID ổn định đạt; chưa có truy vấn vector live |
| IP06: MLflow Registry | Kiểm thử provenance đạt; chưa có promotion/rollback live |
| IP07: vLLM | Có GPU vật lý; **UNVERIFIED** đến khi endpoint thật được xác nhận |
| IP08: Envoy | Cấu hình đạt; chưa có bằng chứng response 200/429 live |
| IP09: Prometheus/Grafana | Cấu hình có trong repo; chưa có targets/dashboard live |
| IP10: Trace | Logic truyền header và span đạt; chưa có trace xuyên hệ thống |
| J1–J5 | **Chưa xác minh trên toàn bộ stack** |
| LangSmith | **UNVERIFIED** — chưa có credential được cung cấp |
| Kubernetes/Argo CD runtime | **UNVERIFIED** — chưa có Kubernetes context được cấu hình |
| Load profile P50/P95/P99 | **Chưa đo trên hệ thống đang phục vụ** |

[integration-report.json](integration-report.json) là output probe của CLI tại
thời điểm thu. Các điểm `unverified` hoặc `not_ready` cần được đọc cùng trạng
thái triển khai trên; không diễn giải điểm số probe thành điểm rubric của bài.

Không tạo các file IP rỗng để làm đủ số lượng. Danh mục bằng chứng cần thu và
các lệnh tiếp tục nằm trong [evidence/README.md](evidence/README.md).

## 5. Git, CI và các file nộp

- `.gitignore` giữ source, test, dữ liệu mẫu, cấu hình, `uv.lock`, báo cáo và các
  tên evidence mà ma trận yêu cầu. `evidence/` không còn bị bỏ qua toàn bộ.
- Môi trường ảo, `.lab28/`, cache, secret, database và trọng số mô hình được bỏ qua.
- `.dockerignore` loại môi trường cục bộ và secret khỏi build context.
- CI chạy starter tests và fast suite trên cả push, pull request và chạy thủ công.
  Bỏ gate yêu cầu bốn TODO còn trống trên push vì đây là bản bài làm đã triển khai.
- Các action pin và những gate Ruff/matrix/portability/manifests được giữ nguyên.
- Kiểm tra [git-hygiene.json](reports/git-hygiene.json) xác nhận file bài nộp
  không bị ignore; không phát hiện credential theo các mẫu đã quét. Đây không
  phải cam kết phát hiện được mọi dạng secret.
- Repo đích: `TimingTime/Day28-Track2-NguyenMinhPhuong-2A202601947`, nhánh `main`.

Tài liệu bổ sung: [ANSWERS.md](ANSWERS.md),
[kiến trúc và trách nhiệm](docs/submission-architecture.md),
[demo runbook](docs/demo-runbook.md).

## 6. Thu lại kiểm tra cục bộ

```text
uv sync --frozen --python 3.11 --extra dev --extra integration --no-editable
uv run python scripts/collect_local_checks.py
uv run python scripts/check_git_hygiene.py
```

Các output này kiểm tra mã và cấu hình. Bằng chứng runtime chỉ được cập nhật
sau khi các dịch vụ thật khởi động và các phép kiểm tra live thực sự chạy.

Trên máy này, các lệnh runtime cần dùng cấu hình cổng riêng:

```powershell
$env:LAB28_API_PORT = '18000'
$env:LAB28_GATEWAY_PORT = '18080'
$env:LAB28_MLFLOW_PORT = '15000'
$env:LAB28_API_URL = 'http://localhost:18000'
$env:LAB28_GATEWAY_URL = 'http://localhost:18080'
$env:MLFLOW_TRACKING_URI = 'http://localhost:15000'
$env:PYTHONIOENCODING = 'utf-8'
docker compose --parallel 1 --env-file ports.template --profile full up -d --build --wait
```

Các biến môi trường trên được dùng trong cùng cửa sổ PowerShell khi chạy các
lệnh CLI, integration test và load profile trong [evidence/README.md](evidence/README.md).
