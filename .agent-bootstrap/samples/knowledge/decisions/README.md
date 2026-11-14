# Architecture Decision Records (ADR)

> Đích gợi ý: `<KNOWLEDGE_DIR>/decisions/README.md`. Repo đã có thư mục ADR/decision record → **dùng cái đã có**, không tạo thư mục thứ hai.

## Cách dùng
1. Copy `_template.md` → `NNNN-tieu-de-kebab-case.md`.
2. `NNNN` = 4 chữ số, tăng dần, **không tái sử dụng** kể cả khi ADR bị bỏ (khoảng trống số là bình thường).
3. Vòng đời: `Proposed` → `Accepted` (khi chốt qua MR) → `Deprecated` / `Superseded by ADR-MMMM`.
   **Không viết lại** Bối cảnh / Quyết định / Hệ quả của ADR đã `Accepted`. Thay đổi sau đó chia 3 loại:

   | Loại thay đổi | Cách làm |
   |---|---|
   | Đảo ngược / thay thế quyết định | ADR mới + ADR cũ `Superseded by …`, hai bên trỏ nhau |
   | **Bổ sung** không đảo ngược (làm rõ ca biên, thêm ràng buộc, chốt điểm còn mở) | Thêm hàng `Sửa đổi` vào bảng metadata (ngày + tóm tắt 1 dòng) **và** mục `## Sửa đổi YYYY-MM-DD — <chủ đề>` **cuối file** (Bối cảnh · Quyết định bổ sung · Phương án loại · Hệ quả). Chỉ thêm, không sửa mục sửa đổi cũ |
   | Bảo trì metadata (đường dẫn trong `Liên quan` đổi do di chuyển thư mục, thêm ADR liên quan) | Sửa trực tiếp hàng metadata |

   Bổ sung đã lớn tới mức đổi bản chất quyết định → dùng cách 1, không chồng thêm sửa đổi.
4. ADR hiệu lực được trỏ từ `architecture.md` (mục quyết định kiến trúc).

## Ngưỡng
- **ADR** = quyết định có đánh đổi, ảnh hưởng lâu dài hoặc xuyên chức năng (cơ chế auth, chiến lược migration, ranh giới service, pattern chính).
- Quyết định nhẹ trong phiên → `<STATE_DIR>/<DEV_ID>/decisions-log.md`, **không** lạm ADR.

## Ai làm gì
- Tạo ADR `Proposed`: `solution-architect` (hoặc dev khi chốt quyết định lớn).
- Soi ADR thiếu / lỗi thời / mâu thuẫn: `architect-reviewer` + skill `decisions-relevance`.
- Chuyển `Accepted`: qua MR, người duyệt quyết định — agent chỉ khuyến nghị.
