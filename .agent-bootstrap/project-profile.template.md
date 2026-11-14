# Hồ sơ dự án — <tên repo>

> **Cách dùng:** agent copy file này thành `project-profile.md` (cùng thư mục `.agent-bootstrap/`) và điền dần
> ở Bước 1–5 của prompt. Đây là **nguồn duy nhất** cho mọi `<PLACEHOLDER>` khi dùng mẫu trong `samples/`.
>
> - Mỗi giá trị **MUST** có cột "Bằng chứng" (path/section trong repo, hoặc "người dùng xác nhận").
> - Không xác định được → ghi `[cần xác nhận]`, KHÔNG đoán.
> - KHÔNG ghi secret, email, URL nội bộ, giá trị `.env`.

## 1. Dự án

| Mục | Giá trị | Bằng chứng |
|---|---|---|
| Tên | `[cần xác nhận]` | |
| Loại (service / web-app / mobile / library / data-pipeline / infra / monorepo / docs) | `[cần xác nhận]` | |
| Ngôn ngữ tài liệu sinh ra | `vi` | Quy tắc ngôn ngữ của prompt |

## 2. Harness (AI agent đang dùng)

| Mục | Giá trị | Bằng chứng |
|---|---|---|
| Harness chính (Claude Code / Codex / Cursor / Copilot / Gemini CLI / khác) | `[cần xác nhận]` | |
| Harness phụ (nếu có) | | |
| File hub chỉ dẫn | `[cần xác nhận]` | `adapters/harness-matrix.md` |
| Hỗ trợ agent/sub-agent | có / không / không rõ | |
| Hỗ trợ skill | có / không / không rõ | |
| Hỗ trợ command do user gọi | có / không / không rõ | |
| Hỗ trợ hook | có / không / không rõ | |
| Điều kiện nạp cấu hình (mở tại gốc / trust workspace / khác) | | `adapters/harness-matrix.md` |

## 3. Mức áp dụng

| Mục | Giá trị | Lý do |
|---|---|---|
| Mức (`minimal` / `standard` / `full`) | `[cần xác nhận]` | quy mô đội · rủi ro thay đổi · hạ tầng có sẵn (`adapters/adoption-tiers.md`) |

## 4. Tầng (layer) — mỗi tầng một dòng

| `id` (`<LAYER>`) | Thư mục | Ngôn ngữ | Lệnh build | Lệnh test (`<TEST_CMD>`) | Lệnh lint | Tài liệu convention | Bằng chứng |
|---|---|---|---|---|---|---|---|
| `[cần xác nhận]` | | | | | không có / … | | |

> Lệnh chỉ ghi khi đã xác nhận từ manifest/script/README/CI; lệnh suy luận ghi kèm `[suy luận]`.

## 5. Đường dẫn

| Placeholder | Giá trị | Bằng chứng |
|---|---|---|
| `<AGENT_DIR>` (vd `.claude`) | `[cần xác nhận]` | |
| `<KNOWLEDGE_DIR>` (vd `docs/agent`) | `[cần xác nhận]` | |
| `<STATE_DIR>` — **một giá trị**, dùng nhất quán mọi file | `[cần xác nhận]` | |
| `<HOOKS_DIR>` | `[cần xác nhận]` / không dùng hook | |

## 6. Quyền sở hữu & đồng bộ

| Mục | Giá trị | Bằng chứng |
|---|---|---|
| File do generator/sync quản lý (KHÔNG sửa trực tiếp) | | |
| Kênh tuỳ biến của dự án | `[cần xác nhận]` | |
| Submodule (đường dẫn + trạng thái init) | | `git submodule status` |

## 7. State & bàn giao phiên

| Mục | Giá trị | Bằng chứng |
|---|---|---|
| Dùng state task | có / không | |
| Cách đặt `<DEV_ID>` (alias cấu hình / `local-dev` / khác — tránh suy từ email) | | |
| State được commit hay gitignore | commit / gitignore | `.gitignore` |
| Tên command lưu / mở lại phiên (`<lệnh-handoff>`, `<lệnh-resume>`) | | tránh trùng lệnh built-in của harness |

## 8. Git & review

| Mục | Giá trị | Bằng chứng |
|---|---|---|
| Nhánh mặc định | `[cần xác nhận]` | |
| Nhánh được bảo vệ | | |
| Quy ước tên nhánh | không có / … | |
| Quy ước commit | không có / … | |
| Nền tảng review (GitLab / GitHub / Azure DevOps / khác) | | |

## 9. Playbook & hook

| Mục | Giá trị | Bằng chứng |
|---|---|---|
| Playbook đang bật + mức enforcement | không có / `tdd: monitor-only` / … | |
| Runtime cho hook (node / python / không dùng hook) | `[cần xác nhận]` | `adapters/stack-hints.md` §4 |

## 10. CI

| Mục | Giá trị | Bằng chứng |
|---|---|---|
| Có CI trong repo | có / không thấy trong repo | |
| File CI | | |

## 11. Thiết kế, ADR, phi chức năng, tra cứu ngoài

| Mục | Giá trị | Bằng chứng |
|---|---|---|
| Có quy trình thiết kế trước khi code | có / không | |
| Thư mục spec nghiệp vụ / thiết kế | không có / … | |
| `<design-standards>` | không áp dụng / đường dẫn | |
| `<thư mục ADR>` (đã có hay sẽ tạo) | không áp dụng / … | |
| Tầng có DB/ORM | có / không | manifest, cấu hình datasource |
| `<non-functional-standards>` + ngưỡng `<N_DETAIL>`/`<N_LIST>`/`<N_WRITE>` | không áp dụng / repo đã có ở … / mặc định đề xuất (chờ đội chốt) | |
| Nguồn tra cứu ngoài repo (MCP, wiki, catalog) — **chỉ tên logic, không URL/token** | không có / … | |
| `<external-knowledge>` | không áp dụng / đường dẫn | |

## 12. Quyết định thích ứng

> Mỗi lần mẫu được điều chỉnh/bỏ cho khớp repo (Bước 5 và skill `workflow-adapt`) — ghi 1 dòng.
> Bảng tín hiệu: `adapters/adaptation-rules.md`.

| Ngày | Tín hiệu | Bằng chứng | Điều chỉnh | Lý do | Đảo ngược bằng |
|---|---|---|---|---|---|
| | | | | | |

## 13. Còn chờ xác nhận

- [ ] <liệt kê mọi mục còn `[cần xác nhận]` để hỏi người dùng một lần>
