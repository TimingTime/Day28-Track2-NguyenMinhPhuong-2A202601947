# Chạy lại demo trên máy nộp bài

Mã ứng dụng, bằng chứng và các manifest nằm trong Git. Dữ liệu Docker, mật khẩu
Airflow, kubeconfig, model cache và `.env` nằm ngoài Git theo yêu cầu bài nộp.

## Compose và GPU 8 GB

Máy dùng MLflow `15000`, API `18000`, gateway `18080` để tránh trùng các bài khác.
Trong cùng cửa sổ PowerShell:

```powershell
. ./scripts/local-environment.ps1
docker compose --parallel 1 --env-file ports.template -f compose.yaml -f compose.gpu.yaml -f compose.gpu.8gb.yaml -f compose.laptop.yaml --profile full --profile gpu up -d --build
```

Script đặt URL client thành `127.0.0.1`: sau khi Docker Desktop khởi động lại,
`localhost` phân giải ưu tiên `::1` và có endpoint timeout, trong khi cùng cổng
qua IPv4 trả 200 dưới một giây. Đây là thay đổi địa chỉ kết nối, không tăng
timeout hoặc bỏ điều kiện của kiểm thử. Chạy các lệnh bên dưới từ thư mục repo.

`compose.gpu.8gb.yaml` chọn vLLM 0.28.0 CUDA 12.9, Qwen3-1.7B, context 4096,
tối đa 2 sequence, dùng 65% VRAM và eager execution. Runner V1 tránh yêu cầu
UVA/pinned memory của V2 trên Windows/WSL. Tắt thinking ở chat template
để dành giới hạn 320 output token của lab cho câu trả lời. Đây là cấu hình laptop;
không suy ra năng lực phục vụ production từ cấu hình này.

vLLM xuất OTLP bằng `--otlp-traces-endpoint` và tên service `lab28-vllm`, dùng
OpenTelemetry SDK có sẵn trong image. Nhờ vậy trace có emitter từ chính process
inference, ngoài API/gateway/Airflow; span client mang tên `lab28.vllm.chat_completion`
không tự chứng minh server đã xuất trace.

`compose.laptop.yaml` dùng một worker MLflow, Airflow parallelism 1 và Spark
local[2] với heap 768 MiB, hai shuffle partition để giảm tải cho Docker VM 7.4 GiB.
Kafka quảng bá listener ngoài qua IPv4 và ghi log vào named volume `kafka-data`.
Với container cũ của khung bài, sao lưu/chuyển thư mục log hiện có trước khi
tạo lại container: mặc định được quan sát là `/tmp/kafka-logs`, không nằm trong
volume dữ liệu. Lần chuyển của bài nộp đã đối chiếu toàn bộ topic offsets bằng
nhau trước/sau; xem `reports/runtime/kafka-migration.json`. Không dùng `down -v`.

Nguồn cấu hình: [vLLM 0.28.0 release artifacts](https://github.com/vllm-project/vllm/releases/tag/v0.28.0),
[engine arguments](https://docs.vllm.ai/en/v0.28.0/configuration/engine_args/),
[reasoning outputs](https://docs.vllm.ai/en/v0.28.0/features/reasoning_outputs/).

Sau khi health của vLLM trả 200:

```text
uv run lab28 topics
uv run lab28 seed
uv run lab28 index --source file
uv run lab28 release
uv run pytest integration-tests -m "not langsmith" -q
uv run python load-tests/run_ask_profile.py --url http://127.0.0.1:18080 --requests 30 --workers 2 --warmup 5 --asker-id demo
```

Index từ file chỉ chuẩn bị collection. Bằng chứng Delta → Qdrant phải đến từ
DAG thật và J1. Lệnh `lab28 evidence` ghi đè một số file bằng probe ngắn hơn;
thu vào thư mục tạm và giữ lại payload J1/J3/J5 khi đã có bằng chứng phong phú hơn.

Chọn `--asker-id` đã được DAG materialize vào Feast. Mặc định `load-profile`
chưa có online row, nên phép đo đó kiểm tra nhánh default feature và response
được đánh dấu degraded. Báo cáo giữ riêng kết quả cold entity và entity có feature.

Nếu bộ nhớ không đủ khi batch và GPU cùng chạy, demo được chia pha: nhận sự kiện
qua gateway lúc vLLM sẵn sàng; dừng riêng vLLM, chạy DAG; dừng Spark/Airflow sau
khi DAG success, bật lại vLLM và hỏi bằng cùng entity/traceparent. Kafka, Delta,
Feast, Qdrant, collector và Jaeger được giữ giữa các pha. Đây là bằng chứng luồng
dữ liệu thật, không được ghi thành kết quả PASS của full suite chạy đồng thời.

## Kubernetes và GitOps

Demo đã dùng kind **0.33.0**, Kubernetes **1.37.0**, Argo CD Core **3.5.2**,
Envoy Gateway **1.9.1**, metrics-server **0.9.0**. Cluster tên `lab28`, kubeconfig
riêng `.lab28/kubeconfig`. API/Gateway chạy trong Kubernetes; các dịch vụ dữ liệu
vẫn ở Compose. Overlay local giữ vLLM tùy chọn để kiểm tra GitOps độc lập với GPU.

```text
kind create cluster --name lab28 --kubeconfig .lab28/kubeconfig
docker network connect lab28-platform_default lab28-control-plane
docker build -f docker/api/Dockerfile -t lab28-platform-api:submission-20260903-v1 .
kind load docker-image lab28-platform-api:submission-20260903-v1 --name lab28
```

Tag image trên nhận diện bản demo đã thu; khi thay mã, tạo tag mới và cập nhật
overlay. Lần chạy được ghi lại tái sử dụng dependency layer từ image API cục bộ,
cài lại package từ source hiện tại rồi chạy UID `10001`; không tải image bài làm
từ một registry bên ngoài. Digest được ghi trong các snapshot pod.

Cài manifest chính thức của [Argo CD Core](https://argo-cd.readthedocs.io/en/stable/operator-manual/core/),
[Envoy Gateway 1.9.1](https://github.com/envoyproxy/gateway/releases/tag/v1.9.1)
và [metrics-server 0.9.0](https://github.com/kubernetes-sigs/metrics-server/releases/tag/v0.9.0).
Với metrics-server trong kind, thêm `--kubelet-insecure-tls` cho chứng chỉ kubelet
tự ký của cluster local. Không dùng tùy chọn này làm cấu hình TLS production.

Trước khi áp dụng, kiểm tra subnet bằng `docker network inspect
lab28-platform_default`. `network-policy-local.yaml` ghi subnet thực tế của máy
nộp bài `172.22.0.0/16`; máy khác phải cập nhật cho khớp. Policy mở các cổng cần
thiết tới dịch vụ dữ liệu và ingress từ namespace Envoy Gateway.

```text
kubectl --kubeconfig .lab28/kubeconfig apply -f gitops/project.yaml -f gitops/application.yaml
kubectl --kubeconfig .lab28/kubeconfig get application -n argocd
kubectl --kubeconfig .lab28/kubeconfig get pods,gateway,hpa -n lab28
```

`Application` trỏ repo bài nộp và SHA cố định; mỗi rollout cần push commit trước,
cập nhật `targetRevision`, rồi apply Application. `prune` và `selfHeal` được bật.
Không dùng `kubectl rollout undo` thay cho việc revert desired state trong Git.

Bằng chứng đã thu tại [reports/runtime/gitops](../reports/runtime/gitops):
baseline → drift → self-heal → candidate 2 replica → Git revert → baseline 1 replica.
`scripts/capture_gitops.py` lưu UTC, Git SHA, Argo status, pod/image IDs và HTTP
qua gateway. Cổng port-forward của máy nộp bài là `127.0.0.1:19580`.

Cluster có thể dừng bằng `docker stop lab28-control-plane` và chạy lại bằng
`docker start lab28-control-plane`; thao tác này giữ trạng thái cluster và tiết
kiệm RAM khi chạy GPU. Port-forward cần khởi động lại sau khi chạy lại cluster.

## LangSmith

`compose.langsmith.yaml` là cấu hình opt-in, chỉ bật sau khi cho phép gửi trace
của lab tới tài khoản LangSmith. Giữ key trong `.env`, dùng `LANGSMITH_API_KEY`
hoặc tên cũ `LANGCHAIN_API_KEY`; không commit key. Tên project có cùng cơ chế
tương thích `LANGSMITH_PROJECT`/`LANGCHAIN_PROJECT`.

Collector nhận OTLP một lần, gửi cùng luồng tới Jaeger và LangSmith theo
[hướng dẫn OpenTelemetry của LangSmith](https://docs.langchain.com/langsmith/trace-with-opentelemetry).
Cấu hình bổ sung không tự chứng minh exporter đã chạy: cần kiểm tra project,
counter exporter và test đánh dấu `langsmith` trong kết quả runtime.

Khi đã cho phép gửi trace, thêm `--env-file .env` trước file cấu hình cổng và
`-f compose.langsmith.yaml` vào lệnh Compose. Chạy toàn bộ gate, giữ nguyên test:

```text
uv run python scripts/collect_live_checks.py --require-gpu --include-langsmith
```

Script chỉ đọc key khi chọn `--include-langsmith`, hỗ trợ tên biến cũ và lưu
log/metadata vào `reports/runtime/full-suite.*`. `--require-gpu` từ chối chạy nếu
endpoint chưa chứng minh được identity vLLM, tránh nhầm kết quả skip với PASS.
