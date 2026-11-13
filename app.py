import os
import sys
import time
import tempfile
import uvicorn
from typing import List, Optional
from pydantic import BaseModel
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from faster_whisper import WhisperModel
from dotenv import load_dotenv

# Tự động nạp cấu hình từ .env
load_dotenv()

from llm_service import summarize_text, expand_chips, LLM_MODEL, LLM_BASE_URL

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
    version="1.1.0"
)

# Cho phép Mobile / Web gọi API không bị chặn CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CPU_THREADS = min(8, os.cpu_count() or 4)
print(f"[*] Khởi tạo PhoWhisperModel ('{MODEL_NAME}', CPU, int8, cpu_threads={CPU_THREADS}) từ: {MODEL_DIR}...")
whisper_model = WhisperModel(MODEL_NAME, device="cpu", compute_type="int8", download_root=MODEL_DIR, cpu_threads=CPU_THREADS)
print("[+] Model PhoWhisper đã sẵn sàng phục vụ!")

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

# ----------------- Helper Functions -----------------
def run_transcribe(audio_file_path: str, language: str = "vi") -> tuple[str, float]:
    segments, info = whisper_model.transcribe(
        audio_file_path,
        language=language if language != "auto" else None,
        beam_size=1,
        vad_filter=True
    )
    text_parts = [s.text for s in segments]
    transcript = "".join(text_parts).strip()
    return transcript, round(info.duration, 2)

# ----------------- API Endpoints -----------------

@app.post("/api/v1/speech/transcribe")
async def transcribe_audio(
    audio: UploadFile = File(...),
    language: str = Form("vi")
):
    """
    API nhận diện giọng nói tiếng Việt từ file âm thanh (.wav, .mp3, .m4a, .webm, .ogg)
    """
    t_start = time.time()
    suffix = os.path.splitext(audio.filename or "")[1] or ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await audio.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        transcript, duration = run_transcribe(tmp_path, language=language)
        t_proc_ms = int((time.time() - t_start) * 1000)
        return {
            "success": True,
            "text": transcript,
            "language": language,
            "duration_seconds": duration,
            "processing_time_ms": t_proc_ms
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi nhận diện âm thanh: {str(e)}")
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass

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
    """
    t_start = time.time()
    suffix = os.path.splitext(audio.filename or "")[1] or ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await audio.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        transcript, duration = run_transcribe(tmp_path, language="vi")
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
            processing_time_ms=t_proc_ms
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi xử lý tóm tắt: {str(e)}")
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass

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

        .quick-replies-title { font-size: 13px; font-weight: 700; color: #475569; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px; }
        .quick-replies-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 8px; }
        .reply-btn { padding: 10px 14px; background: #ffffff; border: 1px solid #cbd5e1; border-radius: 8px; font-size: 14px; font-weight: 600; color: #1e293b; text-align: left; cursor: pointer; transition: all 0.2s; box-shadow: 0 1px 2px rgba(0,0,0,0.05); }
        .reply-btn:hover { border-color: var(--primary); background: #f8fafc; color: var(--primary); transform: translateY(-1px); }

        .transcript-box { background: #f8fafc; border: 1px solid var(--border); border-radius: 8px; padding: 12px; font-size: 14px; color: #334155; margin-top: 14px; }
        .loading { display: none; text-align: center; padding: 20px; }
        .spinner { border: 3px solid #f3f3f3; border-top: 3px solid var(--primary); border-radius: 50%; width: 28px; height: 28px; animation: spin 1s linear infinite; margin: 0 auto 10px; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }

        .chip-tag { display: inline-flex; align-items: center; gap: 6px; padding: 6px 12px; background: #e2e8f0; border-radius: 999px; font-size: 13px; font-weight: 600; margin: 4px; cursor: pointer; }
        .chip-tag.selected { background: var(--primary); color: #fff; }
    </style>
</head>
<body>
<div class="container">
    <header>
        <h1>🌉 SignBridge AI Studio</h1>
        <div class="subtitle">Speech-to-Text (PhoWhisper) & Trợ lý Tóm tắt 2 chiều cho Người Khiếm Thính</div>
        <div class="badge-bar">
            <span class="badge">STT: PhoWhisper small (ct2)</span>
            <span id="llmBadge" class="badge badge-green">LLM: Đang kiểm tra...</span>
            <span class="badge">CPU int8 (Fast)</span>
        </div>
    </header>

    <div class="main-tabs">
        <button class="main-tab-btn active" onclick="switchMainTab('summarize')">🎙️ Nhận diện & Tóm tắt (/api/summarize)</button>
        <button class="main-tab-btn" onclick="switchMainTab('expand')">🏷️ Mở rộng Thẻ Ký hiệu (/api/expand)</button>
    </div>

    <!-- TAB 1: SUMMARIZE -->
    <div id="section-summarize">
        <div class="card">
            <div class="card-title">⚙️ Cấu hình ngữ cảnh</div>
            <div class="row">
                <div class="col">
                    <label>Ngữ cảnh (Context)</label>
                    <select id="contextSelect">
                        <option value="PHARMACY">PHARMACY - Quầy thuốc</option>
                        <option value="CAFE" selected>CAFE - Đồ uống / Đồ ăn</option>
                        <option value="PUBLIC">PUBLIC - Thủ tục hành chính</option>
                        <option value="CUSTOM">CUSTOM - Tự do</option>
                    </select>
                </div>
                <div class="col">
                    <label>Lời người khiếm thính vừa nói (Lượt trước)</label>
                    <input type="text" id="prevOutgoing" placeholder="Ví dụ: Cho mình một trà sữa trân châu">
                </div>
            </div>

            <div class="card-title" style="margin-top: 14px;">🔊 Đầu vào âm thanh của nhân viên</div>
            <div style="display: flex; gap: 10px; margin-bottom: 12px;">
                <button id="inputModeMic" class="reply-btn" style="flex:1; text-align:center;" onclick="setInputMode('mic')">🔴 Ghi âm Mic</button>
                <button id="inputModeFile" class="reply-btn" style="flex:1; text-align:center;" onclick="setInputMode('file')">📁 Chọn file (.mp3, .wav, .m4a)</button>
            </div>

            <div id="paneMic" class="mic-box">
                <button id="micBtn" class="mic-btn" onclick="toggleRecord()">🎙️</button>
                <div id="micLabel" style="font-size: 13px; color: var(--muted); margin-top: 8px;">Bấm để ghi âm lời nhân viên</div>
                <div id="recordTime" style="font-weight: 700; color: var(--danger); margin-top: 4px; display: none;">00:00</div>
                <audio id="audioPlayback" controls style="display: none; margin: 12px auto 0; width: 100%; max-width: 380px;"></audio>
                <button id="btnSubmitMic" class="btn-primary" style="display: none;" onclick="submitAudioCurrent()">🚀 Phiên âm & Tóm tắt ngay</button>
            </div>

            <div id="paneFile" style="display: none;">
                <div class="upload-area" onclick="document.getElementById('fileInput').click()">
                    <div style="font-size: 32px; margin-bottom: 6px;">📁</div>
                    <div style="font-weight: 600;">Kéo thả hoặc bấm vào đây để chọn file âm thanh</div>
                    <div style="font-size: 12px; color: var(--muted); margin-top: 4px;">(Hỗ trợ file sample trong test_audio-text/test.mp3)</div>
                    <input type="file" id="fileInput" accept="audio/*" style="display:none;" onchange="handleFileSelected(this)">
                </div>
                <div id="fileUploadName" style="margin-top: 8px; font-weight: 600; font-size: 13px; color: var(--primary);"></div>
                <button id="btnSubmitFile" class="btn-primary" disabled onclick="submitAudioCurrent()">🚀 Phiên âm & Tóm tắt file này</button>
            </div>
        </div>

        <div id="loadingBox" class="card loading">
            <div class="spinner"></div>
            <div style="font-weight: 700;">Đang xử lý (PhoWhisper STT + LLM Tóm tắt)...</div>
        </div>

        <!-- MÀN HÌNH CHIA ĐÔI CHO NGƯỜI KHIẾM THÍNH (OUTPUT) -->
        <div id="resultBox" class="card" style="display: none;">
            <div class="card-title">📱 Kết quả hiển thị cho Người Khiếm Thính</div>
            
            <div class="summary-card">
                <div class="summary-header">
                    <div class="summary-icon" id="iconDisplay">ℹ️</div>
                    <span style="font-size: 12px; font-weight: 700; color: #1d4ed8; background: #dbeafe; padding: 4px 8px; border-radius: 6px;" id="procTimeBadge">4.8s</span>
                </div>
                <div class="summary-text" id="summaryDisplay">...</div>
                
                <div class="highlights-box" id="highlightsBox"></div>

                <div class="quick-replies-title">⚡ 3 Câu phản hồi nhanh (Chạm để phát âm):</div>
                <div class="quick-replies-grid" id="repliesGrid"></div>
            </div>

            <div class="transcript-box">
                <div style="font-size: 12px; font-weight: 700; color: var(--muted); margin-bottom: 4px;">VĂN BẢN ĐẦY ĐỦ TỪ PHOWHISPER:</div>
                <div id="transcriptDisplay" style="font-style: italic;">...</div>
            </div>
        </div>
    </div>

    <!-- TAB 2: EXPAND CHIPS -->
    <div id="section-expand" style="display: none;">
        <div class="card">
            <div class="card-title">🏷️ Chọn hoặc Nhập Thẻ từ khóa (Chips)</div>
            <p style="font-size: 13px; color: var(--muted); margin-bottom: 12px;">Mô phỏng thao tác người khiếm thính chọn thẻ trên màn hình để ghép thành câu phát qua loa.</p>
            
            <div style="margin-bottom: 12px;">
                <label>Gợi ý thẻ theo bối cảnh:</label>
                <div id="chipContainer">
                    <span class="chip-tag selected" onclick="toggleChip(this)">Trà sữa trân châu</span>
                    <span class="chip-tag selected" onclick="toggleChip(this)">Ít đường</span>
                    <span class="chip-tag selected" onclick="toggleChip(this)">50% đá</span>
                    <span class="chip-tag" onclick="toggleChip(this)">Mang đi</span>
                    <span class="chip-tag" onclick="toggleChip(this)">Panadol</span>
                    <span class="chip-tag" onclick="toggleChip(this)">Đau đầu</span>
                    <span class="chip-tag" onclick="toggleChip(this)">Uống sau ăn</span>
                </div>
            </div>

            <div class="row">
                <div class="col">
                    <label>Hoặc nhập danh sách thẻ (cách nhau bởi dấu phẩy):</label>
                    <input type="text" id="customChipsInput" value="Trà sữa trân châu, Ít đường, 50% đá">
                </div>
            </div>

            <button class="btn-primary" onclick="submitExpand()">🗣️ Tạo câu nói tự nhiên (/api/expand)</button>
        </div>

        <div id="expandResultBox" class="card" style="display: none; background: #f0fdf4; border-color: #bbf7d0;">
            <div class="card-title" style="color: #166534;">🔊 Câu nói tiếng Việt sinh ra để phát loa:</div>
            <div id="spokenSentenceDisplay" style="font-size: 20px; font-weight: 800; color: #14532d; margin: 12px 0;">...</div>
            <button class="btn-primary" style="background: #16a34a; width: auto; padding: 8px 18px;" onclick="speakCurrentSentence()">🔊 Phát âm thanh thử (TTS)</button>
        </div>
    </div>
</div>

<script>
let currentInputMode = 'mic';
let isRecording = false;
let mediaRecorder;
let audioChunks = [];
let recordedBlob = null;
let currentSelectedFile = null;

const ICON_MAP = {
    'PILL': '💊', 'MONEY': '💵', 'QR_PAYMENT': '📱', 'COUNTER': '🏢',
    'TIME': '⏱️', 'DOCUMENT': '📄', 'DRINK': '🥤', 'FOOD': '🍜',
    'CHECK': '✅', 'WARNING': '⚠️', 'INFO': 'ℹ️'
};

async function checkHealth() {
    try {
        const res = await fetch('/api/health');
        const data = await res.json();
        const badge = document.getElementById('llmBadge');
        if (data.llm_configured) {
            badge.innerText = "LLM: " + data.llm_model + " (9router/Online)";
            badge.className = "badge badge-green";
        } else {
            badge.innerText = "LLM: Mock / Heuristic (Chưa có API key)";
            badge.className = "badge badge-amber";
        }
    } catch (e) {
        console.error(e);
    }
}
checkHealth();

function switchMainTab(tab) {
    document.querySelectorAll('.main-tab-btn').forEach(b => b.classList.remove('active'));
    if (tab === 'summarize') {
        document.querySelectorAll('.main-tab-btn')[0].classList.add('active');
        document.getElementById('section-summarize').style.display = 'block';
        document.getElementById('section-expand').style.display = 'none';
    } else {
        document.querySelectorAll('.main-tab-btn')[1].classList.add('active');
        document.getElementById('section-summarize').style.display = 'none';
        document.getElementById('section-expand').style.display = 'block';
    }
}

function setInputMode(mode) {
    currentInputMode = mode;
    if (mode === 'mic') {
        document.getElementById('paneMic').style.display = 'block';
        document.getElementById('paneFile').style.display = 'none';
        document.getElementById('inputModeMic').style.borderColor = 'var(--primary)';
        document.getElementById('inputModeFile').style.borderColor = 'var(--border)';
    } else {
        document.getElementById('paneMic').style.display = 'none';
        document.getElementById('paneFile').style.display = 'block';
        document.getElementById('inputModeFile').style.borderColor = 'var(--primary)';
        document.getElementById('inputModeMic').style.borderColor = 'var(--border)';
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
                const audioURL = URL.createObjectURL(recordedBlob);
                const player = document.getElementById('audioPlayback');
                player.src = audioURL;
                player.style.display = 'block';
                document.getElementById('btnSubmitMic').style.display = 'block';
            };
            mediaRecorder.start();
            isRecording = true;
            document.getElementById('micBtn').classList.add('recording');
            document.getElementById('micLabel').innerText = "Đang thu âm... Bấm lần nữa để dừng";
            document.getElementById('recordTime').style.display = 'block';
        } catch (err) {
            alert("Không thể truy cập Microphone: " + err.message);
        }
    } else {
        mediaRecorder.stop();
        mediaRecorder.stream.getTracks().forEach(t => t.stop());
        isRecording = false;
        document.getElementById('micBtn').classList.remove('recording');
        document.getElementById('micLabel').innerText = "Đã thu xong. Bấm nút bên dưới để xử lý.";
    }
}

function handleFileSelected(input) {
    if (input.files && input.files[0]) {
        currentSelectedFile = input.files[0];
        document.getElementById('fileUploadName').innerText = "Đã chọn: " + currentSelectedFile.name + " (" + (currentSelectedFile.size / 1024).toFixed(1) + " KB)";
        document.getElementById('btnSubmitFile').disabled = false;
    }
}

async function submitAudioCurrent() {
    const loadingBox = document.getElementById('loadingBox');
    const resultBox = document.getElementById('resultBox');
    loadingBox.style.display = 'block';
    resultBox.style.display = 'none';

    let fileToUpload = currentInputMode === 'mic' ? recordedBlob : currentSelectedFile;
    let fileName = currentInputMode === 'mic' ? 'recorded_audio.webm' : (currentSelectedFile ? currentSelectedFile.name : 'audio.mp3');

    if (!fileToUpload) {
        alert("Vui lòng ghi âm hoặc chọn file âm thanh trước.");
        loadingBox.style.display = 'none';
        return;
    }

    const formData = new FormData();
    formData.append('audio', fileToUpload, fileName);
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

            // Quick Replies
            const repGrid = document.getElementById('repliesGrid');
            repGrid.innerHTML = '';
            (data.quickReplies || []).forEach(r => {
                const btn = document.createElement('button');
                btn.className = 'reply-btn';
                btn.innerText = '👉 ' + r;
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
        const u = new SpeechSynthesisUtterance(text);
        u.lang = 'vi-VN';
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
