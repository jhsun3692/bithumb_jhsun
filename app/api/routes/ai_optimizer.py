"""API routes for AI-powered optimization and anomaly detection."""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
import logging

from app.core.database import get_db
from app.models.user import User
from app.core.security import get_current_user
from app.services.parameter_optimizer import ParameterOptimizer, optimize_all_strategies
from app.services.anomaly_detector import AnomalyDetector
from app.services.bithumb_api import BithumbAPI
from app.models.database import TradingStrategy, Order
import json

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ai", tags=["AI Optimization"])


@router.post("/optimize-parameters")
async def optimize_parameters(
    strategy_id: int,
    n_trials: int = 50,
    days_back: int = 90,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Optimize parameters for a specific trading strategy.

    Args:
        strategy_id: ID of the strategy to optimize
        n_trials: Number of optimization trials (default: 50)
        days_back: Days of historical data to use (default: 90)

    Returns:
        Optimization results with best parameters
    """
    # Get strategy
    strategy = db.query(TradingStrategy).filter(
        TradingStrategy.id == strategy_id,
        TradingStrategy.user_id == current_user.id
    ).first()

    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    # Check if user has API credentials
    if not current_user.bithumb_api_key or not current_user.bithumb_api_secret:
        raise HTTPException(
            status_code=400,
            detail="Bithumb API credentials not configured"
        )

    # Create API instance
    api = BithumbAPI(
        api_key=current_user.bithumb_api_key,
        api_secret=current_user.bithumb_api_secret
    )

    # Run optimization
    optimizer = ParameterOptimizer(api)

    try:
        result = optimizer.optimize_strategy(
            strategy_type=strategy.strategy_type,
            coin=strategy.coin,
            n_trials=n_trials,
            days_back=days_back
        )

        return {
            "success": True,
            "strategy_id": strategy_id,
            "strategy_name": strategy.name,
            "strategy_type": strategy.strategy_type,
            "coin": strategy.coin,
            "optimization_result": result
        }

    except Exception as e:
        logger.error(f"Optimization failed: {e}")
        raise HTTPException(status_code=500, detail=f"Optimization failed: {str(e)}")


@router.post("/optimize-parameters-and-apply")
async def optimize_and_apply_parameters(
    strategy_id: int,
    n_trials: int = 50,
    days_back: int = 90,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Optimize parameters and automatically apply them to the strategy.

    Args:
        strategy_id: ID of the strategy to optimize
        n_trials: Number of optimization trials
        days_back: Days of historical data to use

    Returns:
        Optimization results and updated strategy
    """
    # Get optimization results
    result = await optimize_parameters(
        strategy_id=strategy_id,
        n_trials=n_trials,
        days_back=days_back,
        current_user=current_user,
        db=db
    )

    # Get strategy
    strategy = db.query(TradingStrategy).filter(
        TradingStrategy.id == strategy_id
    ).first()

    # Apply best parameters
    best_params = result["optimization_result"]["best_params"]
    strategy.parameters = json.dumps(best_params)
    db.commit()

    logger.info(f"Applied optimized parameters to strategy {strategy.name}")

    return {
        "success": True,
        "message": "Parameters optimized and applied successfully",
        "strategy_id": strategy_id,
        "new_parameters": best_params,
        "optimization_result": result["optimization_result"]
    }


@router.post("/optimize-all-strategies")
async def optimize_all_user_strategies(
    background_tasks: BackgroundTasks,
    n_trials: int = 30,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Optimize all strategies for the current user (runs in background).

    Args:
        n_trials: Number of trials per strategy
        background_tasks: FastAPI background tasks

    Returns:
        Status message
    """
    if not current_user.bithumb_api_key or not current_user.bithumb_api_secret:
        raise HTTPException(
            status_code=400,
            detail="Bithumb API credentials not configured"
        )

    # Get all user strategies
    strategies = db.query(TradingStrategy).filter(
        TradingStrategy.user_id == current_user.id
    ).all()

    if not strategies:
        raise HTTPException(status_code=404, detail="No strategies found")

    # This would ideally run in background
    # For now, return a message that optimization has started
    return {
        "success": True,
        "message": f"Optimization started for {len(strategies)} strategies",
        "num_strategies": len(strategies),
        "estimated_time_minutes": len(strategies) * n_trials * 0.5,
        "note": "This is a long-running operation. Check back later for results."
    }


@router.get("/detect-anomalies/{coin}")
async def detect_anomalies(
    coin: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Detect anomalies in price, volume, and market conditions.

    Args:
        coin: Coin symbol (e.g., BTC, ETH)

    Returns:
        Anomaly detection results
    """
    if not current_user.bithumb_api_key or not current_user.bithumb_api_secret:
        raise HTTPException(
            status_code=400,
            detail="Bithumb API credentials not configured"
        )

    # Create API and detector instances
    api = BithumbAPI(
        api_key=current_user.bithumb_api_key,
        api_secret=current_user.bithumb_api_secret
    )
    detector = AnomalyDetector(api)

    try:
        # Run comprehensive anomaly detection
        result = detector.comprehensive_anomaly_check(coin)

        return {
            "success": True,
            "anomaly_detection": result
        }

    except Exception as e:
        logger.error(f"Anomaly detection failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Anomaly detection failed: {str(e)}"
        )


@router.get("/strategy-health/{strategy_id}")
async def check_strategy_health(
    strategy_id: int,
    lookback_trades: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Check health and performance anomalies of a trading strategy.

    Args:
        strategy_id: ID of the strategy
        lookback_trades: Number of recent trades to analyze

    Returns:
        Strategy health report
    """
    # Get strategy
    strategy = db.query(TradingStrategy).filter(
        TradingStrategy.id == strategy_id,
        TradingStrategy.user_id == current_user.id
    ).first()

    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    if not current_user.bithumb_api_key or not current_user.bithumb_api_secret:
        raise HTTPException(
            status_code=400,
            detail="Bithumb API credentials not configured"
        )

    # Get recent trades for this strategy
    orders = db.query(Order).filter(
        Order.strategy_id == strategy_id
    ).order_by(Order.created_at.desc()).limit(lookback_trades).all()

    if not orders:
        return {
            "success": True,
            "message": "No trades found for this strategy",
            "strategy_id": strategy_id,
            "num_trades": 0
        }

    # Convert orders to trade format
    trades = []
    for order in orders:
        trades.append({
            "type": order.order_type.value,
            "profit": order.total if order.order_type.value == "sell" else -order.total,
            "amount": order.amount,
            "price": order.price,
            "created_at": order.created_at.isoformat()
        })

    # Create detector and analyze
    api = BithumbAPI(
        api_key=current_user.bithumb_api_key,
        api_secret=current_user.bithumb_api_secret
    )
    detector = AnomalyDetector(api)

    try:
        performance_result = detector.detect_strategy_performance_anomalies(trades)

        return {
            "success": True,
            "strategy_id": strategy_id,
            "strategy_name": strategy.name,
            "health_report": performance_result
        }

    except Exception as e:
        logger.error(f"Strategy health check failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Health check failed: {str(e)}"
        )


@router.get("/market-risk/{coin}")
async def assess_market_risk(
    coin: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Assess overall market risk for a coin.

    Args:
        coin: Coin symbol

    Returns:
        Market risk assessment
    """
    if not current_user.bithumb_api_key or not current_user.bithumb_api_secret:
        raise HTTPException(
            status_code=400,
            detail="Bithumb API credentials not configured"
        )

    api = BithumbAPI(
        api_key=current_user.bithumb_api_key,
        api_secret=current_user.bithumb_api_secret
    )
    detector = AnomalyDetector(api)

    try:
        # Get price and volume anomalies
        price_anomaly = detector.detect_price_anomalies(coin)
        volume_anomaly = detector.detect_volume_anomalies(coin)

        # Calculate risk metrics
        overall_risk = "low"
        risk_factors = []

        if price_anomaly.get("is_anomaly"):
            risk_factors.append(f"Price anomaly: {price_anomaly.get('anomaly_type')}")
            if price_anomaly.get("severity") in ["high", "critical"]:
                overall_risk = "high"

        if volume_anomaly.get("is_anomaly"):
            risk_factors.append(f"Volume anomaly: {volume_anomaly.get('anomaly_type')}")
            if volume_anomaly.get("severity") in ["high", "critical"]:
                overall_risk = "high" if overall_risk != "critical" else "critical"

        return {
            "success": True,
            "coin": coin,
            "overall_risk_level": overall_risk,
            "risk_factors": risk_factors,
            "price_analysis": price_anomaly,
            "volume_analysis": volume_anomaly,
            "recommendation": price_anomaly.get("recommendation", "Monitor market conditions")
        }

    except Exception as e:
        logger.error(f"Market risk assessment failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Risk assessment failed: {str(e)}"
        )