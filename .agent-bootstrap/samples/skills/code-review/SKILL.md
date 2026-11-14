---
description: >
  Review nhanh code tầng <LAYER> theo 5 chiều (Security, Performance, Correctness, Style,
  Reuse & Duplication) trong phiên, TRƯỚC khi commit. Kích hoạt khi implement xong, hoặc khi nghe
  "review", "check code", "kiểm tra code" cho thay đổi tầng <LAYER>. Review toàn diện trước MR →
  agent code-reviewer-<LAYER>. Tầng khác → code-review-<tầng khác>.
---

# Code Review — tầng <LAYER> (nhanh, trước commit)

> Tiêu chí cụ thể lấy từ knowledge dự án. Skill chỉ định nghĩa 5 chiều — cùng bộ chiều với
> agent `code-reviewer-<LAYER>` (`samples/agents/code-reviewer.md`), bản rút gọn để chạy trong phiên.

## MUST trigger
- Implement xong thay đổi tầng `<LAYER>` — **trước khi commit**.

**NEVER** commit khi chưa chạy đủ 5 chiều.

## Quy trình
1. **Phạm vi:** diff nào? Người dùng đã chỉ định → bắt đầu luôn.
2. **5 chiều:**
   - **Security** — secret, log lộ dữ liệu, truy cập dữ liệu tham số hoá, phân quyền đúng `<security tầng>`.
   - **Performance** — ngưỡng số truy vấn `<non-functional-standards>` *(khi có DB)*, N+1, phân trang, I/O trong vòng lặp.
   - **Correctness** — khớp spec/thiết kế, null/biên, lỗi, transaction, test đã chạy PASS.
   - **Style** — `<convention tầng>`, ranh giới module theo `architecture.md`.
   - **Reuse** — Reuse Report có chưa (khi tạo thành phần dùng chung), trùng với thứ đã có, logic lặp.
3. **Phân loại:** CRITICAL (security hole, mất dữ liệu, logic sai) · MAJOR (hiệu năng, bảo trì) · MINOR (style).
4. **Đề xuất sửa:** mỗi CRITICAL/MAJOR kèm đoạn code gợi ý + `file:line`.

## Liên kết
- Review trước MR → agent `code-reviewer-<LAYER>`
