import os
import sys
import time
import io
import uvicorn
from typing import List, Optional, Any
from pydantic import BaseModel
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# Tự động nạp cấu hình từ .env
load_dotenv()

# Tối ưu hóa: Bật chế độ offline để CTranslate2 không gửi request thăm dò HuggingFace gây trễ
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

from faster_whisper import WhisperModel
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
def run_transcribe(audio_source: Any, language: str = "vi", context: str = "CUSTOM") -> tuple[str, float]:
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
    return transcript, round(info.duration, 2)

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
        transcript, duration = run_transcribe(io.BytesIO(content), language=language, context=context)
        t_proc_ms = int((time.time() - t_start) * 1000)

        return {
            "success": True,
            "text": transcript,
            "language": info.language,
            "language_probability": round(info.language_probability, 2),
            "duration_seconds": round(info.duration, 2),
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
        transcript, duration = run_transcribe(io.BytesIO(content), language="vi", context=context)
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
    return {"status": "UP", "service": "SignBridge-AI"}

@app.get("/", response_class=HTMLResponse)
def index_page():
    return """
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SignBridge AI - Test Studio (V1 Speech-to-Text)</title>
    <style>
        :root {
            --primary: #2563eb;
            --primary-hover: #1d4ed8;
            --success: #16a34a;
            --danger: #dc2626;
            --bg: #f8fafc;
            --card: #ffffff;
            --border: #e2e8f0;
            --text: #0f172a;
            --muted: #64748b;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
        body { background: var(--bg); color: var(--text); padding: 24px 16px; display: flex; justify-content: center; }
        .container { width: 100%; max-width: 760px; }
        header { text-align: center; margin-bottom: 24px; }
        h1 { font-size: 26px; color: var(--primary); display: flex; align-items: center; justify-content: center; gap: 8px; }
        .subtitle { color: var(--muted); font-size: 14px; margin-top: 6px; }
        .badge { display: inline-block; padding: 3px 10px; border-radius: 999px; font-size: 12px; font-weight: 600; background: #e0e7ff; color: #3730a3; margin-top: 8px; }
        .card { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 20px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); margin-bottom: 20px; }
        .card-title { font-size: 16px; font-weight: 700; margin-bottom: 14px; display: flex; align-items: center; gap: 6px; }
        .tabs { display: flex; gap: 10px; margin-bottom: 16px; }
        .tab-btn { flex: 1; padding: 10px; border: 1px solid var(--border); border-radius: 8px; background: #f1f5f9; cursor: pointer; font-weight: 600; font-size: 14px; transition: all 0.2s; }
        .tab-btn.active { background: var(--primary); color: #fff; border-color: var(--primary); }
        .pane { display: none; }
        .pane.active { display: block; }
        
        .mic-box { text-align: center; padding: 20px 0; }
        .mic-btn { width: 80px; height: 80px; border-radius: 50%; border: none; background: #fee2e2; color: var(--danger); font-size: 32px; cursor: pointer; transition: all 0.2s; display: inline-flex; align-items: center; justify-content: center; box-shadow: 0 4px 12px rgba(220,38,38,0.2); }
        .mic-btn.recording { background: var(--danger); color: #fff; animation: pulse 1.2s infinite; }
        @keyframes pulse {
            0% { transform: scale(1); box-shadow: 0 0 0 0 rgba(220,38,38,0.7); }
            70% { transform: scale(1.06); box-shadow: 0 0 0 16px rgba(220,38,38,0); }
            100% { transform: scale(1); box-shadow: 0 0 0 0 rgba(220,38,38,0); }
        }
        .mic-label { margin-top: 12px; font-size: 14px; font-weight: 600; color: var(--muted); }
        .upload-area { border: 2px dashed var(--border); border-radius: 10px; padding: 28px; text-align: center; cursor: pointer; background: #f8fafc; transition: border-color 0.2s; }
        .upload-area:hover { border-color: var(--primary); }
        input[type="file"] { display: none; }
        
        .btn-action { display: block; width: 100%; padding: 12px; border-radius: 8px; border: none; background: var(--primary); color: #fff; font-weight: 600; font-size: 15px; cursor: pointer; margin-top: 14px; transition: background 0.2s; }
        .btn-action:hover { background: var(--primary-hover); }
        .btn-action:disabled { background: var(--muted); cursor: not-allowed; }

        .result-box { margin-top: 16px; border-top: 1px solid var(--border); padding-top: 16px; }
        .transcript-text { font-size: 20px; font-weight: 600; line-height: 1.5; color: #1e293b; background: #f8fafc; border: 1px solid #cbd5e1; padding: 16px; border-radius: 8px; min-height: 60px; }
        .stats-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-top: 12px; }
        .stat-item { background: #f1f5f9; padding: 10px; border-radius: 6px; text-align: center; }
        .stat-val { font-size: 18px; font-weight: 700; color: var(--primary); }
        .stat-lbl { font-size: 12px; color: var(--muted); margin-top: 2px; }
        pre.json-box { background: #1e293b; color: #f8fafc; padding: 12px; border-radius: 6px; font-size: 12px; overflow-x: auto; margin-top: 12px; max-height: 180px; }
        .loading { display: none; text-align: center; padding: 14px; color: var(--primary); font-weight: 600; }
        .links { text-align: center; margin-top: 16px; font-size: 13px; color: var(--muted); }
        .links a { color: var(--primary); text-decoration: none; font-weight: 600; }
    </style>
</head>
<body>
<div class="container">
    <header>
        <h1> SignBridge AI Studio</h1>
        <div class="subtitle">Trang kiểm thử Speech-to-Text (V1) & Thử nghiệm mô hình trên máy local</div>
        <div class="badge">Model: PhoWhisper small (ct2) | Runtime: CPU int8</div>
    </header>

    <div class="card">
        <div class="card-title">Thao tác kiểm thử</div>
        <div class="tabs">
            <button class="tab-btn active" onclick="switchTab('mic')">🔴 Ghi âm trực tiếp (Mic)</button>
            <button class="tab-btn" onclick="switchTab('upload')">📁 Tải file âm thanh (.m4a, .mp3, .wav)</button>
        </div>

        <!-- Tab 1: Mic -->
        <div id="tab-mic" class="pane active">
            <div class="mic-box">
                <button id="micBtn" class="mic-btn" onclick="toggleRecord()">🎤</button>
                <div id="micLabel" class="mic-label">Nhấn để bắt đầu nói</div>
                <div id="recordTime" style="font-size:13px; color:var(--danger); margin-top:4px; font-weight:600; display:none;">00:00</div>
            </div>
            <audio id="audioPlayback" controls style="width:100%; display:none; margin-top:10px;"></audio>
            <button id="transcribeMicBtn" class="btn-action" style="display:none;" onclick="submitAudio(recordedBlob, 'record.webm')">⚡ Nhận diện tiếng Việt </button>
        </div>

        <!-- Tab 2: Upload -->
        <div id="tab-upload" class="pane">
            <div class="upload-area" onclick="document.getElementById('fileInput').click()">
                <div style="font-size:32px; margin-bottom:8px;">📤</div>
                <div id="fileUploadName" style="font-weight:600; color:var(--text);">Bấm vào đây để chọn file âm thanh</div>
                <div style="font-size:12px; color:var(--muted); margin-top:4px;">Hỗ trợ .wav, .mp3, .m4a, .webm</div>
            </div>
            <input type="file" id="fileInput" accept="audio/*" onchange="handleFileSelected(this)">
            <button id="transcribeFileBtn" class="btn-action" disabled onclick="submitFile()">⚡ Nhận diện tiếng Việt</button>
        </div>

        <div id="loading" class="loading">⏳ Đang xử lý âm thanh với faster-whisper... Vui lòng đợi trong giây lát...</div>

        <!-- Kết quả -->
        <div id="resultBox" class="result-box" style="display:none;">
            <div class="card-title" style="margin-bottom:8px;">📝 Văn bản nhận diện:</div>
            <div id="transcriptOutput" class="transcript-text"></div>
            
            <div class="stats-grid">
                <div class="stat-item">
                    <div id="statTime" class="stat-val">0 ms</div>
                    <div class="stat-lbl">Thời gian xử lý</div>
                </div>
                <div class="stat-item">
                    <div id="statDuration" class="stat-val">0 s</div>
                    <div class="stat-lbl">Độ dài âm thanh</div>
                </div>
                <div class="stat-item">
                    <div id="statStatus" class="stat-val" style="color:var(--success);">ĐẠT (&lt; 5s)</div>
                    <div class="stat-lbl">Chuẩn Hackathon</div>
                </div>
            </div>

            <div style="margin-top:14px; font-size:12px; font-weight:700; color:var(--muted);">Dữ liệu JSON trả về cho Mobile/Backend:</div>
            <pre id="jsonOutput" class="json-box"></pre>
        </div>
    </div>

    <div class="links">
        API Endpoint: <code>POST /api/v1/speech/transcribe</code> | 
        <a href="/docs" target="_blank">📖 Mở Swagger API Docs</a>
    </div>
</div>

<script>
let mediaRecorder;
let audioChunks = [];
let recordedBlob = null;
let isRecording = false;
let recordTimerInterval = null;
let recordSeconds = 0;

function switchTab(tab) {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.pane').forEach(p => p.classList.remove('active'));
    if(tab === 'mic') {
        event.target.classList.add('active');
        document.getElementById('tab-mic').classList.add('active');
    } else {
        event.target.classList.add('active');
        document.getElementById('tab-upload').classList.add('active');
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
                document.getElementById('transcribeMicBtn').style.display = 'block';
            };
            mediaRecorder.start();
            isRecording = true;
            document.getElementById('micBtn').classList.add('recording');
            document.getElementById('micLabel').innerText = "Đang thu âm... Bấm lần nữa để dừng";
            
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
        document.getElementById('micLabel').innerText = "Đã thu xong, check thử";
    }
}

function handleFileSelected(input) {
    if (input.files && input.files[0]) {
        const file = input.files[0];
        document.getElementById('fileUploadName').innerText = "Đã chọn: " + file.name + " (" + (file.size / 1024).toFixed(1) + " KB)";
        document.getElementById('transcribeFileBtn').disabled = false;
    }
}

function submitFile() {
    const file = document.getElementById('fileInput').files[0];
    if (file) submitAudio(file, file.name);
}

async function submitAudio(blobOrFile, filename) {
    const loading = document.getElementById('loading');
    const resultBox = document.getElementById('resultBox');
    loading.style.display = 'block';
    resultBox.style.display = 'none';

    const formData = new FormData();
    formData.append('audio', blobOrFile, filename);
    formData.append('language', 'vi');

    try {
        const res = await fetch('/api/v1/speech/transcribe', {
            method: 'POST',
            body: formData
        });
        const data = await res.json();
        loading.style.display = 'none';

        if (data.success) {
            resultBox.style.display = 'block';
            document.getElementById('transcriptOutput').innerText = data.text || "(Không nhận diện được giọng nói trong đoạn thu)";
            document.getElementById('statTime').innerText = data.processing_time_ms + " ms";
            document.getElementById('statDuration').innerText = data.duration_seconds + " s";
            
            const isFast = data.processing_time_ms < 5000;
            const statusEl = document.getElementById('statStatus');
            statusEl.innerText = isFast ? "ĐẠT (< 5s)" : "CHƯA ĐẠT";
            statusEl.style.color = isFast ? "var(--success)" : "var(--danger)";

            document.getElementById('jsonOutput').innerText = JSON.stringify(data, null, 2);
        } else {
            alert("Lỗi: " + (data.detail || "Không nhận diện được"));
        }
    } catch (err) {
        loading.style.display = 'none';
        alert("Lỗi kết nối API: " + err.message);
    }
}
</script>
</body>
</html>
    """

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)
