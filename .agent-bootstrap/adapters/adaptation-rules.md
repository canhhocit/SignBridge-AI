# Bản đồ thích ứng — tín hiệu dự án → cách điều chỉnh hạ tầng agent

> Mẫu trong `samples/` mô tả một bộ hạ tầng **đầy đủ** rút từ repo mẫu. Repo đích hiếm khi giống hệt.
> File này cho agent biết: **thấy tín hiệu nào trong repo → điều chỉnh thành phần nào, theo hướng nào**.
> Dùng ở Bước 4–5 của prompt (lập blueprint) và mỗi lần chạy skill `workflow-adapt` (sau bootstrap).
>
> Mỗi quyết định thích ứng **MUST** ghi vào mục 12 của `project-profile.md`: tín hiệu · bằng chứng · điều chỉnh · lý do.

## 1. Nguyên tắc

1. **Bằng chứng trước, mẫu sau.** Mẫu chỉ là điểm khởi đầu. Repo có quy ước khác → theo repo; không "chuẩn hoá" repo theo mẫu.
2. **Bỏ được nghi thức, không bỏ được guardrail.** Có thể bỏ/gộp agent, skill, bước duyệt cho phù hợp quy mô. **Không** bỏ:
   cổng "không báo pass khi chưa chạy test", ranh giới an toàn (secret, thao tác phá huỷ), quy tắc "không đoán — ghi `[cần xác nhận]`".
3. **Thu hẹp, không suy rộng.** Không rõ tín hiệu → chọn cấu hình nhỏ hơn + ghi `[cần xác nhận]`; nâng sau (`adoption-tiers.md`).
4. **Một nguồn cho mỗi sự thật.** Thích ứng bằng cách sửa giá trị ở **kênh tuỳ biến** (hồ sơ, knowledge dự án), không nhân bản mẫu rồi sửa lệch nhau.
5. **Điều chỉnh có dấu vết.** Mọi điều chỉnh có thể đảo ngược và đọc lại được lý do (mục 12 của hồ sơ hoặc ADR nếu là quyết định lớn).

## 2. Bảng tín hiệu → điều chỉnh

### 2.1 Hình dạng repo

| Tín hiệu (bằng chứng) | Điều chỉnh |
|---|---|
| Một tầng duy nhất | Bỏ hậu tố tầng (`developer`, `code-reviewer`, `debug`…); bỏ bước "xác định tầng" trong routing |
| Nhiều tầng / monorepo | Mỗi tầng một dòng ở mục 4 hồ sơ; procedure/skill có hậu tố theo cột `id`; routing theo **thư mục**, không theo đuôi file |
| Tầng không phải backend/frontend (`data`, `infra`, `mobile`) | Đặt tên theo tầng thật; viết lại checklist review/debug theo rủi ro của tầng đó (vd `infra`: drift, quyền, chi phí; `data`: idempotent, backfill, schema) |
| Thư viện / SDK (không có app chạy) | Review nhấn **public API & tương thích ngược**; `reuse-scan` quét thêm API công khai đã phát hành; thêm cổng changelog/semver nếu repo có |
| Repo chỉ tài liệu | Chỉ hub + quy tắc ngôn ngữ + checklist review tài liệu; không TDD, không hook code |
| Prototype / spike | Mức `minimal`; không playbook; giữ cổng test nếu có test |

### 2.2 Kiểm thử & chất lượng

| Tín hiệu | Điều chỉnh |
|---|---|
| Có test + lệnh test xác nhận được | Cổng test bắt buộc ở `developer-*` + `progress-tracker` |
| Có test nhưng không xác nhận được lệnh | Ghi `[cần xác nhận]`; cổng test vẫn giữ, hỏi người dùng lệnh thật |
| Không có test | Không bật TDD; cổng test đổi thành "nêu cách kiểm chứng thủ công + ghi giới hạn"; đề xuất thêm test ở Next actions |
| Quy ước vị trí test khác mẫu (vd test cạnh source, thư mục `spec/`) | Cập nhật ánh xạ source → test của playbook guard **trước khi bật**; fixture guard dùng đường dẫn thật của repo |
| Có lint/format/static analysis | Đưa vào cổng "sau sửa" với lệnh đã xác nhận; không thêm hook format toàn repo |
| CI đã chạy secret scan / lint | Không tạo hook lặp lại CI; hook harness chỉ phủ phần CI không bắt được lúc agent ghi file |

### 2.3 Dữ liệu & phi chức năng

| Tín hiệu | Điều chỉnh |
|---|---|
| Có ORM/DB/migration | Bật chuẩn phi chức năng (`samples/knowledge/non-functional-standards.md`): phân trang, ngưỡng số truy vấn, index; cổng **dừng lúc thiết kế** khi không đạt ngưỡng |
| Không có DB | Bỏ mục truy vấn; giữ phần phù hợp (timeout I/O ngoài, tác vụ dài tách bất đồng bộ) nếu có gọi hệ thống ngoài |
| Có migration framework | Agent soạn migration nhưng **không chạy**; review migration theo checklist rollback |
| Ngưỡng hiệu năng đã có trong repo | Trỏ tới ngưỡng đó; **không** áp ngưỡng mặc định của mẫu |

### 2.4 Quy trình đội

| Tín hiệu | Điều chỉnh |
|---|---|
| Có spec nghiệp vụ / thiết kế trước khi code | Bật tầng thiết kế (`solution-architect`, `architect-reviewer`) + ADR |
| Không có quy trình thiết kế | Bỏ tầng thiết kế; giữ cổng duyệt kế hoạch trong `developer-*` |
| Có thư mục ADR / decision record | Dùng đúng thư mục + định dạng sẵn có; skill `decisions-relevance` trỏ vào đó |
| ADR đã `Accepted` được bổ sung bằng mục "Sửa đổi" có ngày (thực hành thật trong repo) | Ghi thực hành đó vào README của thư mục ADR nếu chưa có; `decisions-relevance` không coi là vi phạm |
| Nhiều chức năng đã có thiết kế, thư mục được gom theo cụm | Theo bố cục ở `design/README.md`; agent thiết kế đặt thư mục mới theo đó |
| Quy ước nhánh/commit thành văn | Chép **đường dẫn** quy ước vào hub, không chép nội dung |
| Không có quy ước commit | Suy từ `git log` gần đây, ghi `[suy luận]`, hỏi xác nhận |
| Đội 1–3 người | Gộp `code-reviewer` vào skill `code-review`; bỏ state theo namespace (một thư mục state) |
| Đội lớn / nhiều người cùng nhánh | State theo namespace dev; quyết định state commit hay gitignore và ghi khớp `.gitignore` |

### 2.5 Tri thức & công cụ

| Tín hiệu | Điều chỉnh |
|---|---|
| Có repo dùng chung chuẩn tổ chức (submodule/package) | Theo mô hình repo dùng chung (`samples/shared-repo/README.md`): file org-owned không sửa, tuỳ biến qua kênh dự án |
| Có thư viện dùng chung nội bộ | `reuse-scan` Bước 0 xác định thư viện **từ manifest**, không từ tài liệu |
| Có nguồn tra cứu ngoài repo (MCP server, wiki, catalog API) | Thêm quy tắc tra cứu ngoài (`samples/knowledge/external-knowledge.md`); hook đầu phiên chỉ **nhắc** khi thiếu, không chặn |
| Không có nguồn ngoài | Bỏ phần tra cứu ngoài; hợp đồng service khác → `[cần xác nhận]` |
| Harness không có hook / sub-agent / skill | Dùng fallback `harness-matrix.md` §2; không mô tả chỉ dẫn markdown như enforcement |
| Runtime hook không chắc có trên mọi máy | Ưu tiên git hook + CI; hook harness là tuỳ chọn, ghi điều kiện chạy |

### 2.6 Rủi ro & tuân thủ

| Tín hiệu | Điều chỉnh |
|---|---|
| Dữ liệu nhạy cảm / tài chính / y tế | Mức `full`; thêm chiều security vào mọi review; log hook tối thiểu + redact |
| Có quy định bảo mật thành văn | Hub `@` file đó (nếu ngắn) hoặc trỏ "đọc khi review" |
| Repo công khai | Không ghi tên nội bộ/URL/tên người vào bất kỳ file agent nào |

## 3. Thích ứng sau bootstrap (vòng tự điều chỉnh)

Hạ tầng agent không đứng yên. Repo đổi stack, đội đổi quy trình, agent gặp chỗ mẫu không khớp. Vòng dưới
giữ hạ tầng **khớp thực tế** mà không trôi dạt:

```text
Phát hiện lệch ──► Xác minh bằng chứng ──► Đề xuất điều chỉnh ──► Người dùng duyệt ──► Sửa ở kênh tuỳ biến ──► Ghi dấu vết
```

**Tín hiệu kích hoạt** (skill `workflow-adapt` bắt các tín hiệu này):

- Người dùng sửa cùng một hành vi của agent **≥ 2 lần** ("đừng…", "ở repo này thì…").
- Lệnh trong hồ sơ/hub chạy lỗi vì lệnh đã đổi (manifest, script, CI mới).
- Quy tắc trong hub mâu thuẫn với code/convention đang dùng thật.
- Hook chặn nhầm lặp lại cùng một mẫu.
- Thành phần không ai dùng sau một thời gian (skill không bao giờ kích hoạt, command không ai gọi).
- Repo thêm/bỏ tầng, đổi framework test, thêm DB, thêm nguồn tra cứu ngoài.

**Giới hạn:**

- Không tự sửa file org-owned / do sync quản lý — đề xuất MR sang nguồn.
- Không tự nới guardrail (mục 1.2). Nới enforcement hook (`block` → `warn`) cần duyệt + lý do.
- Một lần điều chỉnh = một thay đổi nhỏ, có lý do, đảo ngược được.
