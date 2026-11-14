# Kiến thức dự án — <PROJECT_NAME>

> Cổng vào ngữ cảnh **đặc thù** của dự án; hub gốc trỏ tới file này. **Khi mâu thuẫn với kiến thức tổ chức, nội dung ở đây ghi đè** — khai báo mục ghi đè cụ thể ở `architecture.md` §"Quy ước đặc thù".

> [!IMPORTANT]
> `@path` = nạp vào context **mọi phiên** (tốn token, dễ loãng). **Chỉ `@` file cần ở hầu hết mọi phiên**
> (kiến trúc, thuật ngữ). Tài liệu theo tình huống → liệt kê ở §2, KHÔNG `@`. Nghi ngờ → cho vào §2.

## 1. Auto-load (`@`)

@./architecture.md
@./domain-glossary.md

---

## 2. Tham chiếu — đọc khi cần (KHÔNG `@`)

> Mục lục điều hướng. Mỗi dòng chỉ ghi **đường dẫn + khi nào đọc**; chi tiết nằm trong file được trỏ tới.

### 2.1 Bản đồ nhanh

| Tình huống | Đọc |
|---|---|
| Thiết kế chức năng `<MÃ>` | Spec nghiệp vụ (§2.2) → thiết kế đã có cùng module (§2.3) |
| Code chức năng `<MÃ>` | Thiết kế `design/<MÃ>/` (§2.3) — **MUST bám** |
| Tích hợp thư viện dùng chung | Guide (§2.4) |

### 2.2 Đặc tả nghiệp vụ

#### `<MÃ_CHỨC_NĂNG>` — <tên chức năng>

| Đường dẫn | Đọc khi nào |
|---|---|
| `business-spec/<MÃ>/<file spec>.md` | Khi làm bất kỳ màn nào của `<MÃ>` — spec chính |
| `business-spec/<MÃ>/CHANGELOG.md` | Khi cần biết spec vừa đổi gì |

### 2.3 Thiết kế kỹ thuật

#### `<MÃ_CHỨC_NĂNG>`

| Đường dẫn | Đọc khi nào |
|---|---|
| `design/<MÃ>/API_Spec.md` | Khi làm API — hợp đồng, DTO, mã lỗi |
| `design/<MÃ>/Component_Class_Design.md` | Khi code — sơ đồ lớp, entity |
| `design/<MÃ>/Processing_Flow.md` | Khi cần luồng xử lý + ranh giới transaction |

### 2.4 Tích hợp thư viện dùng chung

| Đường dẫn | Đọc khi nào |
|---|---|
| `guides/<tên guide>.md` | Khi làm chức năng cần thư viện `<tên>` |

---

## 3. Bảo trì file này

- Chức năng mới → thêm một cụm `####` + bảng ở §2.2 / §2.3. Tất cả **KHÔNG `@`**.
- Thư mục thiết kế được gom theo cụm (`design/<CỤM>/<MÃ>/`, `design/SHARED/<MÃ>/`) → đường dẫn ở §2.3 ghi đầy đủ theo cụm; di chuyển thư mục thì sửa file này trong cùng thay đổi.
- Chỉ thêm `@` ở §1 khi file thực sự cần ở hầu hết mọi phiên.
