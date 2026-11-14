"""Kiểm tra lại output AI trước khi trả cho mobile (mục 4.6, 7.4) + bộ ký hiệu demo (mục 7.1, 7.2).

Không phụ thuộc HTTP/FastAPI. Không lưu gì.
"""
import os
import re
import unicodedata
from typing import Any, Dict, List, Optional

from errors import ApiError

CONTEXTS = ("CAFE", "PHARMACY", "PUBLIC", "CUSTOM")
UNKNOWN = "UNKNOWN"

# confidence >= ngưỡng thì mobile phát loa luôn
CONFIDENCE_THRESHOLD = float(os.getenv("SIGN_CONFIDENCE_THRESHOLD", "0.7"))

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
