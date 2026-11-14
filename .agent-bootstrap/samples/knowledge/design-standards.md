# Chuẩn viết tài liệu thiết kế kỹ thuật

> Đích gợi ý: `<KNOWLEDGE_DIR>/design-standards.md` (hoặc thư mục knowledge dùng chung của tổ chức).
> Dùng cho `solution-architect` (sinh) + `architect-reviewer` (soi). Chỉ tạo khi repo có tầng thiết kế.
> File này **chỉ trỏ** tới quy ước gốc (API, convention) — KHÔNG chép giá trị quy tắc vào đây (tránh trôi lệch).

## 1. Phạm vi theo tầng
- Thiết kế **chỉ tầng repo phụ trách** (xác định từ `architecture.md` + `src/`; không rõ → hỏi, không mặc định full-stack).
- Tầng ngoài phạm vi → một dòng "Ngoài phạm vi repo này" (+ trỏ repo/tài liệu liên quan nếu biết).

## 2. Một chức năng = tối đa 3 tài liệu (+ changelog khi sửa)

Thư mục `<KNOWLEDGE_DIR>/design/<MÃ>/`, copy từ `design/_template/`:

| Tài liệu | Trả lời | Bám nguồn |
|---|---|---|
| `API_Spec.md` | Hợp đồng ngoài: endpoint, request/response, lỗi, thay đổi schema | `<api-convention>` |
| `Component_Class_Design.md` | Cấu trúc trong: module, class, entity, DTO — chia phần theo tầng | `architecture.md`, `<convention tầng>` |
| `Processing_Flow.md` | Luồng chạy + ranh giới transaction | `architecture.md` |
| `CHANGELOG.md` | Lịch sử sửa — **chỉ tạo ở lần sửa đầu tiên sau baseline** | §8 |

> Đổi tên/số tài liệu theo quy ước sẵn có của repo nếu đã có — đây là khung mặc định.

**Gom thư mục khi số chức năng tăng:** `design/<CỤM>/<MÃ>/` theo cụm chức năng, và `design/SHARED/<MÃ>/` cho khung
kỹ thuật dùng chung nhiều cụm (tích hợp, ký số, danh mục…). Bố cục đang dùng ghi ở `design/README.md` — agent đọc
file đó để biết đặt thư mục mới ở đâu, không đoán.

**Tham chiếu tài liệu thiết kế phải chịu được việc di chuyển thư mục:**
- **NEVER** ghi đường dẫn tài liệu thiết kế vào comment code — tài liệu trỏ tới code, không ngược lại.
- Khi di chuyển/đổi tên thư mục thiết kế: grep mọi chỗ trỏ tới (knowledge, ADR, hub, `architecture.md`) và sửa trong cùng thay đổi.

## 3. Header chuẩn
Bảng: **Mã chức năng · Phạm vi tầng · Repo/stack · Quy ước áp dụng · Ràng buộc dữ liệu · Tác giả/Ngày/Phiên bản**.

## 4. Cổng tuân thủ (bắt buộc trước khi trình)
- **Mở lại file quy ước bản hiện hành** và soi **từng** endpoint/field — không dựa trí nhớ hay "thói quen REST".
- Tối thiểu: path & đặt tên (casing là chỗ hay sai nhất) · envelope/mã lỗi/phân trang · kiểu & định dạng field · tên DTO/class/tầng · thuật ngữ.
- Còn 1 điểm lệch → sửa ngay, chưa trình. Tra không thấy quy tắc → `[cần xác nhận]`.

## 5. Sơ đồ
- Mặc định **Mermaid** (`sequenceDiagram` cho luồng, `classDiagram` cho lớp) nếu nền tảng review hiển thị được; không thì ASCII.

## 6. `[cần xác nhận]` (bắt buộc)
- Mọi điểm spec yêu cầu mà chưa map 1-1 (cột, mã trạng thái, liên kết, quyền) → đánh dấu inline **và** gom danh sách đánh số cuối mỗi tài liệu.
- **Không đoán cho xong.**

## 7. Bất biến cho thao tác ghi
- Ranh giới transaction · khoá lạc quan khi sửa/xoá đồng thời · soft-delete vs hard-delete · audit cùng transaction · idempotency cho retry.
- Có DB → nêu **số truy vấn dự kiến** mỗi API so với ngưỡng (`non-functional-standards.md`).

## 8. Súc tích — tối ưu cho AI đọc
- **Một thông tin = một nơi**; tài liệu khác chỉ trỏ (dùng tiêu đề mục làm mỏ neo), không chép lại bảng field/JSON.
- Không lặp trong cùng tài liệu; bỏ diễn giải dài, chép spec nguyên văn, boilerplate chưa điền.
- Ưu tiên bảng / danh sách / code-fence.

## 9. Nhất quán chéo
- Trước khi thiết kế, quét thiết kế đã có (cùng module / dùng chung khái niệm). Trùng → trỏ/tái dùng.
- Xung đột không tự hoà giải → `[cần xác nhận]`, không đè thiết kế cũ.

## 10. Changelog thiết kế
- Bản sinh lần đầu = **baseline vX.Y**, không có changelog.
- Mỗi lần **sửa** sau baseline: thêm 1 entry **lên đầu** `CHANGELOG.md`: `## [vX.Y] — YYYY-MM-DD`, type (MAJOR/MINOR), tóm tắt 1 câu, danh sách thay đổi (vị trí · loại · cũ → mới · lý do), ảnh hưởng.
- **MAJOR** = phá vỡ hợp đồng (xoá/đổi endpoint, đổi shape DTO, đổi/bỏ mã lỗi). **MINOR** = thêm / sửa không phá vỡ / chốt `[cần xác nhận]`.
- Version entry mới nhất **khớp** header các tài liệu. Không sửa/xoá entry cũ.
