"""Database models for trading system."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Enum, ForeignKey
from app.core.database import Base, kst_now
import enum


class OrderType(str, enum.Enum):
    """Order type enumeration."""
    BUY = "buy"
    SELL = "sell"


class OrderStatus(str, enum.Enum):
    """Order status enumeration."""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Order(Base):
    """Order model for tracking buy/sell orders."""
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    order_type = Column(Enum(OrderType), nullable=False)
    coin = Column(String, nullable=False, index=True)
    currency = Column(String, default="KRW")
    amount = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    total = Column(Float, nullable=False)
    status = Column(Enum(OrderStatus), default=OrderStatus.PENDING)
    order_id = Column(String, nullable=True)  # Bithumb order ID
    strategy_id = Column(Integer, nullable=True)  # Reference to strategy that created this order
    error_message = Column(String, nullable=True)
    created_at = Column(DateTime, default=kst_now)
    updated_at = Column(DateTime, default=kst_now, onupdate=kst_now)


class Trade(Base):
    """Trade model for tracking completed trades."""
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, nullable=False)
    coin = Column(String, nullable=False, index=True)
    currency = Column(String, default="KRW")
    trade_type = Column(Enum(OrderType), nullable=False)
    amount = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    total = Column(Float, nullable=False)
    fee = Column(Float, default=0.0)
    profit = Column(Float, nullable=True)  # For sell orders
    created_at = Column(DateTime, default=kst_now)


class Balance(Base):
    """Balance model for tracking current holdings."""
    __tablename__ = "balances"

    id = Column(Integer, primary_key=True, index=True)
    coin = Column(String, nullable=False, unique=True, index=True)
    total = Column(Float, default=0.0)
    available = Column(Float, default=0.0)
    in_use = Column(Float, default=0.0)
    avg_buy_price = Column(Float, nullable=True)
    updated_at = Column(DateTime, default=kst_now, onupdate=kst_now)


class TradingStrategy(Base):
    """Trading strategy configuration."""
    __tablename__ = "trading_strategies"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)  # Owner of this strategy
    name = Column(String, nullable=False, unique=True)
    coin = Column(String, nullable=False)
    enabled = Column(Boolean, default=False)
    strategy_type = Column(String, nullable=False)  # e.g., "moving_average", "rsi", "macd", "stochastic", "composite"
    parameters = Column(String, nullable=True)  # JSON string of parameters
    max_buy_amount = Column(Float, nullable=True)  # Maximum total buy amount in KRW
    highest_price = Column(Float, nullable=True)  # For trailing stop tracking
    created_at = Column(DateTime, default=kst_now)
    updated_at = Column(DateTime, default=kst_now, onupdate=kst_now)


class StrategyExecutionLog(Base):
    """Log of strategy execution attempts."""
    __tablename__ = "strategy_execution_logs"

    id = Column(Integer, primary_key=True, index=True)
    strategy_id = Column(Integer, nullable=False)
    strategy_name = Column(String, nullable=False)
    coin = Column(String, nullable=False)
    signal = Column(String, nullable=True)  # "buy", "sell", or None
    executed = Column(Boolean, default=False)
    order_id = Column(Integer, nullable=True)  # Reference to orders table
    message = Column(String, nullable=True)
    error = Column(String, nullable=True)
    created_at = Column(DateTime, default=kst_now)