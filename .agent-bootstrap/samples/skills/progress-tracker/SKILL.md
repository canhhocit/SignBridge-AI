---
description: >
  Cập nhật tiến độ task đang làm. Kích hoạt tự động sau MỖI bước implement hoàn thành, hoặc khi
  nghe "đến đâu rồi", "tiến độ", "update progress", "xong bước", "đã xong [X]", "còn lại gì".
  Ghi progress.md và tick current-task.md trong <STATE_DIR>/<DEV_ID>/; chỉ đổi status done khi test đã PASS.
---

# Progress Tracker

## MUST trigger
- Hoàn thành bất kỳ bước nào trong quá trình implement — không chờ người dùng hỏi.
- Mọi DoD đã tick → xét đổi `status: done` (qua cổng test bên dưới).

**NEVER** kết thúc một bước implement mà không cập nhật `progress.md` và tick checkbox.

## Quy trình

### Bước 1 — Đọc state
- `<DEV_ID>` theo **cùng quy ước** với skill `task-state-init` (một nguồn duy nhất).
- Đọc `<STATE_DIR>/<DEV_ID>/current-task.md`. Chưa có → nhắc chạy `task-state-init`, dừng.

### Bước 2 — Đánh giá
- Tick DoD, bước tổng quan, bước con trong "Kế hoạch chi tiết" đã xong (dựa trên code đã viết + output đã chạy).
- "Kế hoạch chi tiết" còn trống → nhắc `developer-<LAYER>` điền trước.
- Ước tính % theo bước con (nếu có), không thì theo bước tổng quan.

### Bước 3 — Ghi `progress.md` (ghi đè, khung ở `samples/state/progress.md`)

### Bước 4 — Báo ngắn
`Task <tên>: <X>% — đang làm <bước>. Còn <N> bước.`

### Bước 5 — Cổng test trước `done`
- Chỉ tick DoD liên quan code và đổi `status: done` khi đã có **output test thật, PASS** trong phiên.
- Chưa chạy / còn fail → giữ `status: in_progress`, không tick DoD đó, nêu lý do.
- Repo không có test → DoD ghi cách kiểm chứng đã làm + giới hạn; không được ghi "test PASS".

## Liên kết
- Khởi tạo task → `task-state-init` · Lưu phiên → `/<lệnh-handoff>` · Mở lại → `/<lệnh-resume>`
