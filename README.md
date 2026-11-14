# SignBridge-AI

Dịch vụ AI Microservice cho dự án giao tiếp hai chiều **SignBridge** (dành cho người khiếm thính và cộng đồng).

---

## 1. Giới thiệu & Vai trò kiến trúc

Hệ thống SignBridge bao gồm 2 thành phần chính:
- **Mobile Client (React Native / Expo):** Ứng dụng di động dành cho người khiếm thính và nhân viên thu ngân/phục vụ.
- **SignBridge Unified AI Backend (FastAPI - Repo này):** Đóng vai trò Backend hợp nhất kiêm AI Inference Engine & Database:
  - **Speech-to-Text (STT):** Nhận diện giọng nói tiếng Việt độ chính xác cao bằng mô hình **PhoWhisper** chạy qua **CTranslate2** (`faster-whisper`), tối ưu CPU với lượng tử hóa `int8`.
  - **Tóm tắt & Gợi ý phản hồi:** Tóm tắt lời nói ≤ 15 từ, Zero-Number-Error Guardrail, 3 câu trả lời nhanh cho người khiếm thính.
  - **Mở rộng thẻ từ khóa:** Chuyển thẻ ký hiệu thành câu phát âm thanh lịch sự.
  - **VSL / Vision:** Nhận diện khung hình ngôn ngữ ký hiệu (Vietnamese Sign Language) từ camera.
  - **CSDL Thẻ từ khóa (Quick Chips):** Quản lý thẻ hệ thống và thẻ cá nhân người dùng (PostgreSQL / SQLite fallback).

---

## 2. Cấu trúc thư mục

```
SignBridge-AI/
├── app.py                     # Ứng dụng FastAPI & Web Test Studio
├── test_transcribe.py         # Script CLI đo độ trễ & benchmark phiên âm
├── requirements.txt           # Danh sách thư viện Python
├── docs/                      # Tài liệu thiết kế & phân công
│   ├── luong-xu-ly-chinh.md   # Thiết kế luồng xử lý chi tiết (Mermaid sequence)
│   └── phan-cong.md           # Phân công công việc nhóm
├── data/                      # Lưu trữ weights model CTranslate2 (git ignored)
│   └── sample_vi.wav          # Audio mẫu ngắn tiếng Việt
├── test_audio-text/           # Thư mục chứa audio thực tế kiểm thử
│   └── test.mp3               # Audio mẫu kiểm thử thực tế (câu đặt đồ uống)
└── README.md
```

---

## 3. Cài đặt môi trường

### Yêu cầu
- **Python:** 3.11+
- **Hệ điều hành:** Windows / Linux / macOS (trên Windows cần cài Microsoft Visual C++ Redistributable 2015-2022)

### Các bước cài đặt

1. Tạo và kích hoạt môi trường ảo (Virtual Environment):
   ```powershell
   # Windows (PowerShell)
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```

2. Cài đặt các thư viện cần thiết:
   ```powershell
   pip install -r requirements.txt
   ```

---

## 4. Hướng dẫn chạy & Kiểm thử

### Cách 1: Kiểm thử nhanh qua dòng lệnh (CLI Benchmark)
Dùng script `test_transcribe.py` để đo thời gian tải model, tốc độ xử lý âm thanh thực tế và độ chính xác:
```powershell
.\venv\Scripts\python.exe test_transcribe.py test_audio-text\test.mp3 vi
```

### Cách 2: Khởi chạy API Server & Web Studio
Khởi động FastAPI server bằng Uvicorn:
```powershell
.\venv\Scripts\python.exe -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

Sau khi server chạy:
- **Giao diện Web Test Studio:** Mở trình duyệt tại [http://localhost:8000](http://localhost:8000) (hỗ trợ ghi âm trực tiếp qua Micro hoặc upload file âm thanh `.mp3`, `.wav`, `.m4a`).
- **Tài liệu Swagger UI:** Truy cập [http://localhost:8000/docs](http://localhost:8000/docs) để xem và test các endpoint API tương tác.

---

## 5. Danh sách API chính

### 1. Kiểm tra trạng thái hệ thống
- **Endpoint:** `GET /api/health`
- **Response:**
  ```json
  {
    "status": "UP",
    "service": "SignBridge-AI"
  }
  ```

### 2. Phiên âm giọng nói sang văn bản (Speech-to-Text)
- **Endpoint:** `POST /api/v1/speech/transcribe`
- **Content-Type:** `multipart/form-data`
- **Parameters:**
  - `audio` (file, bắt buộc): File âm thanh định dạng `.wav`, `.mp3`, `.m4a`, `.webm`, `.ogg`.
  - `language` (string, mặc định: `"vi"`): Mã ngôn ngữ phiên âm (`vi` hoặc `auto`).
- **Response mẫu:**
  ```json
  {
    "success": true,
    "text": "tôi muốn mua một cốc trà sữa trân châu nhưng ít đường năm mươi phần trăm đá.",
    "language": "vi",
    "language_probability": 1.0,
    "duration_seconds": 4.86,
    "processing_time_ms": 4827
  }
  ```

---


### 3. Endpoint cho mobile (hợp đồng `docs/luong-xu-ly-chinh.md` §4)

| Method | Path | Body |
|---|---|---|
| GET | `/api/health` | — |
| POST | `/api/sign` | multipart: `context`, `frames` (4/8/12/16 file JPEG ≤ 250KB), `personalChips` (JSON array ≤ 20), `previousIncoming` (≤ 300 ký tự) |
| POST | `/api/expand` | JSON: `{context, chips[1..5] (≤ 50 ký tự), previousIncoming}` |
| POST | `/api/summarize` | multipart: `context`, `audio` (m4a ≤ 2MB; Web Studio thêm webm/wav/mp3/ogg), `previousOutgoing` |
| GET/POST/DELETE | `/api/chips` (alias `/api/v1/chips`), `POST /api/chips/reset` | Thẻ hệ thống + thẻ cá nhân, người dùng xác định bằng header `X-User-Id` (hoặc `user_id`) — mở rộng, không có trong §4 |
| POST | `/api/ai/suggest-chips` (alias `/api/v1/ai/suggest-chips`) | JSON: `{context, recentText, existingChips}` — mở rộng |

Mọi lỗi trả `{"error": {"code", "message"}}` với mã theo bảng §4.0 (`INVALID_REQUEST`, `PAYLOAD_TOO_LARGE`,
`UNSUPPORTED_MEDIA_TYPE`, `NO_SIGN_DETECTED`, `NO_SPEECH_DETECTED`, `AI_UPSTREAM_ERROR`, `AI_TIMEOUT`).
Chưa đặt `LLM_API_KEY` → chế độ mock (gửi `personalChips=["MOCK_LOW"]` lên `/api/sign` để thử luồng confidence thấp).

### 4. Chạy test

```powershell
.env\Scripts\python.exe -m pip install -r requirements-dev.txt
.env\Scripts\python.exe -m pytest -q
```

---

## 6. Cấu hình Mô hình

Mặc định server sử dụng mô hình tối ưu tiếng Việt **PhoWhisper**:
- **Model ID:** `diepho/PhoWhisper-small-ct2`
- **Định dạng:** CTranslate2 int8 (tối ưu chạy trên CPU không cần GPU rời)
- **Tùy biến:** Có thể đổi mô hình bằng biến môi trường `WHISPER_MODEL`, ví dụ:
  ```powershell
  $env:WHISPER_MODEL="diepho/PhoWhisper-base-ct2"
  ```

---

## 7. Tài liệu tham khảo
- [PhoWhisper - VinAI Research](https://github.com/VinAIResearch/PhoWhisper)
- [faster-whisper (CTranslate2)](https://github.com/SYSTRAN/faster-whisper)
- [Vietnamese Sign Language Recognition](https://github.com/photienanh/Vietnamese-Sign-Language-Recognition)
