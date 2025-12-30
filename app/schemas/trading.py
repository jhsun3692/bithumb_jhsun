"""Pydantic schemas for API request/response validation."""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from enum import Enum


class OrderTypeEnum(str, Enum):
    """Order type enumeration."""
    BUY = "buy"
    SELL = "sell"


class OrderStatusEnum(str, Enum):
    """Order status enumeration."""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class OrderCreate(BaseModel):
    """Schema for creating a new order."""
    order_type: OrderTypeEnum
    coin: str = Field(..., description="Coin symbol (e.g., BTC, ETH)")
    amount: float = Field(..., gt=0, description="Amount to buy/sell")
    price: Optional[float] = Field(None, gt=0, description="Price per coin (None for market price)")


class OrderResponse(BaseModel):
    """Schema for order response."""
    id: int
    order_type: OrderTypeEnum
    coin: str
    currency: str
    amount: float
    price: float
    total: float
    status: OrderStatusEnum
    order_id: Optional[str]
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TradeResponse(BaseModel):
    """Schema for trade response."""
    id: int
    order_id: int
    coin: str
    currency: str
    trade_type: OrderTypeEnum
    amount: float
    price: float
    total: float
    fee: float
    profit: Optional[float]
    created_at: datetime

    class Config:
        from_attributes = True


class BalanceResponse(BaseModel):
    """Schema for balance response."""
    coin: str
    total: float
    available: float
    in_use: float
    avg_buy_price: Optional[float]
    updated_at: datetime

    class Config:
        from_attributes = True


class MarketPrice(BaseModel):
    """Schema for current market price."""
    coin: str
    price: float
    timestamp: datetime


class ProfitSummary(BaseModel):
    """Schema for profit summary."""
    total_invested: float
    current_value: float
    realized_profit: float
    unrealized_profit: float
    total_profit: float
    roi_percentage: float