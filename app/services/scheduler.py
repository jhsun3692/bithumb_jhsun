"""Trading scheduler service."""
import logging
from typing import Optional
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.database import SessionLocal
from app.core.config import get_settings
from app.models.database import TradingStrategy as TradingStrategyModel, StrategyExecutionLog
from app.services.strategy import (
    MovingAverageStrategy,
    BollingerBandStrategy,
    RSIStrategy,
    MACDStrategy,
    StochasticStrategy,
    CompositeStrategy
)
from app.services.trading_engine import TradingEngine
from app.services.bithumb_api import BithumbAPI
import json

logger = logging.getLogger(__name__)
settings = get_settings()


class TradingScheduler:
    """Manages scheduled execution of trading strategies."""

    def __init__(self):
        """Initialize the scheduler."""
        self.scheduler: Optional[BackgroundScheduler] = None

    def start(self):
        """Start the scheduler."""
        if not settings.scheduler_enabled:
            logger.info("Scheduler is disabled in settings")
            return

        if self.scheduler and self.scheduler.running:
            logger.warning("Scheduler is already running")
            return

        self.scheduler = BackgroundScheduler(timezone=settings.scheduler_timezone)

        # Add job to run strategy checks
        self.scheduler.add_job(
            func=self.run_strategy_checks,
            trigger=IntervalTrigger(seconds=settings.scheduler_interval_seconds),
            id="strategy_check_job",
            name="Check and execute trading strategies",
            replace_existing=True
        )

        self.scheduler.start()
        logger.info(
            f"Scheduler started. Running strategy checks every {settings.scheduler_interval_seconds} seconds"
        )

    def stop(self):
        """Stop the scheduler."""
        if self.scheduler and self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Scheduler stopped")

    def run_strategy_checks(self):
        """Run checks for all enabled strategies."""
        db = SessionLocal()
        try:
            # First, check profit targets and stop losses for all strategies
            self._check_profit_targets_and_stop_losses(db)

            # Get all enabled strategies
            strategies = db.query(TradingStrategyModel).filter(
                TradingStrategyModel.enabled == True
            ).all()

            if not strategies:
                logger.debug("No enabled strategies found")
                return

            logger.info(f"Checking {len(strategies)} enabled strategies")

            for strategy_model in strategies:
                try:
                    self._execute_strategy(db, strategy_model)
                except Exception as e:
                    logger.error(f"Error executing strategy {strategy_model.name}: {e}")
                    self._log_execution(
                        db,
                        strategy_model,
                        signal=None,
                        executed=False,
                        error=str(e)
                    )

        finally:
            db.close()

    def _execute_strategy(self, db: Session, strategy_model: TradingStrategyModel):
        """Execute a single strategy.

        Args:
            db: Database session
            strategy_model: TradingStrategy model instance
        """
        # Get the user who owns this strategy
        from app.models.user import User
        user = db.query(User).filter(User.id == strategy_model.user_id).first()

        if not user:
            logger.error(f"Strategy {strategy_model.name} has no owner (user_id: {strategy_model.user_id})")
            return

        # Check if user has API credentials configured
        if not user.bithumb_api_key or not user.bithumb_api_secret:
            error_msg = f"User {user.username} has no API credentials configured"
            logger.warning(error_msg)
            self._log_execution(
                db,
                strategy_model,
                signal=None,
                executed=False,
                error=error_msg
            )
            return

        # Create user-specific API instance
        api = BithumbAPI(api_key=user.bithumb_api_key, api_secret=user.bithumb_api_secret)

        # Parse parameters
        params = {}
        if strategy_model.parameters:
            try:
                params = json.loads(strategy_model.parameters)
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON parameters for strategy {strategy_model.name}")
                return

        coin = strategy_model.coin

        # Get current price and balance
        current_price = api.get_current_price(coin)
        balance_data = api.get_balance(coin)
        coin_balance = balance_data.get("total", 0.0)
        avg_buy_price = balance_data.get("avg_buy_price")

        # Calculate current value and profit
        current_value = coin_balance * current_price if current_price and coin_balance > 0 else 0
        profit_pct = ((current_price - avg_buy_price) / avg_buy_price * 100) if avg_buy_price and current_price else 0

        logger.info(f"\n{'='*80}")
        logger.info(f"전략 실행: {strategy_model.name} ({strategy_model.strategy_type.upper()})")
        logger.info(f"코인: {coin}")
        logger.info(f"현재가: {current_price:,.0f}원" if current_price else "현재가: N/A")
        logger.info(f"보유량: {coin_balance:.4f} {coin}")
        if avg_buy_price:
            logger.info(f"평균 매수가: {avg_buy_price:,.0f}원")
            logger.info(f"현재 가치: {current_value:,.0f}원")
            logger.info(f"수익률: {profit_pct:+.2f}%")

        # Create strategy instance based on type
        strategy = None
        if strategy_model.strategy_type == "moving_average":
            short_period = params.get("short_period", 5)
            long_period = params.get("long_period", 20)
            strategy = MovingAverageStrategy(api, short_period, long_period)
            logger.info(f"이동평균: 단기 {short_period}일 / 장기 {long_period}일")

        elif strategy_model.strategy_type == "bollinger":
            period = params.get("period", 20)
            std_dev = params.get("std_dev", 2.0)
            strategy = BollingerBandStrategy(api, period, std_dev)

            # Get Bollinger Bands values
            df = api.get_ohlcv(coin, interval="day")
            if df is not None and len(df) >= period:
                closes = df['close'].values
                middle_band = closes[-period:].mean()
                std = closes[-period:].std()
                upper_band = middle_band + (std_dev * std)
                lower_band = middle_band - (std_dev * std)

                logger.info(f"볼린저 밴드 (기간: {period}일, 표준편차: {std_dev})")
                logger.info(f"  상단 밴드: {upper_band:,.0f}원")
                logger.info(f"  중간 밴드: {middle_band:,.0f}원")
                logger.info(f"  하단 밴드: {lower_band:,.0f}원")
                if current_price:
                    if current_price > upper_band:
                        logger.info(f"  ▲ 현재가가 상단 밴드 위 (매도 대기)")
                    elif current_price < lower_band:
                        logger.info(f"  ▼ 현재가가 하단 밴드 아래 (반등 대기)")
                    elif current_price >= upper_band * 0.99:
                        logger.info(f"  ⚠️  상단 밴드 근처 (반락 시 매도)")
                    elif current_price <= lower_band * 1.01:
                        logger.info(f"  ⚠️  하단 밴드 근처 (반등 시 매수)")
                    else:
                        logger.info(f"  ● 현재가가 밴드 중간 영역")

        elif strategy_model.strategy_type == "rsi":
            period = params.get("period", 14)
            oversold = params.get("oversold", 30)
            overbought = params.get("overbought", 70)
            strategy = RSIStrategy(api, period, oversold, overbought)
            logger.info(f"RSI: 기간 {period}일 / 과매도 {oversold} / 과매수 {overbought}")

        elif strategy_model.strategy_type == "macd":
            fast_period = params.get("fast_period", 12)
            slow_period = params.get("slow_period", 26)
            signal_period = params.get("signal_period", 9)
            strategy = MACDStrategy(api, fast_period, slow_period, signal_period)
            logger.info(f"MACD: 빠른 EMA {fast_period}일 / 느린 EMA {slow_period}일 / 시그널 {signal_period}일")

        elif strategy_model.strategy_type == "stochastic":
            k_period = params.get("k_period", 14)
            d_period = params.get("d_period", 3)
            oversold = params.get("oversold", 20)
            overbought = params.get("overbought", 80)
            strategy = StochasticStrategy(api, k_period, d_period, oversold, overbought)
            logger.info(f"Stochastic: %K {k_period}일 / %D {d_period}일 / 과매도 {oversold} / 과매수 {overbought}")

        elif strategy_model.strategy_type == "composite":
            # Composite strategy combines multiple strategies
            strategy_types = params.get("strategy_types", [])
            min_confirmations = params.get("min_confirmations", 2)

            sub_strategies = []
            for st in strategy_types:
                st_type = st.get("type")
                st_params = st.get("params", {})

                if st_type == "moving_average":
                    sub_strategies.append(MovingAverageStrategy(
                        api,
                        st_params.get("short_period", 5),
                        st_params.get("long_period", 20)
                    ))
                elif st_type == "rsi":
                    sub_strategies.append(RSIStrategy(
                        api,
                        st_params.get("period", 14),
                        st_params.get("oversold", 30),
                        st_params.get("overbought", 70)
                    ))
                elif st_type == "bollinger":
                    sub_strategies.append(BollingerBandStrategy(
                        api,
                        st_params.get("period", 20),
                        st_params.get("std_dev", 2.0)
                    ))
                elif st_type == "macd":
                    sub_strategies.append(MACDStrategy(
                        api,
                        st_params.get("fast_period", 12),
                        st_params.get("slow_period", 26),
                        st_params.get("signal_period", 9)
                    ))
                elif st_type == "stochastic":
                    sub_strategies.append(StochasticStrategy(
                        api,
                        st_params.get("k_period", 14),
                        st_params.get("d_period", 3),
                        st_params.get("oversold", 20),
                        st_params.get("overbought", 80)
                    ))

            strategy = CompositeStrategy(api, sub_strategies, min_confirmations)
            logger.info(f"복합 전략: {len(sub_strategies)}개 전략 조합 / 최소 확인 {min_confirmations}개")

        else:
            logger.error(f"Unknown strategy type: {strategy_model.strategy_type}")
            return

        # Check for buy/sell signals
        should_buy = strategy.should_buy(coin)
        should_sell = strategy.should_sell(coin)

        # Log signal decision
        if should_buy:
            logger.info(f"✅ 매수 시그널 발생!")
        elif should_sell:
            logger.info(f"🔴 매도 시그널 발생!")
        else:
            logger.info(f"⏸️  시그널 없음 (관망)")
        logger.info(f"{'='*80}\n")

        # Execute trades based on signals
        engine = TradingEngine(db, api)

        if should_buy:
            logger.info(f"Buy signal detected for {coin} using {strategy_model.name}")

            # Get trade amount from parameters or use default
            trade_amount = params.get("trade_amount", 0.001)  # Default: 0.001 of coin
            trade_amount_krw = params.get("trade_amount_krw", 10000)

            # Check max_buy_amount limit
            if strategy_model.max_buy_amount and strategy_model.max_buy_amount > 0:
                # Calculate total amount already invested by this strategy
                from app.models.database import Order, OrderType, OrderStatus
                total_invested = db.query(func.sum(Order.total)).filter(
                    Order.strategy_id == strategy_model.id,
                    Order.order_type == OrderType.BUY,
                    Order.status == OrderStatus.COMPLETED
                ).scalar() or 0.0

                # Check if adding this order would exceed the limit
                if total_invested + trade_amount_krw > strategy_model.max_buy_amount:
                    remaining = strategy_model.max_buy_amount - total_invested
                    logger.warning(
                        f"Buy order skipped: would exceed max buy amount limit. "
                        f"Total invested: {total_invested:,.0f} KRW, "
                        f"Limit: {strategy_model.max_buy_amount:,.0f} KRW, "
                        f"Remaining: {remaining:,.0f} KRW"
                    )
                    self._log_execution(
                        db,
                        strategy_model,
                        signal="buy",
                        executed=False,
                        message=f"Buy order skipped: max buy amount limit reached ({total_invested:,.0f}/{strategy_model.max_buy_amount:,.0f} KRW)"
                    )
                    # Skip this buy order
                    return

            try:
                order = engine.execute_buy_order(
                    coin=coin,
                    amount=trade_amount,
                    strategy_id=strategy_model.id
                )

                self._log_execution(
                    db,
                    strategy_model,
                    signal="buy",
                    executed=(order.status.value == "completed"),
                    order_id=order.id,
                    message=f"Buy order {'executed' if order.status.value == 'completed' else 'created'}: {order.amount} {coin}"
                )

                logger.info(f"Buy order executed for {coin}: {order.id}")

            except Exception as e:
                logger.error(f"Error executing buy order: {e}")
                self._log_execution(
                    db,
                    strategy_model,
                    signal="buy",
                    executed=False,
                    error=str(e)
                )

        elif should_sell:
            logger.info(f"Sell signal detected for {coin} using {strategy_model.name}")

            # Get trade amount from parameters or use default
            trade_amount = params.get("trade_amount", 0.001)

            try:
                order = engine.execute_sell_order(
                    coin=coin,
                    amount=trade_amount,
                    strategy_id=strategy_model.id
                )

                self._log_execution(
                    db,
                    strategy_model,
                    signal="sell",
                    executed=(order.status.value == "completed"),
                    order_id=order.id,
                    message=f"Sell order {'executed' if order.status.value == 'completed' else 'created'}: {order.amount} {coin}"
                )

                logger.info(f"Sell order executed for {coin}: {order.id}")

            except Exception as e:
                logger.error(f"Error executing sell order: {e}")
                self._log_execution(
                    db,
                    strategy_model,
                    signal="sell",
                    executed=False,
                    error=str(e)
                )
        else:
            # No signal - log as check with no action
            logger.debug(f"No signal for {coin} using {strategy_model.name}")
            self._log_execution(
                db,
                strategy_model,
                signal=None,
                executed=False,
                message="Strategy checked - no signal"
            )

    def _check_profit_targets_and_stop_losses(self, db: Session):
        """Check profit targets and stop losses for all strategies with holdings.

        Args:
            db: Database session
        """
        from app.models.database import Balance, Order, OrderType, OrderStatus
        from app.models.user import User

        # Get all enabled strategies
        strategies = db.query(TradingStrategyModel).filter(
            TradingStrategyModel.enabled == True
        ).all()

        for strategy_model in strategies:
            try:
                # Get the user who owns this strategy
                user = db.query(User).filter(User.id == strategy_model.user_id).first()

                if not user or not user.bithumb_api_key or not user.bithumb_api_secret:
                    continue  # Skip if no API credentials

                # Create user-specific API instance
                api = BithumbAPI(api_key=user.bithumb_api_key, api_secret=user.bithumb_api_secret)

                # Parse parameters
                params = {}
                if strategy_model.parameters:
                    try:
                        params = json.loads(strategy_model.parameters)
                    except json.JSONDecodeError:
                        continue

                profit_target = params.get("profit_target")
                stop_loss = params.get("stop_loss")

                # Skip if no profit target or stop loss defined
                if not profit_target and not stop_loss:
                    continue

                coin = strategy_model.coin

                # Get balance from API (includes avg_buy_price from exchange)
                # Strategy manages ALL holdings of this coin, regardless of purchase source
                balance_data = api.get_balance(coin)
                coin_total = balance_data.get("total", 0.0)
                avg_buy_price = balance_data.get("avg_buy_price")

                # If no balance or no avg_buy_price, try DB as fallback
                if coin_total <= 0 or not avg_buy_price:
                    balance = db.query(Balance).filter(Balance.coin == coin).first()
                    if not balance or balance.total <= 0:
                        continue
                    coin_total = balance.total
                    avg_buy_price = balance.avg_buy_price
                    if not avg_buy_price:
                        continue

                # Get current price
                current_price = api.get_current_price(coin)
                if not current_price:
                    logger.warning(f"Could not get current price for {coin}")
                    continue

                # Calculate profit percentage
                buy_price = avg_buy_price
                profit_percentage = ((current_price - buy_price) / buy_price) * 100

                logger.debug(
                    f"{coin} - Buy: {buy_price}, Current: {current_price}, "
                    f"Profit: {profit_percentage:.2f}%"
                )

                # Check profit target
                if profit_target and profit_percentage >= profit_target:
                    logger.info(
                        f"Profit target reached for {coin} ({profit_percentage:.2f}% >= {profit_target}%) "
                        f"- executing sell order"
                    )
                    # Get available balance (use balance_data if from API, otherwise balance object)
                    available = balance_data.get("available", coin_total) if isinstance(balance_data, dict) else coin_total
                    self._execute_profit_target_sell(db, strategy_model, api, coin, available, "profit_target")

                # Check stop loss
                elif stop_loss and stop_loss > 0 and profit_percentage <= -stop_loss:
                    logger.info(
                        f"Stop loss triggered for {coin} ({profit_percentage:.2f}% <= -{stop_loss}%) "
                        f"- executing sell order"
                    )
                    # Get available balance
                    available = balance_data.get("available", coin_total) if isinstance(balance_data, dict) else coin_total
                    self._execute_profit_target_sell(db, strategy_model, api, coin, available, "stop_loss")

            except Exception as e:
                logger.error(f"Error checking profit/loss for strategy {strategy_model.name}: {e}")

    def _execute_profit_target_sell(
        self,
        db: Session,
        strategy_model: TradingStrategyModel,
        api: BithumbAPI,
        coin: str,
        amount: float,
        reason: str
    ):
        """Execute a sell order when profit target or stop loss is reached.

        Args:
            db: Database session
            strategy_model: Strategy that triggered the sell
            api: BithumbAPI instance for this user
            coin: Coin symbol
            amount: Amount to sell
            reason: Reason for selling ('profit_target' or 'stop_loss')
        """
        engine = TradingEngine(db, api)

        try:
            # Sell all available balance for this coin
            order = engine.execute_sell_order(
                coin=coin,
                amount=amount,
                strategy_id=strategy_model.id
            )

            reason_text = "Profit target" if reason == "profit_target" else "Stop loss"
            self._log_execution(
                db,
                strategy_model,
                signal="sell",
                executed=(order.status.value == "completed"),
                order_id=order.id,
                message=f"{reason_text} sell order: {order.amount} {coin}"
            )

            logger.info(f"{reason_text} sell executed for {coin}: {order.id}")

        except Exception as e:
            logger.error(f"Error executing {reason} sell for {coin}: {e}")
            self._log_execution(
                db,
                strategy_model,
                signal="sell",
                executed=False,
                error=str(e)
            )

    def _log_execution(
        self,
        db: Session,
        strategy_model: TradingStrategyModel,
        signal: Optional[str],
        executed: bool,
        order_id: Optional[int] = None,
        message: Optional[str] = None,
        error: Optional[str] = None
    ):
        """Log strategy execution.

        Args:
            db: Database session
            strategy_model: Strategy model
            signal: Signal type ("buy", "sell", or None)
            executed: Whether order was executed
            order_id: Order ID if executed
            message: Log message
            error: Error message if failed
        """
        log = StrategyExecutionLog(
            strategy_id=strategy_model.id,
            strategy_name=strategy_model.name,
            coin=strategy_model.coin,
            signal=signal,
            executed=executed,
            order_id=order_id,
            message=message,
            error=error
        )
        db.add(log)
        db.commit()


# Global scheduler instance
trading_scheduler = TradingScheduler()