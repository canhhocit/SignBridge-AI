# Tra cứu tri thức ngoài repo (MCP / wiki / catalog)

> Đích gợi ý: `<KNOWLEDGE_DIR>/external-knowledge.md`. **Chỉ tạo khi repo/đội có nguồn tra cứu ngoài**
> (MCP server, wiki nội bộ, catalog API). Không có → bỏ file này; hợp đồng service khác ghi `[cần xác nhận]`.
> KHÔNG ghi URL, token, tên server nội bộ vào file version-control — chỉ ghi **tên logic** + nơi xin cấu hình.

## 1. Nguồn có sẵn

| Tên logic | Nội dung | Dùng cho |
|---|---|---|
| `<nguồn tài liệu>` | Tài liệu/spec các repo khác | Đặc tả nghiệp vụ, thiết kế ngoài repo |
| `<nguồn đồ thị code>` | Class, hàm, API, lời gọi | Ai gọi ai, ảnh hưởng khi sửa, controller của một API |

Danh sách nguồn **bắt buộc** (máy đọc, không chứa URL/token) để hook đầu phiên đối chiếu: `<file manifest>` (vd JSON liệt kê tên server).

## 2. Quy tắc

### Khi nào dùng
- **MUST** tra nguồn ngoài khi thông tin **nằm ngoài repo đang mở**: hợp đồng API / DTO / mã lỗi của service khác, nơi gọi tới endpoint của repo, thư viện dùng chung, luồng chéo repo.
- **MUST** dùng **source local** cho repo đang mở — nguồn ngoài có thể trễ hoặc khác nhánh. Lệch nhau → local đúng; ghi rõ độ lệch nếu ảnh hưởng kết luận.
- **NEVER** suy đoán hợp đồng service khác khi chưa tra ("chắc giống bên này" là lỗi).

### Dẫn chứng
- **MUST** dẫn chứng kết luận từ nguồn ngoài bằng `repo` + `path:line` (hoặc định danh tương đương).
- Khẳng định về **code** xác nhận bằng code/đồ thị, không chỉ bằng tài liệu thiết kế (có thể đã cũ).
- **NEVER** đưa secret, token, dữ liệu nhạy cảm vào câu tra cứu (có thể bị ghi log phía server).

### Khi nguồn vắng hoặc lỗi
- **MUST** báo người dùng **ngay khi cần mà không tra được** + trỏ hướng dẫn cài đặt.
- **MUST** làm tiếp bằng nguồn local, ghi rõ phần **chưa kiểm chứng**.
- **NEVER** chặn công việc chỉ vì thiếu nguồn ngoài; **NEVER** lấp chỗ trống bằng phỏng đoán trình bày như sự thật.

## 3. Cài đặt (mỗi máy dev)
- Cấu hình theo scope **người dùng** (token cá nhân không đóng gói vào repo). Lệnh cụ thể xin quản trị nguồn.
- Hook đầu phiên (tuỳ chọn) chỉ **kiểm đã đăng ký** (offline) và **nhắc** — không chặn, không kiểm kết nối (xem `samples/hooks/README.md` §8).
- Quyền gọi tool **chỉ đọc** của nguồn ngoài có thể cho sẵn trong cấu hình chia sẻ của harness — thay đổi permission là **cấu hình đang hoạt động → cần duyệt**.
  Liệt kê **tường minh từng tool chỉ đọc** (không wildcard theo server), để tool ghi/xoá nếu server thêm sau này vẫn phải hỏi.

## 4. Nối quy tắc vào procedure
Thêm 1 dòng "phụ thuộc ngoài repo → tra nguồn ngoài; vắng → báo + ghi chưa kiểm chứng" vào bước đọc context của:
`developer-<LAYER>` (Bước 1), `solution-architect` (Bước 1), `debug-<LAYER>` (Bước Isolate), và một MUST/NEVER ở hub.
