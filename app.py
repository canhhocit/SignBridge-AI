import os
import sys
import time
import io
import json
import logging
import threading
from contextlib import asynccontextmanager
from typing import List, Optional, Literal

import uvicorn
from pydantic import BaseModel, Field, StringConstraints
from typing_extensions import Annotated
from fastapi import FastAPI, UploadFile, File, Form, Request, Header
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Tự động nạp cấu hình từ .env
load_dotenv()

# Tối ưu hóa: Bật chế độ offline để CTranslate2 không gửi request thăm dò HuggingFace gây trễ
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

from errors import ApiError, error_body, install_error_handlers
import conversation
from conversation import CONTEXTS
from llm_service import (summarize_text, expand_chips, recognize_sign, compose_from_glosses, suggest_smart_chips,
                         LLM_MODEL, LLM_BASE_URL)

# Cấu hình encoding trên Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
log = logging.getLogger("SignBridge.Request")

# Tự động kết nối cơ sở dữ liệu (PostgreSQL / SQLite fallback)
try:
    import database
    database.init_db()
    DB_AVAILABLE = True
except Exception as e:
    print(f"[-] Database khởi tạo thất bại ({type(e).__name__}). Sẽ chạy không có API thẻ.")
    DB_AVAILABLE = False

MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
MODEL_NAME = os.getenv("WHISPER_MODEL", "diepho/PhoWhisper-small-ct2")
# Benchmark thực tế: 4 CPU threads đạt hiệu suất cao nhất trên CTranslate2 (tránh context-switching)
CPU_THREADS = min(4, os.cpu_count() or 4)

# ----------------- Giới hạn input (mục 4.2–4.5) -----------------
MAX_FRAME_BYTES = 250 * 1024
MAX_AUDIO_BYTES = 2 * 1024 * 1024
MAX_REQUEST_BYTES = 6 * 1024 * 1024     # tương đương spring.servlet.multipart.max-request-size
MAX_TEXT = 300
MAX_PERSONAL_CHIPS = 20
MAX_USER_ID = 64
MAX_DEVICE_GLOSSES = 10
ALLOWED_FRAME_COUNTS = (4, 8, 12, 16)
# Hợp đồng mục 4.4 chỉ yêu cầu m4a; thêm webm/wav/mp3/ogg cho Web Studio (tập cha, mobile không bị ảnh hưởng)
AUDIO_TYPES = {
    "audio/m4a", "audio/mp4", "audio/x-m4a", "audio/aac",
    "audio/webm", "audio/wav", "audio/x-wav", "audio/wave", "audio/mpeg", "audio/mp3", "audio/ogg",
}

ContextType = Literal["CAFE", "PHARMACY", "PUBLIC", "CUSTOM"]
ChipText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
ShortText = Annotated[str, StringConstraints(max_length=MAX_TEXT)]
UserId = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]

# ----------------- PhoWhisper (nạp lười, test không cần model) -----------------
_whisper_model = None
_whisper_lock = threading.Lock()


def get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        with _whisper_lock:
            if _whisper_model is None:
                from faster_whisper import WhisperModel
                print(f"[*] Khởi tạo PhoWhisperModel ('{MODEL_NAME}', CPU, int8, cpu_threads={CPU_THREADS}) từ: {MODEL_DIR}...")
                _whisper_model = WhisperModel(
                    MODEL_NAME,
                    device="cpu",
                    compute_type="int8",
                    download_root=MODEL_DIR,
                    local_files_only=True,
                    cpu_threads=CPU_THREADS
                )
                print("[+] Model PhoWhisper đã sẵn sàng phục vụ!")
    return _whisper_model


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Nạp model khi khởi động server để request đầu không bị chậm (WHISPER_PRELOAD=0 để tắt)
    if os.getenv("WHISPER_PRELOAD", "1") != "0":
        get_whisper_model()
    yield


app = FastAPI(
    title="SignBridge AI Service",
    description="Speech-to-Text & VSL LLM Service cho dự án SignBridge",
    version="1.3.0",
    lifespan=lifespan,
)
install_error_handlers(app)

# Cho phép Mobile / Web gọi API không bị chặn CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_logging(request: Request, call_next):
    """Mỗi request một dòng log metadata. KHÔNG log payload (frame, audio, transcript, câu nói)."""
    start = time.perf_counter()
    length = int(request.headers.get("content-length") or 0)
    if length > MAX_REQUEST_BYTES:
        request.state.error_code = "PAYLOAD_TOO_LARGE"
        from fastapi.responses import JSONResponse
        response = JSONResponse(status_code=413, content=error_body(
            "PAYLOAD_TOO_LARGE", "File gửi lên quá lớn, vui lòng nén lại."))
    else:
        response = await call_next(request)
    ms = int((time.perf_counter() - start) * 1000)
    forwarded = request.headers.get("x-forwarded-for", "")
    ip = forwarded.split(",")[0].strip() if forwarded.strip() else (request.client.host if request.client else "-")
    code = getattr(request.state, "error_code", None)
    line = (f"{request.method} {request.url.path} status={response.status_code} {ms}ms ip={ip} "
            f"contentType={request.headers.get('content-type')} bytes={length}"
            + (f" error={code}" if code else ""))
    (log.warning if response.status_code >= 500 else log.info)(line)
    return response

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
    context: ContextType = "CUSTOM"
    transcript: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
    previousOutgoing: Optional[ShortText] = None

class ExpandRequest(BaseModel):
    context: ContextType = "CUSTOM"
    chips: List[ChipText] = Field(min_length=1, max_length=5)
    previousIncoming: Optional[ShortText] = None

class ExpandResponse(BaseModel):
    spoken_sentence: str

class SignResponse(BaseModel):
    glosses: List[str]
    confidence: float
    spoken_sentence: str
    suggestedChips: List[str]

class SignGlossesRequest(BaseModel):
    """Mục 4.2a: ký hiệu đã nhận diện offline trên mobile (model TFLite), đúng thứ tự ký."""
    context: ContextType
    glosses: List[ChipText] = Field(max_length=MAX_DEVICE_GLOSSES)
    confidences: List[Annotated[float, Field(ge=0.0, le=1.0)]] = Field(max_length=MAX_DEVICE_GLOSSES)
    personalChips: List[ChipText] = Field(default_factory=list, max_length=MAX_PERSONAL_CHIPS)
    previousIncoming: Optional[ShortText] = None

class CreateChipRequest(BaseModel):
    text: ChipText
    context: ContextType = "CUSTOM"
    user_id: Optional[UserId] = None

class UpdateChipRequest(BaseModel):
    text: Optional[ChipText] = None
    context: Optional[ContextType] = None
    user_id: Optional[UserId] = None

class SuggestChipsRequest(BaseModel):
    context: ContextType = "CUSTOM"
    recentText: Optional[ShortText] = None
    existingChips: List[ChipText] = Field(default_factory=list, max_length=50)

# ----------------- Helper Functions -----------------
def check_context(context: str) -> str:
    if context not in CONTEXTS:
        raise ApiError.invalid_request(f"context phải là một trong {', '.join(CONTEXTS)}.")
    return context


def check_length(field: str, value: Optional[str]) -> Optional[str]:
    """Kiểm tra độ dài rồi trả về chuỗi đã trim, chuỗi rỗng → None."""
    if value is not None and len(value) > MAX_TEXT:
        raise ApiError.invalid_request(f"{field} tối đa {MAX_TEXT} ký tự.")
    return value.strip() if value and value.strip() else None


def media_type(upload: UploadFile) -> str:
    return (upload.content_type or "").split(";")[0].strip().lower()


def parse_personal_chips(raw: Optional[str]) -> List[str]:
    if raw is None or not raw.strip():
        return []
    try:
        chips = json.loads(raw)
    except ValueError:
        chips = None
    if not isinstance(chips, list) or not all(isinstance(c, str) for c in chips):
        raise ApiError.invalid_request("personalChips phải là JSON array chuỗi.")
    if len(chips) > MAX_PERSONAL_CHIPS:
        raise ApiError.invalid_request(f"personalChips tối đa {MAX_PERSONAL_CHIPS} phần tử.")
    return chips


def run_transcribe(audio_source, language: str = "vi", context: str = "CUSTOM") -> tuple[str, float, str, float]:
    """
    Nhận diện âm thanh siêu tốc trực tiếp từ bộ nhớ RAM (In-Memory Buffer)
    Sử dụng greedy search (beam_size=1) + temperature=0.0 + initial_prompt theo ngữ cảnh.
    Tối ưu VAD (threshold=0.3, speech_pad_ms=250) để bắt trọn cả tiếng nói nhỏ, nói thầm, tránh bị nuốt từ.
    """
    initial_prompt = CONTEXT_PROMPTS.get(context, CONTEXT_PROMPTS["CUSTOM"])
    segments, info = get_whisper_model().transcribe(
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
    transcript = "".join(s.text for s in segments).strip()
    return transcript, round(info.duration, 2), getattr(info, "language", language), round(getattr(info, "language_probability", 1.0), 2)


def transcribe_or_raise(content: bytes, language: str, context: str) -> tuple[str, float, str, float]:
    try:
        return run_transcribe(io.BytesIO(content), language=language, context=context)
    except ApiError:
        raise
    except Exception as e:
        # Không đưa nội dung lỗi (có thể chứa dữ liệu audio) ra response/log
        logging.getLogger("SignBridge.STT").warning("AI transcribe: AI_UPSTREAM_ERROR (%s)", type(e).__name__)
        raise ApiError.ai_upstream_error("Dịch vụ nhận dạng giọng nói trả lỗi.")


def build_summary(transcript: str, context: str, previous_outgoing: Optional[str], t_start: float) -> SummarizeResponse:
    ai_output = conversation.check_summarize_output(summarize_text(
        transcript=transcript,
        context=context,
        previous_outgoing=previous_outgoing
    ))
    return SummarizeResponse(
        transcript=transcript,
        summary=ai_output["summary"],
        highlights=ai_output["highlights"],
        iconCode=ai_output["iconCode"],
        quickReplies=ai_output["quickReplies"],
        suggestedChips=ai_output.get("suggestedChips", []),
        processing_time_ms=int((time.time() - t_start) * 1000)
    )

# ----------------- API Endpoints -----------------

@app.post("/api/v1/speech/transcribe")
async def transcribe_audio(
    audio: UploadFile = File(...),
    language: str = Form("vi"),
    context: str = Form("CUSTOM")
):
    """
    API nhận diện giọng nói tiếng Việt từ file âm thanh (.wav, .mp3, .m4a, .webm, .ogg).
    Xử lý trực tiếp in-memory không ghi đĩa, giảm tối đa độ trễ I/O.
    """
    t_start = time.time()
    check_context(context)
    content = await audio.read()
    if len(content) > MAX_AUDIO_BYTES:
        raise ApiError.payload_too_large("Audio phải ≤ 2 MB.")
    if not content:
        raise ApiError.no_speech_detected()

    transcript, duration, lang, lang_prob = transcribe_or_raise(content, language, context)
    return {
        "success": True,
        "text": transcript,
        "language": lang,
        "language_probability": lang_prob,
        "duration_seconds": duration,
        "processing_time_ms": int((time.time() - t_start) * 1000)
    }

@app.post("/api/v1/ai/summarize", response_model=SummarizeResponse)
async def summarize_transcript(req: SummarizeTextRequest):
    """
    Tóm tắt văn bản lời nói nhân viên qua LLM (OpenAI / 9router) — dùng khi đã có transcript.
    """
    return build_summary(req.transcript, req.context, check_length("previousOutgoing", req.previousOutgoing), time.time())

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
    check_context(context)
    if media_type(audio) not in AUDIO_TYPES:
        raise ApiError.unsupported_media_type(f"Audio phải là m4a (nhận {audio.content_type}).")
    previous = check_length("previousOutgoing", previousOutgoing)
    content = await audio.read()
    if len(content) > MAX_AUDIO_BYTES:
        raise ApiError.payload_too_large("Audio phải ≤ 2 MB.")
    if not content:
        raise ApiError.no_speech_detected()

    transcript, _, _, _ = transcribe_or_raise(content, "vi", context)
    if not transcript:
        raise ApiError.no_speech_detected()
    return build_summary(transcript, context, previous, t_start)

@app.post("/api/v1/ai/expand", response_model=ExpandResponse)
@app.post("/api/expand", response_model=ExpandResponse)
async def process_expand_chips(req: ExpandRequest):
    """
    Endpoint mở rộng thẻ từ khóa thành câu nói tiếng Việt lịch sự (mục 4.3)
    """
    res = expand_chips(
        chips=req.chips,
        context=req.context,
        previous_incoming=check_length("previousIncoming", req.previousIncoming)
    )
    return ExpandResponse(**conversation.check_expand_output(res))

@app.post("/api/sign", response_model=SignResponse)
async def process_sign_frames(
    frames: List[UploadFile] = File(...),
    context: str = Form("CUSTOM"),
    personalChips: Optional[str] = Form(None),
    previousIncoming: Optional[str] = Form(None)
):
    """
    Endpoint nhận diện ngôn ngữ ký hiệu từ chuỗi frame ảnh JPEG (mục 4.2, 7.4).
    """
    check_context(context)
    if len(frames) not in ALLOWED_FRAME_COUNTS:
        raise ApiError.invalid_request(f"Số frame phải là 4, 8, 12 hoặc 16 (nhận {len(frames)}).")
    for f in frames:
        if media_type(f) != "image/jpeg":
            raise ApiError.unsupported_media_type(f"Frame phải là image/jpeg (nhận {f.content_type}).")
        if f.size is not None and f.size > MAX_FRAME_BYTES:
            raise ApiError.payload_too_large("Mỗi frame phải ≤ 250 KB.")
    previous = check_length("previousIncoming", previousIncoming)
    chips = parse_personal_chips(personalChips)

    frames_bytes = []
    for f in frames:
        data = await f.read()
        if len(data) > MAX_FRAME_BYTES:
            raise ApiError.payload_too_large("Mỗi frame phải ≤ 250 KB.")
        frames_bytes.append(data)
    if not any(frames_bytes):
        raise ApiError.no_sign_detected()

    allowed = conversation.allowed_glosses(context)
    result = recognize_sign(
        frames_bytes=frames_bytes,
        context=context,
        personal_chips=chips,
        previous_incoming=previous,
        allowed_glosses=allowed
    )
    return SignResponse(**conversation.check_sign_output(context, result))


@app.post("/api/v1/sign/glosses", response_model=SignResponse)
@app.post("/api/sign/glosses", response_model=SignResponse)
def process_device_glosses(req: SignGlossesRequest):
    """
    Luồng Hybrid (mục 4.2a): mobile nhận diện ký hiệu offline → server kiểm tra (mục 7.4) rồi ghép câu.
    `def` (không async) để FastAPI chạy trong threadpool, lời gọi LLM không chặn event loop.
    """
    if len(req.confidences) != len(req.glosses):
        raise ApiError.invalid_request("confidences phải có cùng số phần tử với glosses.")
    checked = conversation.check_device_glosses(req.context, req.glosses, req.confidences)
    sentence = ""
    if not checked["needConfirm"]:
        display = [conversation.display_gloss(g) for g in checked["glosses"]]
        out = compose_from_glosses(
            glosses=display,
            context=req.context,
            personal_chips=req.personalChips,
            previous_incoming=check_length("previousIncoming", req.previousIncoming)
        )
        sentence = conversation.check_gloss_sentence(out, checked["glosses"])
    return SignResponse(
        glosses=checked["glosses"],
        confidence=checked["confidence"],
        spoken_sentence=sentence,
        suggestedChips=checked["suggestedChips"],
    )

# ----------------- Quick Chips (CSDL) — mở rộng của bản Python, không có trong mục 4 -----------------

def get_current_user_id(x_user_id: Optional[str] = None, user_id: Optional[str] = None) -> str:
    """Ưu tiên header X-User-Id, sau đó query/body user_id, mặc định default_user."""
    candidate = (x_user_id or user_id or "").strip()
    if len(candidate) > MAX_USER_ID:
        raise ApiError.invalid_request(f"user_id tối đa {MAX_USER_ID} ký tự.")
    return candidate or "default_user"

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
    uid = get_current_user_id(x_user_id, user_id)
    if context is not None and context != "ALL":
        check_context(context)
    if not DB_AVAILABLE:
        return []
    return database.get_chips_for_user(uid, context)

@app.post("/api/v1/chips")
@app.post("/api/chips")
def create_chip(req: CreateChipRequest, x_user_id: Optional[str] = Header(None, alias="X-User-Id")):
    """
    Thêm thẻ cá nhân cho người dùng hiện tại
    """
    uid = get_current_user_id(x_user_id, req.user_id)
    if not DB_AVAILABLE:
        raise ApiError.database_unavailable()
    try:
        return database.add_user_chip(uid, req.text, req.context)
    except ValueError as e:
        raise ApiError.invalid_request(str(e))

@app.put("/api/v1/chips/{chip_id}")
@app.put("/api/chips/{chip_id}")
@app.patch("/api/v1/chips/{chip_id}")
@app.patch("/api/chips/{chip_id}")
def update_chip(
    chip_id: str,
    req: UpdateChipRequest,
    user_id: Optional[str] = None,
    x_user_id: Optional[str] = Header(None, alias="X-User-Id")
):
    """
    Sửa nội dung hoặc ngữ cảnh của thẻ cá nhân (chỉ sửa thẻ của mình, không sửa thẻ hệ thống)
    """
    uid = get_current_user_id(x_user_id, req.user_id or user_id)
    if not DB_AVAILABLE:
        raise ApiError.database_unavailable()
    if req.text is None and req.context is None:
        raise ApiError.invalid_request("Cần cung cấp ít nhất text hoặc context để cập nhật.")
    try:
        updated = database.update_user_chip(uid, chip_id, req.text, req.context)
        if not updated:
            raise ApiError(404, "NOT_FOUND", "Không tìm thấy thẻ cá nhân hoặc không có quyền sửa.")
        return updated
    except ValueError as e:
        raise ApiError.invalid_request(str(e))

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
    uid = get_current_user_id(x_user_id, user_id)
    if not DB_AVAILABLE:
        raise ApiError.database_unavailable()
    return {"success": database.delete_user_chip(uid, chip_id)}

@app.post("/api/v1/chips/reset")
@app.post("/api/chips/reset")
def reset_chips(user_id: Optional[str] = None, x_user_id: Optional[str] = Header(None, alias="X-User-Id")):
    """
    Khôi phục danh sách thẻ về mặc định của hệ thống cho user_id hiện tại
    """
    uid = get_current_user_id(x_user_id, user_id)
    if not DB_AVAILABLE:
        raise ApiError.database_unavailable()
    return {"success": database.reset_user_chips(uid)}

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
    if not DB_AVAILABLE:
        db_name = "Disabled"
    else:
        db_name = "PostgreSQL" if database.engine.dialect.name == "postgresql" else "SQLite"
    return {
        "status": "UP",
        "service": "SignBridge-AI",
        "database": db_name,
        "whisper_model": MODEL_NAME,
        "llm_model": os.getenv("LLM_MODEL", LLM_MODEL),
        "llm_configured": api_key_configured,
        "vsl_labels": len(conversation.vsl_labels()),
        "llm_base_url": os.getenv("LLM_BASE_URL", LLM_BASE_URL)
    }

# ----------------- Web Test Studio HTML -----------------

WEB_INDEX_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web", "index.html")

@app.get("/", response_class=HTMLResponse)
def index_page():
    if os.path.exists(WEB_INDEX_PATH):
        with open(WEB_INDEX_PATH, "r", encoding="utf-8") as f:
            return f.read()
    return """<!DOCTYPE html><html><body><h1>SignBridge AI Studio</h1><p>web/index.html not found</p></body></html>"""

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)
