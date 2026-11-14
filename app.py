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

class SuggestChipsRequest(BaseModel):
    context: str = "CUSTOM"
    recentText: Optional[str] = None
    existingChips: Optional[List[str]] = []

# ----------------- Helper Functions -----------------
def run_transcribe(audio_source: Any, language: str = "vi", context: str = "CUSTOM") -> tuple[str, float, str, float]:
    """
    Nhận diện âm thanh siêu tốc trực tiếp từ bộ nhớ RAM (In-Memory Buffer)
    Sử dụng greedy search (beam_size=1) + temperature=0.0 + initial_prompt theo ngữ cảnh
    """
    initial_prompt = CONTEXT_PROMPTS.get(context, CONTEXT_PROMPTS["CUSTOM"])
    segments, info = whisper_model.transcribe(
        audio_source,
        language=language if language != "auto" else None,
        beam_size=1,                         # Greedy search: nhanh gấp 2-3 lần beam search
        temperature=0.0,                     # Tuyệt đối ổn định & nhanh nhất
        condition_on_previous_text=False,    # Tắt suy đoán chuỗi trước để tránh lặp câu và giảm tính toán
        vad_filter=True,                     # Lọc bỏ khoảng lặng
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

@app.get("/api/chips")
def list_chips(user_id: str = "default_user", context: Optional[str] = None):
    """
    Lấy danh sách thẻ từ khóa (thẻ hệ thống + thẻ cá nhân người dùng)
    """
    if not DB_AVAILABLE:
        return []
    return database.get_chips_for_user(user_id, context)

@app.post("/api/chips")
def create_chip(req: CreateChipRequest):
    """
    Thêm thẻ cá nhân cho người dùng
    """
    if not DB_AVAILABLE:
        raise HTTPException(status_code=503, detail="DATABASE_NOT_AVAILABLE")
    try:
        return database.add_user_chip(req.user_id, req.text, req.context)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/api/chips/{chip_id}")
def remove_chip(chip_id: str, user_id: str = "default_user"):
    """
    Xóa thẻ cá nhân của người dùng
    """
    if not DB_AVAILABLE:
        raise HTTPException(status_code=503, detail="DATABASE_NOT_AVAILABLE")
    ok = database.delete_user_chip(user_id, chip_id)
    return {"success": ok}

@app.get("/api/health")
def health_check():
    api_key_configured = bool(os.getenv("LLM_API_KEY", "").strip())
    return {
        "status": "UP",
        "service": "SignBridge-AI",
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
        .container { width: 100%; max-width: 820px; }
        header { text-align: center; margin-bottom: 20px; }
        h1 { font-size: 26px; color: var(--primary); display: flex; align-items: center; justify-content: center; gap: 8px; }
        .subtitle { color: var(--muted); font-size: 14px; margin-top: 6px; }
        .badge-bar { display: flex; gap: 8px; justify-content: center; flex-wrap: wrap; margin-top: 10px; }
        .badge { padding: 4px 12px; border-radius: 999px; font-size: 12px; font-weight: 600; background: #e0e7ff; color: #3730a3; }
        .badge-green { background: #dcfce7; color: #166534; }
        .badge-amber { background: #fef3c7; color: #92400e; }
        
        .main-tabs { display: flex; gap: 8px; margin-bottom: 16px; border-bottom: 2px solid var(--border); padding-bottom: 6px; }
        .main-tab-btn { padding: 10px 18px; border: none; background: transparent; cursor: pointer; font-size: 15px; font-weight: 700; color: var(--muted); border-radius: 8px; }
        .main-tab-btn.active { color: var(--primary); background: #eff6ff; }
        
        .card { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 20px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); margin-bottom: 20px; }
        .card-title { font-size: 16px; font-weight: 700; margin-bottom: 14px; display: flex; align-items: center; gap: 6px; }
        
        .row { display: flex; gap: 12px; margin-bottom: 14px; }
        .col { flex: 1; }
        label { display: block; font-size: 13px; font-weight: 600; color: var(--muted); margin-bottom: 6px; }
        select, input[type="text"] { width: 100%; padding: 8px 12px; border: 1px solid var(--border); border-radius: 8px; font-size: 14px; }

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
        
        .chips-container { display: flex; flex-wrap: wrap; gap: 8px; margin: 12px 0; }
        .chip-tag { padding: 8px 14px; border-radius: 999px; background: #f1f5f9; border: 1px solid var(--border); font-size: 14px; font-weight: 600; cursor: pointer; transition: all 0.2s; }
        .chip-tag.selected { background: var(--primary); color: #fff; border-color: var(--primary); }
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
            <span class="badge badge-amber">Latency: Optimized</span>
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
                    <select id="contextSelect">
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
                <button class="chip-tag selected" id="btnModeMic" onclick="switchAudioMode('mic')">🔴 Ghi âm qua Mic</button>
                <button class="chip-tag" id="btnModeUpload" onclick="switchAudioMode('upload')">📁 Tải file âm thanh (.mp3, .m4a, .wav)</button>
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
            <p style="font-size:13px; color:var(--muted); margin-bottom:12px;">Chạm vào các thẻ từ khóa bên dưới để mô phỏng người khiếm thính chọn ý muốn nói:</p>
            
            <div class="chips-container" id="presetChips">
                <span class="chip-tag" onclick="toggleChip(this)">Trà sữa trân châu</span>
                <span class="chip-tag" onclick="toggleChip(this)">Ít đường</span>
                <span class="chip-tag" onclick="toggleChip(this)">50% đá</span>
                <span class="chip-tag" onclick="toggleChip(this)">Panadol giảm đau</span>
                <span class="chip-tag" onclick="toggleChip(this)">Uống sau ăn</span>
                <span class="chip-tag" onclick="toggleChip(this)">Bao nhiêu tiền</span>
                <span class="chip-tag" onclick="toggleChip(this)">Chuyển khoản QR</span>
                <span class="chip-tag" onclick="toggleChip(this)">Cho hỏi đường ra chợ</span>
                <span class="chip-tag" onclick="toggleChip(this)">Cảm ơn</span>
            </div>

            <div style="margin-top:14px;">
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

let mediaRecorder;
let audioChunks = [];
let recordedBlob = null;
let isRecording = false;
let recordTimerInterval = null;
let recordSeconds = 0;

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
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
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
        } else {
            alert("Lỗi: " + (data.detail || "Không thể xử lý"));
        }
    } catch (err) {
        loadingBox.style.display = 'none';
        alert("Lỗi kết nối: " + err.message);
    }
}

function toggleChip(el) {
    el.classList.toggle('selected');
    const selected = Array.from(document.querySelectorAll('.chip-tag.selected')).map(c => c.innerText);
    document.getElementById('customChipsInput').value = selected.join(', ');
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
            headers: { 'Content-Type': 'application/json' },
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
        window.speechSynthesis.cancel(); // Dừng câu đang nói trước đó nếu có
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
</script>
</body>
</html>
"""

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)
