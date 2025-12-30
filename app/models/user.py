"""User model for authentication."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from app.core.database import Base, kst_now


class User(Base):
    """User model for authentication and authorization."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    is_approved = Column(Boolean, default=False)  # 관리자 승인 여부
    bithumb_api_key = Column(String, nullable=True)
    bithumb_api_secret = Column(String, nullable=True)
    otp_secret = Column(String, nullable=True)  # Google OTP 시크릿
    otp_enabled = Column(Boolean, default=False)  # 2FA 활성화 여부
    created_at = Column(DateTime, default=kst_now)
    updated_at = Column(DateTime, default=kst_now, onupdate=kst_now)