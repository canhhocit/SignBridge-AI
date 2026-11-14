# Bảng ánh xạ theo harness

> Mỗi khái niệm trong blueprint (hub, agent, skill, command, hook, state) được đặt ở đâu tuỳ harness.
> **Chỉ cột Claude Code được kiểm chứng ở repo mẫu.** Các cột khác là [Unverified] — dựa trên hiểu biết
> chung, có thể đã thay đổi. Agent **MUST** xác minh với tài liệu chính thức hiện hành của harness
> (hoặc cấu hình đang có trong repo) trước khi tạo file; không xác minh được → chỉ viết tài liệu, không tạo file thực thi.

## 1. Ánh xạ khái niệm

| Khái niệm | Claude Code (đã kiểm chứng) | Codex CLI [Unverified] | Cursor [Unverified] | GitHub Copilot [Unverified] | Gemini CLI [Unverified] |
|---|---|---|---|---|---|
| Hub chỉ dẫn | `CLAUDE.md` (gốc; hỗ trợ `@import`) | `AGENTS.md` | `.cursor/rules/*.mdc` (hoặc `AGENTS.md`) | `.github/copilot-instructions.md` | `GEMINI.md` |
| Chỉ dẫn theo path | `CLAUDE.md` trong thư mục con | `AGENTS.md` trong thư mục con | frontmatter `globs` của rule | `.github/instructions/*.instructions.md` (`applyTo`) | `GEMINI.md` trong thư mục con |
| Agent / sub-agent | `.claude/agents/<tên>.md` (`name`, `description`) | Không có định dạng riêng → mô tả role trong `AGENTS.md` | Không có định dạng riêng → rule mô tả role | Không có định dạng riêng → chỉ dẫn | Không có định dạng riêng → chỉ dẫn |
| Skill | `.claude/skills/<tên>/SKILL.md` (`description`) | Xác minh | Rule `alwaysApply: false` + `description` | Xác minh | Xác minh |
| Command do user gọi | `.claude/commands/<tên>.md` (`disable-model-invocation`) | Xác minh | Xác minh | Prompt file (xác minh) | Xác minh |
| Hook harness | `.claude/settings.json → hooks` (`SessionStart`, `PreToolUse`, `PostToolUse`…) | Xác minh | Xác minh | Xác minh | Xác minh |
| Cấu hình chia sẻ / local | `.claude/settings.json` / `.claude/settings.local.json` | Xác minh | Xác minh | Xác minh | Xác minh |
| Hook đầu phiên đưa context cho model | `SessionStart` — `stdout` / `additionalContext` vào context, `systemMessage` hiện cho người dùng | Xác minh | Xác minh | Xác minh | Xác minh |
| Nguồn tra cứu ngoài (MCP) | Scope user/local trong `~/.claude.json`; scope project `.mcp.json` | Xác minh | Xác minh | Xác minh | Xác minh |
| Điều kiện nạp cấu hình | Mở tại gốc repo + workspace đã trust; thiếu → hook/permission chia sẻ bị bỏ qua | Xác minh | Xác minh | Xác minh | Xác minh |

## 2. Fallback khi harness thiếu tính năng

| Thiếu | Thay bằng |
|---|---|
| Agent / sub-agent | Mục "Procedure" trong hub hoặc `<knowledge_dir>/procedures/<tên>.md`; coordinator đọc và thực thi tuần tự, ghi rõ "mô phỏng" |
| Skill tự kích hoạt | Bảng "Khi nào làm gì" trong hub + file quy trình; không tuyên bố tự kích hoạt |
| Command | Mục "Câu lệnh gợi ý" trong README — người dùng dán vào chat |
| Hook harness | **Git hook** (`pre-commit`) + CI job cho phần cần ép buộc; còn lại là checklist. KHÔNG mô tả chỉ dẫn là enforcement |
| State | File markdown trong `<state_dir>` do người dùng yêu cầu cập nhật |
| Hook đầu phiên | Mục "Đầu phiên cần kiểm" trong hub (agent tự kiểm khi bắt đầu) + script người dùng chạy tay |
| Nguồn tra cứu ngoài | Ghi hợp đồng ngoài là `[cần xác nhận]`; người dùng dán tài liệu cần thiết |

## 3. Nhiều harness trong cùng repo

- Giữ **một** nguồn nội dung (vd `<knowledge_dir>/`), các file hub của từng harness chỉ **trỏ tới** nguồn đó — không nhân bản nội dung.
- Nếu harness đọc chung một file (vd nhiều công cụ đọc `AGENTS.md`), ưu tiên file đó làm hub chính.
- Ghi bảng "harness nào đọc file nào" vào README của hạ tầng agent.

## 4. Quy trình xác minh một tính năng harness

1. Tìm cấu hình đang có trong repo (bằng chứng mạnh nhất).
2. Đọc tài liệu chính thức hiện hành của harness — chỉ khi người dùng cho phép truy cập mạng.
3. Không có 1 hoặc 2 → ghi `"không rõ"` vào mục 2 của hồ sơ dự án và dùng fallback ở §2.
