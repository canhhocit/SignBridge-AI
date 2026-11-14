---
description: >
  Lưu trạng thái phiên làm việc hiện tại để bàn giao / tiếp tục sau. Đọc state của dev hiện tại
  (current-task, progress), gom file đang sửa từ git, rồi GHI ĐÈ session-handoff.md. Chỉ chạy khi
  user gõ lệnh này (không tự kích hoạt).
disable-model-invocation: true
argument-hint: "(không cần tham số)"
---

# /<lệnh-handoff> — Lưu phiên

> Lệnh **chỉ user gọi** (`disable-model-invocation: true`) ở ranh giới kết thúc phiên.
> Đóng gói state do `task-state-init` / `progress-tracker` tạo thành một snapshot bàn giao.

## Quy trình (tuần tự — không bỏ bước)

### Bước 1 — Xác định `<DEV_ID>`
- Theo **cùng quy ước** với skill `task-state-init` (một nguồn duy nhất — không định nghĩa lại khác đi).

### Bước 2 — Đọc state
- Đọc `<STATE_DIR>/<DEV_ID>/current-task.md` và `progress.md`.
- Chưa có namespace → báo "Chưa có task nào đang theo dõi" rồi **DỪNG** (không tạo file rỗng).

### Bước 3 — Gom file đang sửa
- `git status --short` và `git diff --name-only` (chỉ đọc).

### Bước 4 — Ghi đè `session-handoff.md`

```markdown
---
dev: <DEV_ID>
saved: <YYYY-MM-DD HH:MM>
task: <từ current-task.md>
status: <từ current-task.md>
---

## Đang làm dở
- Task: <task>
- Bước hiện tại: <từ progress.md>

## File đang sửa (git status lúc handoff)
- <danh sách>

## Quyết định / context quan trọng
- <tóm tắt; tham chiếu decisions-log.md nếu có>

## Blockers
- <hoặc "_không có_">

## Việc tiếp theo
- [ ] <việc cụ thể>
```

> KHÔNG ghi secret, nội dung `.env`, log nguyên văn có dữ liệu nhạy cảm vào handoff.

### Bước 5 — Xác nhận
Báo ngắn: đã lưu handoff cho `<DEV_ID>`; gõ `/<lệnh-resume>` để tiếp tục.

## Ràng buộc
- **MUST** ghi đúng namespace `<STATE_DIR>/<DEV_ID>/`.
- **NEVER** sửa state của dev khác.
- Snapshot **ghi đè**, không lưu lịch sử.
