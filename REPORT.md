# Báo cáo Day 28 — Track 2

Nguyễn Minh Phương — **2A202601947**. Thực hiện ngày **03/09/2026**, cá nhân,
có hỗ trợ AI khi triển khai, kiểm tra và viết tài liệu.

**Đã hoàn thành mã tích hợp, kiểm thử không cần GPU, GPU serving, LangSmith và
GitOps runtime. Chưa xác nhận toàn bộ DoD:** full suite có GPU bị gián đoạn khi
Docker mất phản hồi; demo theo pha đã thu đủ 11 span bắt buộc từ 4 dịch vụ,
không có error span và có kết quả hỏi đáp GPU. Các giới hạn được ghi dưới đây.
Không tính lần chạy dở hoặc test bị bỏ chọn là PASS.

## 1. Mã và các bản sửa

| Phần | Kết quả |
|---|---|
| `event_headers` | Header idempotency dạng bytes; chỉ truyền trace khi có giá trị |
| `dedupe_latest` | Duyệt một lần, chọn bản mới nhất mỗi khóa, tie-break bằng Event ID |
| `feast_online_request` | Entity và bốn feature đúng contract, không chia sẻ list có thể bị sửa |
| `readiness_status` | Lỗi bắt buộc ưu tiên; xử lý được generator |
| Kafka consumer | Chờ partition assignment trước khi kết luận topic rỗng; timeout riêng và reset idle sau dữ liệu |
| CLI JSON | Hỗ trợ stdout CP1252; đưa thông báo MLflow sang stderr để stdout là JSON hợp lệ |
| Triển khai | API UID 10001, root filesystem chỉ đọc trên Kubernetes, `/tmp` writable; NetworkPolicy cho đúng các cổng dữ liệu |
| Vận hành | Profile GPU/laptop, exporter LangSmith, listener IPv4, volume Kafka, script kiểm thử và thu bằng chứng |
| Envoy readiness | Active health check dùng `/ready`, loại API khỏi routing khi Qdrant không sẵn sàng; timeout 5 giây phù hợp phép đo readiness |

Giữ nguyên starter tests, integration tests, fixtures và các gate môi trường.
Các kiểm thử bổ sung tập trung vào trường hợp biên, JSON Windows và Kafka assignment.
Mã chính ở [integration_tasks.py](src/lab28_platform/integration_tasks.py),
[event_bus.py](src/lab28_platform/event_bus.py) và [cli.py](src/lab28_platform/cli.py).

## 2. Kết quả kiểm tra

| Kiểm tra | Kết quả thực tế | Bằng chứng |
|---|---|---|
| Starter + fast suite | **98 passed** | [output](reports/local-checks/fast-suite.txt) |
| Ruff / ma trận / portability / manifests | PASS; ma trận **245 checks** | [summary](reports/local-checks/summary.json) |
| Offline integration | **1 passed, 71 deselected** | [output](reports/local-checks/offline-integration.txt) |
| Compose cơ bản/full/GPU+laptop+LangSmith | Cấu hình hợp lệ | [summary](reports/local-checks/summary.json) |
| Live không cần GPU/LangSmith | **56 passed, 16 deselected**, 424.37 giây | [output](reports/runtime/live-suite.txt), [metadata](reports/runtime/live-suite.json) |
| J3/J4 GPU + LangSmith | **8 passed, 15 deselected**, 217.92 giây; sau bản sửa Envoy | [output](reports/runtime/gpu-langsmith-suite.txt), [metadata](reports/runtime/gpu-langsmith-suite.json) |
| Full suite có GPU/LangSmith | **Chưa đạt toàn bộ**; Docker mất phản hồi sau 5 test hoàn tất | [lần gián đoạn](reports/runtime/full-suite-docker-stall.json) |
| CI trên GitHub | **PASS**: Ubuntu, Windows, macOS; commit `7c86cc5` | [CI run](https://github.com/TimingTime/Day28-Track2-NguyenMinhPhuong-2A202601947/actions/runs/33766265191), [snapshot](reports/github-ci.json) |

CI kiểm tra mã và manifest; không tự chạy stack GPU. Kết quả live 56 test thuộc
lần chạy trước khi bật GPU/LangSmith. Log timeout ban đầu được giữ trong
[full-suite-startup-timeout.txt](reports/runtime/full-suite-startup-timeout.txt).

## 3. Các điểm tích hợp đã quan sát

| Điểm | Bằng chứng |
|---|---|
| IP01 HTTP → Kafka | [Bản tin thật, partition/offset, idempotency và trace headers](evidence/ip01-kafka-consume.json) |
| IP02 Kafka → Airflow | [DAG success, bốn task và asset events](evidence/ip02-airflow-run.json) |
| IP03 Spark → Delta | [MERGE history và time travel](evidence/ip03-delta-history.json) |
| IP04 Delta → Feast | [Online entity, giá trị feature và PRESENT statuses](evidence/ip04-feast-online.json) |
| IP05 Delta → Qdrant | [Truy vấn có ID/score](evidence/ip05-qdrant-search.json); J1 xác minh nhánh index từ Delta |
| IP06 MLflow | [J3 promotion/rollback và provenance](evidence/ip06-mlflow-release.json) |
| IP07 vLLM | v0.28.0, Qwen3-1.7B, GPU thật; [câu trả lời đầu](reports/runtime/first-gpu-answer.json) |
| IP08 Envoy | [HTTP 200/429, counter và request IDs](evidence/ip08-gateway.json) |
| IP09 Prometheus/Grafana | [Targets](evidence/ip09-prometheus-targets.json), [dashboard](evidence/ip09-grafana-dashboards.json) |
| IP10 tracing | [Trace cuối đủ 11 span qua các process](evidence/ip10-trace.json); [LangSmith có run đọc lại được](reports/runtime/langsmith.json) |

Có **11 file IP cho 10 điểm** vì IP09 có hai file. Snapshot cũ vẫn giữ đúng thời
điểm thu: các trạng thái vLLM chưa sẵn sàng hoặc serving spans thiếu trong snapshot
trước không được sửa thành PASS bằng tay. IP10 cuối được đọc lại từ Jaeger sau
replay cùng khóa: **35 spans**, đủ **11 tên span bắt buộc**, từ API, gateway,
Airflow và vLLM. Không span nào có `error=true` hoặc `otel.status_code=ERROR`.
Span `llm_request` được process vLLM xuất qua OTLP; không đổi tên service để
làm tăng số emitter.

`integration-report.json` là probe của CLI. Bốn điểm cần quan sát ngoài process
có thể vẫn là `unverified` dù đã có file evidence riêng. Điểm probe không phải
điểm chấm rubric và không chứng minh toàn bộ hệ thống production-ready.

## 4. Luồng dữ liệu, release và khôi phục

J1 đã đưa sự kiện qua Kafka, Airflow, Spark/Delta, materialize Feast và index
Qdrant. Bộ dữ liệu ban đầu có 13 tài liệu; snapshot sau các journey đầu có
**17 tài liệu ở Delta v4**, **19 feedback ở Delta v7**, Qdrant 17 points.
Version/count có thể tăng khi chạy lại journey; lịch sử trong evidence là nguồn đối chiếu.

Release phục vụ cuối **v5**, run `f5d18a25d5bf4be6aa55c1986c1eb811`, dùng prompt
`day28-final`, Qwen3-1.7B, `top_k=3` và dữ liệu đánh giá Delta v8;
xem [registration](reports/runtime/mlflow-registration-final.json).
Sau replay cuối, bảng feedback lên v10 nhưng vẫn 21 hàng; documents v6 có 19 hàng.
Phiên bản dữ liệu của release được giữ đúng provenance, không tự thay bằng
phiên bản bảng mới nhất.
J3 trước đó đã tạo v3, chuyển champion và rollback; giá trị evaluation 0.83/640
trong fixture J3 là dữ liệu kiểm thử, không phải benchmark đo được của mô hình.

J4 trong lần live 56 test đã kiểm tra mất Feast, mất Qdrant, phục hồi readiness,
bản tin lỗi vào DLQ, bản tin tốt cùng batch vẫn vào Delta và replay không tạo
thêm hàng logic. Lần kiểm thử GPU riêng đã xác minh promotion/rollback khi trả lời,
Feast degraded, Envoy loại API không ready khi mất Qdrant, và câu trả lời trực tiếp
có cờ degraded khi retrieval hỏng. Test LangSmith cũng đạt; không cộng các lần
chạy thành một kết quả `72 passed`.

Lần GPU trước bản sửa phát hiện Envoy dùng `/health` nên tiếp tục chuyển traffic
khi API không ready: **5 passed, 1 failed**. Giữ nguyên
[log lỗi](reports/runtime/gpu-langsmith-before-gateway-fix.txt); chuyển health check
sang `/ready`, rồi chạy lại toàn bộ nhóm tám test gốc và đạt.

Kafka ban đầu ghi `/tmp/kafka-logs` trong lớp ghi của container. Trước khi tạo
lại để sửa listener, đã dừng broker, sao chép nguyên log sang named volume,
giữ bản backup ngoài Git và đối chiếu **toàn bộ offsets trước/sau bằng nhau**:
[kafka-migration.json](reports/runtime/kafka-migration.json). Không xóa volume.

Demo cuối ở [happy-path.json](reports/runtime/happy-path.json): trace
`6757a43c8c04458c920e8a8c15483b8c`, DAG `it-622b303d`, entity
`final-02e60d6c`. Cùng khóa được phát lại; Kafka giữ các bản gửi,
Delta vẫn một hàng logic. Câu trả lời có tài liệu vừa nộp trong sources, audit
hashes và feature thật; không degraded. Batch và GPU chạy theo pha.
Trace trước `c292556b1c754bb8a11a9716d90cf7ee` chứa cả lỗi lúc khởi động được
giữ nguyên tại [trace-with-startup-errors.json](reports/runtime/trace-with-startup-errors.json)
và [demo trước](reports/runtime/happy-path-before-clean-trace.json).
[recovery.json](reports/runtime/recovery.json) còn đối chiếu dữ liệu J4 sau
Docker restart: bản replay có hai Kafka copies, một hàng Delta.

## 5. Kubernetes/GitOps đã chạy thật

Dùng kind 0.33.0, Kubernetes 1.37.0, Argo CD Core 3.5.2, Envoy Gateway 1.9.1
và metrics-server 0.9.0. API và gateway chạy trong Kubernetes; các dịch vụ dữ
liệu vẫn ở Compose. Overlay local để vLLM tùy chọn tại thời điểm demo GitOps.

- Baseline commit `0016c41`: Argo `Synced/Healthy`, gateway trả HTTP 200.
- Sửa trực tiếp ConfigMap thành `manual-drift`: Argo tự khôi phục sau **5.875 giây**.
- Commit `18a4d17`: rollout lên **hai replica ready**, marker `candidate`.
- Git revert `cea46f0`: trở về **một replica**, marker `baseline`, `Synced/Healthy` và HTTP 200.

[Bộ snapshot](reports/runtime/gitops/) chứa revision, image IDs, Deployment,
HPA, Gateway và HTTP. HPA có CPU metrics thật; đây không phải bằng chứng autoscale
qua tải cao. Cluster được dừng tạm để dành RAM cho GPU; trạng thái và volume giữ nguyên.

## 6. Hiệu năng và giới hạn

Baseline **100 GET `/ready`, 4 workers**, tất cả HTTP 200:
P50 **467.220 ms**, P95 **1610.549 ms**, P99 **2596.758 ms**;
[load result](reports/runtime/readiness-load.json).
Trong 100 trace readiness gần nhất, resolve MLflow trung bình 430.50 ms trên
root trung bình 600.78 ms, khoảng 72%. Đây là tập trace có cả health traffic,
không phải ghép chính xác từng request benchmark:
[trace profile](reports/runtime/readiness-trace-profile.json).

Câu hỏi GPU đầu tiên mất **37.77 giây ở ứng dụng**, có timeout Feast trong lúc
khởi động; retrieval 21.99 giây và LLM 11.80 giây. Đây là cold request,
**không phải P50/P95/P99 của RAG**. Chưa dùng nó để tuyên bố đáp ứng SLO.
Script [run_ask_profile.py](load-tests/run_ask_profile.py) đo 30 câu hỏi, hai worker,
loại năm warm-up và lưu response/audit/trace ID từng request.

Phép đo có feature thật: **30/30 HTTP 200, 0 degraded**, entity
`final-02e60d6c`, hai workers, năm warm-up bị loại. P50 **3558.412 ms**,
P95 **12309.638 ms**, P99 **12565.525 ms**, throughput **0.417 request/s**.
Xem [request-level output](reports/runtime/ask-load.json) và
[bottleneck trên 30 trace tương ứng](reports/runtime/ask-bottleneck.json).
LLM trung bình 3609.68 ms trên tổng 4674.22 ms, khoảng **77%**; resolve MLflow
trên trace trung bình 685.08 ms, retrieval 355.61 ms, feature 21.34 ms.
Cả 30 request đều vượt 1000 ms. Hướng tối ưu cần đo tiếp là generation/token
budget, kernel/batching phù hợp GPU, rồi cache release có cơ chế invalidation.
Không thay budget để làm đẹp kết quả.

Phép đo cold entity được giữ riêng tại [ask-load-cold-entity.json](reports/runtime/ask-load-cold-entity.json):
30 HTTP 200 nhưng 30 degraded do entity chưa materialize; P50/P95/P99 lần lượt
3427.512/6956.037/7161.482 ms. Hai phép đo đều tạm dừng Spark/Airflow và diễn ra
trước khi bật thêm exporter bên trong vLLM. Đây không phải benchmark toàn stack
đang chạy batch, cũng không phải đánh giá độ đúng ngữ nghĩa trên một tập chuẩn.

Budget gốc giữ nguyên: feature 5 ms, retrieval 50 ms, LLM 500 ms, tổng 1000 ms.
Một response HTTP 200 không có nghĩa đã đạt các budget này.

## 7. Môi trường và sự cố

Windows; Python 3.11.16; uv 0.12.9; 16 logical CPU, RAM khoảng 15.3 GiB;
Docker VM 7.4 GiB; RTX 4060 Laptop 8 GiB, driver 577.02. Docker Engine 28.1.1,
Compose 2.35.1-desktop.1. Cổng riêng: MLflow 15000, API 18000, gateway 18080.

Đã xử lý lỗi pull image EOF/concurrent map writes, Kafka chưa assignment nhưng
DAG trả polled=0, JSON Windows và kết nối IPv6. vLLM image CUDA 13 không phù hợp
driver hiện tại; chọn bản CUDA 12.9. Runner V2 gặp UVA; cấu hình cuối dùng V1,
65% VRAM, context 4096, tối đa hai sequence, eager execution và tắt thinking.

Khi Spark chạy cùng GPU, Docker có lần trả 500 và mọi HTTP dịch vụ timeout.
Đã phục hồi Docker; không dùng kết quả bị gián đoạn làm bằng chứng đạt. Jaeger
in-memory mất lịch sử sau restart; các JSON đã lưu và trace LangSmith vẫn còn.
Profile laptop giảm MLflow xuống một worker, Airflow parallelism 1 và Spark
local[2]/heap 768 MiB; máy vẫn cần thêm tài nguyên cho full-stack peak.

Sau demo thành công, lần thu snapshot bổ sung lại gặp timeout Feast/Qdrant/OTLP
và Docker Engine trả HTTP 500. Lệnh dừng riêng vLLM cũng trả 500, nên **không xác
nhận stack còn healthy lúc bàn giao**. Preflight cuối trả `local_ready=false`;
exit code 0 của lệnh preflight không được hiểu là môi trường đã sẵn sàng.
Các bằng chứng thành công trước đó giữ nguyên timestamp; snapshot bổ sung lỗi
không ghi đè chúng. Xem [trạng thái cuối](reports/runtime/runtime-final.json).
Spark, Airflow và kind đã được dừng trước pha GPU; dữ liệu và volume giữ nguyên.

## 8. File nộp và chạy lại

`.gitignore`/`.dockerignore` giữ source, test, cấu hình, dữ liệu mẫu, `uv.lock`,
report và 11 file IP; loại `.env`, `.lab28`, `.venv`, database, cache và weights.
[Git hygiene](reports/git-hygiene.json) quét tính hiển thị và mẫu credential phổ biến.
[Rà soát artifact](reports/submission-audit.json) kiểm tra JSON, link file trong
báo cáo và đối chiếu trực tiếp giá trị credential cục bộ với các file sẽ nộp.
Key LangSmith chỉ được dùng sau khi có phép, không nằm trong Git hoặc báo cáo.

```powershell
. ./scripts/local-environment.ps1
uv run python scripts/collect_local_checks.py
uv run python scripts/collect_live_checks.py --require-gpu --include-langsmith
uv run python scripts/check_git_hygiene.py
```

Cấu hình khởi động, lưu ý Kafka cũ và các phiên bản đã dùng nằm trong
[hướng dẫn chạy lại](docs/local-runtime.md). Xem thêm
[architecture/ownership](docs/submission-architecture.md) và [reflection](ANSWERS.md).
