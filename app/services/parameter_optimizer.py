"""Parameter optimization using Optuna for trading strategies."""
import optuna
from optuna.pruners import MedianPruner
from optuna.samplers import TPESampler
import logging
from typing import Dict, Any, Optional, Tuple
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from app.services.backtesting import Backtester
from app.services.strategy import (
    MovingAverageStrategy,
    RSIStrategy,
    BollingerBandStrategy,
    MACDStrategy,
    StochasticStrategy
)
from app.services.bithumb_api import BithumbAPI

logger = logging.getLogger(__name__)


class ParameterOptimizer:
    """Optimize trading strategy parameters using Bayesian optimization."""

    def __init__(self, api: BithumbAPI):
        """Initialize the parameter optimizer.

        Args:
            api: BithumbAPI instance
        """
        self.api = api

    def optimize_strategy(
        self,
        strategy_type: str,
        coin: str,
        n_trials: int = 50,
        initial_balance: float = 1000000,
        days_back: int = 90
    ) -> Dict[str, Any]:
        """Optimize parameters for a given strategy.

        Args:
            strategy_type: Type of strategy (moving_average, rsi, bollinger, macd, stochastic)
            coin: Coin symbol to optimize for
            n_trials: Number of optimization trials
            initial_balance: Initial balance for backtesting
            days_back: Number of days of historical data to use

        Returns:
            Dictionary with best parameters and performance metrics
        """
        logger.info(f"Starting parameter optimization for {strategy_type} on {coin}")
        logger.info(f"Trials: {n_trials}, Initial balance: {initial_balance:,.0f} KRW")

        # Create study with TPE sampler and Median pruner
        study = optuna.create_study(
            direction="maximize",
            sampler=TPESampler(seed=42),
            pruner=MedianPruner(n_startup_trials=5, n_warmup_steps=10)
        )

        # Optimize
        study.optimize(
            lambda trial: self._objective(
                trial, strategy_type, coin, initial_balance, days_back
            ),
            n_trials=n_trials,
            show_progress_bar=True
        )

        # Get best results
        best_params = study.best_params
        best_value = study.best_value

        # Run final backtest with best parameters
        performance = self._run_backtest(
            strategy_type, coin, best_params, initial_balance, days_back
        )

        logger.info(f"\nOptimization complete!")
        logger.info(f"Best parameters: {best_params}")
        logger.info(f"Best Sharpe ratio: {best_value:.4f}")
        logger.info(f"Total return: {performance['total_return']:.2f}%")
        logger.info(f"Win rate: {performance['win_rate']:.2f}%")

        return {
            "best_params": best_params,
            "sharpe_ratio": best_value,
            "performance": performance,
            "optimization_history": [
                {"trial": i, "value": trial.value, "params": trial.params}
                for i, trial in enumerate(study.trials)
            ]
        }

    def _objective(
        self,
        trial: optuna.Trial,
        strategy_type: str,
        coin: str,
        initial_balance: float,
        days_back: int
    ) -> float:
        """Objective function for optimization.

        Args:
            trial: Optuna trial object
            strategy_type: Type of strategy
            coin: Coin symbol
            initial_balance: Initial balance
            days_back: Days of historical data

        Returns:
            Sharpe ratio (metric to maximize)
        """
        # Suggest parameters based on strategy type
        params = self._suggest_parameters(trial, strategy_type)

        # Run backtest
        try:
            performance = self._run_backtest(
                strategy_type, coin, params, initial_balance, days_back
            )

            # Return Sharpe ratio as optimization metric
            # Penalize strategies with low number of trades
            if performance['num_trades'] < 5:
                return -10.0

            return performance['sharpe_ratio']

        except Exception as e:
            logger.warning(f"Trial failed: {e}")
            return -10.0

    def _suggest_parameters(self, trial: optuna.Trial, strategy_type: str) -> Dict[str, Any]:
        """Suggest parameters for the trial.

        Args:
            trial: Optuna trial object
            strategy_type: Type of strategy

        Returns:
            Dictionary of suggested parameters
        """
        if strategy_type == "moving_average":
            return {
                "short_period": trial.suggest_int("short_period", 3, 15),
                "long_period": trial.suggest_int("long_period", 15, 50),
                "profit_target": trial.suggest_float("profit_target", 1.0, 10.0),
                "stop_loss": trial.suggest_float("stop_loss", 1.0, 5.0),
            }

        elif strategy_type == "rsi":
            return {
                "period": trial.suggest_int("period", 7, 28),
                "oversold": trial.suggest_int("oversold", 20, 40),
                "overbought": trial.suggest_int("overbought", 60, 80),
                "profit_target": trial.suggest_float("profit_target", 1.0, 10.0),
                "stop_loss": trial.suggest_float("stop_loss", 1.0, 5.0),
            }

        elif strategy_type == "bollinger":
            return {
                "period": trial.suggest_int("period", 10, 40),
                "std_dev": trial.suggest_float("std_dev", 1.5, 3.0),
                "profit_target": trial.suggest_float("profit_target", 1.0, 10.0),
                "stop_loss": trial.suggest_float("stop_loss", 1.0, 5.0),
            }

        elif strategy_type == "macd":
            fast = trial.suggest_int("fast_period", 8, 16)
            slow = trial.suggest_int("slow_period", 20, 35)
            # Ensure slow > fast
            if slow <= fast:
                slow = fast + 5

            return {
                "fast_period": fast,
                "slow_period": slow,
                "signal_period": trial.suggest_int("signal_period", 5, 15),
                "profit_target": trial.suggest_float("profit_target", 1.0, 10.0),
                "stop_loss": trial.suggest_float("stop_loss", 1.0, 5.0),
            }

        elif strategy_type == "stochastic":
            return {
                "k_period": trial.suggest_int("k_period", 10, 21),
                "d_period": trial.suggest_int("d_period", 2, 5),
                "oversold": trial.suggest_int("oversold", 15, 30),
                "overbought": trial.suggest_int("overbought", 70, 85),
                "profit_target": trial.suggest_float("profit_target", 1.0, 10.0),
                "stop_loss": trial.suggest_float("stop_loss", 1.0, 5.0),
            }

        else:
            raise ValueError(f"Unknown strategy type: {strategy_type}")

    def _run_backtest(
        self,
        strategy_type: str,
        coin: str,
        params: Dict[str, Any],
        initial_balance: float,
        days_back: int
    ) -> Dict[str, float]:
        """Run backtest with given parameters.

        Args:
            strategy_type: Type of strategy
            coin: Coin symbol
            params: Strategy parameters
            initial_balance: Initial balance
            days_back: Days of historical data

        Returns:
            Performance metrics dictionary
        """
        # Create strategy with given parameters
        if strategy_type == "moving_average":
            strategy = MovingAverageStrategy(
                self.api,
                short_period=params["short_period"],
                long_period=params["long_period"]
            )
        elif strategy_type == "rsi":
            strategy = RSIStrategy(
                self.api,
                period=params["period"],
                oversold=params["oversold"],
                overbought=params["overbought"]
            )
        elif strategy_type == "bollinger":
            strategy = BollingerBandStrategy(
                self.api,
                period=params["period"],
                std_dev=params["std_dev"]
            )
        elif strategy_type == "macd":
            strategy = MACDStrategy(
                self.api,
                fast_period=params["fast_period"],
                slow_period=params["slow_period"],
                signal_period=params["signal_period"]
            )
        elif strategy_type == "stochastic":
            strategy = StochasticStrategy(
                self.api,
                k_period=params["k_period"],
                d_period=params["d_period"],
                oversold=params["oversold"],
                overbought=params["overbought"]
            )
        else:
            raise ValueError(f"Unknown strategy type: {strategy_type}")

        # Run backtest
        backtester = Backtester(api=self.api)

        result = backtester.run_backtest(
            strategy=strategy,
            coin=coin,
            initial_balance=initial_balance,
            days=days_back
        )

        return self._calculate_metrics(result, initial_balance)

    def _calculate_metrics(
        self,
        backtest_result,
        initial_balance: float
    ) -> Dict[str, float]:
        """Calculate performance metrics from backtest results.

        Args:
            backtest_result: BacktestResult object
            initial_balance: Initial balance

        Returns:
            Performance metrics
        """
        # BacktestResult already has most metrics calculated
        return {
            "total_return": backtest_result.total_return_pct,
            "sharpe_ratio": backtest_result.sharpe_ratio if backtest_result.sharpe_ratio != 0 else -10.0,
            "max_drawdown": backtest_result.max_drawdown,
            "win_rate": backtest_result.win_rate,
            "num_trades": backtest_result.total_trades
        }


def optimize_all_strategies(
    coin: str,
    n_trials: int = 50,
    api_key: str = "",
    api_secret: str = ""
) -> Dict[str, Dict[str, Any]]:
    """Optimize all strategy types for a given coin.

    Args:
        coin: Coin symbol
        n_trials: Number of trials per strategy
        api_key: Bithumb API key
        api_secret: Bithumb API secret

    Returns:
        Dictionary mapping strategy type to optimization results
    """
    api = BithumbAPI(api_key=api_key, api_secret=api_secret)
    optimizer = ParameterOptimizer(api)

    strategies = ["moving_average", "rsi", "bollinger", "macd", "stochastic"]
    results = {}

    for strategy_type in strategies:
        logger.info(f"\n{'='*80}")
        logger.info(f"Optimizing {strategy_type.upper()} strategy for {coin}")
        logger.info(f"{'='*80}")

        try:
            results[strategy_type] = optimizer.optimize_strategy(
                strategy_type=strategy_type,
                coin=coin,
                n_trials=n_trials
            )
        except Exception as e:
            logger.error(f"Failed to optimize {strategy_type}: {e}")
            results[strategy_type] = None

    return results