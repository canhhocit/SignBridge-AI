import os
import json
import logging
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Tự động nạp cấu hình từ .env nếu có
load_dotenv()

logger = logging.getLogger("SignBridge.LLM")

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.9router.com/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")

SUMMARIZE_SYSTEM_PROMPT = """Bạn là trợ lý AI tóm tắt hội thoại cho người khiếm thính trong dự án SignBridge.
Nhiệm vụ: Đọc văn bản lời nói của nhân viên quầy và tạo thông tin hiển thị trực quan cho người khiếm thính.

QUY TẮC BẮT BUỘC:
1. "summary":
   - Tối đa 15 từ.
   - PHẢI GIỮ NGUYÊN MỌI CON SỐ (giá tiền, số lượng, liều dùng, số quầy, thời gian, giờ giấc). TUYỆT ĐỐI KHÔNG LÀM SAI CON SỐ.
   - Bỏ toàn bộ từ đệm, kính ngữ xã giao (dạ, vâng, ạ, nhé, xin chào, cảm ơn...).
   - Dùng dấu chấm tròn '•' để ngăn cách các ý chính nếu cần.
2. "highlights":
   - Danh sách các từ/cụm từ quan trọng cần làm nổi bật trên màn hình.
   - Mỗi phần tử gồm: {"type": "<LOẠI>", "text": "<chuỗi>"}.
   - "text" PHẢI XUẤT HIỆN NGUYÊN VĂN trong "summary".
   - "type" chỉ được là 1 trong các giá trị: "PRICE", "COUNTER", "DOSAGE", "TIME", "QUANTITY", "OTHER".
3. "iconCode":
   - Chọn đúng 1 icon đại diện trực quan nhất từ danh sách sau:
     "PILL" (thuốc, liều dùng), "MONEY" (giá tiền, tiền mặt), "QR_PAYMENT" (chuyển khoản, quét mã QR),
     "COUNTER" (số quầy, vị trí), "TIME" (thời gian, chờ đợi), "DOCUMENT" (giấy tờ, hồ sơ),
     "DRINK" (đồ uống), "FOOD" (đồ ăn), "CHECK" (đồng ý, xong), "WARNING" (cảnh báo, từ chối, hết hàng),
     "INFO" (thông tin chung khác).
4. "quickReplies":
   - Đúng 3 gợi ý câu trả lời ngắn (mỗi câu <= 6 từ) để người khiếm thính bấm nhanh phản hồi lại nhân viên.
   - Đứng từ góc nhìn người khiếm thính (ví dụ: "Lấy 1 hộp", "Chuyển khoản QR", "Có loại khác không?").

CHỈ TRẢ VỀ DUY NHẤT 1 ĐỐI TƯỢNG JSON HỢP LỆ VỚI CÁC TRƯỜNG:
{
  "summary": "...",
  "highlights": [{"type": "...", "text": "..."}],
  "iconCode": "...",
  "quickReplies": ["...", "...", "..."]
}
"""

EXPAND_SYSTEM_PROMPT = """Bạn là trợ lý AI hỗ trợ người khiếm thính trong dự án SignBridge.
Nhiệm vụ: Chuyển danh sách các thẻ từ khóa (chips) mà người khiếm thính vừa chọn thành một câu nói tiếng Việt tự nhiên, lịch sự và ngắn gọn để phát qua loa cho nhân viên nghe.

QUY TẮC BẮT BUỘC:
1. "spoken_sentence":
   - Giữ đầy đủ nghĩa của tất cả các thẻ trong danh sách chips theo đúng thứ tự.
   - Thêm lời chào, kính ngữ (anh/chị/bạn/mình), từ nối (nhé, ạ, giúp mình) cho tự nhiên, lịch sự.
   - Độ dài: tối đa 40 từ.
   - KHÔNG ĐƯỢC thêm sự thật mới, không bịa thêm số lượng, giá tiền, tên thuốc hay món ngoài các thẻ đã chọn.
   - Phù hợp với ngữ cảnh đã cho và mạch hội thoại trước đó (nếu có).

CHỈ TRẢ VỀ DUY NHẤT 1 ĐỐI TƯỢNG JSON HỢP LỆ:
{
  "spoken_sentence": "..."
}
"""

def get_openai_client():
    api_key = os.getenv("LLM_API_KEY", LLM_API_KEY).strip()
    if not api_key:
        return None
    from openai import OpenAI
    base_url = os.getenv("LLM_BASE_URL", LLM_BASE_URL).strip()
    return OpenAI(base_url=base_url, api_key=api_key, timeout=10.0)

def clean_json_text(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text

def summarize_text(transcript: str, context: str = "CUSTOM", previous_outgoing: Optional[str] = None) -> Dict[str, Any]:
    client = get_openai_client()
    model = os.getenv("LLM_MODEL", LLM_MODEL).strip()

    if not client:
        return mock_summarize(transcript, context)

    user_prompt = f"Ngữ cảnh: {context}\n"
    if previous_outgoing:
        user_prompt += f"Lời người khiếm thính nói lượt trước: {previous_outgoing}\n"
    user_prompt += f"Lời nhân viên vừa nói: {transcript}\n\nHãy tóm tắt ra JSON theo đúng quy tắc."

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SUMMARIZE_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=400
        )
        content = clean_json_text(response.choices[0].message.content or "{}")
        data = json.loads(content)
        
        # Đảm bảo trường highlights nguyên văn trong summary
        summary = data.get("summary", "")
        raw_highlights = data.get("highlights", [])
        clean_highlights = [
            h for h in raw_highlights
            if isinstance(h, dict) and h.get("text") and h.get("text") in summary
        ]
        data["highlights"] = clean_highlights

        # Đảm bảo quickReplies đủ 3 phần tử
        quick_replies = data.get("quickReplies", [])
        if len(quick_replies) != 3:
            data["quickReplies"] = (quick_replies + ["Đồng ý", "Chuyển khoản QR", "Cảm ơn"])[:3]

        return data
    except Exception as e:
        logger.error(f"Lỗi gọi LLM summarize: {e}")
        return mock_summarize(transcript, context)

def expand_chips(chips: List[str], context: str = "CUSTOM", previous_incoming: Optional[str] = None) -> Dict[str, Any]:
    client = get_openai_client()
    model = os.getenv("LLM_MODEL", LLM_MODEL).strip()

    if not client:
        return {"spoken_sentence": f"Chào bạn, mình muốn: {', '.join(chips)}. Cảm ơn bạn!"}

    user_prompt = f"Ngữ cảnh: {context}\n"
    if previous_incoming:
        user_prompt += f"Lời nhân viên vừa nói lượt trước: {previous_incoming}\n"
    user_prompt += f"Các thẻ từ khóa người khiếm thính đã chọn: {json.dumps(chips, ensure_ascii=False)}\n\nHãy sinh câu nói tiếng Việt lịch sự dạng JSON."

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": EXPAND_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=200
        )
        content = clean_json_text(response.choices[0].message.content or "{}")
        return json.loads(content)
    except Exception as e:
        logger.error(f"Lỗi gọi LLM expand: {e}")
        return {"spoken_sentence": f"Chào bạn, cho mình hỏi về {', '.join(chips)} với ạ. Cảm ơn bạn!"}

def mock_summarize(transcript: str, context: str) -> Dict[str, Any]:
    # Heuristic fallback khi chưa nhập API key
    lower = transcript.lower()
    if "panadol" in lower or "thuốc" in lower or context == "PHARMACY":
        return {
            "summary": "Panadol Xanh • 1 viên sau ăn • Ngày 2 lần • 35.000đ",
            "highlights": [
                {"type": "DOSAGE", "text": "1 viên"},
                {"type": "QUANTITY", "text": "Ngày 2 lần"},
                {"type": "PRICE", "text": "35.000đ"}
            ],
            "iconCode": "PILL",
            "quickReplies": ["Lấy 1 hộp", "Chuyển khoản QR", "Có loại rẻ hơn không?"]
        }
    elif "trà sữa" in lower or "cà phê" in lower or "đá" in lower or context == "CAFE":
        return {
            "summary": "Trà sữa trân châu • Ít đường • 50% đá",
            "highlights": [
                {"type": "QUANTITY", "text": "Ít đường"},
                {"type": "QUANTITY", "text": "50% đá"}
            ],
            "iconCode": "DRINK",
            "quickReplies": ["Đúng rồi", "Thêm trân châu", "Chuyển khoản QR"]
        }
    else:
        return {
            "summary": transcript[:60] if len(transcript) > 60 else transcript,
            "highlights": [],
            "iconCode": "INFO",
            "quickReplies": ["Đồng ý", "Chuyển khoản QR", "Cảm ơn"]
        }
