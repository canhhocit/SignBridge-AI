# Hồ sơ dự án — SignBridge-AI

> Chuyển từ hồ sơ `signbridge-backend` (Spring, 2026-11-13) sang repo Python ngày 2026-11-14,
> sau commit `2b1994c refactor: remove Java backend, unify on FastAPI AI service with database`.
> Nguồn duy nhất cho mọi `<PLACEHOLDER>` khi dùng mẫu. Không chứa secret/URL nội bộ.

## 1. Dự án

| Mục | Giá trị | Bằng chứng |
|---|---|---|
| Tên | `SignBridge-AI` | tên repo; `app.py` `FastAPI(title=...)` |
| Loại | service (REST API + STT/LLM, prototype hackathon) | `README.md` §1; `docs/luong-xu-ly-chinh.md` §4.0 |
| Ngôn ngữ tài liệu sinh ra | `vi` | Quy tắc ngôn ngữ của prompt |
| Trọng tâm | Chỉ code; ưu tiên chất lượng code | giữ nguyên từ hồ sơ Spring |

## 2. Harness

| Mục | Giá trị | Bằng chứng |
|---|---|---|
| Harness chính | Claude Code | phiên hiện tại |
| Harness phụ | không thấy | không có `AGENTS.md`, `.cursor/`, `.github/` |
| File hub chỉ dẫn | `CLAUDE.md` (gốc) | `adapters/harness-matrix.md` §1 |
| Hỗ trợ agent / skill / command / hook | có | `harness-matrix.md` §1 |
| Điều kiện nạp cấu hình | Mở tại gốc repo + workspace đã trust | `harness-matrix.md` §1 |

## 3. Mức áp dụng

| Mục | Giá trị | Lý do |
|---|---|---|
| Mức | `minimal` + 2 skill của `standard` (`backend-review`, `debug`) | Giữ nguyên mức đã duyệt cho backend Spring; quy mô tương đương (1 tầng, 5 module) |

## 4. Tầng

| `id` | Thư mục | Ngôn ngữ | Lệnh build | Lệnh test (`<TEST_CMD>`) | Lệnh lint | Tài liệu convention | Bằng chứng |
|---|---|---|---|---|---|---|---|
| `backend` (một tầng → bỏ hậu tố) | gốc repo (`app.py`, `conversation.py`, `llm_service.py`, `errors.py`, `database.py`) | Python 3.11, FastAPI, Pydantic v2, SQLAlchemy 2, faster-whisper, openai | không có (thông dịch) | `./venv/Scripts/python.exe -m pytest -q` | không có | rút từ code, ghi trong hub | `requirements.txt`, `requirements-dev.txt`, `pytest.ini` |

> `pytest -q` đã chạy ngày 2026-11-14: `69 passed`.

## 5. Đường dẫn

| Placeholder | Giá trị | Bằng chứng |
|---|---|---|
| `<AGENT_DIR>` | `.claude` | Claude Code |
| `<KNOWLEDGE_DIR>` | không dùng — hub `CLAUDE.md` đủ nhỏ | quy mô repo |
| `<STATE_DIR>` | không dùng | mức `minimal` |
| `<HOOKS_DIR>` | không dùng hook | mức `minimal` |

## 6. Quyền sở hữu & đồng bộ

| Mục | Giá trị | Bằng chứng |
|---|---|---|
| File do generator quản lý | không có | — |
| Dữ liệu không commit | `data/models--*` (weights PhoWhisper), `venv/`, `*.db`, `.env` | `.gitignore` |
| Kênh tuỳ biến của dự án | `CLAUDE.md` gốc | — |
| Submodule | không có | — |

## 7. State & bàn giao phiên

| Mục | Giá trị | Bằng chứng |
|---|---|---|
| Dùng state task | không | mức `minimal` |

## 8. Git & review

| Mục | Giá trị | Bằng chứng |
|---|---|---|
| Nhánh mặc định | `main` | `git status` |
| Nhánh được bảo vệ | `[cần xác nhận]` | |
| Quy ước commit | Conventional Commits `type(scope): …` | `git log` (`feat(ai): …`, `refactor: …`) |
| Nền tảng review | GitHub | remote `canhhocit/SignBridge-AI` |

## 9. Playbook & hook

| Mục | Giá trị | Bằng chứng |
|---|---|---|
| Playbook đang bật | không có | |
| Runtime cho hook | không dùng hook | mức `minimal` |

## 10. CI

| Mục | Giá trị | Bằng chứng |
|---|---|---|
| Có CI trong repo | không | không có `.github/` |

## 11. Thiết kế, ADR, phi chức năng, tra cứu ngoài

| Mục | Giá trị | Bằng chứng |
|---|---|---|
| Spec nghiệp vụ | `docs/luong-xu-ly-chinh.md` (API §4, bộ ký hiệu §7) | `docs/` |
| Tầng có DB/ORM | có — SQLAlchemy, chỉ bảng thẻ `quick_chips` được dùng | `database.py` |
| `<non-functional-standards>` | timeout LLM (§4.6), timeout mobile 10 giây (§4.0), giới hạn upload (§4.2–4.5) | spec |
| Nguồn tra cứu ngoài | nhà cung cấp LLM OpenAI-compatible (`LLM_BASE_URL`), model PhoWhisper | `.env.example` |

## 12. Quyết định thích ứng

| Ngày | Tín hiệu | Bằng chứng | Điều chỉnh | Lý do | Đảo ngược bằng |
|---|---|---|---|---|---|
| 2026-11-14 | Backend Spring bị xoá, gộp vào FastAPI | commit `2b1994c` | Chuyển hub/skill sang Python; lệnh test `pytest` | Repo này là backend duy nhất | — |
| 2026-11-14 | Có DB (thẻ) — khác Spring stateless | `database.py` | Hub §4 cho phép DB chỉ chứa thẻ; cấm ghi frame/audio/transcript | Spec §4.0 vẫn yêu cầu không lưu lịch sử | Hỏi người dùng trước khi ghi `message_turns` |
| 2026-11-14 | Test cần chạy không có model/LLM/Postgres | `tests/conftest.py` | Nạp PhoWhisper lười (`WHISPER_PRELOAD`), SQLite tạm, mock LLM | Cổng test phải chạy được trên mọi máy dev | — |
| 2026-11-14 | Bản Python fallback heuristic khi LLM lỗi (summarize/expand) | `llm_service.py` | Giữ, ghi rõ trong hub §2; riêng `/api/sign` ném 502/504 | Fallback của sign bịa câu sẽ được phát loa | Đổi quyết định trong hub |

## 13. Còn chờ xác nhận

- [ ] Nhánh được bảo vệ.
- [ ] Mobile có cần `/api/health` chỉ trả `{"status":"UP"}` hay chấp nhận field thêm.
- [ ] Git pre-commit quét secret (repo có `LLM_API_KEY` trong `.env`).
