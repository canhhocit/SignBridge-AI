---
description: >
  Debug có hệ thống tầng <LAYER> theo 4 bước Reproduce → Isolate → Diagnose → Fix. Kích hoạt khi
  "debug", "lỗi", "bug", "exception", "error", "không chạy", "tại sao lại…" ở tầng <LAYER>.
  Lỗi thuộc tầng khác → debug-<tầng khác>.
---

# Debug — tầng <LAYER>

> Công cụ cụ thể (log, profiler, debugger) lấy từ knowledge dự án. Skill chỉ định nghĩa quy trình.

## MUST trigger
- Nhận báo lỗi ở tầng `<LAYER>`.
- Agent định đoán nguyên nhân khi chưa tái hiện — **dừng, quay về Bước 1**.

**NEVER** đề xuất nguyên nhân khi chưa qua Bước 1.

## Quy trình (đúng thứ tự)

### Bước 1 — Reproduce
- Triệu chứng cụ thể; input gây lỗi; stack trace / log quanh thời điểm lỗi (đã redact).
- Tái hiện ở môi trường nhỏ nhất (ưu tiên một test FAIL).
- Không tái hiện được → không đoán; thu thêm dữ liệu hoặc hỏi người dùng.

### Bước 2 — Isolate
- Khoanh **tầng/module** xảy ra lỗi theo `architecture.md` — chưa cần biết vì sao.
- Checklist theo tầng *(điều chỉnh theo rủi ro của tầng thật)*:
  - server: ranh giới transaction, dữ liệu nạp trễ ngoài phạm vi, vòng đời đối tượng, timeout gọi ngoài;
  - giao diện: state/render, race khi gọi mạng, cache client;
  - data/infra: idempotency, thứ tự chạy, drift cấu hình.
- Dấu vết dẫn sang **service/repo khác** (lỗi trả về từ API khác, DTO lệch, thư viện dùng chung) → đối chiếu code bên đó qua nguồn tra cứu ngoài (`<external-knowledge>`). Không tra được → báo người dùng, ghi rõ giả thuyết **chưa kiểm chứng**.

### Bước 3 — Diagnose
- Tìm **root cause** (5 Whys), không dừng ở triệu chứng.
- So cấu hình ứng dụng với biến môi trường (chỉ so **tên key**, không in giá trị bí mật).

### Bước 4 — Fix
- Fix nhỏ nhất xử lý root cause; viết test chặn tái diễn; chạy test, dán output.

## Dừng và hỏi
- Lỗi chập chờn không tái hiện được.
- Root cause ở service/repo khác.
- Fix cần thay đổi kiến trúc.
