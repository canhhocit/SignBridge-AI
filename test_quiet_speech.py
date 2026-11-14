import os
import json
from dotenv import load_dotenv
load_dotenv()

from llm_service import summarize_text

def test_semantic_recovery_and_warning():
    print("=== TEST 1: Khôi phục ngữ nghĩa khi nói nhỏ / nuốt chữ ===")
    res1 = summarize_text(
        transcript="...băm nhăm... quét mã kia...",
        context="CAFE",
        previous_outgoing="Cho em hỏi ly trà sữa này bao nhiêu tiền ạ?"
    )
    print("Kết quả 1:")
    print(" - Summary:", res1.get("summary"))
    print(" - Icon:", res1.get("iconCode"))
    print(" - Highlights:", res1.get("highlights"))
    print(" - QuickReplies:", res1.get("quickReplies"))
    print(" - SuggestedChips:", res1.get("suggestedChips"))

    print("\n=== TEST 2: Xử lý khi nói quá nhỏ / không rõ chữ (Uncertainty Fallback) ===")
    res2 = summarize_text(
        transcript="ừ...",
        context="CUSTOM",
        previous_outgoing=None
    )
    print("Kết quả 2:")
    print(" - Summary:", res2.get("summary"))
    print(" - Icon:", res2.get("iconCode"))
    print(" - Highlights:", res2.get("highlights"))
    print(" - QuickReplies:", res2.get("quickReplies"))
    print(" - SuggestedChips:", res2.get("suggestedChips"))

if __name__ == "__main__":
    test_semantic_recovery_and_warning()
