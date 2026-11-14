"""Cấu hình chung: SQLite tạm, không nạp PhoWhisper, không gọi LLM thật (chế độ mock)."""
import os
import sys
import tempfile

_TMP = tempfile.mkdtemp(prefix="signbridge-test-")
# Đặt TRƯỚC khi import app: load_dotenv() không ghi đè biến đã có → .env máy dev không lọt vào test
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(_TMP, "test.db").replace("\\", "/")
os.environ["WHISPER_PRELOAD"] = "0"
os.environ["LLM_API_KEY"] = ""

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient

import app as app_module


@pytest.fixture
def client():
    return TestClient(app_module.app, raise_server_exceptions=False)


@pytest.fixture
def fake_stt(monkeypatch):
    """Thay PhoWhisper bằng transcript cố định; trả hàm để đổi transcript/ném lỗi."""
    state = {"text": "Dạ bạn dùng Panadol xanh nha, uống 1 viên sau ăn, ngày 2 lần, hộp này giá 35 nghìn.", "error": None}

    def fake(_audio, language="vi", context="CUSTOM"):
        if state["error"]:
            raise state["error"]
        return state["text"], 3.0, language, 1.0

    monkeypatch.setattr(app_module, "run_transcribe", fake)
    return state
