# CLAUDE.md — Hub điều phối của <PROJECT_NAME>

> Trang điều phối trung tâm. **Chỉ trỏ** đến kiến thức, agent, skill, playbook — không chứa nội dung chi tiết.
>
> <!-- Nếu file này được SINH/GHI ĐÈ bởi cơ chế sync: ghi rõ nguồn sự thật + kênh tuỳ biến, vd: -->
> ⚠️ **Nguồn sự thật:** `<nguồn sinh file>`. KHÔNG sửa trực tiếp — mọi tuỳ biến đặt ở `<KNOWLEDGE_DIR>/CLAUDE.md` (§2).
>
> Quy tắc **MUST / NEVER** ở §8 có độ ưu tiên CAO NHẤT.

---

## §1 — Kiến thức nền (tổ chức / chung)

### Nạp mọi phiên (`@`) — chỉ file nhỏ, ổn định
@<đường dẫn security-policy>
@<đường dẫn git-workflow>

### Tham chiếu — đọc khi cần (KHÔNG `@`)

| File | Đọc khi nào |
|---|---|
| `<convention tầng <LAYER>>` | Trước khi thiết kế / viết / review code tầng `<LAYER>` |
| `<api-convention>` | Khi thiết kế / viết API |
| `<non-functional-standards>` | Khi viết API trả danh sách, truy vấn DB, tác vụ dài *(chỉ khi có DB)* |
| `<design-standards>` | Khi sinh / review tài liệu thiết kế *(chỉ khi có tầng thiết kế)* |
| `<external-knowledge>` | Khi cần thông tin ngoài repo (service khác, thư viện dùng chung) *(chỉ khi có nguồn ngoài)* |

---

## §2 — Kiến thức dự án · GHI ĐÈ §1

> Ưu tiên: Dự án > Tổ chức. Dự án không đề cập → áp dụng Tổ chức.

@<KNOWLEDGE_DIR>/CLAUDE.md

---

## §3 — Routing

> Xác định **tầng** trước: thay đổi phía server → `backend`; giao diện/client → `frontend`. Không rõ → hỏi user 1 câu.

@<AGENT_DIR>/AGENTS.md

| Request | Tầng | MUST thực thi | NEVER |
|---|---|---|---|
| Thiết kế từ spec (chưa code) | theo phạm vi dự án | procedure `solution-architect` | nhảy thẳng vào code |
| Review tài liệu thiết kế | theo phạm vi dự án | procedure `architect-reviewer` | review code thay vì thiết kế |
| Implement / viết / tạo code production | `<LAYER>` | procedure `developer-<LAYER>` | viết code tự do không qua procedure |
| Debug / lỗi | `<LAYER>` | skill `debug-<LAYER>` | đoán nguyên nhân khi chưa reproduce |
| Review code / chuẩn bị MR | `<LAYER>` | procedure `code-reviewer-<LAYER>` | commit khi chưa review |
| Agent lệch quy ước repo (lặp lại) | — | skill `workflow-adapt` | tự nới guardrail |
| Hỏi đáp / giải thích / tìm kiếm | — | xử lý trực tiếp | — |

> Decision tree + cách thực thi: `<AGENT_DIR>/AGENTS.md` (mẫu `samples/rules/routing.md`).
> Coordinator **tự đọc procedure và thực thi inline** — không yêu cầu user chuyển agent thủ công.
> Bỏ dòng nào repo không có (vd không có tầng thiết kế → bỏ 2 dòng đầu).

---

## §4 — Skills

| Skill | Dùng khi |
|---|---|
| `task-state-init` | Bắt đầu implement tính năng mới |
| `progress-tracker` | Sau mỗi bước implement hoàn thành |
| `reuse-scan` | Trước khi tạo thành phần dùng chung mới |
| `code-review-<LAYER>` | Review nhanh trước commit |
| `debug-<LAYER>` | Debug có hệ thống (reproduce → isolate → diagnose → fix) |
| `decisions-relevance` | Rà kho ADR (lỗi thời / mồ côi / mâu thuẫn) *(khi có ADR)* |
| `workflow-adapt` | Điều chỉnh cách làm việc khi agent lệch quy ước repo |

---

## §5 — Playbooks

> Bật/tắt **chỉ ở một nơi**: `<file cấu hình> → playbooks.<tên>.enabled`. Chỉ áp dụng playbook `enabled: true`.

| Playbook | Knowledge (đọc khi bật) | Bật/tắt |
|---|---|---|
| `tdd` | `<thư mục playbook>/tdd/knowledge/...` | `playbooks.tdd.enabled` |

---

## §6 — Hook an toàn

> Hook chạy ở tầng harness. Chỉ liệt kê hook **đã cấu hình và kiểm chứng** — không mô tả chỉ dẫn markdown như enforcement.

- **SessionStart** (`startup|resume|clear`) → `<hook đầu phiên>` — chỉ nhắc (git hook path, nguồn tra cứu ngoài), luôn `exit 0`.
- **PreToolUse** (`Bash|Write|Edit`) → `"${CLAUDE_PROJECT_DIR:-.}/<HOOKS_DIR>/<file hook>"` (viết theo hướng dẫn hook) — chặn (stderr + `exit 2`): `<danh sách luật>`.
- **PostToolUse** (`.*`) → `<logger>` — ghi log tối thiểu, redact, không bao giờ chặn.
- **Git pre-commit** → quét secret staged, dùng **chung module luật** với hook PreToolUse.
- **Điều kiện hook chạy:** mở harness tại gốc repo · runtime hook có trên PATH · submodule chứa hook đã init · workspace đã được trust.

---

## §7 — State & bàn giao phiên

- Thư mục state: `<STATE_DIR>/<DEV_ID>/` (copy từ `<STATE_DIR>/_template/`). **Một giá trị duy nhất** ở mọi file.
- State được `<commit / gitignore>` — tài liệu phải khớp `.gitignore`.
- `/<lệnh-handoff>` lưu phiên · `/<lệnh-resume>` đọc lại và **hỏi trước khi code tiếp**.

---

## §8 — MUST / NEVER (ưu tiên cao nhất)

### MUST
- Nhận yêu cầu implement → **MUST** chạy `task-state-init` trước khi viết code.
- Chức năng đã có thiết kế ở `<KNOWLEDGE_DIR>/design/<MÃ>/` → **MUST** bám theo; cần lệch → cập nhật thiết kế trước.
- **MUST** ghi kế hoạch chi tiết vào `current-task.md` và chờ user duyệt — một cổng duyệt duy nhất.
- **MUST** tuân thủ mọi playbook đang bật (vd TDD → test trước).
- Viết endpoint / truy vấn DB → **MUST** đọc `<non-functional-standards>` **trước** khi lập kế hoạch; không đạt ngưỡng → dừng, chờ xác nhận.
- Sau khi viết/sửa code → **MUST** chạy `<TEST_CMD>` liên quan, dán output, xác nhận PASS.
- Sau mỗi bước implement → **MUST** chạy `progress-tracker`.
- Trước khi commit → **MUST** chạy `code-review-<LAYER>`.
- Debug → **MUST** reproduce trước khi nêu nguyên nhân.

### NEVER
- **NEVER** báo xong / tick DoD khi test chưa chạy hoặc còn fail.
- **NEVER** tạo thành phần dùng chung mới khi chưa có Reuse Report.
- **NEVER** suy đoán hợp đồng service/repo khác khi chưa tra nguồn — không tra được → `[cần xác nhận]`.
- **NEVER** sửa file bị ghi đè khi sync — tuỳ biến qua `<KNOWLEDGE_DIR>/CLAUDE.md`.
- **NEVER** `@` mọi tài liệu — chỉ `@` file cần ở hầu hết mọi phiên.
- **NEVER** tự commit / push / tạo MR khi chưa được yêu cầu.

---

## §9 — Tự điều chỉnh cách làm việc

- Hạ tầng agent phải khớp repo. Khi agent lệch quy ước repo lặp lại, lệnh trong hub hết đúng, hoặc quy tắc mâu thuẫn code → skill `workflow-adapt`.
- Điều chỉnh đi vào **kênh tuỳ biến** (`<KNOWLEDGE_DIR>/`), có bằng chứng, được duyệt, ghi dấu vết. Không nới guardrail ở §8.
