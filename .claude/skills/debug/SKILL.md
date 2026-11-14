---
description: >
  Debug có hệ thống SignBridge-AI (FastAPI) theo 4 bước Reproduce → Isolate → Diagnose → Fix. Kích hoạt
  khi "debug", "lỗi", "bug", "exception", "error", "test fail", "500", "không chạy", "tại sao lại…",
  hoặc khi mobile nhận response sai. Review trước commit → skill backend-review.
---

# debug — Reproduce → Isolate → Diagnose → Fix

**NEVER** nêu nguyên nhân khi chưa qua Bước 1.

## Bước 1 — Reproduce
- Thu: endpoint, request (field, số frame, content type, kích thước — **không** dán nội dung frame/audio), status + `error.code` nhận được, dòng log `SignBridge.Request` quanh thời điểm lỗi.
- Tái hiện bằng **test FAIL** ở lớp nhỏ nhất:
  - lỗi validate/HTTP/mapping lỗi → `tests/test_api.py` (`TestClient`);
  - lỗi xử lý output AI → `tests/test_conversation.py` gọi thẳng `conversation.check_*` với output xấu;
  - lỗi khi LLM trả bất thường → `monkeypatch.setattr(llm_service, "get_openai_client", ...)` trả nội dung/exception giả.
- Chạy `./venv/Scripts/python.exe -m pytest tests/<file>.py -k <tên> -q`, xác nhận FAIL đúng triệu chứng.
- Không tái hiện được → không đoán; hỏi thêm dữ liệu.

## Bước 2 — Isolate

| Triệu chứng | Nghi trước |
|---|---|
| 400 `INVALID_REQUEST` bất ngờ | Tên field `Form`/`File` lệch field mobile gửi; `check_context`; `RequestValidationError` handler trong `errors.py` |
| 413 / 415 | `MAX_*` trong `app.py`; middleware `Content-Length` > 6 MB; `media_type()` (content type null, có `;codecs=`, biến thể `audio/x-m4a`) |
| 500 `INTERNAL_ERROR` | Exception chưa bọc thành `ApiError`; output AI sai kiểu lọt qua `check_*` |
| 502 `AI_UPSTREAM_ERROR` | `conversation.check_*` (schema); `transcribe_or_raise` (STT lỗi decode); `recognize_sign` (LLM lỗi/JSON sai) |
| 504 `AI_TIMEOUT` | `AI_TIMEOUT_SIGN` / timeout client OpenAI |
| Gloss thành `UNKNOWN` | `normalize_gloss` (NFC, khoảng trắng, hoa), `allowed_glosses(context)` |
| `spoken_sentence` rỗng | `confidence` < `SIGN_CONFIDENCE_THRESHOLD` hoặc có `UNKNOWN` — đúng thiết kế §7.4 |
| Kết quả luôn giống nhau | Đang ở chế độ mock (thiếu `LLM_API_KEY`) hoặc LLM lỗi → fallback heuristic (summarize/expand) |
| Server không khởi động | PhoWhisper chưa có trong `data/` (`local_files_only=True`) → thử `WHISPER_PRELOAD=0`; PostgreSQL không kết nối → đã fallback SQLite? |

- Kiểm tra `GET /api/health` (`llm_configured`, `database`) trước — mock trả dữ liệu cố định, không phản ánh AI thật.
- Lỗi nằm ở mobile hoặc nhà cung cấp LLM → không đoán hợp đồng; báo người dùng, ghi giả thuyết `[cần xác nhận]`.

## Bước 3 — Diagnose
- Tìm root cause (hỏi "vì sao" tới khi gặp dòng code/cấu hình gây lỗi), không dừng ở triệu chứng.
- So cấu hình: chỉ so **tên key** biến môi trường, không in giá trị.

## Bước 4 — Fix
- Sửa nhỏ nhất ở đúng file (CLAUDE.md §2). Giữ test ở Bước 1 làm regression test.
- Chạy `pytest -q` toàn bộ, dán dòng `N passed` / `N failed`.

## Dừng và hỏi
- Lỗi chập chờn không tái hiện được.
- Root cause ở repo/service khác.
- Fix cần đổi hợp đồng API hoặc thêm dependency.
