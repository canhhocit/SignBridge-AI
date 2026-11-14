# AGENTS.md — Routing & cách coordinator thực thi procedure

> Đích gợi ý: `<AGENT_DIR>/AGENTS.md` (hoặc mục §3 của hub nếu muốn gộp). Hub chỉ **trỏ** tới file này.
> Phiên mặc định = **coordinator**: nhận request → chọn procedure → **tự đọc và thực thi inline**,
> không bắt người dùng chuyển agent thủ công. Harness không có sub-agent → vẫn dùng file này (fallback `harness-matrix.md` §2).

## §1 — Decision tree

> **Bước 0 — Xác định tầng** theo **thư mục / loại thay đổi** (mục 4 hồ sơ dự án), không đoán từ một tên file.
> Không rõ → hỏi người dùng **1 câu**. Repo một tầng → bỏ bước này và bỏ hậu tố tầng.

```text
Nhận request
├── Thiết kế từ spec (chưa code)             → procedure solution-architect      [chỉ khi repo có tầng thiết kế]
├── Review tài liệu thiết kế                  → procedure architect-reviewer      [chỉ khi repo có tầng thiết kế]
├── Implement / viết / tạo / sửa code         → task-state-init → procedure developer-<LAYER>
├── Debug / lỗi / không chạy                  → skill debug-<LAYER>
├── Review code / chuẩn bị MR                 → procedure code-reviewer-<LAYER>
├── Agent làm lệch quy ước repo (lặp lại)     → skill workflow-adapt
└── Hỏi đáp / giải thích / tìm kiếm           → xử lý trực tiếp
```

## §2 — Bảng procedure

| Procedure / skill | Trigger | Output | Không làm |
|---|---|---|---|
| `solution-architect` | "thiết kế [X]", "design API/luồng" | Tài liệu `<KNOWLEDGE_DIR>/design/<MÃ>/` | Viết code |
| `architect-reviewer` | "review thiết kế", "soi design" | CRITICAL/MAJOR/MINOR | Sửa tài liệu, review code |
| `developer-<LAYER>` | "implement/viết/tạo/build/thêm [X]" | Code + test PASS + state cập nhật | Code khi chưa duyệt kế hoạch |
| `code-reviewer-<LAYER>` | "review code", "tạo MR" | CRITICAL/MAJOR/MINOR có `file:line` | Tự sửa / commit |
| `debug-<LAYER>` | "lỗi", "bug", "exception" | Root cause + fix + test | Đoán khi chưa reproduce |
| `workflow-adapt` | Người dùng sửa cùng hành vi ≥ 2 lần; lệnh/quy tắc lệch repo | Đề xuất điều chỉnh có bằng chứng | Nới guardrail, sửa file org-owned |

## §3 — Khi nào xử lý trực tiếp

| Loại request | Trực tiếp? |
|---|---|
| Giải thích code, tra cứu, tóm tắt, so sánh | ✅ |
| Đọc log / error message | ✅ — nhưng sửa lỗi phải qua `debug-<LAYER>` |
| Viết / sửa code production | ✗ → `developer-<LAYER>` |
| Review trước merge | ✗ → `code-reviewer-<LAYER>` |

## §4 — Cách thực thi một procedure

1. Báo ngắn: "Bắt đầu `<procedure>` (tầng: `<LAYER>`) — Bước 1: đọc context…".
2. Đọc file procedure **khi cần** (không nạp sẵn mọi procedure vào context).
3. Thực thi tuần tự, không bỏ bước; gặp tín hiệu dừng → dừng và hỏi.
4. Sau mỗi bước implement → `progress-tracker`.

**NEVER** yêu cầu người dùng chuyển agent trong UI; **NEVER** bỏ bước vì "nhanh hơn".
