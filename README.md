# SignBridge-AI (TV3)

Phần AI / Model cho dự án giao tiếp hai chiều **SignBridge** (Hackathon).

## 1. Cấu trúc thư mục

```
SignBridge-AI/
├── docs/                      # Tài liệu luồng xử lý và phân công nhóm
│   ├── luong-xu-ly-chinh.md
│   └── phan-cong.md
├── data/                      # Lưu trữ audio mẫu & model weights (git ignored)
│   └── sample_vi.wav          # File audio mẫu tiếng Việt
├── test_transcribe.py         # Script kiểm thử và đo độ trễ V1
├── requirements.txt           # Danh sách thư viện Python
└── README.md
```

## 2. Hướng dẫn cài đặt & Chạy thử V1 (Speech-to-Text)

### Yêu cầu môi trường
- Python 3.11+
- Windows (đã cài đặt Microsoft Visual C++ 2015-2022 Redistributable x64)

### Cài đặt môi trường ảo
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Chạy kiểm thử phiên âm tiếng Việt (CPU int8)
```powershell
.\venv\Scripts\python.exe test_transcribe.py data\sample_vi.wav vi
```

## 3. Các repository liên quan nghiên cứu
- `faster-whisper`: https://github.com/SYSTRAN/faster-whisper
- `whisper.cpp`: https://github.com/ggml-org/whisper.cpp
- `Vietnamese-Sign-Language-Recognition`: https://github.com/photienanh/Vietnamese-Sign-Language-Recognition
