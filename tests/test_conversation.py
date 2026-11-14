"""Kiểm tra lại output AI (port từ ConversationServiceTest của bản Spring) — unit, không cần HTTP."""
import unicodedata

import pytest

import conversation
from errors import ApiError
from llm_service import verify_and_protect_numbers


def sign_out(glosses, confidence=0.9, sentence="Câu nói.", chips=("a", "b", "c")):
    return {"glosses": list(glosses), "confidence": confidence, "spoken_sentence": sentence,
            "suggestedChips": list(chips)}


def test_gloss_outside_vocabulary_becomes_unknown_and_sentence_is_cleared():
    out = conversation.check_sign_output("PHARMACY", sign_out(["ĐAU", "BIA"]))
    assert out["glosses"] == ["ĐAU", "UNKNOWN"]
    assert out["spoken_sentence"] == ""
    assert out["confidence"] < conversation.CONFIDENCE_THRESHOLD


def test_gloss_is_normalized():
    nfd = unicodedata.normalize("NFD", "  cà   phê ")
    out = conversation.check_sign_output("CAFE", sign_out([nfd, "đá"]))
    assert out["glosses"] == ["CÀ PHÊ", "ĐÁ"]
    assert out["spoken_sentence"] == "Câu nói."


def test_gloss_from_other_context_is_rejected():
    out = conversation.check_sign_output("PHARMACY", sign_out(["CÀ PHÊ"]))
    assert out["glosses"] == ["UNKNOWN"]


def test_custom_context_allows_all_groups():
    allowed = conversation.allowed_glosses("CUSTOM")
    for g in ("THUỐC", "CÀ PHÊ", "GIẤY TỜ", "XIN CHÀO", "NGÀY"):
        assert g in allowed
    assert allowed.count("MUA") == 1


def test_low_confidence_clears_sentence():
    out = conversation.check_sign_output("PHARMACY", sign_out(["ĐAU", "ĐẦU"], confidence=0.5))
    assert out["spoken_sentence"] == ""
    assert out["glosses"] == ["ĐAU", "ĐẦU"]


def test_empty_glosses_is_no_sign_detected():
    with pytest.raises(ApiError) as e:
        conversation.check_sign_output("PHARMACY", sign_out([]))
    assert (e.value.status, e.value.code) == (422, "NO_SIGN_DETECTED")


@pytest.mark.parametrize("bad", [None, [], {"glosses": ["ĐAU"]}, sign_out(["ĐAU"], confidence="cao")])
def test_missing_or_bad_sign_fields_is_upstream_error(bad):
    with pytest.raises(ApiError) as e:
        conversation.check_sign_output("PHARMACY", bad)
    assert (e.value.status, e.value.code) == (502, "AI_UPSTREAM_ERROR")


def summary_out(**kw):
    base = {"summary": "Panadol • 1 viên • 35.000đ",
            "highlights": [{"type": "DOSAGE", "text": "1 viên"}, {"type": "PRICE", "text": "50.000đ"}],
            "iconCode": "PILL", "quickReplies": ["a", "b", "c"]}
    base.update(kw)
    return base


def test_highlight_not_in_summary_is_dropped():
    out = conversation.check_summarize_output(summary_out())
    assert out["highlights"] == [{"type": "DOSAGE", "text": "1 viên"}]


@pytest.mark.parametrize("kw", [{"quickReplies": ["a", "b"]}, {"summary": ""}, {"iconCode": None}])
def test_bad_summary_schema_is_upstream_error(kw):
    with pytest.raises(ApiError) as e:
        conversation.check_summarize_output(summary_out(**kw))
    assert e.value.code == "AI_UPSTREAM_ERROR"


def test_blank_expand_is_upstream_error():
    with pytest.raises(ApiError) as e:
        conversation.check_expand_output({"spoken_sentence": "  "})
    assert e.value.code == "AI_UPSTREAM_ERROR"


def test_expand_passes_through():
    assert conversation.check_expand_output({"spoken_sentence": " Chào bạn. "}) == {"spoken_sentence": "Chào bạn."}


def test_guardrail_snaps_highlight_to_exact_summary_text():
    data = verify_and_protect_numbers("Giá 35 Nghìn ạ", {
        "summary": "Giá 35 Nghìn",
        "highlights": [{"type": "PRICE", "text": "35 nghìn"}],
        "iconCode": "MONEY", "quickReplies": ["a", "b", "c"],
    })
    assert data["highlights"] == [{"type": "PRICE", "text": "35 Nghìn"}]


def test_guardrail_keeps_numbers_missing_from_summary():
    data = verify_and_protect_numbers("Quầy số 3, chờ 15 phút", {
        "summary": "Đến quầy", "highlights": [], "iconCode": "XYZ", "quickReplies": []})
    assert "15 phút" in data["summary"]
    assert data["iconCode"] == "INFO"
    assert len(data["quickReplies"]) == 3
