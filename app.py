import os
import sys
import time
import io
import json
import uvicorn
from typing import List, Optional, Any
from pydantic import BaseModel
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Header
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Tự động nạp cấu hình từ .env
load_dotenv()

# Tối ưu hóa: Bật chế độ offline để CTranslate2 không gửi request thăm dò HuggingFace gây trễ
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

from faster_whisper import WhisperModel
from llm_service import summarize_text, expand_chips, recognize_sign, suggest_smart_chips, LLM_MODEL, LLM_BASE_URL

# Tự động kết nối cơ sở dữ liệu (PostgreSQL / SQLite fallback)
try:
    import database
    database.init_db()
    DB_AVAILABLE = True
except Exception as e:
    print(f"[-] Database khởi tạo thất bại ({e}). Sẽ chạy ở chế độ in-memory.")
    DB_AVAILABLE = False
    DB_AVAILABLE = False

# Cấu hình encoding trên Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
MODEL_NAME = os.getenv("WHISPER_MODEL", "diepho/PhoWhisper-small-ct2")

app = FastAPI(
    title="SignBridge AI Service",
    description="Speech-to-Text & VSL LLM Service cho dự án SignBridge",
    version="1.2.0"
)

# Cho phép Mobile / Web gọi API không bị chặn CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Benchmark thực tế: 4 CPU threads đạt hiệu suất cao nhất trên CTranslate2 (tránh context-switching)
CPU_THREADS = min(4, os.cpu_count() or 4)
print(f"[*] Khởi tạo PhoWhisperModel ('{MODEL_NAME}', CPU, int8, cpu_threads={CPU_THREADS}) từ: {MODEL_DIR}...")
whisper_model = WhisperModel(
    MODEL_NAME,
    device="cpu",
    compute_type="int8",
    download_root=MODEL_DIR,
    local_files_only=True,
    cpu_threads=CPU_THREADS
)
print("[+] Model PhoWhisper đã sẵn sàng phục vụ!")

# ----------------- Contextual Prompt Biasing -----------------
# Gợi ý từ vựng cho PhoWhisper theo từng bối cảnh -> Tăng độ chính xác nhận diện từ khóa & số liệu
CONTEXT_PROMPTS = {
    "CAFE": "Menu quán: cà phê, trà sữa, trân châu, ít đường, năm mươi phần trăm đá, giá tiền, chuyển khoản QR, mang về.",
    "PHARMACY": "Đơn thuốc: panadol, thuốc giảm đau, liều dùng, viên sau ăn, ngày hai lần, giá tiền, vỉ, hộp.",
    "PUBLIC": "Thủ tục hành chính: quầy số, nộp hồ sơ, giấy tờ, căn cước công dân, đóng tiền, lệ phí, biên lai.",
    "CUSTOM": "Giao tiếp hàng ngày: giá tiền, số quầy, số lượng, thời gian, đồng ý, cảm ơn."
}

# ----------------- Data Models -----------------
class HighlightItem(BaseModel):
    type: str
    text: str

class SummarizeResponse(BaseModel):
    transcript: str
    summary: str
    highlights: List[HighlightItem]
    iconCode: str
    quickReplies: List[str]
    suggestedChips: List[str] = []
    processing_time_ms: Optional[int] = None

class SummarizeTextRequest(BaseModel):
    context: str = "CUSTOM"
    transcript: str
    previousOutgoing: Optional[str] = None

class ExpandRequest(BaseModel):
    context: str = "CUSTOM"
    chips: List[str]
    previousIncoming: Optional[str] = None

class ExpandResponse(BaseModel):
    spoken_sentence: str

class SignResponse(BaseModel):
    glosses: List[str]
    confidence: float
    spoken_sentence: str
    suggestedChips: List[str]

class CreateChipRequest(BaseModel):
    text: str
    context: str = "CUSTOM"
    user_id: Optional[str] = None

class SuggestChipsRequest(BaseModel):
    context: str = "CUSTOM"
    recentText: Optional[str] = None
    existingChips: Optional[List[str]] = []

# ----------------- Helper Functions -----------------
def run_transcribe(audio_source: Any, language: str = "vi", context: str = "CUSTOM") -> tuple[str, float, str, float]:
    """
    Nhận diện âm thanh siêu tốc trực tiếp từ bộ nhớ RAM (In-Memory Buffer)
    Sử dụng greedy search (beam_size=1) + temperature=0.0 + initial_prompt theo ngữ cảnh.
    Tối ưu VAD (threshold=0.3, speech_pad_ms=250) để bắt trọn cả tiếng nói nhỏ, nói thầm, tránh bị nuốt từ.
    """
    initial_prompt = CONTEXT_PROMPTS.get(context, CONTEXT_PROMPTS["CUSTOM"])
    segments, info = whisper_model.transcribe(
        audio_source,
        language=language if language != "auto" else None,
        beam_size=1,                         # Greedy search: nhanh gấp 2-3 lần beam search
        temperature=0.0,                     # Tuyệt đối ổn định & nhanh nhất
        condition_on_previous_text=False,    # Tắt suy đoán chuỗi trước để tránh lặp câu và giảm tính toán
        vad_filter=True,                     # Lọc bỏ khoảng lặng
        vad_parameters=dict(
            threshold=0.3,                   # Hạ ngưỡng từ 0.5 xuống 0.3 để bắt cả giọng nói nhỏ, thì thầm
            min_speech_duration_ms=120,      # Nhận diện cả các từ ngắn, nuốt âm
            speech_pad_ms=250                # Đệm 250ms hai đầu để tránh cụt âm tiết đầu/cuối
        ),
        initial_prompt=initial_prompt        # Mồi từ khóa theo ngữ cảnh để nhận diện chính xác số và tên món
    )
    text_parts = [s.text for s in segments]
    transcript = "".join(text_parts).strip()
    return transcript, round(info.duration, 2), getattr(info, "language", language), round(getattr(info, "language_probability", 1.0), 2)

# ----------------- API Endpoints -----------------

@app.post("/api/v1/speech/transcribe")
async def transcribe_audio(
    audio: UploadFile = File(...),
    language: str = Form("vi"),
    context: str = Form("CUSTOM")
):
    """
    API nhận diện giọng nói tiếng Việt từ file âm thanh.
    Hỗ trợ .wav, .mp3, .m4a, .webm, .ogg
    Xử lý trực tiếp in-memory không ghi đĩa, giảm tối đa độ trễ I/O
    """
    t_start = time.time()
    
    # Lưu file tạm để đưa vào faster-whisper
    content = await audio.read()
    if not content:
        raise HTTPException(status_code=400, detail="INVALID_AUDIO_FILE")

    try:
        transcript, duration, lang, lang_prob = run_transcribe(io.BytesIO(content), language=language, context=context)
        t_proc_ms = int((time.time() - t_start) * 1000)

        return {
            "success": True,
            "text": transcript,
            "language": lang,
            "language_probability": lang_prob,
            "duration_seconds": duration,
            "processing_time_ms": t_proc_ms
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi nhận diện âm thanh: {str(e)}")

@app.post("/api/v1/ai/summarize", response_model=SummarizeResponse)
async def summarize_transcript(req: SummarizeTextRequest):
    """
    Tóm tắt văn bản lời nói nhân viên qua LLM (OpenAI / 9router)
    """
    t_start = time.time()
    ai_output = summarize_text(
        transcript=req.transcript,
        context=req.context,
        previous_outgoing=req.previousOutgoing
    )
    t_proc_ms = int((time.time() - t_start) * 1000)
    return SummarizeResponse(
        transcript=req.transcript,
        summary=ai_output.get("summary", ""),
        highlights=ai_output.get("highlights", []),
        iconCode=ai_output.get("iconCode", "INFO"),
        quickReplies=ai_output.get("quickReplies", []),
        suggestedChips=ai_output.get("suggestedChips", []),
        processing_time_ms=t_proc_ms
    )

@app.post("/api/summarize", response_model=SummarizeResponse)
async def process_summarize_audio(
    audio: UploadFile = File(...),
    context: str = Form("CUSTOM"),
    previousOutgoing: Optional[str] = Form(None)
):
    """
    Endpoint chuẩn theo hợp đồng (mục 4.4): Nhận audio -> STT PhoWhisper -> LLM Tóm tắt trực tiếp
    Toàn bộ xử lý in-memory stream, giảm I/O và tối ưu response time
    """
    t_start = time.time()
    content = await audio.read()
    if not content:
        raise HTTPException(status_code=400, detail="EMPTY_AUDIO_FILE")

    try:
        transcript, duration, _, _ = run_transcribe(io.BytesIO(content), language="vi", context=context)
        if not transcript:
            raise HTTPException(status_code=422, detail="NO_SPEECH_DETECTED")

        ai_output = summarize_text(
            transcript=transcript,
            context=context,
            previous_outgoing=previousOutgoing
        )
        t_proc_ms = int((time.time() - t_start) * 1000)

        return SummarizeResponse(
            transcript=transcript,
            summary=ai_output.get("summary", ""),
            highlights=ai_output.get("highlights", []),
            iconCode=ai_output.get("iconCode", "INFO"),
            quickReplies=ai_output.get("quickReplies", []),
            suggestedChips=ai_output.get("suggestedChips", []),
            processing_time_ms=t_proc_ms
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi xử lý tóm tắt: {str(e)}")

@app.post("/api/v1/ai/expand", response_model=ExpandResponse)
@app.post("/api/expand", response_model=ExpandResponse)
async def process_expand_chips(req: ExpandRequest):
    """
    Endpoint mở rộng thẻ từ khóa thành câu nói tiếng Việt lịch sự (mục 4.3)
    """
    res = expand_chips(
        chips=req.chips,
        context=req.context,
        previous_incoming=req.previousIncoming
    )
    return ExpandResponse(spoken_sentence=res.get("spoken_sentence", ""))

@app.post("/api/sign", response_model=SignResponse)
async def process_sign_frames(
    frames: List[UploadFile] = File(...),
    context: str = Form("CUSTOM"),
    personalChips: Optional[str] = Form(None),
    previousIncoming: Optional[str] = Form(None)
):
    """
    Endpoint nhận diện ngôn ngữ ký hiệu từ chuỗi frame ảnh JPEG (mục 4.2).
    """
    frames_bytes = [await f.read() for f in frames if f.size and f.size > 0]
    if not frames_bytes:
        raise HTTPException(status_code=422, detail="NO_SIGN_DETECTED")

    chips_list = []
    if personalChips:
        try:
            chips_list = json.loads(personalChips)
        except Exception:
            chips_list = [c.strip() for c in personalChips.split(",") if c.strip()]

    result = recognize_sign(
        frames_bytes=frames_bytes,
        context=context,
        personal_chips=chips_list,
        previous_incoming=previousIncoming
    )
    return SignResponse(**result)

# ----------------- Quick Chips & History (CSDL) -----------------

def get_current_user_id(x_user_id: Optional[str] = None, user_id: Optional[str] = None) -> str:
    candidate = x_user_id or user_id
    if candidate and candidate.strip():
        return candidate.strip()
    return "default_user"

@app.get("/api/v1/chips")
@app.get("/api/chips")
def list_chips(
    user_id: Optional[str] = None,
    context: Optional[str] = None,
    x_user_id: Optional[str] = Header(None, alias="X-User-Id")
):
    """
    Lấy danh sách thẻ từ khóa (thẻ hệ thống + thẻ cá nhân của user_id hiện tại).
    Đảm bảo tính đa người dùng (Multi-tenancy): người dùng A không thấy thẻ người dùng B.
    """
    if not DB_AVAILABLE:
        return []
    uid = get_current_user_id(x_user_id, user_id)
    return database.get_chips_for_user(uid, context)

@app.post("/api/v1/chips")
@app.post("/api/chips")
def create_chip(
    req: CreateChipRequest,
    x_user_id: Optional[str] = Header(None, alias="X-User-Id")
):
    """
    Thêm thẻ cá nhân cho người dùng hiện tại
    """
    if not DB_AVAILABLE:
        raise HTTPException(status_code=503, detail="DATABASE_NOT_AVAILABLE")
    uid = get_current_user_id(x_user_id, req.user_id)
    try:
        return database.add_user_chip(uid, req.text, req.context)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/api/v1/chips/{chip_id}")
@app.delete("/api/chips/{chip_id}")
def remove_chip(
    chip_id: str,
    user_id: Optional[str] = None,
    x_user_id: Optional[str] = Header(None, alias="X-User-Id")
):
    """
    Xóa thẻ cá nhân của người dùng hiện tại (chỉ được xóa thẻ của mình, không thể xóa thẻ hệ thống)
    """
    if not DB_AVAILABLE:
        raise HTTPException(status_code=503, detail="DATABASE_NOT_AVAILABLE")
    uid = get_current_user_id(x_user_id, user_id)
    ok = database.delete_user_chip(uid, chip_id)
    return {"success": ok}

@app.post("/api/v1/chips/reset")
@app.post("/api/chips/reset")
def reset_chips(
    user_id: Optional[str] = None,
    x_user_id: Optional[str] = Header(None, alias="X-User-Id")
):
    """
    Khôi phục danh sách thẻ về mặc định của hệ thống cho user_id hiện tại
    """
    if not DB_AVAILABLE:
        raise HTTPException(status_code=503, detail="DATABASE_NOT_AVAILABLE")
    uid = get_current_user_id(x_user_id, user_id)
    ok = database.reset_user_chips(uid)
    return {"success": ok}

@app.post("/api/v1/ai/suggest-chips")
@app.post("/api/ai/suggest-chips")
def get_ai_suggest_chips(req: SuggestChipsRequest):
    """
    AI tự động gợi ý các thẻ từ khóa thông minh dựa theo ngữ cảnh và câu nói vừa trao đổi
    """
    chips = suggest_smart_chips(
        context=req.context,
        recent_text=req.recentText,
        existing_chips=req.existingChips
    )
    return {"suggestedChips": chips}

@app.get("/api/health")
def health_check():
    api_key_configured = bool(os.getenv("LLM_API_KEY", "").strip())
    return {
        "status": "UP",
        "service": "SignBridge-AI",
        "database": "PostgreSQL" if DB_AVAILABLE else "Disabled",
        "whisper_model": MODEL_NAME,
        "llm_model": os.getenv("LLM_MODEL", LLM_MODEL),
        "llm_configured": api_key_configured,
        "llm_base_url": os.getenv("LLM_BASE_URL", LLM_BASE_URL)
    }

# ----------------- Web Test Studio HTML -----------------

@app.get("/", response_class=HTMLResponse)
def index_page():
    return """
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SignBridge AI Studio</title>
    <style>
        :root {
            --primary: #2563eb;
            --primary-hover: #1d4ed8;
            --success: #16a34a;
            --danger: #dc2626;
            --warning: #f59e0b;
            --bg: #f8fafc;
            --card: #ffffff;
            --border: #e2e8f0;
            --text: #0f172a;
            --muted: #64748b;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
        body { background: var(--bg); color: var(--text); padding: 24px 16px; display: flex; justify-content: center; }
        .container { width: 100%; max-width: 840px; }
        header { text-align: center; margin-bottom: 20px; }
        h1 { font-size: 26px; color: var(--primary); display: flex; align-items: center; justify-content: center; gap: 8px; }
        .subtitle { color: var(--muted); font-size: 14px; margin-top: 6px; }
        .badge-bar { display: flex; gap: 8px; justify-content: center; flex-wrap: wrap; margin-top: 10px; }
        .badge { padding: 4px 12px; border-radius: 999px; font-size: 12px; font-weight: 600; background: #e0e7ff; color: #3730a3; }
        .badge-green { background: #dcfce7; color: #166534; }
        .badge-amber { background: #fef3c7; color: #92400e; }
        .badge-user { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; background: #f1f5f9; padding: 4px 12px; border-radius: 999px; border: 1px solid #cbd5e1; margin-top: 8px; }
        
        .main-tabs { display: flex; gap: 8px; margin-bottom: 16px; border-bottom: 2px solid var(--border); padding-bottom: 6px; }
        .main-tab-btn { padding: 10px 18px; border: none; background: transparent; cursor: pointer; font-size: 15px; font-weight: 700; color: var(--muted); border-radius: 8px; }
        .main-tab-btn.active { color: var(--primary); background: #eff6ff; }
        
        .card { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 20px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); margin-bottom: 20px; }
        .card-title { font-size: 16px; font-weight: 700; margin-bottom: 14px; display: flex; align-items: center; gap: 6px; }
        
        .row { display: flex; gap: 12px; margin-bottom: 14px; }
        .col { flex: 1; }
        label { display: block; font-size: 13px; font-weight: 600; color: var(--muted); margin-bottom: 6px; }
        select, input[type="text"] { width: 100%; padding: 8px 12px; border: 1px solid var(--border); border-radius: 8px; font-size: 14px; }

        .mode-chip-btn { padding: 8px 14px; border-radius: 999px; background: #f1f5f9; border: 1px solid var(--border); font-size: 14px; font-weight: 600; cursor: pointer; transition: all 0.2s; }
        .mode-chip-btn.selected { background: var(--primary); color: #fff; border-color: var(--primary); }

        .mic-box { text-align: center; padding: 16px 0; }
        .mic-btn { width: 72px; height: 72px; border-radius: 50%; border: none; background: #fee2e2; color: var(--danger); font-size: 28px; cursor: pointer; transition: all 0.2s; display: inline-flex; align-items: center; justify-content: center; box-shadow: 0 4px 12px rgba(220,38,38,0.2); }
        .mic-btn.recording { background: var(--danger); color: #fff; animation: pulse 1.2s infinite; }
        @keyframes pulse {
            0% { transform: scale(1); box-shadow: 0 0 0 0 rgba(220,38,38,0.7); }
            70% { transform: scale(1.06); box-shadow: 0 0 0 16px rgba(220,38,38,0); }
            100% { transform: scale(1); box-shadow: 0 0 0 0 rgba(220,38,38,0); }
        }
        
        .upload-area { border: 2px dashed var(--border); border-radius: 12px; padding: 24px 16px; text-align: center; cursor: pointer; transition: border 0.2s; }
        .upload-area:hover { border-color: var(--primary); background: #f8fafc; }
        
        .btn-primary { width: 100%; padding: 12px; background: var(--primary); color: #fff; border: none; border-radius: 8px; font-weight: 700; font-size: 15px; cursor: pointer; transition: background 0.2s; margin-top: 10px; }
        .btn-primary:hover { background: var(--primary-hover); }
        .btn-primary:disabled { background: #94a3b8; cursor: not-allowed; }

        /* Màn hình hiển thị cho người khiếm thính */
        .summary-card { background: #eff6ff; border: 2px solid #bfdbfe; border-radius: 12px; padding: 20px; margin-top: 16px; }
        .summary-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
        .summary-icon { font-size: 32px; background: #fff; border-radius: 10px; width: 48px; height: 48px; display: flex; align-items: center; justify-content: center; box-shadow: 0 2px 4px rgba(0,0,0,0.06); }
        .summary-text { font-size: 22px; font-weight: 800; color: #1e3a8a; line-height: 1.4; margin-bottom: 12px; }
        
        .highlights-box { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 16px; }
        .hl-tag { padding: 4px 10px; border-radius: 6px; font-size: 13px; font-weight: 700; }
        .hl-PRICE { background: #dcfce7; color: #15803d; border: 1px solid #bbf7d0; }
        .hl-DOSAGE { background: #ffedd5; color: #c2410c; border: 1px solid #fed7aa; }
        .hl-QUANTITY { background: #f3e8ff; color: #7e22ce; border: 1px solid #e9d5ff; }
        .hl-TIME { background: #e0f2fe; color: #0369a1; border: 1px solid #bae6fd; }
        .hl-COUNTER { background: #fef08a; color: #854d0e; border: 1px solid #fde047; }
        .hl-OTHER { background: #f1f5f9; color: #475569; border: 1px solid #cbd5e1; }

        .quick-replies-title { font-size: 13px; font-weight: 700; color: #475569; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px; display: flex; align-items: center; gap: 6px; }
        .quick-replies-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 10px; }
        .reply-btn { padding: 12px 14px; background: #ffffff; border: 1.5px solid #cbd5e1; border-radius: 10px; font-size: 14px; font-weight: 600; color: #1e293b; text-align: left; cursor: pointer; transition: all 0.2s; box-shadow: 0 1px 3px rgba(0,0,0,0.06); display: flex; align-items: center; justify-content: space-between; }
        .reply-btn:hover { border-color: var(--primary); background: #f0f7ff; color: var(--primary); transform: translateY(-2px); box-shadow: 0 4px 6px -1px rgba(37,99,235,0.15); }
        .reply-btn .speaker-icon { font-size: 16px; opacity: 0.7; }

        .transcript-box { background: #f8fafc; border: 1px solid var(--border); border-radius: 8px; padding: 12px; font-size: 14px; color: #334155; margin-top: 14px; }
        
        .chips-container { display: flex; flex-wrap: wrap; gap: 8px; margin: 12px 0; min-height: 48px; }
        .chip-tag { padding: 7px 12px; border-radius: 999px; background: #f1f5f9; border: 1px solid var(--border); font-size: 14px; font-weight: 600; cursor: pointer; transition: all 0.2s; display: inline-flex; align-items: center; gap: 4px; user-select: none; }
        .chip-tag:hover { border-color: var(--primary); background: #f8fafc; }
        .chip-tag.selected { background: var(--primary); color: #fff; border-color: var(--primary); }
        .chip-tag.custom { border-style: dashed; border-color: #3b82f6; background: #eff6ff; }
        .chip-tag.custom.selected { background: var(--primary); color: #fff; border-style: solid; }
        .chip-tag .btn-del { font-size: 16px; margin-left: 4px; cursor: pointer; opacity: 0.6; line-height: 1; border: none; background: none; color: inherit; padding: 0 2px; }
        .chip-tag .btn-del:hover { opacity: 1; color: var(--danger); font-weight: bold; }

        .ai-chip-pill { padding: 6px 12px; border-radius: 999px; background: #dcfce7; color: #166534; border: 1px solid #86efac; font-size: 13px; font-weight: 600; cursor: pointer; transition: all 0.2s; display: inline-flex; align-items: center; gap: 4px; }
        .ai-chip-pill:hover { background: #bbf7d0; transform: translateY(-1px); }
    </style>
</head>
<body>
<div class="container">
    <header>
        <h1>🌉 SignBridge AI Studio</h1>
        <div class="subtitle">Môi trường kiểm thử Hai Chiều: Speech-to-Text, Tóm tắt Thông minh & Gợi ý Phản hồi cho Người Khiếm Thính/Câm</div>
        <div class="badge-bar">
            <span class="badge">STT: PhoWhisper small (ct2)</span>
            <span class="badge badge-green" id="llmBadge">LLM: Active</span>
            <span class="badge badge-amber">DB: PostgreSQL</span>
        </div>
        <div>
            <div class="badge-user">
                <span>👤 User ID: <strong id="userIdDisplay" style="color:var(--primary);">...</strong></span>
                <button onclick="promptChangeUserId()" style="border:none; background:none; color:var(--primary); font-weight:700; cursor:pointer; text-decoration:underline;">Đổi ID</button>
            </div>
        </div>
    </header>

    <div class="main-tabs">
        <button class="main-tab-btn active" onclick="switchMainTab('summarize')">🎙️ Chiều Về: Giọng nói ➔ Tóm tắt & Gợi ý (Cho Người Khiếm Thính)</button>
        <button class="main-tab-btn" onclick="switchMainTab('expand')">🖐️ Chiều Đi: Thẻ Ký hiệu ➔ Câu Lời Nói (Phát Loa)</button>
    </div>

    <!-- TAB 1: SUMMARIZE -->
    <div id="tab-summarize" class="tab-content">
        <div class="card">
            <div class="card-title">⚙️ Thiết lập Ngữ cảnh Cuộc gọi / Quầy Dịch vụ</div>
            <div class="row">
                <div class="col">
                    <label>Bối cảnh (Context Preset):</label>
                    <select id="contextSelect" onchange="onContextChange()">
                        <option value="CAFE">Quán Ăn / Cà Phê (CAFE)</option>
                        <option value="PHARMACY">Hiệu Thuốc / Bệnh Viện (PHARMACY)</option>
                        <option value="PUBLIC">Hành Chính Công (PUBLIC)</option>
                        <option value="CUSTOM" selected>Tự do / Hỏi đường / Chung (CUSTOM)</option>
                    </select>
                </div>
                <div class="col">
                    <label>Câu người khiếm thính nói lượt trước (previousOutgoing):</label>
                    <input type="text" id="prevOutgoing" placeholder="VD: Cho em hỏi đường ra chợ với ạ">
                </div>
            </div>

            <div class="tabs" style="display:flex; gap:8px; margin-bottom:12px;">
                <button class="mode-chip-btn selected" id="btnModeMic" onclick="switchAudioMode('mic')">🔴 Ghi âm qua Mic</button>
                <button class="mode-chip-btn" id="btnModeUpload" onclick="switchAudioMode('upload')">📁 Tải file âm thanh (.mp3, .m4a, .wav)</button>
            </div>

            <!-- Mode 1: Mic -->
            <div id="mode-mic">
                <div class="mic-box">
                    <button id="micBtn" class="mic-btn" onclick="toggleRecord()">🎤</button>
                    <div id="micLabel" style="margin-top:10px; font-weight:600; font-size:14px; color:var(--muted);">Bấm để bắt đầu thu âm</div>
                    <div id="recordTime" style="font-size:13px; color:var(--danger); margin-top:4px; font-weight:700; display:none;">00:00</div>
                </div>
                <audio id="audioPlayback" controls style="width:100%; display:none; margin-top:10px;"></audio>
                <button id="submitMicBtn" class="btn-primary" style="display:none;" onclick="submitAudioData(recordedBlob, 'mic.webm')">🚀 Phiên âm & Tóm tắt ngay</button>
            </div>

            <!-- Mode 2: Upload -->
            <div id="mode-upload" style="display:none;">
                <div class="upload-area" onclick="document.getElementById('audioFileInput').click()">
                    <div style="font-size:32px; margin-bottom:6px;">📤</div>
                    <div id="fileNameDisplay" style="font-weight:600;">Bấm vào đây để chọn file âm thanh</div>
                    <div style="font-size:12px; color:var(--muted); margin-top:4px;">Hỗ trợ .wav, .mp3, .m4a, .webm, .ogg</div>
                </div>
                <input type="file" id="audioFileInput" accept="audio/*" style="display:none;" onchange="handleFilePicked(this)">
                <button id="submitFileBtn" class="btn-primary" disabled onclick="submitFileAudio()">🚀 Phiên âm & Tóm tắt ngay</button>
            </div>

            <div id="loadingBox" style="display:none; text-align:center; padding:20px; color:var(--primary); font-weight:700;">
                ⏳ Đang phiên âm PhoWhisper & gọi LLM tóm tắt... Vui lòng đợi trong giây lát!
            </div>

            <!-- Kết quả hiển thị cho người khiếm thính -->
            <div id="resultBox" style="display:none;">
                <div class="card-title" style="margin-top:20px;">📱 Kết quả hiển thị cho Người Khiếm Thính (Màn hình nửa dưới)</div>
                <div class="summary-card">
                    <div class="summary-header">
                        <div id="iconDisplay" class="summary-icon">ℹ️</div>
                        <span id="procTimeBadge" class="badge" style="background:#dbeafe; color:#1e40af;">0.0s</span>
                    </div>
                    <div id="summaryDisplay" class="summary-text">Chưa có kết quả</div>
                    <div id="highlightsBox" class="highlights-box"></div>

                    <div class="quick-replies-title">⚡ 3 CÂU PHẢN HỒI NHANH (CHẠM ĐỂ PHÁT ÂM RA LOA):</div>
                    <div id="repliesGrid" class="quick-replies-grid"></div>

                    <!-- Gợi ý từ khóa phản hồi -->
                    <div style="margin-top:16px; padding:12px; background:#f0fdf4; border:1px solid #bbf7d0; border-radius:10px;">
                        <span style="font-size:12px; font-weight:700; color:#15803d; text-transform:uppercase;">💡 GỢI Ý TỪ KHÓA ĐỂ BẠN TRẢ LỜI (CHẠM ĐỂ CHỌN SANG CHIỀU ĐI):</span>
                        <div id="summarySuggestedChips" style="display:flex; flex-wrap:wrap; gap:6px; margin-top:8px;"></div>
                    </div>
                </div>

                <div class="transcript-box">
                    <span style="font-weight:700; color:var(--muted);">VĂN BẢN ĐẦY ĐỦ TỪ PHOWHISPER:</span>
                    <p id="transcriptDisplay" style="margin-top:4px; font-weight:600; font-size:15px; color:#1e293b;"></p>
                </div>
            </div>
        </div>
    </div>

    <!-- TAB 2: EXPAND -->
    <div id="tab-expand" class="tab-content" style="display:none;">
        <div class="card">
            <div class="card-title">🖐️ Người khiếm thính chọn Thẻ từ khóa (Chips)</div>
            <p style="font-size:13px; color:var(--muted); margin-bottom:12px;">Chạm vào các thẻ từ khóa bên dưới để mô phỏng người khiếm thính chọn ý muốn nói. Thẻ có viền đứt nét là thẻ riêng của bạn (có nút <strong>&times;</strong> để xóa):</p>
            
            <!-- Bộ thẻ từ Database -->
            <div class="chips-container" id="presetChips">
                <span style="color:var(--muted); font-size:13px;">Đang tải danh sách thẻ từ PostgreSQL...</span>
            </div>

            <!-- Form thêm thẻ cá nhân -->
            <div style="display:flex; gap:8px; margin: 12px 0;">
                <input type="text" id="newChipInput" placeholder="Thêm thẻ cá nhân mới (VD: Dị ứng tôm, Không đường)..." style="flex:1;" onkeydown="if(event.key==='Enter') addNewChip()">
                <button class="btn-primary" style="width:auto; padding:8px 16px; margin:0; white-space:nowrap;" onclick="addNewChip()">➕ Thêm Thẻ</button>
                <button style="width:auto; padding:8px 14px; margin:0; white-space:nowrap; background:#fff; border:1px solid #cbd5e1; border-radius:8px; cursor:pointer; font-weight:600; color:#64748b;" onclick="resetCustomChips()" title="Khôi phục thẻ hệ thống mặc định">🔄 Đặt lại</button>
            </div>

            <!-- Gợi ý thẻ từ AI -->
            <div style="margin-top:14px; padding:12px; background:#f8fafc; border:1.5px dashed #93c5fd; border-radius:10px;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                    <span style="font-size:13px; font-weight:700; color:#1e40af;">✨ AI GỢI Ý THẺ THEO BỐI CẢNH:</span>
                    <button style="background:none; border:none; color:var(--primary); font-weight:700; cursor:pointer; font-size:13px;" onclick="requestAiChips()">✨ AI Gợi ý thêm thẻ</button>
                </div>
                <div id="aiSuggestedChipsContainer" style="display:flex; flex-wrap:wrap; gap:6px;">
                    <span style="font-size:12px; color:var(--muted); font-style:italic;">Bấm 'AI Gợi ý thêm thẻ' để sinh từ khóa thông minh theo ngữ cảnh...</span>
                </div>
            </div>

            <div style="margin-top:16px;">
                <label>Các thẻ đã chọn (ngăn cách bằng dấu phẩy):</label>
                <input type="text" id="customChipsInput" placeholder="VD: Trà sữa trân châu, Ít đường, 50% đá">
            </div>

            <button class="btn-primary" onclick="submitExpand()">🗣️ Mở rộng thành Câu Lời Nói Lịch Sự</button>

            <div id="expandResultBox" style="display:none; margin-top:16px;">
                <div class="card-title">🔊 Câu phát âm cho Nhân viên nghe (Màn hình nửa trên):</div>
                <div style="background:#f0fdf4; border:2px solid #bbf7d0; border-radius:12px; padding:16px;">
                    <div id="spokenSentenceDisplay" style="font-size:20px; font-weight:700; color:#15803d; line-height:1.5;"></div>
                    <button class="btn-primary" style="background:#16a34a; margin-top:12px; width:auto; padding:8px 16px;" onclick="speakCurrentSentence()">🔊 Phát âm thanh (TTS)</button>
                </div>
            </div>
        </div>
    </div>
</div>

<script>
const ICON_MAP = {
    "PILL": "💊",
    "MONEY": "💵",
    "QR_PAYMENT": "📱",
    "COUNTER": "🏢",
    "TIME": "⏱️",
    "DOCUMENT": "📄",
    "DRINK": "🧋",
    "FOOD": "🍲",
    "CHECK": "✅",
    "WARNING": "⚠️",
    "INFO": "ℹ️"
};

// Quản lý Multi-tenancy User ID
let currentUserId = localStorage.getItem('signbridge_user_id');
if (!currentUserId) {
    currentUserId = 'user_' + Math.random().toString(36).substring(2, 9);
    localStorage.setItem('signbridge_user_id', currentUserId);
}
document.getElementById('userIdDisplay').innerText = currentUserId;

function promptChangeUserId() {
    const newId = prompt("Nhập User ID mới (để kiểm tra cơ chế cách ly dữ liệu giữa các người dùng):", currentUserId);
    if (newId && newId.trim()) {
        currentUserId = newId.trim();
        localStorage.setItem('signbridge_user_id', currentUserId);
        document.getElementById('userIdDisplay').innerText = currentUserId;
        loadUserChips();
    }
}

let mediaRecorder;
let audioChunks = [];
let recordedBlob = null;
let isRecording = false;
let recordTimerInterval = null;
let recordSeconds = 0;
let lastRecentTranscript = "";

function switchMainTab(tab) {
    document.querySelectorAll('.main-tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.style.display = 'none');
    if (tab === 'summarize') {
        event.target.classList.add('active');
        document.getElementById('tab-summarize').style.display = 'block';
    } else {
        event.target.classList.add('active');
        document.getElementById('tab-expand').style.display = 'block';
    }
}

function switchAudioMode(mode) {
    if (mode === 'mic') {
        document.getElementById('btnModeMic').classList.add('selected');
        document.getElementById('btnModeUpload').classList.remove('selected');
        document.getElementById('mode-mic').style.display = 'block';
        document.getElementById('mode-upload').style.display = 'none';
    } else {
        document.getElementById('btnModeMic').classList.remove('selected');
        document.getElementById('btnModeUpload').classList.add('selected');
        document.getElementById('mode-mic').style.display = 'none';
        document.getElementById('mode-upload').style.display = 'block';
    }
}

async function toggleRecord() {
    if (!isRecording) {
        try {
            // Tối ưu hóa Micro: Tự động khuếch đại (AGC) khi nói nhỏ + Lọc tiếng ồn môi trường
            const stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    autoGainControl: true,  // Tự động tăng độ nhạy micro khi nói nhỏ/ở xa
                    noiseSuppression: true, // Khử tiếng ồn nền (xe cộ, quạt gió)
                    echoCancellation: true  // Chống dội âm
                }
            });
            mediaRecorder = new MediaRecorder(stream);
            audioChunks = [];
            mediaRecorder.ondataavailable = e => { if (e.data.size > 0) audioChunks.push(e.data); };
            mediaRecorder.onstop = () => {
                recordedBlob = new Blob(audioChunks, { type: 'audio/webm' });
                const player = document.getElementById('audioPlayback');
                player.src = URL.createObjectURL(recordedBlob);
                player.style.display = 'block';
                document.getElementById('submitMicBtn').style.display = 'block';
            };
            mediaRecorder.start();
            isRecording = true;
            document.getElementById('micBtn').classList.add('recording');
            document.getElementById('micLabel').innerText = "Đang thu âm... Bấm để dừng";
            
            recordSeconds = 0;
            const timerEl = document.getElementById('recordTime');
            timerEl.style.display = 'block';
            timerEl.innerText = "00:00";
            recordTimerInterval = setInterval(() => {
                recordSeconds++;
                const mins = String(Math.floor(recordSeconds / 60)).padStart(2, '0');
                const secs = String(recordSeconds % 60).padStart(2, '0');
                timerEl.innerText = `${mins}:${secs}`;
            }, 1000);
        } catch (err) {
            alert("Không thể truy cập Microphone: " + err.message);
        }
    } else {
        mediaRecorder.stop();
        mediaRecorder.stream.getTracks().forEach(t => t.stop());
        isRecording = false;
        clearInterval(recordTimerInterval);
        document.getElementById('micBtn').classList.remove('recording');
        document.getElementById('micLabel').innerText = "Đã thu xong. Bấm nút bên dưới để xử lý.";
    }
}

function handleFilePicked(input) {
    if (input.files && input.files[0]) {
        const file = input.files[0];
        document.getElementById('fileNameDisplay').innerText = "Đã chọn: " + file.name + " (" + (file.size / 1024).toFixed(1) + " KB)";
        document.getElementById('submitFileBtn').disabled = false;
    }
}

function submitFileAudio() {
    const file = document.getElementById('audioFileInput').files[0];
    if (file) submitAudioData(file, file.name);
}

async function submitAudioData(blobOrFile, fileName) {
    const loadingBox = document.getElementById('loadingBox');
    const resultBox = document.getElementById('resultBox');
    loadingBox.style.display = 'block';
    resultBox.style.display = 'none';

    const formData = new FormData();
    formData.append('audio', blobOrFile, fileName);
    formData.append('context', document.getElementById('contextSelect').value);
    const prev = document.getElementById('prevOutgoing').value.trim();
    if (prev) formData.append('previousOutgoing', prev);

    try {
        const res = await fetch('/api/summarize', {
            method: 'POST',
            headers: { 'X-User-Id': currentUserId },
            body: formData
        });
        const data = await res.json();
        loadingBox.style.display = 'none';

        if (res.ok) {
            resultBox.style.display = 'block';
            document.getElementById('iconDisplay').innerText = ICON_MAP[data.iconCode] || 'ℹ️';
            document.getElementById('summaryDisplay').innerText = data.summary;
            document.getElementById('transcriptDisplay').innerText = `"${data.transcript}"`;
            document.getElementById('procTimeBadge').innerText = (data.processing_time_ms / 1000).toFixed(1) + 's';
            lastRecentTranscript = data.transcript || "";

            // Highlights
            const hlBox = document.getElementById('highlightsBox');
            hlBox.innerHTML = '';
            (data.highlights || []).forEach(h => {
                const tag = document.createElement('span');
                tag.className = 'hl-tag hl-' + (h.type || 'OTHER');
                tag.innerText = `[${h.type}] ${h.text}`;
                hlBox.appendChild(tag);
            });

            // Quick Replies (Click to speak out loud)
            const repGrid = document.getElementById('repliesGrid');
            repGrid.innerHTML = '';
            (data.quickReplies || []).forEach(r => {
                const btn = document.createElement('button');
                btn.className = 'reply-btn';
                btn.innerHTML = `<span>👉 ${r}</span><span class="speaker-icon">🔊</span>`;
                btn.title = "Chạm để phát âm thanh câu này";
                btn.onclick = () => speakText(r);
                repGrid.appendChild(btn);
            });

            // Suggested Chips
            const sChipsBox = document.getElementById('summarySuggestedChips');
            sChipsBox.innerHTML = '';
            const suggestedChips = data.suggestedChips || [];
            if (suggestedChips.length > 0) {
                suggestedChips.forEach(chipText => {
                    const pill = document.createElement('span');
                    pill.className = 'ai-chip-pill';
                    pill.innerHTML = `<span>➕ ${chipText}</span>`;
                    pill.title = "Chạm để chuyển từ khóa này sang Chiều Đi";
                    pill.onclick = () => selectSuggestedChipToTab2(chipText);
                    sChipsBox.appendChild(pill);
                });
                renderAiSuggestedChips(suggestedChips);
            } else {
                sChipsBox.innerHTML = '<span style="font-size:12px; color:var(--muted);">Chưa có gợi ý từ khóa mới</span>';
            }
        } else {
            alert("Lỗi: " + (data.detail || "Không thể xử lý"));
        }
    } catch (err) {
        loadingBox.style.display = 'none';
        alert("Lỗi kết nối: " + err.message);
    }
}

function selectSuggestedChipToTab2(chipText) {
    const input = document.getElementById('customChipsInput');
    const parts = input.value.split(',').map(s => s.trim()).filter(Boolean);
    if (!parts.includes(chipText)) {
        parts.push(chipText);
        input.value = parts.join(', ');
    }
    // Chuyển sang Tab Chiều Đi
    document.querySelectorAll('.main-tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.style.display = 'none');
    document.querySelectorAll('.main-tab-btn')[1].classList.add('active');
    document.getElementById('tab-expand').style.display = 'block';
}

// ----------------- Quick Chips Multi-Tenant CRUD -----------------

async function loadUserChips() {
    const container = document.getElementById('presetChips');
    const ctx = document.getElementById('contextSelect').value;
    try {
        const res = await fetch(`/api/v1/chips?context=${ctx}`, {
            headers: { 'X-User-Id': currentUserId }
        });
        const chips = await res.json();
        container.innerHTML = '';

        if (!chips || chips.length === 0) {
            container.innerHTML = '<span style="color:var(--muted); font-size:13px;">Chưa có thẻ nào cho ngữ cảnh này.</span>';
            return;
        }

        const selectedSet = new Set(
            document.getElementById('customChipsInput').value.split(',').map(s => s.trim()).filter(Boolean)
        );

        chips.forEach(chip => {
            const span = document.createElement('span');
            span.className = 'chip-tag' + (chip.is_system ? '' : ' custom') + (selectedSet.has(chip.text) ? ' selected' : '');
            span.setAttribute('data-id', chip.id);
            span.setAttribute('data-text', chip.text);

            let html = `<span>${chip.text}</span>`;
            if (!chip.is_system) {
                html += `<button class="btn-del" onclick="deleteCustomChip(event, '${chip.id}')" title="Xóa thẻ riêng này">&times;</button>`;
            }
            span.innerHTML = html;
            span.onclick = (e) => {
                if (e.target.classList.contains('btn-del')) return;
                toggleChip(span);
            };
            container.appendChild(span);
        });
    } catch (err) {
        console.error("Lỗi nạp thẻ:", err);
    }
}

function toggleChip(el) {
    el.classList.toggle('selected');
    updateSelectedChipsFromUI();
}

function updateSelectedChipsFromUI() {
    // Chỉ chọn trong phạm vi #presetChips để tránh đụng độ các nút tab khác
    const selected = Array.from(document.querySelectorAll('#presetChips .chip-tag.selected'))
        .map(c => c.getAttribute('data-text') || c.innerText.replace('×', '').trim())
        .filter(Boolean);
    document.getElementById('customChipsInput').value = selected.join(', ');
}

async function addNewChip() {
    const input = document.getElementById('newChipInput');
    const text = input.value.trim();
    if (!text) return;

    try {
        const res = await fetch('/api/v1/chips', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-User-Id': currentUserId
            },
            body: JSON.stringify({
                text: text,
                context: document.getElementById('contextSelect').value
            })
        });
        if (res.ok) {
            input.value = '';
            await loadUserChips();
        } else {
            const err = await res.json();
            alert("Lỗi: " + (err.detail || "Không thể thêm thẻ"));
        }
    } catch (e) {
        alert("Lỗi kết nối: " + e.message);
    }
}

async function deleteCustomChip(event, chipId) {
    event.stopPropagation();
    if (!confirm("Bạn có chắc muốn xóa thẻ riêng này?")) return;

    try {
        const res = await fetch(`/api/v1/chips/${chipId}`, {
            method: 'DELETE',
            headers: { 'X-User-Id': currentUserId }
        });
        if (res.ok) {
            await loadUserChips();
            updateSelectedChipsFromUI();
        }
    } catch (e) {
        alert("Lỗi xóa thẻ: " + e.message);
    }
}

async function resetCustomChips() {
    if (!confirm("Khôi phục danh sách về thẻ mặc định của hệ thống? Toàn bộ thẻ cá nhân của bạn sẽ được xóa.")) return;
    try {
        const res = await fetch('/api/v1/chips/reset', {
            method: 'POST',
            headers: { 'X-User-Id': currentUserId }
        });
        if (res.ok) {
            await loadUserChips();
            updateSelectedChipsFromUI();
        }
    } catch (e) {
        alert("Lỗi đặt lại: " + e.message);
    }
}

async function requestAiChips() {
    const container = document.getElementById('aiSuggestedChipsContainer');
    container.innerHTML = '<span style="font-size:12px; color:var(--primary); font-weight:600;">⏳ AI đang suy nghĩ các từ khóa tối ưu...</span>';

    const existingChips = Array.from(document.querySelectorAll('#presetChips .chip-tag')).map(c => c.getAttribute('data-text') || c.innerText.trim());

    try {
        const res = await fetch('/api/v1/ai/suggest-chips', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                context: document.getElementById('contextSelect').value,
                recentText: lastRecentTranscript || document.getElementById('prevOutgoing').value,
                existingChips: existingChips
            })
        });
        const data = await res.json();
        renderAiSuggestedChips(data.suggestedChips || []);
    } catch (e) {
        container.innerHTML = '<span style="font-size:12px; color:var(--danger);">Lỗi gợi ý: ' + e.message + '</span>';
    }
}

function renderAiSuggestedChips(chips) {
    const container = document.getElementById('aiSuggestedChipsContainer');
    container.innerHTML = '';
    if (!chips || chips.length === 0) {
        container.innerHTML = '<span style="font-size:12px; color:var(--muted); font-style:italic;">Không có gợi ý mới.</span>';
        return;
    }
    chips.forEach(chipText => {
        const pill = document.createElement('span');
        pill.className = 'ai-chip-pill';
        pill.innerHTML = `<span>➕ ${chipText}</span>`;
        pill.title = "Bấm để lưu thành thẻ cá nhân và chọn luôn";
        pill.onclick = async () => {
            document.getElementById('newChipInput').value = chipText;
            await addNewChip();
            selectSuggestedChipToTab2(chipText);
        };
        container.appendChild(pill);
    });
}

function onContextChange() {
    loadUserChips();
}

async function submitExpand() {
    const raw = document.getElementById('customChipsInput').value;
    const chips = raw.split(',').map(s => s.trim()).filter(Boolean);
    if (chips.length === 0) {
        alert("Vui lòng chọn hoặc nhập ít nhất 1 thẻ.");
        return;
    }

    try {
        const res = await fetch('/api/expand', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-User-Id': currentUserId
            },
            body: JSON.stringify({
                context: document.getElementById('contextSelect').value,
                chips: chips
            })
        });
        const data = await res.json();
        if (res.ok) {
            document.getElementById('expandResultBox').style.display = 'block';
            document.getElementById('spokenSentenceDisplay').innerText = data.spoken_sentence;
        } else {
            alert("Lỗi: " + (data.detail || "Không thành công"));
        }
    } catch (e) {
        alert("Lỗi kết nối: " + e.message);
    }
}

function speakText(text) {
    if ('speechSynthesis' in window) {
        window.speechSynthesis.cancel();
        const u = new SpeechSynthesisUtterance(text);
        u.lang = 'vi-VN';
        u.rate = 1.0;
        window.speechSynthesis.speak(u);
    } else {
        alert("Trình duyệt không hỗ trợ Web Speech TTS");
    }
}

function speakCurrentSentence() {
    const text = document.getElementById('spokenSentenceDisplay').innerText;
    speakText(text);
}

// Khởi chạy khi load trang
document.addEventListener('DOMContentLoaded', () => {
    loadUserChips();
});
</script>
</body>
</html>
"""

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)
