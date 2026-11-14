import os
import uuid
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy import create_engine, Column, String, Boolean, Integer, DateTime, ForeignKey, Text, Index
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("SignBridge.DB")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/signbridge")
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)


# Tạo engine kết nối với cơ chế tự động fallback sang SQLite nếu PostgreSQL chưa sẵn sàng
try:
    if DATABASE_URL.startswith("sqlite"):
        # FastAPI chạy endpoint sync trên threadpool → SQLite cần tắt check_same_thread
        engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
    else:
        engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=10, max_overflow=20)
    # Test kết nối
    with engine.connect() as conn:
        logger.info("[+] Đã kết nối thành công tới PostgreSQL Database!")
except Exception as e:
    logger.warning(f"[-] Không thể kết nối tới PostgreSQL ({e}). Đang chuyển sang SQLite local fallback...")
    local_sqlite_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    os.makedirs(local_sqlite_dir, exist_ok=True)
    DATABASE_URL = f"sqlite:///{os.path.join(local_sqlite_dir, 'signbridge_local.db')}"
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ----------------- Database Models -----------------

class User(Base):
    __tablename__ = "users"
    id = Column(String(64), primary_key=True, index=True)  # device_uuid hoặc user_id
    name = Column(String(100), default="Người dùng")
    created_at = Column(DateTime, default=datetime.utcnow)

class QuickChip(Base):
    __tablename__ = "quick_chips"
    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(64), index=True, nullable=False) # 'SYSTEM' hoặc id cụ thể của user
    text = Column(String(100), nullable=False)
    context = Column(String(20), default="CUSTOM", index=True) # CAFE, PHARMACY, PUBLIC, CUSTOM
    is_system = Column(Boolean, default=False, index=True)      # True: thẻ mẫu chung, False: thẻ người dùng tạo
    usage_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

class ConversationSession(Base):
    __tablename__ = "conversation_sessions"
    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(64), index=True, nullable=False)
    context = Column(String(20), default="CUSTOM")
    created_at = Column(DateTime, default=datetime.utcnow)

class MessageTurn(Base):
    __tablename__ = "message_turns"
    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(64), ForeignKey("conversation_sessions.id", ondelete="CASCADE"), index=True)
    sender_type = Column(String(20), nullable=False) # 'HEARING_PERSON' hoặc 'DEAF_PERSON'
    raw_text = Column(Text, nullable=True)
    summary_text = Column(Text, nullable=True)
    icon_code = Column(String(20), default="INFO")
    created_at = Column(DateTime, default=datetime.utcnow)

# ----------------- Hệ thống Thẻ Mẫu Ban Đầu -----------------

SYSTEM_PRESET_CHIPS = [
    # Quán ăn / Cà phê (CAFE)
    {"text": "Trà sữa trân châu", "context": "CAFE"},
    {"text": "Ít đường", "context": "CAFE"},
    {"text": "50% đá", "context": "CAFE"},
    {"text": "Cà phê đá", "context": "CAFE"},
    {"text": "Mang đi", "context": "CAFE"},
    {"text": "Bao nhiêu tiền", "context": "CAFE"},
    {"text": "Chuyển khoản QR", "context": "CAFE"},

    # Hiệu thuốc / Bệnh viện (PHARMACY)
    {"text": "Panadol giảm đau", "context": "PHARMACY"},
    {"text": "Uống sau ăn", "context": "PHARMACY"},
    {"text": "Ngày 2 lần", "context": "PHARMACY"},
    {"text": "Đau đầu", "context": "PHARMACY"},
    {"text": "Đau bụng", "context": "PHARMACY"},
    {"text": "Bị sốt", "context": "PHARMACY"},
    {"text": "Lấy 1 hộp", "context": "PHARMACY"},

    # Hành chính công (PUBLIC)
    {"text": "Nộp hồ sơ", "context": "PUBLIC"},
    {"text": "Giấy tờ tùy thân", "context": "PUBLIC"},
    {"text": "Căn cước công dân", "context": "PUBLIC"},
    {"text": "Quầy số mấy", "context": "PUBLIC"},
    {"text": "Lệ phí bao nhiêu", "context": "PUBLIC"},

    # Tự do / Hỏi đường / Chung (CUSTOM)
    {"text": "Cho hỏi đường ra chợ", "context": "CUSTOM"},
    {"text": "Đi bộ có xa không", "context": "CUSTOM"},
    {"text": "Cảm ơn bạn", "context": "CUSTOM"},
    {"text": "Xin chào", "context": "CUSTOM"}
]

def init_db():
    """Khởi tạo toàn bộ các bảng trong PostgreSQL và nạp thẻ hệ thống mặc định"""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # Kiểm tra xem đã có thẻ hệ thống nào chưa
        system_chips_count = db.query(QuickChip).filter(QuickChip.is_system == True).count()
        if system_chips_count == 0:
            logger.info("[*] Đang nạp bộ thẻ mẫu hệ thống ban đầu vào PostgreSQL...")
            for item in SYSTEM_PRESET_CHIPS:
                chip = QuickChip(
                    id=str(uuid.uuid4()),
                    user_id="SYSTEM",
                    text=item["text"],
                    context=item["context"],
                    is_system=True,
                    usage_count=0
                )
                db.add(chip)
            db.commit()
            logger.info(f"[+] Đã nạp thành công {len(SYSTEM_PRESET_CHIPS)} thẻ mẫu hệ thống!")
    except Exception as e:
        db.rollback()
        logger.error(f"[-] Lỗi nạp dữ liệu ban đầu: {e}")
    finally:
        db.close()

# ----------------- CRUD Service Functions -----------------

def get_chips_for_user(user_id: str, context: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Lấy danh sách thẻ theo cơ chế cách ly:
    Trả về = Thẻ Hệ Thống (SYSTEM) + Thẻ Riêng của User đó (USER_ID)
    Người khác KHÔNG thể nhìn thấy thẻ của user này.
    """
    db = SessionLocal()
    try:
        query = db.query(QuickChip).filter(
            (QuickChip.is_system == True) | (QuickChip.user_id == user_id)
        )
        if context and context != "ALL":
            # Lấy thẻ thuộc context đó hoặc thẻ chung (CUSTOM)
            query = query.filter((QuickChip.context == context) | (QuickChip.context == "CUSTOM"))

        # Ưu tiên sắp xếp: Thẻ cá nhân hiển thị trước, sau đó đến thẻ hệ thống
        chips = query.order_by(QuickChip.is_system.asc(), QuickChip.created_at.desc()).all()
        return [
            {
                "id": c.id,
                "text": c.text,
                "context": c.context,
                "is_system": c.is_system,
                "user_id": c.user_id,
                "usage_count": c.usage_count
            }
            for c in chips
        ]
    finally:
        db.close()

def add_user_chip(user_id: str, text: str, context: str = "CUSTOM") -> Dict[str, Any]:
    """
    Thêm thẻ cá nhân cho user_id cụ thể.
    """
    clean_text = text.strip()
    if not clean_text:
        raise ValueError("Nội dung thẻ không được để trống")

    db = SessionLocal()
    try:
        # Kiểm tra xem thẻ đã tồn tại với user này hoặc trong hệ thống chưa
        existing = db.query(QuickChip).filter(
            ((QuickChip.user_id == user_id) | (QuickChip.is_system == True)),
            QuickChip.text == clean_text
        ).first()

        if existing and existing.user_id == user_id:
            # Nếu user đã tạo rồi thì trả về thẻ đó
            return {
                "id": existing.id,
                "text": existing.text,
                "context": existing.context,
                "is_system": existing.is_system,
                "user_id": existing.user_id,
                "usage_count": existing.usage_count
            }

        new_chip = QuickChip(
            id=str(uuid.uuid4()),
            user_id=user_id,
            text=clean_text,
            context=context,
            is_system=False,
            usage_count=0
        )
        db.add(new_chip)
        db.commit()
        db.refresh(new_chip)
        return {
            "id": new_chip.id,
            "text": new_chip.text,
            "context": new_chip.context,
            "is_system": new_chip.is_system,
            "user_id": new_chip.user_id,
            "usage_count": new_chip.usage_count
        }
    finally:
        db.close()

def delete_user_chip(user_id: str, chip_id: str) -> bool:
    """
    Xóa thẻ cá nhân.
    CHỈ CHO PHÉP XÓA thẻ của chính user_id đó. Tuyệt đối KHÔNG xóa thẻ hệ thống (is_system=True).
    """
    db = SessionLocal()
    try:
        chip = db.query(QuickChip).filter(
            QuickChip.id == chip_id,
            QuickChip.user_id == user_id,
            QuickChip.is_system == False
        ).first()
        if not chip:
            return False
        db.delete(chip)
        db.commit()
        return True
    finally:
        db.close()

def reset_user_chips(user_id: str) -> bool:
    """
    Xóa toàn bộ thẻ cá nhân của user_id, đưa về trạng thái mặc định.
    """
    db = SessionLocal()
    try:
        db.query(QuickChip).filter(
            QuickChip.user_id == user_id,
            QuickChip.is_system == False
        ).delete()
        db.commit()
        return True
    finally:
        db.close()
