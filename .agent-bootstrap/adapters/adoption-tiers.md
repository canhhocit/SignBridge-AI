# Mức áp dụng (adoption tier)

> Không phải dự án nào cũng cần toàn bộ hạ tầng. Chọn mức ở Bước 5 của prompt, ghi vào
> mục 3 của hồ sơ dự án (`project-profile.md`). Bắt đầu thấp, nâng dần khi đội đã quen — giống enforcement
> `monitor-only → warn → block` của playbook.

## Bảng chọn nhanh

| Tiêu chí | `minimal` | `standard` | `full` |
|---|---|---|---|
| Quy mô đội | 1–3 người | 3–10 người | > 10 người hoặc nhiều repo dùng chung chuẩn |
| Rủi ro thay đổi | Thấp (tool nội bộ, prototype) | Trung bình | Cao (tài chính, dữ liệu nhạy cảm, production quan trọng) |
| Hạ tầng agent có sẵn | Không có | Có một phần | Có repo dùng chung / chuẩn tổ chức |
| Có quy trình thiết kế trước khi code | Không | Tuỳ | Có |

Khi tiêu chí lệch nhau → chọn theo **rủi ro thay đổi**; vẫn chưa rõ → hỏi người dùng.

## Thành phần theo mức

| Thành phần | `minimal` | `standard` | `full` | Mẫu |
|---|---|---|---|---|
| Hub chỉ dẫn (precedence, lệnh test, ranh giới an toàn) | ✅ | ✅ | ✅ | `samples/rules/hub.md` (rút gọn §1, §8) |
| Quy tắc ngôn ngữ + MUST/NEVER cốt lõi | ✅ | ✅ | ✅ | prompt §Quy tắc ngôn ngữ |
| Bản đồ thích ứng ghi vào hồ sơ (mục 12) | ✅ | ✅ | ✅ | `adapters/adaptation-rules.md` |
| Kênh tuỳ biến dự án + context on-demand | — | ✅ | ✅ | `samples/rules/project-knowledge.md` |
| Routing theo loại việc/tầng | — | ✅ | ✅ | `samples/rules/routing.md` |
| Procedure developer / code-reviewer theo tầng | — | ✅ | ✅ | `samples/agents/developer.md`, `code-reviewer.md` |
| Skill: code-review, debug | — | ✅ | ✅ | `samples/skills/code-review/`, `debug/` |
| Skill: `workflow-adapt` (tự điều chỉnh) | — | ✅ | ✅ | `samples/skills/workflow-adapt/` |
| Skill: task-state-init, progress-tracker, reuse-scan + state template | — | tuỳ | ✅ | `samples/skills/…`, `samples/state/` |
| Command handoff/resume | — | tuỳ | ✅ | `samples/commands/` |
| Chuẩn phi chức năng (khi có DB) | — | tuỳ | ✅ | `samples/knowledge/non-functional-standards.md` |
| Quy tắc tra cứu ngoài repo (khi có nguồn ngoài) | — | tuỳ | ✅ | `samples/knowledge/external-knowledge.md` |
| Hook chặn thao tác nguy hiểm | — | tuỳ (cần duyệt) | ✅ (cần duyệt) | `samples/hooks/README.md` §3 |
| Git pre-commit quét secret (chung module luật) | tuỳ | ✅ (nếu chưa có) | ✅ | `samples/hooks/README.md` §10 |
| Hook đầu phiên (nhắc) + logger | — | tuỳ | ✅ (cần duyệt) | `samples/hooks/README.md` §8–9 |
| Playbook (TDD…) | — | — | tuỳ | `samples/playbook/`, `samples/hooks/README.md` §11 |
| Tầng thiết kế (architect + review thiết kế) + ADR | — | — | tuỳ | `samples/agents/solution-architect.md`, `architect-reviewer.md`, `samples/knowledge/design-standards.md`, `samples/knowledge/decisions/`, `samples/skills/decisions-relevance/` |
| Đồng bộ từ repo dùng chung (file org-owned) | — | — | tuỳ | `samples/shared-repo/README.md` |

## Nguyên tắc

- **Không tạo thành phần không có người dùng**: role không có task rõ, skill không có trigger rõ → bỏ.
- Mức `minimal` vẫn **MUST** có: lệnh test đã xác nhận, ranh giới an toàn, quy tắc ngôn ngữ, cổng "không báo pass khi chưa chạy".
- Nâng mức = thêm thành phần theo bảng; không viết lại phần đã có.
- Mức chỉ quyết định **bao nhiêu** thành phần; **dạng** của từng thành phần do bản đồ thích ứng quyết định
  (`adaptation-rules.md`) — vd mức `full` nhưng repo không có DB thì vẫn bỏ chuẩn phi chức năng phần truy vấn.
