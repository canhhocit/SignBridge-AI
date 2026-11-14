"""Endpoint + validate + mã lỗi (port từ ApiControllerTest / RequestLoggingFilterTest của bản Spring)."""
import json
import logging

import httpx
import openai
import pytest

import llm_service

JPEG = b"\xff\xd8\xff\xe0" + b"0" * 100


def frames(n, content_type="image/jpeg", size=None):
    body = JPEG if size is None else b"0" * size
    return [("frames", (f"f{i}.jpg", body, content_type)) for i in range(n)]


def audio(content=b"m4a-bytes", content_type="audio/mp4"):
    return {"audio": ("a.m4a", content, content_type)}


def assert_error(res, status, code):
    assert res.status_code == status, res.text
    assert res.json()["error"]["code"] == code
    assert res.json()["error"]["message"]


# ---------- health / chung ----------

def test_health(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "UP"


def test_index_page_returns_html(client):
    res = client.get("/")
    assert res.status_code == 200
    assert "SignBridge AI Studio" in res.text
    assert "text/html" in res.headers.get("content-type", "")


def test_unknown_path_is_not_server_error(client):
    assert_error(client.get("/khong-co"), 404, "NOT_FOUND")
    assert_error(client.get("/favicon.ico"), 404, "NOT_FOUND")


def test_openapi_lists_all_endpoints(client):
    paths = client.get("/openapi.json").json()["paths"]
    for p in ("/api/health", "/api/sign", "/api/sign/glosses", "/api/expand", "/api/summarize"):
        assert p in paths


def test_request_over_6mb_is_rejected(client):
    res = client.post("/api/summarize", data={"context": "CAFE"},
                      files=audio(b"0" * (6 * 1024 * 1024 + 1)))
    assert_error(res, 413, "PAYLOAD_TOO_LARGE")


# ---------- /api/sign ----------

def test_sign_returns_sentence(client):
    res = client.post("/api/sign", data={"context": "PHARMACY", "personalChips": '["Dị ứng penicillin"]'},
                      files=frames(4))
    assert res.status_code == 200
    body = res.json()
    assert body["glosses"] == ["ĐAU", "ĐẦU", "MUA", "THUỐC"]
    assert body["confidence"] >= 0.7
    assert body["spoken_sentence"]
    assert body["suggestedChips"]


def test_sign_low_confidence_has_empty_sentence(client):
    res = client.post("/api/sign", data={"context": "PHARMACY", "personalChips": '["MOCK_LOW"]'},
                      files=frames(8))
    assert res.status_code == 200
    assert "UNKNOWN" in res.json()["glosses"]
    assert res.json()["spoken_sentence"] == ""
    assert res.json()["confidence"] < 0.7


@pytest.mark.parametrize("n", [3, 5, 20])
def test_sign_rejects_wrong_frame_count(client, n):
    assert_error(client.post("/api/sign", data={"context": "CAFE"}, files=frames(n)), 400, "INVALID_REQUEST")


def test_sign_rejects_missing_frames(client):
    assert_error(client.post("/api/sign", data={"context": "CAFE"}), 400, "INVALID_REQUEST")


def test_sign_rejects_unknown_context(client):
    assert_error(client.post("/api/sign", data={"context": "BAR"}, files=frames(4)), 400, "INVALID_REQUEST")


def test_sign_rejects_png(client):
    res = client.post("/api/sign", data={"context": "CAFE"}, files=frames(4, content_type="image/png"))
    assert_error(res, 415, "UNSUPPORTED_MEDIA_TYPE")


def test_sign_rejects_frame_over_250kb(client):
    res = client.post("/api/sign", data={"context": "CAFE"}, files=frames(4, size=250 * 1024 + 1))
    assert_error(res, 413, "PAYLOAD_TOO_LARGE")


@pytest.mark.parametrize("chips", ["khong-phai-json", '{"a": 1}', "[1, 2]", json.dumps(["x"] * 21)])
def test_sign_rejects_bad_personal_chips(client, chips):
    res = client.post("/api/sign", data={"context": "CAFE", "personalChips": chips}, files=frames(4))
    assert_error(res, 400, "INVALID_REQUEST")


def test_sign_rejects_long_previous_incoming(client):
    res = client.post("/api/sign", data={"context": "CAFE", "previousIncoming": "a" * 301}, files=frames(4))
    assert_error(res, 400, "INVALID_REQUEST")


def test_sign_all_empty_frames_is_no_sign_detected(client):
    res = client.post("/api/sign", data={"context": "CAFE"}, files=frames(4, size=0))
    assert_error(res, 422, "NO_SIGN_DETECTED")


class _FakeCompletions:
    def __init__(self, behaviour):
        self.behaviour = behaviour

    def create(self, **_kwargs):
        if isinstance(self.behaviour, Exception):
            raise self.behaviour
        msg = type("M", (), {"content": self.behaviour})
        choice = type("C", (), {"message": msg})
        return type("R", (), {"choices": [choice]})


def _fake_client(behaviour):
    chat = type("Chat", (), {"completions": _FakeCompletions(behaviour)})
    return type("Client", (), {"chat": chat})


_REQ = httpx.Request("POST", "http://ai.local")


@pytest.mark.parametrize("behaviour,status,code", [
    (openai.APITimeoutError(request=_REQ), 504, "AI_TIMEOUT"),
    (openai.APIConnectionError(request=_REQ), 502, "AI_UPSTREAM_ERROR"),
    ("khong phai json", 502, "AI_UPSTREAM_ERROR"),
    ('{"glosses": ["ĐAU"]}', 502, "AI_UPSTREAM_ERROR"),
])
def test_sign_real_mode_errors_do_not_fabricate_sentence(client, monkeypatch, behaviour, status, code):
    monkeypatch.setattr(llm_service, "get_openai_client", lambda: _fake_client(behaviour))
    assert_error(client.post("/api/sign", data={"context": "PHARMACY"}, files=frames(4)), status, code)


def test_sign_real_mode_gloss_outside_vocabulary_becomes_unknown(client, monkeypatch):
    out = json.dumps({"glosses": ["cà phê", "BIA"], "confidence": 0.95,
                      "spoken_sentence": "Cho mình cà phê và bia.", "suggestedChips": ["Cà phê", "Bia", "Đá"]},
                     ensure_ascii=False)
    monkeypatch.setattr(llm_service, "get_openai_client", lambda: _fake_client(out))
    res = client.post("/api/sign", data={"context": "CAFE"}, files=frames(4))
    assert res.status_code == 200
    assert res.json()["glosses"] == ["CÀ PHÊ", "UNKNOWN"]
    assert res.json()["spoken_sentence"] == ""


# ---------- /api/expand ----------

def test_expand_returns_sentence(client):
    res = client.post("/api/expand", json={"context": "PHARMACY", "chips": ["Đau đầu", "Uống sau ăn"]})
    assert res.status_code == 200
    assert res.json()["spoken_sentence"]


@pytest.mark.parametrize("body", [
    {"context": "PHARMACY", "chips": ["a", "b", "c", "d", "e", "f"]},
    {"context": "PHARMACY", "chips": []},
    {"context": "PHARMACY", "chips": ["   "]},
    {"context": "PHARMACY", "chips": ["x" * 51]},
    {"context": "BAR", "chips": ["a"]},
    {"context": "PHARMACY", "chips": ["a"], "previousIncoming": "x" * 301},
    {"context": "PHARMACY"},
])
def test_expand_rejects_invalid_body(client, body):
    assert_error(client.post("/api/expand", json=body), 400, "INVALID_REQUEST")


def test_expand_rejects_malformed_json(client):
    res = client.post("/api/expand", content=b"{khong hop le", headers={"content-type": "application/json"})
    assert_error(res, 400, "INVALID_REQUEST")


# ---------- /api/summarize ----------

def test_summarize_returns_summary(client, fake_stt):
    res = client.post("/api/summarize", data={"context": "PHARMACY"}, files=audio())
    assert res.status_code == 200
    body = res.json()
    assert body["transcript"] == fake_stt["text"]
    assert body["summary"]
    assert len(body["quickReplies"]) == 3
    assert body["iconCode"]
    for h in body["highlights"]:
        assert h["text"] in body["summary"]
    assert "35" in body["summary"]


def test_summarize_rejects_non_audio(client, fake_stt):
    res = client.post("/api/summarize", data={"context": "PHARMACY"}, files=audio(content_type="image/png"))
    assert_error(res, 415, "UNSUPPORTED_MEDIA_TYPE")


def test_summarize_accepts_m4a_with_params(client, fake_stt):
    res = client.post("/api/summarize", data={"context": "CAFE"}, files=audio(content_type="audio/x-m4a"))
    assert res.status_code == 200


def test_summarize_rejects_audio_over_2mb(client, fake_stt):
    res = client.post("/api/summarize", data={"context": "PHARMACY"}, files=audio(b"0" * (2 * 1024 * 1024 + 1)))
    assert_error(res, 413, "PAYLOAD_TOO_LARGE")


def test_summarize_empty_audio_is_no_speech(client, fake_stt):
    assert_error(client.post("/api/summarize", data={"context": "CAFE"}, files=audio(b"")), 422, "NO_SPEECH_DETECTED")


def test_summarize_silent_audio_is_no_speech(client, fake_stt):
    fake_stt["text"] = ""
    assert_error(client.post("/api/summarize", data={"context": "CAFE"}, files=audio()), 422, "NO_SPEECH_DETECTED")


def test_summarize_stt_failure_is_upstream_error(client, fake_stt):
    fake_stt["error"] = RuntimeError("decode failed")
    assert_error(client.post("/api/summarize", data={"context": "CAFE"}, files=audio()), 502, "AI_UPSTREAM_ERROR")


def test_summarize_rejects_unknown_context(client, fake_stt):
    assert_error(client.post("/api/summarize", data={"context": "BAR"}, files=audio()), 400, "INVALID_REQUEST")


def test_summarize_rejects_long_previous_outgoing(client, fake_stt):
    res = client.post("/api/summarize", data={"context": "CAFE", "previousOutgoing": "x" * 301}, files=audio())
    assert_error(res, 400, "INVALID_REQUEST")


def test_summarize_rejects_missing_audio(client):
    assert_error(client.post("/api/summarize", data={"context": "CAFE"}), 400, "INVALID_REQUEST")


def test_summarize_text_endpoint(client):
    res = client.post("/api/v1/ai/summarize", json={"context": "CAFE", "transcript": "Của em hết 45 nghìn nhé"})
    assert res.status_code == 200
    assert "45" in res.json()["summary"]


# ---------- /api/chips ----------

def test_chips_crud_is_isolated_per_user(client):
    created = client.post("/api/chips", json={"user_id": "u1", "text": "Dị ứng penicillin", "context": "PHARMACY"})
    assert created.status_code == 200, created.text
    chip_id = created.json()["id"]

    mine = [c["text"] for c in client.get("/api/chips", params={"user_id": "u1"}).json()]
    other = [c["text"] for c in client.get("/api/chips", params={"user_id": "u2"}).json()]
    assert "Dị ứng penicillin" in mine
    assert "Dị ứng penicillin" not in other

    assert client.delete(f"/api/chips/{chip_id}", params={"user_id": "u2"}).json()["success"] is False
    assert client.delete(f"/api/chips/{chip_id}", params={"user_id": "u1"}).json()["success"] is True


def test_chips_update_endpoint(client):
    created = client.post("/api/v1/chips", json={"text": "Ít ngọt", "context": "CAFE"}, headers={"X-User-Id": "u1"}).json()
    chip_id = created["id"]

    # u2 không được sửa thẻ của u1
    assert_error(
        client.put(f"/api/v1/chips/{chip_id}", json={"text": "Nhiều ngọt"}, headers={"X-User-Id": "u2"}),
        404, "NOT_FOUND"
    )

    # u1 sửa thành công
    res = client.put(f"/api/v1/chips/{chip_id}", json={"text": "70% ngọt"}, headers={"X-User-Id": "u1"})
    assert res.status_code == 200
    assert res.json()["text"] == "70% ngọt"

    # kiểm tra danh sách đã đổi
    mine = [c["text"] for c in client.get("/api/v1/chips", params={"context": "CAFE"}, headers={"X-User-Id": "u1"}).json()]
    assert "70% ngọt" in mine
    assert "Ít ngọt" not in mine

    # body rỗng -> 400
    assert_error(client.put(f"/api/v1/chips/{chip_id}", json={}, headers={"X-User-Id": "u1"}), 400, "INVALID_REQUEST")


def test_chips_v1_with_user_header_and_reset(client):
    h = {"X-User-Id": "hdr-user"}
    assert client.post("/api/v1/chips", json={"text": "Không đường", "context": "CAFE"}, headers=h).status_code == 200
    texts = [c["text"] for c in client.get("/api/v1/chips", params={"context": "CAFE"}, headers=h).json()]
    assert "Không đường" in texts

    assert client.post("/api/v1/chips/reset", headers=h).json()["success"] is True
    after = client.get("/api/v1/chips", params={"context": "CAFE"}, headers=h).json()
    assert "Không đường" not in [c["text"] for c in after]
    assert all(c["is_system"] for c in after)


def test_chips_rejects_long_user_header(client):
    assert_error(client.get("/api/v1/chips", headers={"X-User-Id": "u" * 65}), 400, "INVALID_REQUEST")


def test_chips_rejects_unknown_context(client):
    assert_error(client.get("/api/chips", params={"context": "BAR"}), 400, "INVALID_REQUEST")


def test_suggest_chips_mock_mode(client):
    res = client.post("/api/v1/ai/suggest-chips", json={"context": "CAFE", "recentText": "Ly này 30 nghìn"})
    assert res.status_code == 200
    assert res.json()["suggestedChips"]


def test_suggest_chips_rejects_bad_context(client):
    assert_error(client.post("/api/ai/suggest-chips", json={"context": "BAR"}), 400, "INVALID_REQUEST")


def test_health_reports_database_engine(client):
    assert client.get("/api/health").json()["database"] == "SQLite"


@pytest.mark.parametrize("body", [
    {"text": "x" * 51},
    {"text": "   "},
    {"text": "ok", "context": "BAR"},
    {"text": "ok", "user_id": "u" * 65},
])
def test_chips_rejects_invalid_body(client, body):
    assert_error(client.post("/api/chips", json=body), 400, "INVALID_REQUEST")


# ---------- log request ----------

def test_request_log_has_metadata_and_error_code_but_no_payload(client, caplog):
    secret = "NOI-DUNG-NGUOI-DUNG"
    with caplog.at_level(logging.INFO, logger="SignBridge.Request"):
        client.post("/api/sign", data={"context": "CAFE", "previousIncoming": secret}, files=frames(3))
    lines = [r.getMessage() for r in caplog.records if r.name == "SignBridge.Request"]
    assert any("POST /api/sign status=400" in l and "error=INVALID_REQUEST" in l for l in lines)
    assert all(secret not in r.getMessage() for r in caplog.records)


def test_request_log_uses_forwarded_ip(client, caplog):
    with caplog.at_level(logging.INFO, logger="SignBridge.Request"):
        client.get("/api/health", headers={"X-Forwarded-For": "203.0.113.7, 10.0.0.1"})
    assert any("ip=203.0.113.7" in r.getMessage() for r in caplog.records)


# ---------- /api/sign/glosses (mục 4.2a, luồng Hybrid) ----------

def glosses_body(glosses=("ĐAU", "ĐẦU"), confidences=(0.95, 0.9), **extra):
    return {"context": "PHARMACY", "glosses": list(glosses), "confidences": list(confidences), **extra}


class _CountingClient:
    """Client LLM giả đếm số lần gọi; behaviour là chuỗi JSON trả về hoặc exception."""
    def __init__(self, behaviour):
        self.calls = 0
        outer = self

        class _Completions:
            def create(self, **_kwargs):
                outer.calls += 1
                return _FakeCompletions(behaviour).create()
        self.chat = type("Chat", (), {"completions": _Completions()})


@pytest.fixture
def fake_llm(monkeypatch):
    llm_service._gloss_sentence_first_turn.cache_clear()

    def install(behaviour):
        fake = _CountingClient(behaviour)
        monkeypatch.setattr(llm_service, "get_openai_client", lambda: fake)
        return fake

    yield install
    llm_service._gloss_sentence_first_turn.cache_clear()


def test_glosses_mock_mode_returns_template_sentence(client):
    res = client.post("/api/sign/glosses", json=glosses_body())
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["glosses"] == ["ĐAU", "ĐẦU"]
    assert body["confidence"] == 0.9
    assert body["spoken_sentence"] == "Đau, Đầu."
    assert 3 <= len(body["suggestedChips"]) <= 6


def test_glosses_v1_alias(client):
    assert client.post("/api/v1/sign/glosses", json=glosses_body()).status_code == 200


def test_glosses_low_confidence_skips_llm_and_clears_sentence(client, fake_llm):
    llm = fake_llm('{"spoken_sentence": "không được dùng"}')
    res = client.post("/api/sign/glosses", json=glosses_body(confidences=(0.95, 0.3)))
    assert res.status_code == 200
    assert res.json()["glosses"] == ["ĐAU", "UNKNOWN"]
    assert res.json()["spoken_sentence"] == ""
    assert res.json()["suggestedChips"][0] == "Đầu"
    assert llm.calls == 0


def test_glosses_real_mode_uses_llm_sentence(client, fake_llm):
    llm = fake_llm('{"spoken_sentence": "Chào bạn, mình bị đau đầu."}')
    res = client.post("/api/sign/glosses", json=glosses_body())
    assert res.json()["spoken_sentence"] == "Chào bạn, mình bị đau đầu."
    assert llm.calls == 1


def test_glosses_first_turn_is_cached_but_contextual_turn_is_not(client, fake_llm):
    llm = fake_llm('{"spoken_sentence": "Chào bạn, mình bị đau đầu."}')
    for _ in range(3):
        client.post("/api/sign/glosses", json=glosses_body())
    assert llm.calls == 1
    for _ in range(2):
        client.post("/api/sign/glosses", json=glosses_body(previousIncoming="Bạn đau lâu chưa?"))
    assert llm.calls == 3


def test_glosses_llm_adding_number_falls_back_to_template(client, fake_llm):
    fake_llm('{"spoken_sentence": "Mình bị đau đầu 3 ngày rồi."}')
    assert client.post("/api/sign/glosses", json=glosses_body()).json()["spoken_sentence"] == "Đau, Đầu."


@pytest.mark.parametrize("behaviour", [
    openai.APITimeoutError(request=_REQ),
    openai.APIConnectionError(request=_REQ),
    "khong phai json",
])
def test_glosses_llm_failure_falls_back_to_template_and_is_not_cached(client, fake_llm, behaviour):
    llm = fake_llm(behaviour)
    for _ in range(2):
        res = client.post("/api/sign/glosses", json=glosses_body())
        assert res.status_code == 200
        assert res.json()["spoken_sentence"] == "Đau, Đầu."
    assert llm.calls == 2


def test_glosses_accept_model_labels(client, vsl_labels_file):
    vsl_labels_file(["đau bụng", "hiệu thuốc"])
    res = client.post("/api/sign/glosses", json=glosses_body(glosses=("đau bụng", "hiệu thuốc")))
    assert res.json()["glosses"] == ["ĐAU BỤNG", "HIỆU THUỐC"]
    assert res.json()["spoken_sentence"] == "Đau bụng, hiệu thuốc."
    assert client.get("/api/health").json()["vsl_labels"] == 2


def test_glosses_empty_is_no_sign_detected(client):
    assert_error(client.post("/api/sign/glosses", json=glosses_body(glosses=(), confidences=())),
                 422, "NO_SIGN_DETECTED")


@pytest.mark.parametrize("body", [
    glosses_body(confidences=(0.9,)),                                   # lệch số phần tử
    glosses_body(glosses=["ĐAU"] * 11, confidences=[0.9] * 11),         # > 10 ký hiệu
    glosses_body(confidences=(0.9, 1.5)),
    glosses_body(confidences=(0.9, -0.1)),
    glosses_body(glosses=("ĐAU", "   ")),
    glosses_body(glosses=("ĐAU", "x" * 51)),
    glosses_body(previousIncoming="x" * 301),
    glosses_body(personalChips=["a"] * 21),
    {**glosses_body(), "context": "BAR"},
    {k: v for k, v in glosses_body().items() if k != "context"},
    {k: v for k, v in glosses_body().items() if k != "confidences"},
])
def test_glosses_rejects_invalid_body(client, body):
    assert_error(client.post("/api/sign/glosses", json=body), 400, "INVALID_REQUEST")


def test_glosses_log_has_no_payload(client, caplog):
    secret = "NOI-DUNG-NGUOI-DUNG"
    with caplog.at_level(logging.INFO):
        client.post("/api/sign/glosses", json=glosses_body(previousIncoming=secret))
    assert any("POST /api/sign/glosses status=200" in r.getMessage() for r in caplog.records)
    assert all(secret not in r.getMessage() for r in caplog.records)
