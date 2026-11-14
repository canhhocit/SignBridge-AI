---
description: >
  Rà soát kho ADR của repo để bắt quyết định lỗi thời, mồ côi hoặc mâu thuẫn. Kích hoạt khi
  "rà ADR", "soi quyết định kiến trúc", "ADR nào còn hiệu lực"; khi architect-reviewer review
  thiết kế; hoặc khi sửa architecture.md. CHỈ phát hiện + gợi ý, KHÔNG tự sửa ADR.
---

# Decisions Relevance — rà soát ADR

> Chỉ tạo khi repo có kho ADR (`<KNOWLEDGE_DIR>/decisions/` hoặc thư mục tương đương đã có).

## Phạm vi
- Rà: `<thư mục ADR>/NNNN-*.md`. Bỏ qua: `_template.md`, `README.md`, file `_`-prefix.

## Quy trình

### Bước 1 — Thu thập
- Với mỗi ADR: tiêu đề, **Trạng thái**, **Ngày**, **Liên quan**.
- Quét chỗ trỏ tới ADR ở `architecture.md` và các ADR khác ("Liên quan", "Superseded by").

### Bước 2 — Soi
1. **Lỗi thời còn được tin dùng** — ADR `Deprecated`/`Superseded` vẫn được trỏ như căn cứ hiện hành.
2. **Link gãy / mồ côi** — trỏ tới ADR không tồn tại; thiếu link ngược giữa ADR thay thế và ADR bị thay.
3. **Mâu thuẫn** — ≥ 2 ADR `Accepted` cùng chủ đề, quyết định trái nhau.
4. **Trạng thái treo** — ADR `Proposed` lâu chưa chốt.
5. **Sai đánh số** — trùng `NNNN` (khoảng trống số **không** phải lỗi).
6. **Viết lại nội dung ADR đã `Accepted`** (Bối cảnh / Quyết định / Hệ quả bị sửa) thay vì tạo ADR mới + `Superseded`.
   **Không** coi là lỗi: mục `Sửa đổi YYYY-MM-DD` thêm cuối file kèm hàng `Sửa đổi` ở metadata, hoặc sửa đường dẫn trong `Liên quan` (theo `decisions/README.md`).
7. **Sửa đổi lệch metadata** — có mục `Sửa đổi …` cuối file mà thiếu hàng tương ứng ở metadata (hoặc ngược lại); sửa đổi đã đổi bản chất quyết định → gợi ý tách ADR mới.
8. **Đường dẫn chết trong `Liên quan`** — trỏ tới thư mục/tài liệu đã di chuyển.

### Bước 3 — Báo cáo

```text
## Kết quả rà ADR
### 🔴 Cần xử lý   - [ADR-NNNN + vị trí] mô tả + gợi ý
### 🟡 Cần theo dõi - …
### ✅ Nhất quán    - ADR còn hiệu lực
```

## Ràng buộc
- **NEVER** tự sửa ADR / `architecture.md`, **NEVER** tạo ADR mới (việc của `solution-architect`).
- Kho rỗng → báo "chưa có ADR để rà", không bịa vấn đề.
