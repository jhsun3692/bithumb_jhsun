"""Coin model for storing cryptocurrency information."""
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func
from app.core.database import Base


class Coin(Base):
    """Coin model for storing cryptocurrency market data.

    Stores information about available cryptocurrencies including
    Korean and English names.
    """
    __tablename__ = "coins"

    id = Column(Integer, primary_key=True, index=True)

    # Coin symbol (e.g., "BTC", "ETH")
    symbol = Column(String(20), unique=True, index=True, nullable=False)

    # Korean name (e.g., "비트코인")
    korean_name = Column(String(100), nullable=True)

    # English name (e.g., "Bitcoin")
    english_name = Column(String(100), nullable=True)

    # Market identifier (e.g., "KRW-BTC")
    market = Column(String(50), nullable=True)

    # Whether this coin is available for trading
    is_active = Column(Boolean, default=True, nullable=False)

    # Whether this is a major/featured coin (for top display)
    is_major = Column(Boolean, default=False, nullable=False)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<Coin(symbol='{self.symbol}', korean_name='{self.korean_name}')>"