"""Kiểm tra lại output AI trước khi trả cho mobile (mục 4.6, 7.4) + bộ ký hiệu demo (mục 7.1, 7.2).

Không phụ thuộc HTTP/FastAPI. Không lưu gì.
"""
import functools
import json
import logging
import os
import re
import unicodedata
from typing import Any, Dict, List, Optional

from errors import ApiError

logger = logging.getLogger("SignBridge.Conversation")

CONTEXTS = ("CAFE", "PHARMACY", "PUBLIC", "CUSTOM")
UNKNOWN = "UNKNOWN"

# confidence >= ngưỡng thì mobile phát loa luôn
CONFIDENCE_THRESHOLD = float(os.getenv("SIGN_CONFIDENCE_THRESHOLD", "0.7"))
# /api/sign/glosses: xác suất softmax tối thiểu của từng ký hiệu nhận diện trên thiết bị
VSL_MIN_GLOSS_CONFIDENCE = float(os.getenv("VSL_MIN_GLOSS_CONFIDENCE", "0.7"))
# Nhãn của model nhận diện offline trên mobile (sinh bởi tools/convert_vsl_tflite.py)
VSL_LABELS_PATH = os.getenv(
    "VSL_LABELS_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "vsl", "labels.json"),
)
MAX_SENTENCE_WORDS = 40
MAX_SUGGESTED_CHIPS = 6

_COMMON = ("XIN CHÀO", "CẢM ƠN", "CÓ", "KHÔNG", "THANH TOÁN", "BAO NHIÊU")
_NUMBER_TIME = ("MỘT", "HAI", "NGÀY")
_PHARMACY = ("ĐAU", "ĐẦU", "BỤNG", "SỐT", "THUỐC", "MUA")
_CAFE = ("MUA", "CÀ PHÊ", "ĐÁ", "MANG ĐI")
_PUBLIC = ("GIẤY TỜ", "Ở ĐÂU")


def allowed_glosses(context: str) -> List[str]:
    """Danh sách ký hiệu gửi cho AI theo ngữ cảnh (mục 7.2)."""
    result = list(_COMMON) + list(_NUMBER_TIME)
    extra = {
        "PHARMACY": _PHARMACY,
        "CAFE": _CAFE,
        "PUBLIC": _PUBLIC,
        "CUSTOM": _PHARMACY + _CAFE + _PUBLIC,
    }.get(context, ())
    for g in extra:
        if g not in result:
            result.append(g)
    return result


def normalize_gloss(gloss: Optional[str]) -> str:
    """Mục 7.4 bước 1: NFC, bỏ khoảng trắng thừa, viết hoa."""
    if gloss is None:
        return UNKNOWN
    g = unicodedata.normalize("NFC", str(gloss)).strip()
    return re.sub(r"\s+", " ", g).upper()


def check_sign_output(context: str, out: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Mục 7.4: ép glosses về bộ ký hiệu; có UNKNOWN / confidence thấp → spoken_sentence rỗng."""
    if not isinstance(out, dict) or not isinstance(out.get("glosses"), list) \
            or not isinstance(out.get("suggestedChips"), list):
        raise ApiError.ai_upstream_error("AI trả thiếu trường bắt buộc.")
    try:
        confidence = float(out.get("confidence"))
    except (TypeError, ValueError):
        raise ApiError.ai_upstream_error("AI trả confidence sai định dạng.")

    allowed = allowed_glosses(context)
    glosses = [g if g in allowed else UNKNOWN for g in (normalize_gloss(x) for x in out["glosses"])]
    if not glosses:
        raise ApiError.no_sign_detected()

    has_unknown = UNKNOWN in glosses
    need_confirm = has_unknown or confidence < CONFIDENCE_THRESHOLD
    if has_unknown:
        confidence = min(confidence, CONFIDENCE_THRESHOLD - 0.01)
    sentence = out.get("spoken_sentence")
    if need_confirm or not isinstance(sentence, str):
        sentence = ""
    chips = [str(c).strip() for c in out["suggestedChips"] if str(c).strip()]
    return {
        "glosses": glosses,
        "confidence": max(0.0, min(1.0, confidence)),
        "spoken_sentence": sentence,
        "suggestedChips": chips,
    }


@functools.lru_cache(maxsize=4)
def _load_vsl_labels(path: str) -> Dict[str, str]:
    """Đọc labels.json (list theo index hoặc {"nhãn": index}) → {gloss chuẩn hoá: nhãn gốc để hiển thị}."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as e:
        logger.warning("Không đọc được nhãn VSL (%s)", type(e).__name__)
        return {}
    names = data.keys() if isinstance(data, dict) else data if isinstance(data, list) else []
    return {normalize_gloss(n): n.strip() for n in names if isinstance(n, str) and n.strip()}


def vsl_labels() -> Dict[str, str]:
    return _load_vsl_labels(VSL_LABELS_PATH)


def display_gloss(gloss: str) -> str:
    """Gloss chuẩn hoá → chữ hiển thị trên thẻ: nhãn gốc của model, hoặc viết hoa chữ đầu (mục 7.1)."""
    return vsl_labels().get(gloss) or gloss.capitalize()


def check_device_glosses(context: str, glosses: List[str], confidences: List[float]) -> Dict[str, Any]:
    """Mục 4.2a, 7.3, 7.4: ký hiệu nhận diện trên thiết bị → ép về bộ ký hiệu.

    Bộ ký hiệu = mục 7.2 theo context ∪ nhãn model (VSL_LABELS_PATH).
    Ngoài bộ → UNKNOWN. Xác suất < VSL_MIN_GLOSS_CONFIDENCE → UNKNOWN nhưng giữ làm thẻ gợi ý.
    """
    if not glosses:
        raise ApiError.no_sign_detected()
    allowed = set(allowed_glosses(context)) | set(vsl_labels())
    result: List[str] = []
    candidates: List[str] = []
    for raw, conf in zip(glosses, confidences):
        g = normalize_gloss(raw)
        if g not in allowed:
            result.append(UNKNOWN)
        elif conf < VSL_MIN_GLOSS_CONFIDENCE:
            result.append(UNKNOWN)
            candidates.append(g)
        else:
            result.append(g)

    confidence = max(0.0, min(1.0, min(confidences)))
    if UNKNOWN in result:
        confidence = min(confidence, CONFIDENCE_THRESHOLD - 0.01)
    need_confirm = UNKNOWN in result or confidence < CONFIDENCE_THRESHOLD

    chips: List[str] = []
    for g in candidates + [x for x in result if x != UNKNOWN] + allowed_glosses(context):
        chip = display_gloss(g)
        if chip not in chips:
            chips.append(chip)
        if len(chips) == MAX_SUGGESTED_CHIPS:
            break
    return {
        "glosses": result,
        "confidence": confidence,
        "needConfirm": need_confirm,
        "suggestedChips": chips,
    }


def gloss_template_sentence(glosses: List[str]) -> str:
    """Câu dự phòng chỉ gồm đúng các ký hiệu, không thêm ý (mục 7.3 bước 2)."""
    text = ", ".join(display_gloss(g) for g in glosses if g != UNKNOWN)
    return (text[:1].upper() + text[1:] + ".") if text else ""


def check_gloss_sentence(out: Optional[Dict[str, Any]], glosses: List[str]) -> str:
    """Mục 7.3 bước 2: câu LLM sai schema, quá 40 từ hoặc có số không có trong glosses → câu dự phòng."""
    sentence = out.get("spoken_sentence") if isinstance(out, dict) else None
    if isinstance(sentence, str) and sentence.strip():
        sentence = sentence.strip()
        numbers_in_glosses = set(re.findall(r"\d+", " ".join(glosses)))
        if len(sentence.split()) <= MAX_SENTENCE_WORDS \
                and set(re.findall(r"\d+", sentence)) <= numbers_in_glosses:
            return sentence
    return gloss_template_sentence(glosses)


def check_expand_output(out: Optional[Dict[str, Any]]) -> Dict[str, str]:
    sentence = out.get("spoken_sentence") if isinstance(out, dict) else None
    if not isinstance(sentence, str) or not sentence.strip():
        raise ApiError.ai_upstream_error("AI không trả câu nói.")
    return {"spoken_sentence": sentence.strip()}


def check_summarize_output(out: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Mục 4.6 bước 1, 3: đúng schema; bỏ highlight không xuất hiện nguyên văn trong summary."""
    if not isinstance(out, dict):
        raise ApiError.ai_upstream_error("AI trả tóm tắt sai schema.")
    summary = out.get("summary")
    replies = out.get("quickReplies")
    icon = out.get("iconCode")
    if not isinstance(summary, str) or not summary.strip() or not isinstance(icon, str) \
            or not isinstance(replies, list) or len(replies) != 3:
        raise ApiError.ai_upstream_error("AI trả tóm tắt sai schema.")
    highlights = [
        {"type": h["type"], "text": h["text"]}
        for h in (out.get("highlights") or [])
        if isinstance(h, dict) and h.get("type") and isinstance(h.get("text"), str)
        and h["text"].strip() and h["text"] in summary
    ]
    result = dict(out)
    result["highlights"] = highlights
    return result
