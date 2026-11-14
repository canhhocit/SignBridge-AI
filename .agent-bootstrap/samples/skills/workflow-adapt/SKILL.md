---
description: >
  Tự điều chỉnh cách làm việc của agent cho khớp thực tế của repo: phát hiện chỗ hạ tầng agent
  (hub, procedure, skill, hook, lệnh test) lệch với repo hoặc với yêu cầu lặp lại của người dùng,
  rồi đề xuất sửa ở kênh tuỳ biến. Kích hoạt khi người dùng sửa cùng một hành vi ≥2 lần, khi lệnh
  trong hồ sơ chạy lỗi vì đã đổi, khi quy tắc mâu thuẫn với code, hoặc khi nghe "điều chỉnh cách
  làm việc", "agent làm sai quy ước repo này", "cập nhật quy tắc agent", "adapt workflow".
  KHÔNG dùng để sửa code production (→ developer-<LAYER>) hay sửa file org-owned (→ đề xuất MR sang nguồn).
---

# Workflow Adapt — tự điều chỉnh cách làm việc

> Bản đồ tín hiệu → điều chỉnh: `<đường dẫn adaptation-rules>` (bản gốc ở `.agent-bootstrap/adapters/adaptation-rules.md`).
> Skill này **đề xuất và áp dụng sau khi được duyệt** — không tự nới guardrail, không sửa file do sync quản lý.

## MUST trigger

**MUST** thực thi khi một trong các điều kiện sau xảy ra:
- Người dùng sửa cùng một hành vi của agent **≥ 2 lần** trong phiên hoặc qua handoff.
- Lệnh build/test/lint ghi trong hub/hồ sơ chạy lỗi vì lệnh đã đổi (không phải lỗi code).
- Quy tắc trong hub/procedure mâu thuẫn với convention đang dùng thật trong repo.
- Hook chặn nhầm cùng một mẫu từ lần thứ 2.
- Repo đổi hình dạng: thêm/bỏ tầng, đổi framework test, thêm DB, thêm nguồn tra cứu ngoài.

**NEVER** sửa hạ tầng agent "cho tiện" giữa một task implement mà không dừng lại trình đề xuất.

## Quy trình

### Bước 1 — Ghi nhận lệch
- Mô tả lệch bằng 1–2 câu: hành vi hiện tại · hành vi repo/người dùng cần.
- Thu bằng chứng: path/section trong repo, lệnh + exit code, câu người dùng nói (trích ngắn).
- Không có bằng chứng → dừng, hỏi người dùng; **không** điều chỉnh theo phỏng đoán.

### Bước 2 — Định vị nguồn của hành vi
- Hành vi đến từ đâu: hub · procedure · skill · command · hook · cấu hình playbook · hồ sơ dự án.
- Xác định quyền sở hữu: file org-owned / do sync ghi đè → chỉ được **đề xuất MR sang nguồn**; file dự án → được sửa sau khi duyệt.

### Bước 3 — Chọn điều chỉnh nhỏ nhất
- Tra bảng tín hiệu trong `adaptation-rules` §2; không có dòng phù hợp → đề xuất dựa trên bằng chứng, ghi rõ là đề xuất mới.
- Ưu tiên thứ tự: sửa **giá trị** (lệnh, đường dẫn, ngưỡng) → sửa **một quy tắc** → thêm ngoại lệ có điều kiện → bỏ thành phần.
- Kiểm tra không chạm guardrail (cổng test, ranh giới an toàn, `[cần xác nhận]`). Chạm → dừng, nêu rủi ro, chờ quyết định.

### Bước 4 — Trình đề xuất và chờ duyệt
Trình bảng:

| Lệch | Bằng chứng | File sẽ sửa (chủ sở hữu) | Thay đổi | Ảnh hưởng | Đảo ngược |
|---|---|---|---|---|---|

### Bước 5 — Áp dụng và ghi dấu vết
- Sửa đúng file đã duyệt; mọi path/lệnh nhắc ở nhiều file → grep lại để sửa đồng bộ.
- Ghi một dòng vào mục 12 "Quyết định thích ứng" của hồ sơ dự án (hoặc `decisions-log.md` của dev nếu nhỏ; ADR nếu là quyết định kiến trúc lớn).
- Hook/cấu hình bị sửa → chạy lại fixture liên quan, dán kết quả.

## Output
- Bảng đề xuất (Bước 4) và danh sách file đã sửa sau khi duyệt.
- Một dòng dấu vết trong hồ sơ / decisions-log.

## Điều kiện dừng
- Thiếu bằng chứng, hoặc bằng chứng mâu thuẫn nhau.
- Điều chỉnh chạm guardrail hoặc file org-owned.
- Điều chỉnh làm thay đổi cấu hình đang hoạt động (hook, permission, CI) — cần duyệt riêng.

## Liên kết
- Bản đồ tín hiệu → điều chỉnh: `adaptation-rules.md`
- Quyết định kiến trúc lớn → ADR (`samples/knowledge/decisions/`)
- Nâng/hạ mức áp dụng → `adoption-tiers.md`
