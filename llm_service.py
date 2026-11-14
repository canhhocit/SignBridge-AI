import os
import re
import json
import logging
import functools
from typing import List, Optional, Dict, Any, Tuple
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
5. "suggestedChips": 3 đến 5 THẺ TỪ KHÓA NGẮN (mỗi thẻ 1-3 từ, ví dụ: "Đi bộ", "Bao xa", "Ít đường", "Mang về") để Người B có thể bấm chọn nạp thêm ý định.

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

6. KHÔI PHỤC NGỮ NGHĨA KHI NÓI NHỎ / NUỐT ÂM / MẤT TỪ (CỰC KỲ QUAN TRỌNG):
- Do môi trường ồn ào hoặc người nói nói nhỏ/nuốt chữ, văn bản STT có thể bị mất từ, cụt chữ hoặc sai âm học (ví dụ: "...băm nhăm... quét mã kia", "cho ly... ít đường... năm mươi đá", "thẳng... rẽ... chợ kia").
- BẠN BẮT BUỘC PHẢI DỰA VÀO:
  + "Bối cảnh" (CAFE, PHARMACY, PUBLIC, CUSTOM).
  + "Lời người khiếm thính nói lượt trước" (previousOutgoing) nếu có.
  để khôi phục lại câu nói đầy đủ, chuẩn xác theo ngữ cảnh trước khi tóm tắt!
  (Ví dụ: Người khiếm thính hỏi "Ly này bao nhiêu tiền ạ?", người bán nói nhỏ "...băm nhăm..." -> bạn khôi phục thành "35 nghìn", tóm tắt "35 nghìn • Chuyển khoản hoặc tiền mặt").
- NẾU CÂU NÓI THỰC SỰ QUÁ NHỎ HOẶC ĐỨT ĐOẠN KHÔNG THỂ HIỂU ĐƯỢC Ý ĐỊNH:
  + "summary": "Người nói nói hơi nhỏ • Chưa rõ ý"
  + "iconCode": "WARNING"
  + "highlights": [{"type": "OTHER", "text": "Chưa rõ ý"}]
  + "quickReplies": ["Bác nói to hơn một chút giúp cháu nhé", "Cháu bị khiếm thính, bác nói lại giúp cháu ạ", "Bác viết ra giấy hoặc chỉ tay giúp cháu nhé"]
  + "suggestedChips": ["Nói to hơn", "Nói lại", "Viết ra giấy", "Chỉ tay"]

VÍ DỤ TÌNH HUỐNG THỰC TẾ:
- Tình huống chỉ đường (Người A: "Cháu cứ đi thẳng ngã tư rẽ trái, nhìn bên phải là thấy chợ nhé"):
  "summary": "Đi thẳng ngã tư • Rẽ trái • Chợ bên phải",
  "iconCode": "INFO",
  "quickReplies": ["Dạ em cảm ơn ạ", "Đi bộ có xa không ạ?", "Chỉ lại giúp em một chút ạ"]

- Tình huống nói nhỏ/nuốt chữ nhưng khôi phục được nhờ câu hỏi trước (Người B: "Bao nhiêu tiền ạ?", Người A nói nhỏ: "...băm nhăm... quét mã"):
  "summary": "35 nghìn • Quét mã thanh toán",
  "iconCode": "MONEY",
  "quickReplies": ["Em quét mã QR nhé", "Em gửi tiền mặt ạ", "Cho em xin hóa đơn ạ"]

- Tình huống nói quá nhỏ/không nghe được:
  "summary": "Người nói nói hơi nhỏ • Chưa rõ ý",
  "iconCode": "WARNING",
  "quickReplies": ["Bác nói to hơn một chút giúp cháu nhé", "Cháu bị khiếm thính, bác nói lại giúp cháu ạ", "Bác viết ra giấy hoặc chỉ tay giúp cháu nhé"]

CHỈ TRẢ VỀ DUY NHẤT 1 ĐỐI TƯỢNG JSON HỢP LỆ VỚI CÁC TRƯỜNG:
{
  "summary": "...",
  "highlights": [{"type": "...", "text": "..."}],
  "iconCode": "...",
  "quickReplies": ["...", "...", "..."],
  "suggestedChips": ["...", "...", "..."]
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

@functools.lru_cache(maxsize=2)
def _openai_client(base_url: str, api_key: str):
    from openai import OpenAI
    # Dùng chung 1 client → giữ kết nối HTTPS (keep-alive), không bắt tay TLS lại mỗi request.
    # max_retries=0: mục 4.6 không retry; SDK mặc định retry 2 lần → 1 request có thể mất 3× timeout.
    # Timeout 3.5s để phản hồi cực nhanh, không để người dùng chờ lâu
    return OpenAI(base_url=base_url, api_key=api_key, timeout=3.5, max_retries=0)


def get_openai_client():
    api_key = os.getenv("LLM_API_KEY", LLM_API_KEY).strip()
    if not api_key:
        return None
    return _openai_client(os.getenv("LLM_BASE_URL", LLM_BASE_URL).strip(), api_key)

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

    # 3. Lọc highlights: chỉ giữ phần tử có trong summary.
    # So khớp không phân biệt hoa/thường nhưng trả đúng đoạn nguyên văn của summary (mục 4.4)
    def exact_in_summary(text: str) -> Optional[str]:
        idx = summary.lower().find(text.lower())
        if idx < 0:
            return None
        exact = summary[idx:idx + len(text)]
        return exact if exact.lower() == text.lower() else None

    clean_highlights = []
    seen_texts = set()
    for h in highlights:
        if isinstance(h, dict):
            htext = exact_in_summary(str(h.get("text", "")).strip()) if str(h.get("text", "")).strip() else None
            htype = str(h.get("type", "OTHER")).upper()
            if htype not in VALID_HIGHLIGHT_TYPES:
                htype = "OTHER"
            if htext and htext.lower() not in seen_texts:
                clean_highlights.append({"type": htype, "text": htext})
                seen_texts.add(htext.lower())

    # 4. Tự động thêm các số quan trọng vào highlights nếu LLM bỏ quên
    for val, ptype in needed_entities:
        exact = exact_in_summary(val)
        if exact and exact.lower() not in seen_texts:
            clean_highlights.append({"type": ptype, "text": exact})
            seen_texts.add(exact.lower())

    data["summary"] = summary
    data["highlights"] = clean_highlights

    # 5. Đảm bảo iconCode hợp lệ
    icon = data.get("iconCode", "INFO")
    if icon not in VALID_ICON_CODES:
        icon = "INFO"
    data["iconCode"] = icon

    # 6. Đảm bảo quickReplies đứng đúng góc nhìn Người B (khiếm thính/câm) & không lặp lại Người A
    quick_replies = data.get("quickReplies", [])
    if not isinstance(quick_replies, list):
        quick_replies = []
    
    # Lọc bỏ câu rỗng hoặc câu bị lỗi lặp lại nguyên văn chỉ dẫn người nói
    filtered_replies = []
    transcript_lower = transcript.lower()
    is_direction_context = any(w in transcript_lower for w in ["chợ", "rẽ", "đi thẳng", "ngã tư", "ngã ba", "đường", "hướng dẫn"])

    for r in quick_replies:
        r_str = str(r).strip()
        if not r_str:
            continue
        r_lower = r_str.lower()
        # Nếu đang chỉ đường mà câu gợi ý lại là "đi thẳng rẽ phải", "ở gần đây" -> loại bỏ ngay
        if is_direction_context and any(w in r_lower for w in ["đi thẳng", "rẽ phải", "rẽ trái", "ở gần đây"]):
            continue
        filtered_replies.append(r_str)

    # Bộ phản hồi dự phòng chuẩn mực theo từng tình huống
    context_fallbacks = {
        "DIRECTIONS": ["Dạ em cảm ơn ạ", "Đi bộ có xa không ạ?", "Chỉ lại giúp em một chút ạ"],
        "PRICE": ["Em quét mã QR nhé", "Em gửi tiền mặt ạ", "Cho em xin hóa đơn ạ"],
        "PHARMACY": ["Dạ em hiểu rồi, cảm ơn ạ", "Uống trong mấy ngày ạ?", "Viết ra giấy giúp em với"],
        "CAFE": ["Cho em lấy ly này ạ", "Ít ngọt ít đá giúp em", "Cho em mang về nhé"],
        "PUBLIC": ["Dạ em có đủ giấy tờ rồi", "Nộp lệ phí ở đâu ạ?", "Bao giờ có kết quả ạ?"],
        "WARNING": ["Bác nói to hơn một chút giúp cháu nhé", "Cháu bị khiếm thính, bác nói lại giúp cháu ạ", "Bác viết ra giấy hoặc chỉ tay giúp cháu nhé"],
        "DEFAULT": ["Dạ em cảm ơn ạ", "Cho em hỏi thêm một chút", "Chờ em một lát nhé"]
    }

    if icon == "WARNING":
        pool = context_fallbacks["WARNING"]
    elif is_direction_context:
        pool = context_fallbacks["DIRECTIONS"]
    elif icon in ["MONEY", "QR_PAYMENT"]:
        pool = context_fallbacks["PRICE"]
    elif icon == "PILL":
        pool = context_fallbacks["PHARMACY"]
    elif icon in ["DRINK", "FOOD"]:
        pool = context_fallbacks["CAFE"]
    elif icon == "DOCUMENT":
        pool = context_fallbacks["PUBLIC"]
    else:
        pool = context_fallbacks["DEFAULT"]

    for fb in pool:
        if len(filtered_replies) >= 3:
            break
        if fb not in filtered_replies:
            filtered_replies.append(fb)

    data["quickReplies"] = filtered_replies[:3]

    # 7. Đảm bảo suggestedChips hợp lệ
    s_chips = data.get("suggestedChips", [])
    if not isinstance(s_chips, list) or not s_chips:
        if icon == "WARNING":
            s_chips = ["Nói to hơn", "Nói lại", "Viết ra giấy", "Chỉ tay"]
        elif is_direction_context:
            s_chips = ["Đi bộ", "Bao xa", "Gần đây", "Đi xe máy"]
        elif icon in ["MONEY", "QR_PAYMENT"]:
            s_chips = ["Chuyển khoản QR", "Tiền mặt", "Hóa đơn", "Có giảm giá không"]
        elif icon == "PILL":
            s_chips = ["Uống sau ăn", "Ngày 2 lần", "Hộp nhỏ", "Có buồn ngủ không"]
        elif icon in ["DRINK", "FOOD"]:
            s_chips = ["Ít đường", "50% đá", "Mang đi", "Thêm trân châu"]
        else:
            s_chips = ["Cảm ơn", "Đồng ý", "Chờ một chút", "Hỏi thêm"]
    data["suggestedChips"] = [str(x).strip() for x in s_chips if str(x).strip()][:5]

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

    if not clean_text or len(clean_text) < 3:
        return {
            "summary": "Người nói nói hơi nhỏ • Chưa rõ ý",
            "highlights": [{"type": "OTHER", "text": "Chưa rõ ý"}],
            "iconCode": "WARNING",
            "quickReplies": [
                "Bác nói to hơn một chút giúp cháu nhé",
                "Cháu bị khiếm thính, bác nói lại giúp cháu ạ",
                "Bác viết ra giấy hoặc chỉ tay giúp cháu nhé"
            ],
            "suggestedChips": ["Nói to hơn", "Nói lại", "Viết ra giấy", "Chỉ tay"]
        }

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

    # Xác định Icon và QuickReplies phù hợp nhất theo Intent thực tế
    lower = transcript.lower()
    icon = "INFO"
    quick_replies = ["Dạ em cảm ơn ạ", "Cho em hỏi thêm một chút", "Chờ em một lát nhé"]

    # Nhận diện ý định chỉ đường / địa điểm
    is_direction = bool(re.search(r'\b(chợ|đường|rẽ|ngã\s*(?:ba|tư)|đi\s*thẳng|quẹo|hướng|ở\s*đâu|bên\s*(?:trái|phải)|đằng\s*kia|phía\s*trước)\b', transcript, re.IGNORECASE))

    if is_direction:
        icon = "INFO"
        quick_replies = ["Dạ em cảm ơn ạ", "Đi bộ có xa không ạ?", "Chỉ lại giúp em một chút ạ"]
        if not bullet_items:
            # Rút trích cụm hướng dẫn
            dir_phrase = re.sub(r'^(cháu|em|bạn|anh|chị)\s*', '', clean_text, flags=re.IGNORECASE)
            bullet_items.append("Chỉ đường: " + dir_phrase[:35])
    elif "chuyển khoản" in lower or "quét mã" in lower or "qr" in lower:
        icon = "QR_PAYMENT"
        quick_replies = ["Em quét mã QR nhé", "Em gửi tiền mặt ạ", "Cho em xin hóa đơn ạ"]
    elif price_match:
        icon = "MONEY"
        quick_replies = ["Em quét mã QR nhé", "Em gửi tiền mặt ạ", "Cho em xin hóa đơn ạ"]
    elif counter_match:
        icon = "COUNTER"
        quick_replies = ["Dạ em qua quầy ngay", "Chỉ vị trí quầy giúp em", "Cảm ơn ạ"]
    elif "thuốc" in lower or dosage_match or context == "PHARMACY":
        icon = "PILL"
        quick_replies = ["Dạ em hiểu rồi, cảm ơn ạ", "Uống trong mấy ngày ạ?", "Viết ra giấy giúp em với"]
    elif "trà sữa" in lower or "cà phê" in lower or "đá" in lower or "đường" in lower or context == "CAFE":
        icon = "DRINK"
        quick_replies = ["Cho em lấy ly này ạ", "Ít ngọt ít đá giúp em", "Cho em mang về nhé"]
    elif time_match:
        icon = "TIME"
        quick_replies = ["Dạ em sẽ đợi ạ", "Có lâu hơn không ạ?", "Em cảm ơn ạ"]

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

SIGN_SYSTEM_PROMPT = """Bạn là bộ nhận diện ngôn ngữ ký hiệu cho người khiếm thính.
Đầu vào là chuỗi khung hình liên tiếp, 4 khung hình mỗi 1,5 giây.

QUY TẮC BẮT BUỘC:
1. Chỉ được trả "glosses" là chuỗi GIỐNG HỆT một mục trong DANH_SÁCH_KÝ_HIỆU, hoặc "UNKNOWN".
   Không dùng từ đồng nghĩa, không đổi chữ, không thêm từ ngoài danh sách.
2. Không chắc một ký hiệu → "UNKNOWN". Không đoán.
3. Nếu có bất kỳ "UNKNOWN" → "spoken_sentence" = "" và "confidence" < 0.7.
4. "spoken_sentence" chỉ diễn đạt đúng nghĩa các glosses. Được thêm lời chào, kính ngữ, từ nối.
   KHÔNG thêm triệu chứng, món, số lượng, giá, thời gian, tên sản phẩm hay yêu cầu không có trong glosses.
5. Chỉ trả JSON đúng schema, không giải thích:
{"glosses": ["..."], "confidence": 0.0, "spoken_sentence": "...", "suggestedChips": ["...", "...", "..."]}
"""


def recognize_sign(frames_bytes: List[bytes], context: str = "CUSTOM", personal_chips: Optional[List[str]] = None,
                   previous_incoming: Optional[str] = None, allowed_glosses: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Nhận diện ngôn ngữ ký hiệu từ chuỗi frame ảnh JPEG (mục 4.2, 7.3).
    Chưa cấu hình LLM_API_KEY → trả dữ liệu mẫu theo ngữ cảnh (chế độ mock, như MockAiGateway).
    Đã cấu hình mà gọi lỗi → ném ApiError (502/504) để mobile chuyển sang thẻ từ khóa;
    KHÔNG trả câu mẫu vì mobile sẽ phát loa một câu người dùng không hề ký hiệu.
    """
    from errors import ApiError
    import openai

    context_fallbacks = {
        "PHARMACY": {
            "glosses": ["ĐAU", "ĐẦU", "MUA", "THUỐC"],
            "confidence": 0.88,
            "spoken_sentence": "Chào bạn, mình bị đau đầu, muốn mua thuốc.",
            "suggestedChips": ["Đau đầu", "Mua thuốc", "Không buồn ngủ"]
        },
        "CAFE": {
            "glosses": ["CÀ PHÊ", "ĐÁ", "MANG ĐI"],
            "confidence": 0.86,
            "spoken_sentence": "Cho mình một cà phê đá mang đi nhé, cảm ơn bạn.",
            "suggestedChips": ["Cà phê", "Đá", "Mang đi"]
        },
        "PUBLIC": {
            "glosses": ["GIẤY TỜ", "Ở ĐÂU"],
            "confidence": 0.82,
            "spoken_sentence": "Chào anh chị, cho mình hỏi nộp giấy tờ ở đâu ạ?",
            "suggestedChips": ["Giấy tờ", "Ở đâu", "Cảm ơn"]
        },
        "CUSTOM": {
            "glosses": ["XIN CHÀO", "CẢM ƠN"],
            "confidence": 0.90,
            "spoken_sentence": "Xin chào, cảm ơn bạn.",
            "suggestedChips": ["Xin chào", "Cảm ơn", "Có"]
        }
    }

    if personal_chips and "MOCK_LOW" in personal_chips:
        return {
            "glosses": ["UNKNOWN", "NGÀY"],
            "confidence": 0.41,
            "spoken_sentence": "",
            "suggestedChips": ["Một ngày", "Hai ngày", "Một tuần", "Lâu rồi"]
        }

    client = get_openai_client()
    if not client:
        return context_fallbacks.get(context, context_fallbacks["CUSTOM"])

    import base64
    # Chọn frame đầu và frame giữa để gửi vision (giảm độ trễ)
    indices = [0]
    if len(frames_bytes) > 2:
        indices.append(len(frames_bytes) // 2)

    text = (f"DANH_SÁCH_KÝ_HIỆU: {json.dumps(allowed_glosses or [], ensure_ascii=False)}\n"
            f"NGỮ_CẢNH: {context}\n"
            f"CÂU_NHÂN_VIÊN_VỪA_NÓI: {previous_incoming or 'không có'}\n"
            f"THẺ_CÁ_NHÂN: {json.dumps(personal_chips or [], ensure_ascii=False)}")
    content_parts = [{"type": "text", "text": text}]
    for idx in indices:
        b64 = base64.b64encode(frames_bytes[idx]).decode("utf-8")
        content_parts.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})

    try:
        response = client.chat.completions.create(
            model=os.getenv("LLM_MODEL", LLM_MODEL).strip(),
            messages=[
                {"role": "system", "content": SIGN_SYSTEM_PROMPT},
                {"role": "user", "content": content_parts}
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
            max_tokens=150,
            timeout=float(os.getenv("AI_TIMEOUT_SIGN", "6"))
        )
        content = clean_json_text(response.choices[0].message.content or "{}")
        return json.loads(content)
    except openai.APITimeoutError:
        logger.warning("AI sign: AI_TIMEOUT")
        raise ApiError.ai_timeout()
    except openai.APIError as e:
        logger.warning("AI sign: AI_UPSTREAM_ERROR (%s)", type(e).__name__)
        raise ApiError.ai_upstream_error("Dịch vụ AI trả lỗi.")
    except ValueError:
        logger.warning("AI sign: AI_UPSTREAM_ERROR sai định dạng")
        raise ApiError.ai_upstream_error("AI trả dữ liệu sai định dạng.")

GLOSS_SENTENCE_SYSTEM_PROMPT = """Bạn viết câu nói cho người khiếm thính trong dự án SignBridge.
Đầu vào là chuỗi ký hiệu (glosses) mà điện thoại đã nhận diện, đúng thứ tự người dùng ký.

QUY TẮC BẮT BUỘC:
1. "spoken_sentence" chỉ diễn đạt đúng nghĩa các glosses, giữ thứ tự ý. Tối đa 40 từ.
2. Được thêm: lời chào, cảm ơn, kính ngữ (anh/chị/bạn/mình), từ nối, trợ từ (nhé, ạ, giúp mình), sắp lại trật tự cho đúng ngữ pháp.
3. KHÔNG thêm triệu chứng, món, giấy tờ, số lượng, giá, thời gian, tên sản phẩm hay yêu cầu không có trong glosses.
   Không đổi nghĩa, không làm mạnh/nhẹ ý người dùng.
4. Dùng CÂU_NHÂN_VIÊN_VỪA_NÓI để câu trả lời đúng mạch. Dùng THẺ_CÁ_NHÂN chỉ khi liên quan trực tiếp đến glosses.
5. Chỉ trả JSON: {"spoken_sentence": "..."}
"""


def _gloss_sentence_llm(client, glosses: Tuple[str, ...], context: str,
                        personal_chips: Tuple[str, ...], previous_incoming: Optional[str]) -> Dict[str, Any]:
    text = (f"GLOSSES: {json.dumps(list(glosses), ensure_ascii=False)}\n"
            f"NGỮ_CẢNH: {context}\n"
            f"CÂU_NHÂN_VIÊN_VỪA_NÓI: {previous_incoming or 'không có'}\n"
            f"THẺ_CÁ_NHÂN: {json.dumps(list(personal_chips), ensure_ascii=False)}")
    response = client.chat.completions.create(
        model=os.getenv("LLM_MODEL", LLM_MODEL).strip(),
        messages=[
            {"role": "system", "content": GLOSS_SENTENCE_SYSTEM_PROMPT},
            {"role": "user", "content": text}
        ],
        response_format={"type": "json_object"},
        temperature=0.0,
        max_tokens=100,
        timeout=float(os.getenv("AI_TIMEOUT_GLOSSES", "4"))
    )
    return json.loads(clean_json_text(response.choices[0].message.content or "{}"))


@functools.lru_cache(maxsize=256)
def _gloss_sentence_first_turn(model: str, glosses: Tuple[str, ...], context: str) -> Dict[str, Any]:
    """Cache trong RAM cho lượt không có ngữ cảnh hội thoại: cùng chuỗi ký hiệu → cùng câu (temperature 0).
    Chỉ chứa glosses + câu sinh ra; lỗi LLM không được cache."""
    return _gloss_sentence_llm(get_openai_client(), glosses, context, (), None)


def compose_from_glosses(glosses: List[str], context: str = "CUSTOM", personal_chips: Optional[List[str]] = None,
                         previous_incoming: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Ghép ký hiệu đã nhận diện trên thiết bị thành câu nói (mục 4.2a, 7.3 bước 2).
    Trả None khi chưa cấu hình LLM hoặc LLM lỗi → caller dùng câu dự phòng ghép từ chính glosses
    (không bịa thêm ý, nên không cần chặn như /api/sign)."""
    import openai

    client = get_openai_client()
    if not client:
        return None
    try:
        if not personal_chips and not previous_incoming:
            return _gloss_sentence_first_turn(os.getenv("LLM_MODEL", LLM_MODEL).strip(), tuple(glosses), context)
        return _gloss_sentence_llm(client, tuple(glosses), context, tuple(personal_chips or ()), previous_incoming)
    except openai.APITimeoutError:
        logger.warning("AI glosses: AI_TIMEOUT, dùng câu dự phòng")
    except openai.APIError as e:
        logger.warning("AI glosses: AI_UPSTREAM_ERROR (%s), dùng câu dự phòng", type(e).__name__)
    except ValueError:
        logger.warning("AI glosses: AI_UPSTREAM_ERROR sai định dạng, dùng câu dự phòng")
    return None


def suggest_smart_chips(context: str = "CUSTOM", recent_text: Optional[str] = None, existing_chips: Optional[List[str]] = None) -> List[str]:
    """
    AI tự động gợi ý 4-6 thẻ từ khóa ngắn mới dựa theo ngữ cảnh và câu nói vừa nghe.
    """
    client = get_openai_client()
    model = os.getenv("LLM_MODEL", LLM_MODEL).strip()

    fallback_map = {
        "CAFE": ["Trà đào", "Ít ngọt", "Không đá", "Mang về", "Thêm sữa", "Cà phê đen"],
        "PHARMACY": ["Hạ sốt", "Thuốc ngậm", "Dị ứng", "Uống trước ăn", "Một vỉ", "Hộp nhỏ"],
        "PUBLIC": ["Số thứ tự", "Căn cước công dân", "Hẹn ngày lấy", "Nộp tiền mặt", "Xác nhận"],
        "CUSTOM": ["Đi bộ", "Bao xa", "Gần đây", "Không hiểu", "Giúp mình", "Cảm ơn"]
    }
    default_chips = fallback_map.get(context, fallback_map["CUSTOM"])

    if not client:
        return default_chips

    existing_str = ", ".join(existing_chips or [])
    prompt = f"""Bạn là trợ lý gợi ý từ khóa giao tiếp cho người khiếm thính/câm trong dự án SignBridge.
Bối cảnh: {context}
Nội dung người nghe vừa nghe được: {recent_text or 'Không có'}
Các từ khóa đã có: {existing_str or 'Chưa có'}

Nhiệm vụ: Gợi ý 5 cụm từ khóa ngắn mới (mỗi cụm 1-3 từ, ví dụ: 'Ít cay', 'Mang về', 'Bao xa', 'Đi xe máy'...) mà người khiếm thính có thể cần dùng để phản hồi lại trong tình huống này.
Tuyệt đối không trùng với các từ khóa đã có.
Chỉ trả về 1 JSON:
{{"suggested_chips": ["...", "...", "...", "...", "..."]}}
"""
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
            max_tokens=100,
            timeout=3.0
        )
        content = clean_json_text(response.choices[0].message.content or "{}")
        data = json.loads(content)
        chips = data.get("suggested_chips", [])
        if isinstance(chips, list) and len(chips) > 0:
            return [str(c).strip() for c in chips if str(c).strip()][:6]
    except Exception as e:
        logger.warning(f"Lỗi suggest_smart_chips: {e}")

    return default_chips



