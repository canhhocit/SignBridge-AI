# .agent-bootstrap — Bộ hướng dẫn dựng hạ tầng AI agent cho dự án bất kỳ

> Bộ **tài liệu hướng dẫn thuần markdown**, không kèm code hay cấu hình chạy được. Bất kỳ AI coding agent
> nào đọc được file (Claude Code, Codex, Cursor, Copilot, Gemini CLI…) đều làm theo được, trên bất kỳ stack nào.
> Agent khảo sát repo đích, rồi dựng hoặc nâng cấp rules, agent, skill, command, hook, state phù hợp với
> **chính repo đó**. Tài liệu sinh ra viết **tiếng Việt**, giữ tiếng Anh cho từ khoá, thuật ngữ và định danh.

## Cấu trúc

```text
.agent-bootstrap/
├── README.md                            # file này — điểm vào
├── UNIVERSAL_AGENT_BOOTSTRAP_PROMPT.md  # quy trình chính 11 bước (Bước 0–10)
├── project-profile.template.md          # hồ sơ dự án — nguồn duy nhất cho mọi <PLACEHOLDER>
├── adapters/
│   ├── harness-matrix.md                # mỗi khái niệm đặt ở đâu theo từng harness + fallback
│   ├── stack-hints.md                   # manifest → lệnh build/test; tầng, CI, runtime hook, vị trí test, tín hiệu thích ứng
│   ├── adoption-tiers.md                # minimal / standard / full — dựng BAO NHIÊU thành phần
│   └── adaptation-rules.md              # tín hiệu repo → điều chỉnh DẠNG thành phần + vòng tự điều chỉnh sau bootstrap
└── samples/
    ├── rules/        hub · routing · kênh tuỳ biến dự án
    ├── agents/       developer · code-reviewer · solution-architect · architect-reviewer
    ├── skills/       task-state-init · progress-tracker · reuse-scan · code-review · debug
    │                 decisions-relevance · workflow-adapt · skill-template
    ├── commands/     handoff · resume
    ├── state/        current-task · progress · session-handoff · decisions-log · tech-debt
    ├── knowledge/    design-standards · decisions (ADR) · non-functional-standards · external-knowledge
    ├── hooks/        đặc tả + pseudocode + fixture (guard, logger, secret, đầu phiên, playbook)
    ├── playbook/     playbook 4 lớp
    └── shared-repo/  một nguồn chuẩn cho nhiều repo (org-owned, sync, kênh tuỳ biến)
```

## Dùng cho một dự án (5 bước)

1. **Copy** thư mục `.agent-bootstrap/` vào gốc repo đích.
2. **Mở AI agent tại gốc repo.** Với harness có hook/cấu hình theo thư mục, mở ở thư mục con có thể không nạp cấu hình.
3. **Ra lệnh** (dán vào chat của agent):

   ```text
   Đọc .agent-bootstrap/README.md rồi thực hiện đúng .agent-bootstrap/UNIVERSAL_AGENT_BOOTSTRAP_PROMPT.md
   cho repo này. Mức áp dụng: <minimal | standard | full | để agent đề xuất>.
   ```

   Agent không tự đọc được file → dán toàn bộ phần `PROMPT BẮT ĐẦU … PROMPT KẾT THÚC` của file prompt vào chat.
4. **Trả lời câu hỏi** (harness, mức áp dụng, các mục `[cần xác nhận]`) và **duyệt kế hoạch** ở Bước 5.
   Agent phải dừng ở đó, trước khi sửa file gốc, hook, cấu hình harness hay CI.
5. **Kiểm kết quả:**
   - `project-profile.md` đã điền đủ, mỗi giá trị có bằng chứng; mục 12 (bản đồ thích ứng) nêu rõ chỗ khác mẫu và lý do;
   - danh sách file đã tạo/sửa;
   - các lệnh đã chạy kèm kết quả thật;
   - các mục còn chờ.

> Xong việc có thể giữ `.agent-bootstrap/` (để nâng mức sau) hoặc xoá đi — hạ tầng đã nằm ở vị trí thật của harness,
> kèm skill `workflow-adapt` + bản đồ thích ứng để agent tiếp tục tự điều chỉnh theo repo.

## Agent tự thích ứng với dự án như thế nào

| Lúc | Cơ chế |
|---|---|
| Bootstrap | Bước 4 thu **tín hiệu** của repo (một/nhiều tầng, có test/DB/thiết kế/nguồn tra cứu ngoài, quy mô đội, rủi ro) → Bước 5 lập **bản đồ thích ứng** (`adapters/adaptation-rules.md`) → mẫu được bỏ/đổi dạng cho khớp, ghi lý do vào hồ sơ |
| Sau bootstrap | Skill `workflow-adapt` bắt tín hiệu lệch (người dùng sửa cùng hành vi ≥ 2 lần, lệnh đổi, quy tắc mâu thuẫn code, hook chặn nhầm) → đề xuất điều chỉnh có bằng chứng → duyệt → sửa ở kênh tuỳ biến |
| Repo đổi lớn | Chạy lại prompt ở chế độ nâng cấp — chỉ bổ sung phần lệch |

Giới hạn cố định: không điều chỉnh nào được bỏ cổng test, ranh giới an toàn, hay quy tắc "không đoán — ghi `[cần xác nhận]`".

## Nâng cấp dự án đã có hạ tầng agent

Dùng cùng lệnh ở bước 3. Prompt yêu cầu agent **tích hợp, bổ sung nhỏ, liên kết**:
- không ghi đè file có sẵn;
- không sửa file do generator hoặc cơ chế sync quản lý;
- mọi tuỳ biến đi vào kênh tuỳ biến của dự án.

## Vì sao dùng được cho mọi agent, mọi dự án

| Nguyên tắc | Cơ chế |
|---|---|
| Chỉ là hướng dẫn | Không có script/cấu hình chạy sẵn; agent sinh code theo đặc tả, đúng runtime của repo đích (`samples/hooks/README.md`) |
| Không gắn cứng stack | Lệnh build/test lấy từ manifest của repo đích (`adapters/stack-hints.md`), ghi kèm bằng chứng |
| Không gắn cứng harness | Khái niệm trừu tượng → ánh xạ theo harness (`adapters/harness-matrix.md`); thiếu tính năng → fallback |
| Không áp nghi thức thừa | Ba mức áp dụng (`adapters/adoption-tiers.md`) |
| Không ép repo theo mẫu | Bản đồ thích ứng (`adapters/adaptation-rules.md`) — mẫu đổi theo tín hiệu có bằng chứng |
| Một nguồn cho tham số | `project-profile.md` — mọi placeholder trong mẫu lấy từ đây |
| Không bịa | Chưa xác định → `[cần xác nhận]`; khẳng định chưa kiểm chứng → `[Unverified]` |
| An toàn mặc định | Khảo sát chỉ-đọc → kế hoạch → duyệt → mới ghi; hook test bằng fixture + phiên thật |

## Bảo trì bộ hướng dẫn

- **Bài học mới từ một dự án:** khái quát hoá rồi cập nhật prompt (thường ở Bước 7) hoặc file trong `adapters/`.
  KHÔNG đưa tên dự án, nghiệp vụ, URL nội bộ vào bộ này.
- **Harness mới:** thêm cột vào `adapters/harness-matrix.md`, đánh dấu `[Unverified]` cho tới khi kiểm chứng.
- **Stack mới:** thêm dòng vào `adapters/stack-hints.md`.
- **Đổi luật hook mẫu:** cập nhật đặc tả **và** bảng fixture trong `samples/hooks/README.md` cùng lúc.
- **Tín hiệu thích ứng mới:** thêm dòng vào `adapters/adaptation-rules.md` §2 (tín hiệu · điều chỉnh), và mục tương ứng ở hồ sơ nếu cần giá trị mới.
- **Thành phần mới ở repo nguồn** (agent/skill/hook/knowledge): khái quát hoá thành mẫu trong `samples/`, cập nhật
  `samples/README.md` + `adapters/adoption-tiers.md` + (nếu là tuỳ chọn) điều kiện *(chỉ khi …)* trong `adaptation-rules.md`.
