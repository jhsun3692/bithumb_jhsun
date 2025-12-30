"""Analytics and profit tracking API endpoints."""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.database import get_db
from app.schemas.trading import ProfitSummary
from app.models.database import Trade, Balance, OrderType, StrategyExecutionLog
from app.services.bithumb_api import bithumb_api

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/profit", response_model=ProfitSummary)
async def get_profit_summary(db: Session = Depends(get_db)):
    """Get profit summary and statistics.

    Args:
        db: Database session

    Returns:
        Profit summary with various metrics
    """
    # Calculate total invested (total buy orders)
    total_invested = db.query(func.sum(Trade.total)).filter(
        Trade.trade_type == OrderType.BUY
    ).scalar() or 0.0

    # Calculate realized profit from completed sell trades
    realized_profit = db.query(func.sum(Trade.profit)).filter(
        Trade.trade_type == OrderType.SELL,
        Trade.profit.isnot(None)
    ).scalar() or 0.0

    # Calculate current holdings value (unrealized profit)
    balances = db.query(Balance).all()
    current_value = 0.0
    unrealized_profit = 0.0

    for balance in balances:
        if balance.total > 0:
            current_price = bithumb_api.get_current_price(balance.coin)
            if current_price:
                coin_value = balance.total * current_price
                current_value += coin_value

                if balance.avg_buy_price:
                    coin_profit = (current_price - balance.avg_buy_price) * balance.total
                    unrealized_profit += coin_profit

    # Calculate total profit
    total_profit = realized_profit + unrealized_profit

    # Calculate ROI
    roi_percentage = (total_profit / total_invested * 100) if total_invested > 0 else 0.0

    return ProfitSummary(
        total_invested=total_invested,
        current_value=current_value,
        realized_profit=realized_profit,
        unrealized_profit=unrealized_profit,
        total_profit=total_profit,
        roi_percentage=roi_percentage
    )


@router.get("/stats")
async def get_trading_stats(db: Session = Depends(get_db)):
    """Get general trading statistics.

    Args:
        db: Database session

    Returns:
        Trading statistics
    """
    from app.models.database import Order

    total_orders = db.query(func.count(Order.id)).scalar()
    completed_orders = db.query(func.count(Order.id)).filter(
        Order.status == "completed"
    ).scalar()
    failed_orders = db.query(func.count(Order.id)).filter(
        Order.status == "failed"
    ).scalar()

    total_buy_volume = db.query(func.sum(Trade.total)).filter(
        Trade.trade_type == OrderType.BUY
    ).scalar() or 0.0

    total_sell_volume = db.query(func.sum(Trade.total)).filter(
        Trade.trade_type == OrderType.SELL
    ).scalar() or 0.0

    return {
        "total_orders": total_orders,
        "completed_orders": completed_orders,
        "failed_orders": failed_orders,
        "success_rate": (completed_orders / total_orders * 100) if total_orders > 0 else 0,
        "total_buy_volume": total_buy_volume,
        "total_sell_volume": total_sell_volume,
    }


@router.get("/execution-logs")
async def get_execution_logs(
    limit: int = Query(50, ge=1, le=500),
    strategy_id: Optional[int] = None,
    coin: Optional[str] = None,
    signal_only: bool = False,
    db: Session = Depends(get_db)
):
    """Get strategy execution logs.

    Args:
        limit: Maximum number of logs to return (1-500)
        strategy_id: Filter by strategy ID
        coin: Filter by coin symbol
        signal_only: Only return logs with buy/sell signals
        db: Database session

    Returns:
        List of execution logs
    """
    query = db.query(StrategyExecutionLog)

    if strategy_id:
        query = query.filter(StrategyExecutionLog.strategy_id == strategy_id)
    if coin:
        query = query.filter(StrategyExecutionLog.coin == coin)
    if signal_only:
        query = query.filter(StrategyExecutionLog.signal.isnot(None))

    logs = query.order_by(StrategyExecutionLog.created_at.desc()).limit(limit).all()

    return [
        {
            "id": log.id,
            "strategy_id": log.strategy_id,
            "strategy_name": log.strategy_name,
            "coin": log.coin,
            "signal": log.signal,
            "executed": log.executed,
            "order_id": log.order_id,
            "message": log.message,
            "error": log.error,
            "created_at": log.created_at.isoformat() if log.created_at else None
        }
        for log in logs
    ]


@router.get("/execution-summary")
async def get_execution_summary(db: Session = Depends(get_db)):
    """Get summary of strategy executions.

    Args:
        db: Database session

    Returns:
        Execution summary statistics
    """
    total_checks = db.query(func.count(StrategyExecutionLog.id)).scalar() or 0

    total_signals = db.query(func.count(StrategyExecutionLog.id)).filter(
        StrategyExecutionLog.signal.isnot(None)
    ).scalar() or 0

    buy_signals = db.query(func.count(StrategyExecutionLog.id)).filter(
        StrategyExecutionLog.signal == "buy"
    ).scalar() or 0

    sell_signals = db.query(func.count(StrategyExecutionLog.id)).filter(
        StrategyExecutionLog.signal == "sell"
    ).scalar() or 0

    executed_orders = db.query(func.count(StrategyExecutionLog.id)).filter(
        StrategyExecutionLog.executed == True
    ).scalar() or 0

    failed_executions = db.query(func.count(StrategyExecutionLog.id)).filter(
        StrategyExecutionLog.error.isnot(None)
    ).scalar() or 0

    # Get most recent execution
    latest_log = db.query(StrategyExecutionLog).order_by(
        StrategyExecutionLog.created_at.desc()
    ).first()

    return {
        "total_checks": total_checks,
        "total_signals": total_signals,
        "buy_signals": buy_signals,
        "sell_signals": sell_signals,
        "executed_orders": executed_orders,
        "failed_executions": failed_executions,
        "execution_rate": (executed_orders / total_signals * 100) if total_signals > 0 else 0,
        "latest_check": latest_log.created_at.isoformat() if latest_log and latest_log.created_at else None
    }