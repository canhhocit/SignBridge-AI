# samples/ — Mẫu hạ tầng agent đã khái quát hoá

> Mẫu rút từ thực hành đã chạy ở một repo, rồi khái quát hoá để dùng cho **mọi stack và mọi harness**.
> Đã bỏ dữ kiện nghiệp vụ, tên tổ chức, URL nội bộ và định danh cá nhân.
> Dùng làm **khung định dạng** ở Bước 6–7 của `../UNIVERSAL_AGENT_BOOTSTRAP_PROMPT.md` — KHÔNG copy nguyên vào repo đích.
> Toàn bộ là markdown: hook chỉ có **đặc tả + pseudocode + bảng fixture**; agent tự viết code bằng runtime của repo đích.

## Cách dùng

1. Chọn mẫu theo mức áp dụng (`../adapters/adoption-tiers.md`) và kế hoạch đã được duyệt — không bắt buộc dùng hết.
2. Xác định vị trí file theo harness đích (`../adapters/harness-matrix.md`). Mẫu viết theo bố cục Claude Code
   (`.claude/agents`, `.claude/skills`…); harness không có tính năng tương ứng → dùng fallback §2 của bảng đó.
3. Thay mọi `<PLACEHOLDER>` bằng giá trị trong `../project-profile.md` (bảng dưới). Không xác định được →
   `[cần xác nhận]`, KHÔNG đoán.
4. Xác minh schema harness đích (frontmatter, hook event, cấu hình) trước khi tạo file thực thi.
5. Viết theo **Quy tắc ngôn ngữ** của prompt: tiếng Việt, giữ tiếng Anh cho từ khoá/thuật ngữ/định danh.

## Danh mục

| Mẫu | Đích gợi ý (Claude Code — harness khác xem bảng ánh xạ) | Nội dung |
|---|---|---|
**Quy tắc & routing**

| Mẫu | Đích gợi ý | Nội dung |
|---|---|---|
| [`rules/hub.md`](rules/hub.md) | `CLAUDE.md` / `AGENTS.md` / file hub của harness | Hub ngắn: ưu tiên, routing, skill, playbook, hook, state, MUST/NEVER, tự điều chỉnh |
| [`rules/routing.md`](rules/routing.md) | `<AGENT_DIR>/AGENTS.md` | Decision tree + cách coordinator thực thi procedure inline |
| [`rules/project-knowledge.md`](rules/project-knowledge.md) | `<KNOWLEDGE_DIR>/CLAUDE.md` (kênh tuỳ biến) | Tách context nạp mọi phiên với tham chiếu đọc khi cần |

**Agent (procedure)**

| Mẫu | Đích gợi ý | Nội dung |
|---|---|---|
| [`agents/developer.md`](agents/developer.md) | `<AGENT_DIR>/agents/developer-<LAYER>.md` | Implement: context → reuse → kế hoạch + cổng duyệt → code theo playbook → cổng test |
| [`agents/code-reviewer.md`](agents/code-reviewer.md) | `<AGENT_DIR>/agents/code-reviewer-<LAYER>.md` | Review diff 5 chiều trước MR, findings có `file:line` |
| [`agents/solution-architect.md`](agents/solution-architect.md) | `<AGENT_DIR>/agents/solution-architect.md` | Thiết kế từ spec trước khi code *(chỉ khi có tầng thiết kế)* |
| [`agents/architect-reviewer.md`](agents/architect-reviewer.md) | `<AGENT_DIR>/agents/architect-reviewer.md` | Review tài liệu thiết kế + ADR *(chỉ khi có tầng thiết kế)* |

**Skill**

| Mẫu | Nội dung |
|---|---|
| [`skills/skill-template/`](skills/skill-template/SKILL.md) | Khung trống: trigger, quy trình, output, điều kiện dừng |
| [`skills/task-state-init/`](skills/task-state-init/SKILL.md) | Khởi tạo state task (ý định + DoD + bước tổng quan) |
| [`skills/progress-tracker/`](skills/progress-tracker/SKILL.md) | Cập nhật tiến độ sau mỗi bước + cổng test trước `done` |
| [`skills/reuse-scan/`](skills/reuse-scan/SKILL.md) | Quét thứ đã có trước khi viết thành phần dùng chung → Reuse Report |
| [`skills/code-review/`](skills/code-review/SKILL.md) | Review nhanh 5 chiều trước commit |
| [`skills/debug/`](skills/debug/SKILL.md) | Reproduce → Isolate → Diagnose → Fix |
| [`skills/decisions-relevance/`](skills/decisions-relevance/SKILL.md) | Rà kho ADR *(chỉ khi có ADR)* |
| [`skills/workflow-adapt/`](skills/workflow-adapt/SKILL.md) | **Tự điều chỉnh cách làm việc** khi hạ tầng agent lệch repo |

**Command · State · Knowledge · Hook · Playbook · Repo dùng chung**

| Mẫu | Đích gợi ý | Nội dung |
|---|---|---|
| [`commands/handoff.md`](commands/handoff.md), [`commands/resume.md`](commands/resume.md) | `<AGENT_DIR>/commands/<tên>.md` | Lưu / mở lại phiên — chỉ user gọi |
| [`state/`](state/) | `<STATE_DIR>/_template/` | `current-task`, `progress`, `session-handoff`, `decisions-log`, `tech-debt` |
| [`knowledge/design-standards.md`](knowledge/design-standards.md) | `<KNOWLEDGE_DIR>/` | Chuẩn viết 3 tài liệu thiết kế, cổng tuân thủ, changelog |
| [`knowledge/decisions/`](knowledge/decisions/README.md) | `<KNOWLEDGE_DIR>/decisions/` | Vòng đời + template ADR |
| [`knowledge/non-functional-standards.md`](knowledge/non-functional-standards.md) | `<KNOWLEDGE_DIR>/` | Phân trang, ngưỡng số truy vấn, cổng dừng lúc thiết kế *(khi có DB)* |
| [`knowledge/external-knowledge.md`](knowledge/external-knowledge.md) | `<KNOWLEDGE_DIR>/` | Tra cứu ngoài repo (MCP/wiki): khi nào, dẫn chứng, khi vắng |
| [`hooks/README.md`](hooks/README.md) | `<HOOKS_DIR>/` + cấu hình hook | Exit code, đặc tả guard/logger/secret/đầu phiên/playbook, fixture |
| [`playbook/README.md`](playbook/README.md) | `<thư mục playbook>/<tên>/` | Playbook 4 lớp + enforcement tiệm tiến |
| [`shared-repo/README.md`](shared-repo/README.md) | (đề xuất) | Một nguồn chuẩn cho nhiều repo: org-owned, sync, kênh tuỳ biến |

> Chọn mẫu theo **bản đồ thích ứng** (`../adapters/adaptation-rules.md`): mẫu ghi *(chỉ khi …)* bị bỏ nếu repo không có tín hiệu tương ứng.

## Placeholder → mục trong `project-profile.md`

| Placeholder | Mục trong hồ sơ | Ý nghĩa |
|---|---|---|
| `<PROJECT_NAME>`, `<tên repo>` | §1 Dự án | Tên repo đích |
| `<LAYER>` | §4 Tầng — cột `id` | Tầng thật của repo (`backend`, `frontend`, `data`, `infra`…); repo một tầng → bỏ hậu tố tầng |
| `<TEST_CMD>` | §4 Tầng — cột "Lệnh test" | Lệnh test **đã xác nhận** |
| `<AGENT_DIR>`, `<KNOWLEDGE_DIR>`, `<STATE_DIR>`, `<HOOKS_DIR>` | §5 Đường dẫn | `<STATE_DIR>` là **một giá trị**, dùng nhất quán mọi file |
| `<DEV_ID>` | §7 State | ID dev trung lập (alias cấu hình; tránh suy từ email) |
| Nhánh được bảo vệ trong hook | §8 Git | Danh sách nhánh hook chặn force push |
| `<file cấu hình>` của playbook | §9 Playbook & hook | Nơi bật/tắt playbook |
| `<convention tầng …>`, `<api-convention>`, `<security tầng>`, `<security-policy>` | §4 Tầng — cột "Tài liệu convention" · §11 | Đường dẫn tài liệu quy ước **đã có** trong repo |
| `<design-standards>`, `<thư mục ADR>`, `<non-functional-standards>`, `<N_DETAIL>`/`<N_LIST>`/`<N_WRITE>`, `<external-knowledge>` | §11 Thiết kế, ADR, phi chức năng, tra cứu ngoài | Chỉ điền khi repo có tín hiệu tương ứng |
| `<lệnh-handoff>`, `<lệnh-resume>` | §7 State | Tên command — tránh trùng lệnh built-in của harness |

## Không có trong samples (cố ý)

- Code/cấu hình chạy được (script hook, file settings) — agent sinh theo hướng dẫn, đúng runtime và harness đích.
- Spec nghiệp vụ, tên bảng/endpoint, thư viện nội bộ, lệnh sync của bất kỳ tổ chức nào.
- Bộ luật quét secret đầy đủ — chỉ có nguyên tắc; luật thật do repo đích chủ quản và kiểm thử.
