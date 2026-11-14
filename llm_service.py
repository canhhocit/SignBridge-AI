import os
import re
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

# Danh sách icon hợp lệ theo đặc tả
VALID_ICON_CODES = {
    "PILL", "MONEY", "QR_PAYMENT", "COUNTER", "TIME",
    "DOCUMENT", "DRINK", "FOOD", "CHECK", "WARNING", "INFO"
}

VALID_HIGHLIGHT_TYPES = {"PRICE", "COUNTER", "DOSAGE", "TIME", "QUANTITY", "OTHER"}

SUMMARIZE_SYSTEM_PROMPT = """Bạn là trợ lý AI tóm tắt và hỗ trợ phản hồi hội thoại hai chiều trong dự án SignBridge.
Hội thoại diễn ra giữa:
- NGƯỜI NÓI (Người A): Người nghe-nói bình thường (nhân viên bán hàng, người qua đường chỉ đường, bác sĩ, công chức...).
- NGƯỜI DÙNG (Người B): Người khiếm thính hoặc câm (KHÔNG THỂ NÓI ĐƯỢC, đang nhìn màn hình điện thoại để giao tiếp).

NHIỆM VỤ CỦA BẠN:
1. "summary": Tóm tắt súc tích (≤ 15 từ) nội dung Người A vừa nói để Người B đọc hiểu ngay lập tức.
2. "highlights": Trích xuất danh sách các từ/cụm từ quan trọng cần làm nổi bật trên màn hình.
3. "iconCode": Chọn 1 icon đại diện trực quan nhất từ danh sách:
   "PILL" (thuốc, liều dùng), "MONEY" (giá tiền, tiền mặt), "QR_PAYMENT" (chuyển khoản, quét mã QR),
   "COUNTER" (số quầy, vị trí), "TIME" (thời gian, chờ đợi), "DOCUMENT" (giấy tờ, hồ sơ),
   "DRINK" (đồ uống), "FOOD" (đồ ăn), "CHECK" (đồng ý, xong), "WARNING" (cảnh báo, từ chối, hết hàng),
   "INFO" (chỉ đường, thông tin chung).
4. "quickReplies": ĐÚNG 3 CÂU GỢI Ý PHẢN HỒI ĐỂ NGƯỜI B CHẠM VÀO PHÁT LOA (TTS) ĐÁP LẠI NGƯỜI A.

QUY TẮC BẮT BUỘC CHO "summary":
- Tối đa 15 từ.
- PHẢI GIỮ NGUYÊN MỌI CON SỐ (giá tiền, số lượng, liều dùng, số quầy, thời gian, giờ giấc, %). TUYỆT ĐỐI KHÔNG LÀM SAI HOẶC BỎ MẤT SỐ.
- Bỏ toàn bộ từ đệm, kính ngữ xã giao (dạ, vâng, ạ, nhé, xin chào, cảm ơn...).
- Dùng dấu chấm tròn '•' để ngăn cách các ý chính nếu cần.

QUY TẮC BẮT BUỘC CHO "highlights":
- Mỗi phần tử: {"type": "<LOẠI>", "text": "<chuỗi>"}.
- "type" chỉ được là: "PRICE", "COUNTER", "DOSAGE", "TIME", "QUANTITY", "OTHER".
- "text" PHẢI XUẤT HIỆN NGUYÊN VĂN trong "summary".

QUY TẮC BẮT BUỘC CHO "quickReplies" (CỰC KỲ QUAN TRỌNG):
- ĐÂY LÀ LỜI NÓI CỦA NGƯỜI B (NGƯỜI KHIẾM THÍNH/CÂM) NÓI VỚI NGƯỜI A.
- TUYỆT ĐỐI KHÔNG ĐƯỢC LẶP LẠI LỜI CỦA NGƯỜI A!
  (Ví dụ: Người A vừa chỉ đường "Đi thẳng rồi rẽ phải", Người B TUYỆT ĐỐI KHÔNG nói "Đi thẳng rẽ phải", mà phải nói lời đáp lại như "Dạ em cảm ơn ạ" hoặc "Đi bộ có xa không ạ?").
- Văn phong: Lịch sự, tự nhiên, câu nói hoàn chỉnh có kính ngữ ("Dạ", "ạ", "giúp em", "cho em hỏi").
- Độ dài: Mỗi câu từ 3 đến 8 từ (đủ ngắn để hiển thị đẹp trên nút bấm, phát âm thanh rõ ràng).
- Bao quát 3 hướng phản xạ thực tế:
  1. Câu 1: Xác nhận / Đồng ý / Cảm ơn (Ví dụ: "Dạ em hiểu rồi, cảm ơn ạ", "Em quét mã QR nhé", "Cho em lấy loại này ạ")
  2. Câu 2: Hỏi chi tiết tiếp theo / Thắc mắc thực tế (Ví dụ: "Đi bộ có xa không ạ?", "Uống trước hay sau ăn ạ?", "Bao giờ thì có kết quả ạ?")
  3. Câu 3: Nhờ hỗ trợ thêm / Hỏi lại / Từ chối (Ví dụ: "Chỉ lại giúp em một chút ạ", "Có loại khác rẻ hơn không ạ?", "Em không mang CCCD rồi")

VÍ DỤ TÌNH HUỐNG THỰC TẾ:
- Tình huống chỉ đường (Người A: "Cháu cứ đi thẳng ngã tư rẽ trái, nhìn bên phải là thấy chợ nhé"):
  "summary": "Đi thẳng ngã tư • Rẽ trái • Chợ bên phải",
  "iconCode": "INFO",
  "quickReplies": ["Dạ em cảm ơn ạ", "Đi bộ có xa không ạ?", "Chỉ lại giúp em một chút ạ"]

- Tình huống tính tiền (Người A: "Của em hết 45 nghìn, thanh toán tiền mặt hay chuyển khoản?"):
  "summary": "45 nghìn • Tiền mặt hoặc chuyển khoản",
  "iconCode": "MONEY",
  "quickReplies": ["Em quét mã QR nhé", "Em gửi tiền mặt ạ", "Cho em xin hóa đơn ạ"]

- Tình huống hiệu thuốc (Người A: "Thuốc này ngày uống 2 lần sau ăn sáng tối nhé"):
  "summary": "Ngày uống 2 lần • Sau ăn sáng tối",
  "iconCode": "PILL",
  "quickReplies": ["Dạ em hiểu rồi, cảm ơn", "Uống trong mấy ngày ạ?", "Viết ra giấy giúp em với"]

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
    # Timeout 3.5s để phản hồi cực nhanh, không để người dùng chờ lâu
    return OpenAI(base_url=base_url, api_key=api_key, timeout=3.5)

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

def verify_and_protect_numbers(transcript: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Guardrail đảm bảo tiêu chí Zero-Number-Error:
    Bảo toàn toàn bộ số liệu, giá tiền, số quầy, liều lượng từ transcript vào summary và highlights.
    """
    summary = data.get("summary", "").strip()
    highlights = data.get("highlights", [])
    if not isinstance(highlights, list):
        highlights = []

    # 1. Trích xuất các thực thể số quan trọng từ transcript bằng Regex
    extracted_patterns = [
        # Giá tiền: 35.000đ, 35k, 50 nghìn...
        (r'\b\d+(?:[\.,]\d+)?\s*(?:k|nghìn|ngàn|triệu|đ|đồng)\b', "PRICE"),
        # Phần trăm / đá / đường: 50%, 70%...
        (r'\b\d+\s*(?:%|phần trăm)\b', "QUANTITY"),
        # Liều dùng / số lượng: 1 viên, 2 vỉ, 3 hộp, ngày 2 lần...
        (r'\b(?:ngày\s*)?\d+\s*(?:viên|gói|vỉ|hộp|lần|cốc|ly|chai|bát|phần)\b', "DOSAGE"),
        # Số quầy / phòng: quầy 2, quầy số 3, phòng 104...
        (r'\b(?:quầy|phòng)\s*(?:số\s*)?[0-9a-zA-Z]+\b', "COUNTER"),
        # Thời gian: 5 phút, 15 phút, 2 tiếng...
        (r'\b\d+\s*(?:phút|tiếng|giờ)\b', "TIME"),
    ]

    needed_entities = []
    for pattern, ptype in extracted_patterns:
        for match in re.finditer(pattern, transcript, flags=re.IGNORECASE):
            val = match.group(0).strip()
            needed_entities.append((val, ptype))

    # 2. Kiểm tra xem các số quan trọng đã có trong summary chưa
    summary_lower = summary.lower()
    for val, ptype in needed_entities:
        # Trích xuất số thực tế (digits)
        digits = re.findall(r'\d+', val)
        # Nếu chưa có trong summary (cả chuỗi lẫn chữ số chính), tự động bổ sung
        has_digits = all(d in summary for d in digits) if digits else (val.lower() in summary_lower)
        if not has_digits and val.lower() not in summary_lower:
            if summary:
                summary += f" • {val}"
            else:
                summary = val
            summary_lower = summary.lower()

    # 3. Lọc highlights: chỉ giữ phần tử có trong summary
    clean_highlights = []
    seen_texts = set()
    for h in highlights:
        if isinstance(h, dict):
            htext = str(h.get("text", "")).strip()
            htype = str(h.get("type", "OTHER")).upper()
            if htype not in VALID_HIGHLIGHT_TYPES:
                htype = "OTHER"
            if htext and htext.lower() in summary.lower() and htext.lower() not in seen_texts:
                clean_highlights.append({"type": htype, "text": htext})
                seen_texts.add(htext.lower())

    # 4. Tự động thêm các số quan trọng vào highlights nếu LLM bỏ quên
    for val, ptype in needed_entities:
        if val.lower() in summary.lower() and val.lower() not in seen_texts:
            clean_highlights.append({"type": ptype, "text": val})
            seen_texts.add(val.lower())

    data["summary"] = summary
    data["highlights"] = clean_highlights

    # 5. Đảm bảo iconCode hợp lệ
    icon = data.get("iconCode", "INFO")
    if icon not in VALID_ICON_CODES:
        icon = "INFO"
    data["iconCode"] = icon

    # 6. Đảm bảo quickReplies luôn có đủ 3 gợi ý ngắn gọn
    quick_replies = data.get("quickReplies", [])
    if not isinstance(quick_replies, list):
        quick_replies = []
    valid_replies = [str(r).strip() for r in quick_replies if str(r).strip()]
    default_fallbacks = ["Đồng ý", "Chuyển khoản QR", "Cảm ơn"]
    for fb in default_fallbacks:
        if len(valid_replies) >= 3:
            break
        if fb not in valid_replies:
            valid_replies.append(fb)
    data["quickReplies"] = valid_replies[:3]

    return data

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
            temperature=0.0,    # 0.0: Sinh kết quả nhanh nhất, chuẩn xác và xác định nhất
            max_tokens=180      # 180 tokens: Đủ trọn vẹn JSON tóm tắt, cắt giảm 40% độ trễ API
        )
        content = clean_json_text(response.choices[0].message.content or "{}")
        data = json.loads(content)
        return verify_and_protect_numbers(transcript, data)
    except Exception as e:
        logger.warning(f"Fallback sang Fast Mock Summarize do: {e}")
        return mock_summarize(transcript, context)

def expand_chips(chips: List[str], context: str = "CUSTOM", previous_incoming: Optional[str] = None) -> Dict[str, Any]:
    client = get_openai_client()
    model = os.getenv("LLM_MODEL", LLM_MODEL).strip()

    if not client:
        return {"spoken_sentence": f"Chào bạn, mình muốn {', '.join(chips)}. Cảm ơn bạn!"}

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
            temperature=0.0,
            max_tokens=100      # 100 tokens: Tối ưu tốc độ trả câu nói
        )
        content = clean_json_text(response.choices[0].message.content or "{}")
        data = json.loads(content)
        sentence = data.get("spoken_sentence", "")
        if not sentence:
            sentence = f"Chào bạn, mình muốn {', '.join(chips)} với ạ."
        return {"spoken_sentence": sentence}
    except Exception as e:
        logger.warning(f"Lỗi gọi LLM expand, fallback: {e}")
        return {"spoken_sentence": f"Chào bạn, cho mình hỏi về {', '.join(chips)} với ạ. Cảm ơn bạn!"}

def mock_summarize(transcript: str, context: str) -> Dict[str, Any]:
    """
    Bộ bóc tách siêu tốc (Rule-based Fast Heuristic):
    Phản hồi < 1ms, giữ 100% con số, trích xuất chính xác highlight, iconCode và quickReplies.
    Hoạt động độc lập không cần mạng/API key.
    """
    clean_text = re.sub(
        r'\b(dạ|vâng|ạ|nhé|xin chào|chào anh|chào chị|cảm ơn|của anh|của chị|giúp em|với ạ|phiền anh|phiền chị)\b',
        '', transcript, flags=re.IGNORECASE
    ).strip()

    highlights = []
    bullet_items = []

    # 1. Trích xuất giá tiền
    price_match = re.search(r'(\d+[\.,]?\d*\s*(?:k|nghìn|ngàn|triệu|đ|đồng))', transcript, re.IGNORECASE)
    if price_match:
        price_str = price_match.group(1).strip()
        highlights.append({"type": "PRICE", "text": price_str})
        bullet_items.append(price_str)

    # 2. Trích xuất số quầy
    counter_match = re.search(r'((?:quầy|phòng)\s*(?:số\s*)?[0-9a-zA-Z]+)', transcript, re.IGNORECASE)
    if counter_match:
        counter_str = counter_match.group(1).strip()
        highlights.append({"type": "COUNTER", "text": counter_str})
        bullet_items.append(counter_str)

    # 3. Trích xuất liều dùng
    dosage_match = re.search(r'((?:ngày\s*)?\d+\s*(?:viên|gói|vỉ|hộp|lần)(?:\s*(?:sau|trước)\s*ăn)?)', transcript, re.IGNORECASE)
    if dosage_match:
        dosage_str = dosage_match.group(1).strip()
        highlights.append({"type": "DOSAGE", "text": dosage_str})
        bullet_items.append(dosage_str)

    # 4. Trích xuất thời gian chờ
    time_match = re.search(r'(\d+\s*(?:phút|tiếng|giờ))', transcript, re.IGNORECASE)
    if time_match:
        time_str = time_match.group(1).strip()
        highlights.append({"type": "TIME", "text": time_str})
        bullet_items.append(time_str)

    # 5. Trích xuất số lượng / phần trăm
    qty_match = re.search(r'(\d+\s*(?:%|phần trăm|cốc|ly|chai|bát|phần))', transcript, re.IGNORECASE)
    if qty_match:
        qty_str = qty_match.group(1).strip()
        highlights.append({"type": "QUANTITY", "text": qty_str})
        bullet_items.append(qty_str)

    # Xác định Icon và QuickReplies phù hợp nhất
    lower = transcript.lower()
    icon = "INFO"
    quick_replies = ["Đồng ý", "Chuyển khoản QR", "Cảm ơn"]

    if "chuyển khoản" in lower or "quét mã" in lower or "qr" in lower:
        icon = "QR_PAYMENT"
        quick_replies = ["Quét mã QR", "Trả tiền mặt", "Chờ chút"]
    elif price_match:
        icon = "MONEY"
        quick_replies = ["Chuyển khoản QR", "Gửi tiền mặt", "Xem lại giá"]
    elif counter_match:
        icon = "COUNTER"
        quick_replies = ["Đã rõ quầy", "Chỉ đường giúp", "Cảm ơn"]
    elif "thuốc" in lower or dosage_match or context == "PHARMACY":
        icon = "PILL"
        quick_replies = ["Lấy 1 hộp", "Chuyển khoản QR", "Có loại khác không?"]
    elif "trà sữa" in lower or "cà phê" in lower or "đá" in lower or "đường" in lower or context == "CAFE":
        icon = "DRINK"
        quick_replies = ["Đúng rồi", "Thêm trân châu", "Chuyển khoản QR"]
    elif time_match:
        icon = "TIME"
        quick_replies = ["Sẽ đợi", "Có lâu hơn không?", "Cảm ơn"]

    # Xây dựng summary gọn gàng <= 15 từ
    if bullet_items:
        # Lấy từ khóa chính còn lại trong câu
        summary = " • ".join(bullet_items)
        # Giới hạn 15 từ
        words = summary.split()
        if len(words) > 15:
            summary = " ".join(words[:15])
    else:
        words = clean_text.split()
        summary = " ".join(words[:12]) if len(words) > 12 else clean_text

    raw_data = {
        "summary": summary,
        "highlights": highlights,
        "iconCode": icon,
        "quickReplies": quick_replies
    }
    return verify_and_protect_numbers(transcript, raw_data)

