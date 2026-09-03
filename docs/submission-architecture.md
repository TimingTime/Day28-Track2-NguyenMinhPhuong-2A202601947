# Kiến trúc và trách nhiệm — bài nộp Day 28

Người nộp: Nguyễn Minh Phương — 2A202601947. Hình thức: cá nhân, có hỗ trợ AI
trong triển khai, kiểm thử và soạn báo cáo. Sơ đồ mô tả thiết kế của kho mã;
kết quả xác minh từng thành phần được ghi riêng trong `REPORT.md`.

```mermaid
flowchart LR
    user[Người dùng] --> gateway[Envoy]
    gateway --> api[FastAPI]
    api -->|Document / feedback| kafka[Kafka data.raw]
    kafka --> airflow[Airflow]
    airflow --> spark[Spark Connect]
    spark --> delta[Delta Lake]
    delta -->|Đặc trưng tổng hợp| feast[Feast]
    delta -->|Tài liệu và embedding| qdrant[Qdrant]
    delta -->|Phiên bản dữ liệu đánh giá| registry[MLflow Registry]
    api -->|Lấy đặc trưng| feast
    api -->|Truy xuất tài liệu| qdrant
    api -->|Đọc alias champion| registry
    api -->|Prompt có ngữ cảnh| vllm[vLLM thật]
    vllm -->|Kết quả sinh| api
```

```mermaid
flowchart LR
    components[Các dịch vụ] -->|Metrics| prometheus[Prometheus]
    prometheus --> grafana[Grafana và cảnh báo]
    components -->|Spans OTLP| collector[OpenTelemetry Collector]
    collector --> jaeger[Jaeger]
    collector -.->|Cần credential và cấu hình| langsmith[LangSmith]
    git[Git: manifests và revision] --> argo[Argo CD]
    argo --> k8s[Kubernetes / Gateway API]
```

## Điểm kết nối và trách nhiệm cá nhân

| Phần phụ trách | Điểm kết nối | Công việc cần giải thích |
|---|---|---|
| Ingestion và điều phối | IP01, IP02 | Contract sự kiện, Kafka headers, retry, DLQ và Airflow run |
| Dữ liệu và mô hình | IP03, IP04, IP06 | Chọn bản tin mới nhất, Delta MERGE, Feast features, MLflow alias |
| Truy xuất và phục vụ | IP05, IP07 | ID vector ổn định, grounding và nhận diện máy chủ vLLM thật |
| Nền tảng và quan sát | IP08, IP09, IP10 | Gateway, readiness, metrics, trace và manifest triển khai |
| Trình bày | Toàn bộ | Đối chiếu báo cáo, bằng chứng thực tế và các phần chưa xác minh |

## Vì sao cần cả hai bước chống trùng?

`dedupe_latest` chọn một sự kiện cho mỗi `idempotency_key` **trong lô đầu vào**.
Delta `MERGE` đối chiếu các khóa đó với **bảng đang lưu** để cập nhật hoặc thêm.
Hai bước phối hợp để lần phát lại cùng lô không tạo thêm hàng. Hàm Python không
tự ghi Delta và kiểm thử hàm không thay thế bằng chứng phát lại trên hệ thống thật.

Tham khảo [sơ đồ tổng thể gốc](images/lab28-architecture-overview.png),
[ma trận kết nối](../contracts/integration-matrix.yaml) và
[báo cáo bài nộp](../REPORT.md).
