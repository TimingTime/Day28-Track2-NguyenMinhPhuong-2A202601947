# Reflection — Day 28 Track 2

Nguyễn Minh Phương — 2A202601947. Bài làm cá nhân, có hỗ trợ AI khi triển khai,
kiểm tra và viết tài liệu. Kết quả chạy thực tế nằm trong `REPORT.md` và `reports/`.

## 1. Contract giữa HTTP, Kafka và dữ liệu

Contract tập trung trong `src/lab28_platform/contracts.py`. `schema_version`
giúp bên nhận nhận biết phiên bản dữ liệu. `event_id` nhận diện sự kiện, còn
`idempotency_key` nhận diện dữ liệu logic cần chống trùng. Các lần gửi lại có thể
có Event ID khác nhau nhưng vẫn dùng cùng khóa chống trùng.

`event_headers` luôn gửi `idempotency-key` dạng UTF-8 bytes. Khi có trace, hàm
gửi thêm `traceparent`; khi giá trị là `None` hoặc chuỗi rỗng, header được bỏ qua.
Trace giúp chẩn đoán đường đi của yêu cầu; việc chống trùng sử dụng khóa nghiệp vụ.

Khi chạy thật, consumer mới có thể chưa được Kafka phân chia partition trong
ba lần poll đầu. Không thể coi giai đoạn này là topic rỗng. `poll_batch` chờ
assignment theo thời hạn riêng, báo lỗi nếu hết hạn, và chỉ đếm các lần poll
rỗng liên tiếp sau khi đã có assignment. Bản sửa này xử lý trường hợp DAG báo
success với `polled=0` dù topic còn dữ liệu; J1 đã đi được tới Delta sau khi sửa.

## 2. Chống trùng và lựa chọn bản mới nhất

`dedupe_latest` duyệt iterable một lần và lưu sự kiện tốt nhất cho mỗi khóa trong
dictionary. So sánh tuple `(occurred_at, event_id)` ưu tiên thời điểm trước,
Event ID làm tiêu chí phụ khi bằng thời điểm. Kết quả được sắp xếp theo khóa.
Đầu vào rỗng trả về `[]`, và generator chỉ dùng được một lần vẫn được hỗ trợ.

Với `n` sự kiện và `k` khóa khác nhau, chi phí trung bình là `O(n + k log k)`,
bộ nhớ `O(k)`. Cách này dễ kiểm thử ở quy mô lô của bài lab. Với lô quá lớn,
cần chuyển việc chọn bản mới nhất sang xử lý phân tán thay vì giữ cả tập khóa
trong một tiến trình Python.

Giới hạn cần phân biệt: hàm chỉ chọn bản mới nhất trong lô. Câu MERGE của khung
bài cập nhật hàng khớp khóa vô điều kiện; để chống một lô cũ ghi đè dữ liệu mới
đã có trong production, cần thêm điều kiện so sánh phiên bản/thời điểm với bảng đích.
Kiểm thử phát lại cùng lô không tự chứng minh được trường hợp dữ liệu đến muộn này.

## 3. Feast và Qdrant khác nhau thế nào?

Feast trả đặc trưng có cấu trúc theo entity `asker_id`: số feedback, điểm trung
bình, tỷ lệ tiêu cực và phiên bản Delta. Qdrant tìm tài liệu liên quan tới câu
hỏi dựa trên vector. Feature lookup và document retrieval phục vụ hai nhu cầu
khác nhau trong cùng luồng trả lời.

`feast_online_request` dùng `FEATURE_REFS` từ contract chung, tránh danh sách
đặc trưng bị lệch giữa các nơi. Yêu cầu có `entities = {"asker_id": [asker_id]}`
và `full_feature_names = False`. Danh sách được sao chép từ tuple để từng yêu
cầu không chia sẻ một list có thể bị thay đổi ngoài ý muốn.

## 4. Liveness và readiness

Liveness trả lời tiến trình còn phục vụ HTTP được không. Readiness trả lời nó có
đủ thành phần để nhận yêu cầu theo chính sách hiện tại không.

- `not_ready`: có phụ thuộc bắt buộc bị lỗi; ưu tiên cao nhất.
- `degraded`: phụ thuộc bắt buộc hoạt động, nhưng có phụ thuộc tùy chọn bị lỗi.
- `ready`: không có kiểm tra nào bị lỗi; theo yêu cầu bài, tập kiểm tra rỗng cũng trả `ready`.

Hàm xử lý một luồng probe một lần. Lỗi tùy chọn xuất hiện trước không được che
lỗi bắt buộc xuất hiện sau. Feast là phụ thuộc tùy chọn trong serving path;
vLLM có bắt buộc hay không phụ thuộc `LAB28_VLLM_REQUIRE_REAL`.

## 5. Release và rollback

MLflow lưu release có provenance: phiên bản dữ liệu, cấu hình retrieval/prompt,
model ID và thông tin lần chạy. Alias `champion` chọn release đang được phục vụ.
Promotion chuyển alias sang bản mới; rollback chuyển alias về bản đã biết tốt.
Cần kiểm tra cả metadata và hành vi phục vụ sau khi chuyển alias.

GitOps lưu trạng thái triển khai mong muốn trong Git. Rollback deployment cần
trỏ về revision/image bất biến trước đó và kiểm tra lại health. Validation YAML
chỉ chứng minh cấu trúc, không chứng minh Argo CD đã sync hoặc tự sửa drift.

Trong demo kind, thay trực tiếp ConfigMap thành `manual-drift` được Argo CD
tự sửa về `baseline` sau 5.875 giây. Commit rollout tăng API lên hai replica;
Git revert đưa về một replica, cả hai lần đều `Synced/Healthy` và HTTP 200 qua
gateway Kubernetes. API chạy UID 10001; NetworkPolicy chỉ mở các cổng dữ liệu
cần thiết tới subnet Compose. Snapshot nằm trong `reports/runtime/gitops/`.

## 6. Quan sát và khôi phục sự cố

Metrics giúp phát hiện xu hướng: lưu lượng, lỗi, độ trễ, bão hòa và Kafka lag.
Trace giúp truy nguyên một yêu cầu cụ thể qua các dịch vụ. Một mã trace được
tạo ở client chưa đủ làm bằng chứng; cần tìm được các span thực tế trong backend.

Kịch bản khôi phục của bài: ghi trạng thái/count trước sự cố, dừng riêng Feast
hoặc Qdrant, quan sát readiness, khởi động lại dịch vụ, rồi đối chiếu dữ liệu và
khả năng phục vụ. Không xóa volume khi kiểm tra no-data-loss. Các kịch bản trong
runbook chỉ được tính là đã chạy khi có log/bằng chứng tương ứng trong báo cáo.

## 7. Đánh đổi và khoảng cách với production

- Broker Kafka đơn và replication factor 1 phục vụ lab; chưa chịu được mất node.
- Spark/Delta phù hợp xử lý dữ liệu và lịch sử phiên bản nhưng tăng tài nguyên vận hành.
- Cần xác thực, TLS, quản lý secret và phân quyền cho các endpoint trước khi mở ra ngoài.
- Cần kiểm soát retention, compaction, backup và kiểm thử phục hồi dữ liệu định kỳ.
- Gateway rate limit trong lab cần được đánh giá lại khi có nhiều replica.
- Cần kiểm tra cập nhật đến muộn, xung đột ghi và schema migration ngoài phát lại cùng lô.
- Số liệu `/ready` chỉ là baseline; năng lực trả lời RAG phải đo `/api/v1/ask`
  với corpus, mô hình, GPU, concurrency, warm-up và chính sách degraded được ghi rõ.
- Trong 100 trace readiness gần nhất đã thu, bước resolve release từ MLflow
  chiếm phần lớn thời gian. Có thể đánh giá cache ngắn hạn hoặc probe metadata
  nhẹ hơn, nhưng cần cân bằng với tốc độ nhận biết một lần chuyển `champion`.
- Endpoint vLLM phải chứng minh `/version`, model ID và metrics `vllm:`.
  Demo đã xác minh vLLM 0.28.0 và Qwen3-1.7B trên RTX 4060 Laptop 8 GiB.
- CUDA trong image phải tương thích driver. Runner V2 gặp yêu cầu UVA trên WSL;
  cấu hình cuối dùng runner V1, CUDA 12.9, 65% VRAM, tối đa hai sequence và
  eager execution. Giảm parallelism của Spark/Airflow và worker MLflow giúp
  vừa Docker VM 7.4 GiB, đổi lại giảm khả năng xử lý đồng thời.
- Collector xuất cùng trace tới Jaeger và project LangSmith `Lab28` sau khi
  được cấp phép. Đã đọc lại run từ LangSmith; chỉ có key trong `.env` chưa đủ
  chứng minh việc export thành công.

## 8. Đóng góp trong bài nộp

Phạm vi bài cá nhân gồm bốn hàm tích hợp, kiểm thử các trường hợp biên,
hai bản sửa xuất JSON của CLI, bản sửa chờ Kafka assignment phát hiện qua J1,
kiểm tra và lưu output, điều chỉnh CI cho trạng thái bài đã hoàn thành,
bảo vệ file cục bộ bằng `.gitignore`/`.dockerignore`, tài liệu kiến trúc,
báo cáo kết quả và commit/push. Phần vận hành bổ sung gồm profile GPU/laptop,
exporter LangSmith, deployment non-root, NetworkPolicy, Argo CD rollout/rollback
và công cụ thu bằng chứng runtime/load. Kết quả và giới hạn đo được nằm trong
báo cáo, không suy ra từ kết quả unit test.
