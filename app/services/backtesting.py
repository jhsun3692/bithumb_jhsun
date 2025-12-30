"""Backtesting service for testing strategies on historical data."""
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from app.services.bithumb_api import BithumbAPI
from app.services.strategy import TradingStrategy


class BacktestResult:
    """Container for backtest results."""

    def __init__(self):
        """Initialize backtest result."""
        self.trades: List[Dict[str, Any]] = []
        self.initial_balance: float = 0.0
        self.final_balance: float = 0.0
        self.total_return: float = 0.0
        self.total_return_pct: float = 0.0
        self.total_trades: int = 0
        self.winning_trades: int = 0
        self.losing_trades: int = 0
        self.win_rate: float = 0.0
        self.max_drawdown: float = 0.0
        self.sharpe_ratio: float = 0.0
        self.equity_curve: List[float] = []
        self.start_date: Optional[datetime] = None
        self.end_date: Optional[datetime] = None

    def calculate_metrics(self):
        """Calculate performance metrics from trades."""
        if not self.trades:
            return

        # Win rate
        if self.total_trades > 0:
            self.win_rate = (self.winning_trades / self.total_trades) * 100

        # Max drawdown
        if self.equity_curve:
            peak = self.equity_curve[0]
            max_dd = 0
            for value in self.equity_curve:
                if value > peak:
                    peak = value
                dd = (peak - value) / peak if peak > 0 else 0
                max_dd = max(max_dd, dd)
            self.max_drawdown = max_dd * 100

        # Sharpe ratio (simplified)
        if len(self.equity_curve) > 1:
            returns = pd.Series(self.equity_curve).pct_change().dropna()
            if len(returns) > 0 and returns.std() > 0:
                self.sharpe_ratio = (returns.mean() / returns.std()) * np.sqrt(252)  # Annualized

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary.

        Returns:
            Dictionary representation of result
        """
        return {
            "initial_balance": self.initial_balance,
            "final_balance": self.final_balance,
            "total_return": self.total_return,
            "total_return_pct": self.total_return_pct,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": self.win_rate,
            "max_drawdown": self.max_drawdown,
            "sharpe_ratio": self.sharpe_ratio,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "trades": self.trades
        }


class Backtester:
    """Backtest trading strategies on historical data."""

    def __init__(self, api: BithumbAPI):
        """Initialize backtester.

        Args:
            api: BithumbAPI instance
        """
        self.api = api

    def run_backtest(
        self,
        strategy: TradingStrategy,
        coin: str,
        initial_balance: float = 1000000.0,
        trade_amount_pct: float = 100.0,
        days: int = 30,
        interval: str = "day",
        fee_rate: float = 0.0025
    ) -> BacktestResult:
        """Run backtest on historical data.

        Args:
            strategy: Trading strategy to test
            coin: Coin symbol
            initial_balance: Initial KRW balance (default 1,000,000)
            trade_amount_pct: Percentage of balance to use per trade (default 100%)
            days: Number of days to backtest (default 30)
            interval: Data interval ('day', '1h', etc.)
            fee_rate: Trading fee rate (default 0.25%)

        Returns:
            BacktestResult object with performance metrics
        """
        result = BacktestResult()
        result.initial_balance = initial_balance

        # Get historical data
        df = self.api.get_ohlcv(coin, interval=interval)
        if df is None or len(df) == 0:
            return result

        # Limit to specified number of days
        df = df.tail(days)
        result.start_date = df.index[0].to_pydatetime()
        result.end_date = df.index[-1].to_pydatetime()

        # Initialize portfolio
        krw_balance = initial_balance
        coin_balance = 0.0
        position = None  # Track current position

        # Track equity curve
        equity_values = []

        # Simulate trading
        for i in range(len(df)):
            current_date = df.index[i]
            current_price = df.iloc[i]['close']

            # Calculate current equity
            equity = krw_balance + (coin_balance * current_price)
            equity_values.append(equity)

            # Need enough historical data for strategy
            if i < max(strategy.short_period if hasattr(strategy, 'short_period') else 0,
                      strategy.period if hasattr(strategy, 'period') else 0) + 1:
                continue

            # Get strategy signals
            # Note: We check signals at each point in time
            should_buy = strategy.should_buy(coin)
            should_sell = strategy.should_sell(coin)

            # Execute buy
            if should_buy and position is None and krw_balance > 0:
                trade_amount_krw = krw_balance * (trade_amount_pct / 100.0)
                fee = trade_amount_krw * fee_rate
                coin_amount = (trade_amount_krw - fee) / current_price

                coin_balance += coin_amount
                krw_balance -= trade_amount_krw

                position = {
                    "type": "buy",
                    "price": current_price,
                    "amount": coin_amount,
                    "date": current_date,
                    "fee": fee
                }

                result.trades.append({
                    "date": current_date.isoformat(),
                    "type": "buy",
                    "price": current_price,
                    "amount": coin_amount,
                    "total": trade_amount_krw,
                    "fee": fee
                })

            # Execute sell
            elif should_sell and position is not None and coin_balance > 0:
                trade_amount_coin = coin_balance
                trade_amount_krw = trade_amount_coin * current_price
                fee = trade_amount_krw * fee_rate
                net_amount = trade_amount_krw - fee

                krw_balance += net_amount
                coin_balance = 0.0

                # Calculate profit
                buy_price = position["price"]
                profit = (current_price - buy_price) * trade_amount_coin - position["fee"] - fee
                profit_pct = ((current_price - buy_price) / buy_price) * 100

                if profit > 0:
                    result.winning_trades += 1
                else:
                    result.losing_trades += 1

                result.trades.append({
                    "date": current_date.isoformat(),
                    "type": "sell",
                    "price": current_price,
                    "amount": trade_amount_coin,
                    "total": trade_amount_krw,
                    "fee": fee,
                    "profit": profit,
                    "profit_pct": profit_pct,
                    "buy_price": buy_price
                })

                position = None

        # Final equity
        final_price = df.iloc[-1]['close']
        result.final_balance = krw_balance + (coin_balance * final_price)
        result.total_return = result.final_balance - result.initial_balance
        result.total_return_pct = (result.total_return / result.initial_balance) * 100
        result.total_trades = len([t for t in result.trades if t["type"] == "sell"])
        result.equity_curve = equity_values

        # Calculate metrics
        result.calculate_metrics()

        return result

    def optimize_parameters(
        self,
        strategy_class,
        coin: str,
        param_ranges: Dict[str, List[Any]],
        initial_balance: float = 1000000.0,
        days: int = 30
    ) -> Dict[str, Any]:
        """Optimize strategy parameters using grid search.

        Args:
            strategy_class: Strategy class to test
            coin: Coin symbol
            param_ranges: Dictionary of parameter names to lists of values to test
            initial_balance: Initial balance
            days: Number of days to test

        Returns:
            Dictionary with best parameters and their performance
        """
        import itertools

        # Generate all parameter combinations
        param_names = list(param_ranges.keys())
        param_values = list(param_ranges.values())
        combinations = list(itertools.product(*param_values))

        best_result = None
        best_params = None
        best_return = float('-inf')

        results = []

        for combo in combinations:
            params = dict(zip(param_names, combo))

            # Create strategy instance with these parameters
            strategy = strategy_class(self.api, **params)

            # Run backtest
            result = self.run_backtest(
                strategy=strategy,
                coin=coin,
                initial_balance=initial_balance,
                days=days
            )

            # Track results
            results.append({
                "params": params,
                "return_pct": result.total_return_pct,
                "win_rate": result.win_rate,
                "max_drawdown": result.max_drawdown,
                "sharpe_ratio": result.sharpe_ratio
            })

            # Update best if this is better
            if result.total_return_pct > best_return:
                best_return = result.total_return_pct
                best_params = params
                best_result = result

        return {
            "best_params": best_params,
            "best_return_pct": best_return,
            "best_result": best_result.to_dict() if best_result else None,
            "all_results": sorted(results, key=lambda x: x["return_pct"], reverse=True)
        }