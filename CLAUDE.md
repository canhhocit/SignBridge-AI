# CLAUDE.md — SignBridge-AI (backend hợp nhất FastAPI)

> Hub cho AI agent. Repo **chỉ tập trung code**: mọi quy tắc dưới đây phục vụ chất lượng code.
> Hợp đồng API (nguồn sự thật): `docs/luong-xu-ly-chinh.md` §4 (endpoint, mã lỗi) và §7 (bộ ký hiệu).
> Repo này thay thế backend Spring (`signbridge-backend`); mobile gọi thẳng service này.
> Hồ sơ bootstrap: `.agent-bootstrap/project-profile.md`.

## §1 — Lệnh

| Việc | Lệnh |
|---|---|
| Tạo môi trường | `python -m venv venv` rồi `./venv/Scripts/python.exe -m pip install -r requirements-dev.txt` |
| Test toàn bộ | `./venv/Scripts/python.exe -m pytest -q` |
| Test một file / một case | `./venv/Scripts/python.exe -m pytest tests/test_conversation.py -q` · `-k test_sign_rejects_png` |
| Chạy server (cổng 8000, nạp PhoWhisper lúc khởi động) | `./venv/Scripts/python.exe -m uvicorn app:app --host 0.0.0.0 --port 8000` |
| Chạy server không nạp model (chỉ thử LLM/validate) | đặt `WHISPER_PRELOAD=0` |
| Swagger UI / OpenAPI · Web Studio | `http://localhost:8000/docs` · `/openapi.json` · `/` |
| Benchmark STT (không phải test) | `./venv/Scripts/python.exe test_transcribe.py test_audio-text/test.mp3 vi` |

Không có lint/formatter/CI. **Cổng duy nhất là test** (`pytest.ini` chỉ gom `tests/`).

## §2 — Cấu trúc (một tầng, module phẳng ở gốc repo)

| File | Trách nhiệm | KHÔNG được |
|---|---|---|
| `app.py` | Endpoint FastAPI + validate request (số frame, kích thước, media type, độ dài text, enum `context`); middleware log request; nạp lười PhoWhisper (`get_whisper_model`); Web Studio HTML | Chứa luật kiểm tra output AI; gọi `openai` trực tiếp |
| `conversation.py` | Kiểm tra lại output AI (§4.6, §7.4): `check_sign_output`, `check_summarize_output`, `check_expand_output`; bộ ký hiệu `allowed_glosses`, `normalize_gloss` | Import FastAPI / đọc `UploadFile` |
| `llm_service.py` | Gọi LLM (OpenAI-compatible, `LLM_*`): prompt, guardrail số `verify_and_protect_numbers`, fallback heuristic `mock_summarize` | Trả output chưa qua `conversation.check_*` ra ngoài |
| `errors.py` | `ApiError` + factory mã lỗi, handler chung `{"error":{"code","message"}}` | Phụ thuộc ngược vào `app`, `conversation`, `llm_service` |
| `database.py` | SQLAlchemy: thẻ hệ thống + thẻ cá nhân (`/api/chips`); PostgreSQL, tự fallback SQLite | Lưu frame/audio/transcript |

Chiều phụ thuộc: `app → conversation → errors`, `app → llm_service → errors`, `app → database`.

**Chế độ AI:** không có `LLM_API_KEY` → mock (dữ liệu mẫu, như `MockAiGateway` cũ; `personalChips=["MOCK_LOW"]` thử luồng confidence thấp). Có key → gọi LLM thật.
- `/api/sign` lỗi LLM → **ném** `AI_TIMEOUT`/`AI_UPSTREAM_ERROR`, KHÔNG trả câu mẫu (mobile sẽ phát loa câu người dùng không ký hiệu).
- `/api/summarize`, `/api/expand` lỗi LLM → fallback heuristic từ chính transcript/chips (quyết định của bản Python, khác Spring là trả 502).

## §3 — Convention code (rút từ code hiện có — theo đúng, không "chuẩn hoá" khác đi)

- **DTO = Pydantic `BaseModel`**. Tên field JSON giữ đúng hợp đồng: `spoken_sentence` snake_case; còn lại camelCase (`suggestedChips`, `previousIncoming`, `iconCode`).
- **Ràng buộc input** khai báo bằng kiểu (`ContextType = Literal[...]`, `ChipText`, `ShortText`, `Field(min_length, max_length)`); field multipart (`Form`/`File`) kiểm tra tay bằng `check_context`, `check_length`, `media_type`, `parse_personal_chips`.
- **Hằng số giới hạn** viết HOA ở đầu `app.py` (`MAX_FRAME_BYTES`, `MAX_AUDIO_BYTES`, `MAX_REQUEST_BYTES`, `MAX_TEXT`); ngưỡng cấu hình được → biến môi trường có default (`SIGN_CONFIDENCE_THRESHOLD`, `AI_TIMEOUT_SIGN`).
- **Lỗi:** chỉ `raise ApiError.<factory>(...)`. KHÔNG `HTTPException`, KHÔNG `JSONResponse` lỗi tự chế trong endpoint. Mã lỗi mới → thêm factory trong `errors.py` + dòng trong bảng `docs/luong-xu-ly-chinh.md` §4.0.
- **Response lỗi** luôn `{"error":{"code","message"}}`; `message` tiếng Việt, người dùng cuối đọc được, không chứa `str(exception)`.
- **Không tin output AI:** mọi kết quả từ `llm_service` đi qua `conversation.check_*` trước khi trả; sai schema → `ai_upstream_error`.
- Thụt lề 4 dấu cách. Comment/docstring tiếng Việt, ngắn, trỏ mục spec (`mục 4.6`) khi hiện thực một quy tắc spec.

## §4 — Bảo mật & dữ liệu

- `LLM_API_KEY`, `DATABASE_URL` **chỉ** đọc từ biến môi trường / `.env` (qua `python-dotenv`). NEVER hardcode, NEVER commit `.env` (đã có trong `.gitignore`; mẫu ở `.env.example`).
- KHÔNG lưu frame/audio/transcript ra đĩa hay DB. DB chỉ chứa thẻ (`quick_chips`); bảng `conversation_sessions`/`message_turns` đã khai báo nhưng chưa dùng — muốn ghi phải hỏi trước (spec §4.0: lịch sử nằm ở mobile).
- NEVER log payload (frame, audio, transcript, prompt, response AI) hay header chứa key. Log lỗi upstream chỉ ghi `code` + tên exception.
- Mọi input từ client có giới hạn kích thước/số lượng/độ dài — thêm field mới thì thêm giới hạn + test.

## §5 — Cổng chất lượng

| Lúc | Việc |
|---|---|
| Trước sửa | Đọc mục spec liên quan; liệt kê file sẽ sửa. Đổi hợp đồng API (path, field, mã lỗi, status) → **dừng, hỏi** (mobile phụ thuộc) |
| Khi sửa | Thay đổi nhỏ, đúng file (§2). Hành vi mới/nhánh lỗi mới → test mới cùng commit |
| Sau sửa | Chạy `pytest -q`, dán dòng `N passed` / `N failed` |
| Trước commit | Skill `backend-review` |

Vị trí test: endpoint/validate/mã lỗi/log → `tests/test_api.py` (`TestClient`); luật kiểm tra output AI + guardrail số → `tests/test_conversation.py` (unit). `tests/conftest.py` ép SQLite tạm, `WHISPER_PRELOAD=0`, `LLM_API_KEY=""`; fixture `fake_stt` thay PhoWhisper. LLM thật giả bằng `monkeypatch.setattr(llm_service, "get_openai_client", ...)` — test không gọi mạng.

## §6 — MUST / NEVER (ưu tiên cao nhất)

- **MUST** chạy `pytest -q` sau khi sửa code và báo kết quả thật.
- **MUST** mỗi factory trong `ApiError` có ít nhất một test chứng minh status + `error.code`.
- **MUST** reproduce (ưu tiên bằng test FAIL) trước khi nêu nguyên nhân lỗi → skill `debug`.
- **NEVER** báo xong khi test chưa chạy hoặc còn fail.
- **NEVER** thêm dependency vào `requirements*.txt` khi chưa hỏi.
- **NEVER** đoán hợp đồng của mobile (`Sign-Bridge-mobile`) — chưa có nguồn → ghi `[cần xác nhận]`.
- **NEVER** tự commit / push khi chưa được yêu cầu. Commit theo dạng `type(scope): mô tả` (theo `git log`).

## §7 — Skill dự án

| Skill | Dùng khi |
|---|---|
| `backend-review` | Trước commit: checklist riêng repo (hợp đồng API, validate, nhánh lỗi, kiểm tra output AI, bảo mật payload) |
| `debug` | Lỗi, exception, test fail, response sai |

Skill built-in `/code-review` (bug) và `/simplify` (gọn code) vẫn dùng được, bổ sung cho `backend-review`.
