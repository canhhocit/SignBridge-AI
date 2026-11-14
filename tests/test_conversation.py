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


# ---------- /api/sign/glosses: ký hiệu nhận diện trên thiết bị (mục 4.2a) ----------

def test_device_glosses_high_confidence_in_vocabulary():
    out = conversation.check_device_glosses("PHARMACY", ["đau", " ĐẦU "], [0.95, 0.9])
    assert out["glosses"] == ["ĐAU", "ĐẦU"]
    assert out["confidence"] == 0.9
    assert out["needConfirm"] is False
    assert 3 <= len(out["suggestedChips"]) <= 6


def test_device_gloss_low_confidence_becomes_unknown_but_is_suggested_first():
    out = conversation.check_device_glosses("PHARMACY", ["SỐT", "THUỐC"], [0.4, 0.99])
    assert out["glosses"] == ["UNKNOWN", "THUỐC"]
    assert out["needConfirm"] is True
    assert out["confidence"] < conversation.CONFIDENCE_THRESHOLD
    assert out["suggestedChips"][:2] == ["Sốt", "Thuốc"]


def test_device_gloss_outside_vocabulary_is_unknown_and_not_suggested():
    out = conversation.check_device_glosses("CAFE", ["BIA", "CÀ PHÊ"], [0.99, 0.99])
    assert out["glosses"] == ["UNKNOWN", "CÀ PHÊ"]
    assert out["needConfirm"] is True
    assert "Bia" not in out["suggestedChips"]


def test_device_glosses_empty_is_no_sign_detected():
    with pytest.raises(ApiError) as e:
        conversation.check_device_glosses("CAFE", [], [])
    assert (e.value.status, e.value.code) == (422, "NO_SIGN_DETECTED")


def test_model_labels_extend_vocabulary_and_keep_original_text(vsl_labels_file):
    vsl_labels_file(["đau bụng", "hiệu thuốc", "1000 (một nghìn)"])
    out = conversation.check_device_glosses("PHARMACY", ["Đau bụng", "hiệu thuốc"], [0.9, 0.8])
    assert out["glosses"] == ["ĐAU BỤNG", "HIỆU THUỐC"]
    assert out["needConfirm"] is False
    assert out["suggestedChips"][:2] == ["đau bụng", "hiệu thuốc"]
    assert conversation.gloss_template_sentence(out["glosses"]) == "Đau bụng, hiệu thuốc."


def test_model_labels_accept_dict_format(vsl_labels_file):
    vsl_labels_file({"chào": 0, "bao nhiêu": 1})
    assert set(conversation.vsl_labels()) == {"CHÀO", "BAO NHIÊU"}


def test_missing_or_broken_labels_file_falls_back_to_spec_vocabulary(vsl_labels_file):
    path = vsl_labels_file([])
    path.write_text("{khong hop le", encoding="utf-8")
    conversation._load_vsl_labels.cache_clear()
    assert conversation.vsl_labels() == {}
    assert conversation.check_device_glosses("CAFE", ["ĐÁ"], [0.9])["glosses"] == ["ĐÁ"]


def test_gloss_sentence_passes_through():
    assert conversation.check_gloss_sentence(
        {"spoken_sentence": " Chào bạn, mình bị đau đầu. "}, ["ĐAU", "ĐẦU"]) == "Chào bạn, mình bị đau đầu."


@pytest.mark.parametrize("out", [
    None,
    {},
    {"spoken_sentence": ""},
    {"spoken_sentence": 123},
    {"spoken_sentence": "Mình đau đầu 2 ngày rồi."},      # bịa thêm số
    {"spoken_sentence": "chữ " * 41},                       # quá 40 từ
])
def test_bad_gloss_sentence_falls_back_to_template(out):
    assert conversation.check_gloss_sentence(out, ["ĐAU", "ĐẦU"]) == "Đau, Đầu."


def test_gloss_sentence_may_repeat_numbers_from_glosses(vsl_labels_file):
    vsl_labels_file(["1000 (một nghìn)"])
    sentence = "Mình muốn hỏi về 1000 ạ."
    assert conversation.check_gloss_sentence({"spoken_sentence": sentence}, ["1000 (MỘT NGHÌN)"]) == sentence


def test_llm_client_is_reused_and_never_retries(monkeypatch):
    import llm_service
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_BASE_URL", "http://ai.local/v1")
    llm_service._openai_client.cache_clear()
    try:
        first, second = llm_service.get_openai_client(), llm_service.get_openai_client()
        assert first is second
        assert first.max_retries == 0
    finally:
        llm_service._openai_client.cache_clear()
