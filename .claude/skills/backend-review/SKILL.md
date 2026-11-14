---
description: >
  Review thay đổi code của SignBridge-AI (FastAPI) theo checklist riêng repo (hợp đồng API theo
  docs/luong-xu-ly-chinh.md, validate input, nhánh lỗi có test, kiểm tra output AI, gọi LLM/STT,
  bảo mật payload) TRƯỚC khi commit. Kích hoạt khi implement xong, hoặc khi nghe "review",
  "check code", "kiểm tra code", "trước khi commit". Chỉ tìm bug chung → /code-review built-in;
  chỉ làm gọn code → /simplify. Lỗi đang xảy ra → skill debug.
---

# backend-review — review trước commit

## Phạm vi
- Mặc định: `git diff` + `git diff --cached` + file `.py` untracked. Người dùng chỉ định khác → theo đó.
- Không sửa code trong skill này trừ khi người dùng yêu cầu — chỉ báo findings.

## Quy trình

### Bước 1 — Kiểm chứng
- Chạy `./venv/Scripts/python.exe -m pytest -q`. Ghi dòng `N passed` / `N failed`. FAIL → finding CRITICAL, dừng review chi tiết, chuyển skill `debug`.

### Bước 2 — Checklist (chỉ mục liên quan tới diff)

**A. Hợp đồng API** (`docs/luong-xu-ly-chinh.md` §4)
- [ ] Path, method, kiểu body (multipart/JSON), tên field (kể cả snake_case `spoken_sentence`), enum khớp spec.
- [ ] Status HTTP + `error.code` khớp bảng §4.0. Đổi hợp đồng → phải có xác nhận của người dùng + cập nhật spec.
- [ ] Field response mới chỉ được **thêm** (mobile bỏ qua field lạ), không đổi tên/xoá field cũ.

**B. Validate input** (`app.py`)
- [ ] Mọi field mới có giới hạn: số lượng, kích thước byte, media type, độ dài text, enum `context`.
- [ ] Validate trước khi gọi STT/LLM. Lỗi qua `ApiError.<factory>`, message tiếng Việt.
- [ ] Giới hạn từng file không vượt `MAX_REQUEST_BYTES` (6 MB, middleware chặn theo `Content-Length`).

**C. Kiểm tra output AI** (`conversation.py`, §4.6, §7.4)
- [ ] Output từ `llm_service` đều qua `conversation.check_*` trước khi trả.
- [ ] Output null / thiếu field / sai kiểu / sai số lượng → `ai_upstream_error`, không 500.
- [ ] Gloss ngoài `allowed_glosses(context)` → `UNKNOWN`; có `UNKNOWN` hoặc `confidence` < ngưỡng → `spoken_sentence = ""`.
- [ ] Highlight không có **nguyên văn** trong `summary` bị loại; con số không bị đổi (`verify_and_protect_numbers`).

**D. Gọi LLM / STT** (`llm_service.py`, `run_transcribe`)
- [ ] Có timeout (§4.6), không retry. `/api/sign`: timeout → `ai_timeout()`; lỗi API/parse → `ai_upstream_error(...)`.
- [ ] `/api/sign` KHÔNG trả câu mẫu khi LLM lỗi (chỉ mock khi chưa có `LLM_API_KEY`).
- [ ] Key đọc từ biến môi trường; prompt `SIGN_RECOGNIZE` gửi đúng `allowed_glosses`, không gửi tên `context` thay danh sách.
- [ ] Lỗi STT bọc qua `transcribe_or_raise` → 502, không lộ `str(e)`.

**E. Bảo mật & dữ liệu** (CLAUDE.md §4)
- [ ] Không secret/URL thật trong code, test, `.env.example`.
- [ ] Không log frame/audio/transcript/prompt/response AI; `logger.*(f"...{e}")` với exception từ LLM/STT là nghi vấn.
- [ ] Không ghi payload ra đĩa/DB; DB chỉ chứa thẻ.

**F. Test**
- [ ] Mỗi nhánh lỗi mới có test assert status + `res.json()["error"]["code"]`.
- [ ] Hành vi mới có test đúng file: endpoint → `tests/test_api.py`; luật kiểm tra AI → `tests/test_conversation.py`.
- [ ] Test không phụ thuộc mạng, LLM thật, model PhoWhisper (dùng `fake_stt`, `monkeypatch get_openai_client`).

**G. Chất lượng code** (CLAUDE.md §2–§3)
- [ ] Đúng file và chiều phụ thuộc (`errors.py` không import ngược).
- [ ] Không trùng logic đã có (`check_context`, `check_length`, `media_type`, `parse_personal_chips`, `normalize_gloss`) — dùng lại.
- [ ] Không code chết (vd hàm/model Pydantic không endpoint nào dùng), không TODO không lý do, không mở rộng ngoài yêu cầu.

### Bước 3 — Báo cáo
Mỗi finding: `file:line` · mức (`CRITICAL` sai logic/lộ dữ liệu/vỡ hợp đồng · `MAJOR` thiếu test/validate/bảo trì · `MINOR` style) · kịch bản lỗi cụ thể · đoạn code đề xuất (với CRITICAL/MAJOR).

Kết luận một dòng: `Sẵn sàng commit` / `Chưa — còn N CRITICAL/MAJOR`.

## Điều kiện dừng
- Test FAIL → chuyển `debug`.
- Diff đổi hợp đồng API mà chưa có xác nhận → dừng, hỏi người dùng.
