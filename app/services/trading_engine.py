"""Trading engine for executing and managing orders."""
from datetime import datetime
from typing import Optional, List
from sqlalchemy.orm import Session
from app.models.database import Order, Trade, Balance, OrderType, OrderStatus
from app.services.bithumb_api import BithumbAPI
from app.core.config import get_settings
import logging

settings = get_settings()
logger = logging.getLogger(__name__)

# Bithumb minimum order amount in KRW
# Set to 5500 to ensure we're always above the exchange's 5000 KRW minimum
MIN_ORDER_AMOUNT_KRW = 5500


class TradingEngine:
    """Core trading engine for order execution."""

    def __init__(self, db: Session, api: Optional[BithumbAPI] = None):
        """Initialize trading engine.

        Args:
            db: Database session
            api: BithumbAPI instance (optional, creates new if not provided)
        """
        self.db = db
        self.api = api or BithumbAPI()

    def execute_buy_order(
        self,
        coin: str,
        amount: float,
        price: Optional[float] = None,
        strategy_id: Optional[int] = None
    ) -> Order:
        """Execute a buy order.

        Args:
            coin: Coin symbol
            amount: Amount to buy
            price: Price per coin (None for market order)

        Returns:
            Order object
        """
        # Get current price if not specified
        if price is None:
            price = self.api.get_current_price(coin)
            if price is None:
                order = Order(
                    order_type=OrderType.BUY,
                    coin=coin,
                    currency=settings.default_currency,
                    amount=amount,
                    price=0,
                    total=0,
                    status=OrderStatus.FAILED,
                    strategy_id=strategy_id,
                    error_message="Failed to get current price"
                )
                self.db.add(order)
                self.db.commit()
                return order

        total = amount * price

        # Check if order meets minimum amount requirement
        if total < MIN_ORDER_AMOUNT_KRW:
            # Adjust amount to meet minimum with 10% buffer
            min_amount_with_buffer = (MIN_ORDER_AMOUNT_KRW * 1.1) / price
            logger.warning(
                f"Order total {total:.0f} KRW is below minimum {MIN_ORDER_AMOUNT_KRW} KRW. "
                f"Adjusting amount from {amount:.6f} to {min_amount_with_buffer:.6f} {coin}"
            )
            amount = min_amount_with_buffer
            total = amount * price

        # Execute order via API
        if settings.trading_enabled:
            if price:
                result = self.api.buy_limit_order(coin, price, amount)
            else:
                result = self.api.buy_market_order(coin, amount)

            if result and result.get("status") == "0000":
                # Success
                order = Order(
                    order_type=OrderType.BUY,
                    coin=coin,
                    currency=settings.default_currency,
                    amount=amount,
                    price=price,
                    total=total,
                    status=OrderStatus.COMPLETED,
                    order_id=result.get("order_id"),
                    strategy_id=strategy_id
                )
                self.db.add(order)
                self.db.commit()

                # Create trade record
                self._create_trade_record(order)

                # Update balance
                self._update_balance(coin, amount, price)

                return order
            else:
                # Failed
                error_msg = result.get("message", "Unknown error") if result else "API call failed"
                order = Order(
                    order_type=OrderType.BUY,
                    coin=coin,
                    currency=settings.default_currency,
                    amount=amount,
                    price=price,
                    total=total,
                    status=OrderStatus.FAILED,
                    strategy_id=strategy_id,
                    error_message=error_msg
                )
                self.db.add(order)
                self.db.commit()
                return order
        else:
            # Trading disabled - create pending order
            order = Order(
                order_type=OrderType.BUY,
                coin=coin,
                currency=settings.default_currency,
                amount=amount,
                price=price,
                total=total,
                status=OrderStatus.PENDING,
                strategy_id=strategy_id,
                error_message="Trading is disabled"
            )
            self.db.add(order)
            self.db.commit()
            return order

    def execute_sell_order(
        self,
        coin: str,
        amount: float,
        price: Optional[float] = None,
        strategy_id: Optional[int] = None
    ) -> Order:
        """Execute a sell order.

        Args:
            coin: Coin symbol
            amount: Amount to sell
            price: Price per coin (None for market order)

        Returns:
            Order object
        """
        # Get current price if not specified
        if price is None:
            price = self.api.get_current_price(coin)
            if price is None:
                order = Order(
                    order_type=OrderType.SELL,
                    coin=coin,
                    currency=settings.default_currency,
                    amount=amount,
                    price=0,
                    total=0,
                    status=OrderStatus.FAILED,
                    strategy_id=strategy_id,
                    error_message="Failed to get current price"
                )
                self.db.add(order)
                self.db.commit()
                return order

        total = amount * price

        # Check if order meets minimum amount requirement
        if total < MIN_ORDER_AMOUNT_KRW:
            # Adjust amount to meet minimum with 10% buffer
            min_amount_with_buffer = (MIN_ORDER_AMOUNT_KRW * 1.1) / price
            logger.warning(
                f"Sell order total {total:.0f} KRW is below minimum {MIN_ORDER_AMOUNT_KRW} KRW. "
                f"Adjusting amount from {amount:.6f} to {min_amount_with_buffer:.6f} {coin}"
            )
            amount = min_amount_with_buffer
            total = amount * price

        # Execute order via API
        if settings.trading_enabled:
            if price:
                result = self.api.sell_limit_order(coin, price, amount)
            else:
                result = self.api.sell_market_order(coin, amount)

            if result and result.get("status") == "0000":
                # Success
                order = Order(
                    order_type=OrderType.SELL,
                    coin=coin,
                    currency=settings.default_currency,
                    amount=amount,
                    price=price,
                    total=total,
                    status=OrderStatus.COMPLETED,
                    order_id=result.get("order_id"),
                    strategy_id=strategy_id
                )
                self.db.add(order)
                self.db.commit()

                # Create trade record with profit calculation
                self._create_trade_record(order)

                # Update balance
                self._update_balance(coin, -amount, price)

                return order
            else:
                # Failed
                error_msg = result.get("message", "Unknown error") if result else "API call failed"
                order = Order(
                    order_type=OrderType.SELL,
                    coin=coin,
                    currency=settings.default_currency,
                    amount=amount,
                    price=price,
                    total=total,
                    status=OrderStatus.FAILED,
                    strategy_id=strategy_id,
                    error_message=error_msg
                )
                self.db.add(order)
                self.db.commit()
                return order
        else:
            # Trading disabled - create pending order
            order = Order(
                order_type=OrderType.SELL,
                coin=coin,
                currency=settings.default_currency,
                amount=amount,
                price=price,
                total=total,
                status=OrderStatus.PENDING,
                strategy_id=strategy_id,
                error_message="Trading is disabled"
            )
            self.db.add(order)
            self.db.commit()
            return order

    def _create_trade_record(self, order: Order) -> Trade:
        """Create a trade record from an order.

        Args:
            order: Order object

        Returns:
            Trade object
        """
        # Calculate profit for sell orders
        profit = None
        if order.order_type == OrderType.SELL:
            balance = self.db.query(Balance).filter(Balance.coin == order.coin).first()
            if balance and balance.avg_buy_price:
                profit = (order.price - balance.avg_buy_price) * order.amount

        trade = Trade(
            order_id=order.id,
            coin=order.coin,
            currency=order.currency,
            trade_type=order.order_type,
            amount=order.amount,
            price=order.price,
            total=order.total,
            fee=order.total * 0.0005,  # 0.05% fee (Bithumb's typical fee)
            profit=profit
        )
        self.db.add(trade)
        self.db.commit()
        return trade

    def _update_balance(self, coin: str, amount: float, price: float):
        """Update balance after a trade.

        Args:
            coin: Coin symbol
            amount: Amount traded (positive for buy, negative for sell)
            price: Trade price
        """
        balance = self.db.query(Balance).filter(Balance.coin == coin).first()

        if not balance:
            balance = Balance(
                coin=coin,
                total=0,
                available=0,
                in_use=0
            )
            self.db.add(balance)

        if amount > 0:  # Buy
            # Update average buy price
            total_value = (balance.total * (balance.avg_buy_price or 0)) + (amount * price)
            balance.total += amount
            balance.avg_buy_price = total_value / balance.total if balance.total > 0 else price
        else:  # Sell
            balance.total += amount  # amount is negative

        balance.available = balance.total
        self.db.commit()

    def get_orders(
        self,
        coin: Optional[str] = None,
        status: Optional[OrderStatus] = None,
        limit: int = 100
    ) -> List[Order]:
        """Get orders with optional filters.

        Args:
            coin: Filter by coin symbol
            status: Filter by order status
            limit: Maximum number of orders to return

        Returns:
            List of Order objects
        """
        query = self.db.query(Order)

        if coin:
            query = query.filter(Order.coin == coin)
        if status:
            query = query.filter(Order.status == status)

        return query.order_by(Order.created_at.desc()).limit(limit).all()

    def get_balances(self) -> List[Balance]:
        """Get all balances.

        Returns:
            List of Balance objects
        """
        return self.db.query(Balance).all()

    def sync_balance_from_api(self, coin: str) -> Balance:
        """Sync balance from Bithumb API.

        Args:
            coin: Coin symbol

        Returns:
            Updated Balance object
        """
        api_balance = self.api.get_balance(coin)

        balance = self.db.query(Balance).filter(Balance.coin == coin).first()
        if not balance:
            balance = Balance(coin=coin)
            self.db.add(balance)

        balance.total = api_balance["total"]
        balance.available = api_balance["available"]
        balance.in_use = api_balance["in_use"]
        self.db.commit()

        return balance