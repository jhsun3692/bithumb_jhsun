"""Database connection and session management."""
from datetime import datetime
import pytz
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import get_settings

settings = get_settings()

# Korea timezone
KST = pytz.timezone('Asia/Seoul')


def kst_now():
    """Get current datetime in Korea Standard Time (KST).

    Returns:
        datetime: Current datetime in KST timezone
    """
    return datetime.now(KST)

# Create SQLAlchemy engine
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {}
)

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create Base class for models
Base = declarative_base()


def get_db():
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables and create default admin user."""
    from app.models.user import User
    from app.core.security import get_password_hash

    # Create all tables
    Base.metadata.create_all(bind=engine)

    # Create default admin user if not exists
    db = SessionLocal()
    try:
        admin_exists = db.query(User).filter(User.is_admin == True).first()

        if not admin_exists:
            # Create default admin user
            default_admin = User(
                username="admin",
                email="admin@bithumb.local",
                hashed_password=get_password_hash("admin123!"),
                is_admin=True,
                is_approved=True,
                is_active=True
            )
            db.add(default_admin)
            db.commit()
            print("=" * 80)
            print("✅ 기본 관리자 계정이 생성되었습니다!")
            print("   사용자명: admin")
            print("   비밀번호: admin123!")
            print("   ⚠️  보안을 위해 첫 로그인 후 반드시 비밀번호를 변경하세요!")
            print("=" * 80)
    except Exception as e:
        print(f"Error creating default admin user: {e}")
        db.rollback()
    finally:
        db.close()