---
description: >
  Tiếp tục phiên làm việc trước. Đọc session-handoff.md (+ current-task, progress) của dev hiện
  tại, tóm tắt nơi đã dừng và việc kế tiếp, rồi HỎI trước khi viết code. Chỉ chạy khi user gõ lệnh này.
disable-model-invocation: true
argument-hint: "(không cần tham số)"
---

# /<lệnh-resume> — Tiếp tục phiên

> Lệnh **chỉ user gọi**, thao tác **chỉ đọc**. Đi cặp với `/<lệnh-handoff>` (`handoff.md`).
> Tên lệnh: tránh trùng lệnh built-in của harness (vd Claude Code đã có `/resume`) — thêm tiền tố dự án.

## Quy trình

### Bước 1 — Xác định `<DEV_ID>`
- Cùng quy ước với `task-state-init` / `/<lệnh-handoff>`.

### Bước 2 — Đọc handoff + state
- Đọc `<STATE_DIR>/<DEV_ID>/session-handoff.md`.
  Không có / `status: idle` → báo "Chưa có phiên nào được lưu — gõ `/<lệnh-handoff>` trước khi kết thúc phiên", **DỪNG**.
- Đọc kèm `current-task.md`, `progress.md` để đối chiếu.
- So `git status` hiện tại với danh sách file trong handoff; khác biệt → nêu ra (có thể có người/phiên khác đã sửa).

### Bước 3 — Tóm tắt
- **Task** · status · % — **Đã dừng ở** — **File đang sửa** — **Quyết định/context** — **Blockers** — **Next steps**.

### Bước 4 — Hỏi trước khi tiếp tục
"Tiếp tục từ đây không? (bước kế: <next step đầu tiên>)"
- **NEVER** tự viết/sửa code ngay sau resume. Người dùng xác nhận → đi theo routing thường lệ.

## Ràng buộc
- Chỉ đọc namespace của chính dev; **NEVER** ghi state khi resume.
