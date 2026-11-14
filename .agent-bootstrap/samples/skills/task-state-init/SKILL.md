---
description: >
  Khởi tạo trạng thái task mới khi bắt đầu implement một tính năng. Kích hoạt khi
  nghe "implement [X]", "build [X]", "tạo [X]", "viết [X]", "thêm tính năng [X]",
  "bắt đầu làm [X]", "start task". Tạo <STATE_DIR>/<DEV_ID>/current-task.md theo format chuẩn.
---

# Task State Init

## MUST trigger

**MUST** thực thi khi nhận request implement **VÀ** chưa có `current-task.md` với `status: in_progress`.

**NEVER** bắt đầu viết code khi chưa xong đủ 4 bước dưới.

## Mục đích

Mọi implementation có trạng thái rõ ràng, không mất context giữa các phiên.
State theo namespace từng dev (`<STATE_DIR>/<DEV_ID>/`) để nhiều người làm song song không giẫm nhau.

## Quy trình

### Bước 0 — Xác định namespace
- `<DEV_ID>` lấy theo `<quy ước của repo đích — ưu tiên alias cấu hình, tránh dữ liệu định danh cá nhân>`.
  Không xác định được → `local-dev` + cảnh báo.
- Chưa có `<STATE_DIR>/<DEV_ID>/` → copy toàn bộ `<STATE_DIR>/_template/` sang.

### Bước 1 — Thu thập thông tin & đánh giá sơ bộ
- Hỏi nếu chưa rõ: tên task, Definition of Done, ràng buộc kỹ thuật.
- Đánh giá **mức nhẹ**: loại thay đổi, tầng dự kiến, phạm vi thô, yếu tố đặc biệt (migration, đổi public API, bảo mật).
  KHÔNG đọc sâu kiến trúc — đó là việc của agent `developer-*`.

### Bước 2 — Kiểm tra task đang có
- `status: in_progress` → hỏi user: tiếp tục task cũ hay tạo mới (tạo mới = ghi đè).
- `status: done` / `idle` → tạo mới.

### Bước 3 — Ghi file
Ghi `<STATE_DIR>/<DEV_ID>/current-task.md` theo `samples/state/current-task.md`:
- Điền Mô tả, Thiết kế liên quan, DoD, **Các bước thực hiện (tổng quan)** — khung thông dụng, điều chỉnh nhẹ theo đánh giá sơ bộ.
- Để TRỐNG "Tái sử dụng" và "Kế hoạch chi tiết" — agent `developer-*` điền ở bước lập kế hoạch.

### Bước 4 — Xác nhận
Hiển thị task vừa tạo, hỏi "Bắt đầu implement không?".

## Output

- File `<STATE_DIR>/<DEV_ID>/current-task.md` với `status: in_progress`.

## Điều kiện dừng

- User chưa xác nhận tiếp tục hay ghi đè task đang dở.
- Không xác định được DoD.

## Liên kết

- Quét tái sử dụng → skill `reuse-scan`
- Kế hoạch chi tiết → agent `developer-<LAYER>` (Bước 2)
- Cập nhật tiến độ → skill `progress-tracker`
- Bàn giao phiên → lệnh `/<lệnh-handoff>`
