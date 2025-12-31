"""Anomaly detection for trading system."""
import logging
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from scipy import stats
from sklearn.ensemble import IsolationForest

from app.services.bithumb_api import BithumbAPI

logger = logging.getLogger(__name__)


class AnomalyDetector:
    """Detect anomalies in price, volume, and trading performance."""

    def __init__(self, api: BithumbAPI):
        """Initialize the anomaly detector.

        Args:
            api: BithumbAPI instance
        """
        self.api = api

    def detect_price_anomalies(
        self,
        coin: str,
        threshold: float = 3.0,
        lookback_days: int = 30
    ) -> Dict[str, Any]:
        """Detect price anomalies using statistical methods.

        Args:
            coin: Coin symbol
            threshold: Z-score threshold for anomaly detection
            lookback_days: Number of days to look back

        Returns:
            Dictionary with anomaly detection results
        """
        logger.info(f"Detecting price anomalies for {coin}")

        # Get historical data
        df = self.api.get_ohlcv(coin, interval="day")
        if df is None or len(df) < lookback_days:
            logger.warning(f"Insufficient data for {coin}")
            return {"error": "Insufficient data"}

        # Use last N days
        df = df.tail(lookback_days)

        # Calculate price change percentage
        df['price_change_pct'] = df['close'].pct_change() * 100

        # Calculate Z-scores
        mean_change = df['price_change_pct'].mean()
        std_change = df['price_change_pct'].std()
        df['z_score'] = (df['price_change_pct'] - mean_change) / std_change

        # Detect anomalies
        anomalies = df[abs(df['z_score']) > threshold].copy()

        current_price = df['close'].iloc[-1]
        current_change = df['price_change_pct'].iloc[-1]
        current_z_score = df['z_score'].iloc[-1]

        is_anomaly = abs(current_z_score) > threshold

        result = {
            "coin": coin,
            "current_price": current_price,
            "current_change_pct": current_change,
            "current_z_score": current_z_score,
            "is_anomaly": is_anomaly,
            "anomaly_type": self._classify_anomaly(current_z_score, threshold),
            "historical_anomalies": len(anomalies),
            "mean_change": mean_change,
            "std_change": std_change,
            "severity": self._calculate_severity(current_z_score),
            "recommendation": self._get_recommendation(current_z_score, threshold)
        }

        if is_anomaly:
            logger.warning(
                f"⚠️ Price anomaly detected for {coin}! "
                f"Change: {current_change:.2f}%, Z-score: {current_z_score:.2f}"
            )

        return result

    def detect_volume_anomalies(
        self,
        coin: str,
        threshold: float = 2.5,
        lookback_days: int = 30
    ) -> Dict[str, Any]:
        """Detect volume anomalies.

        Args:
            coin: Coin symbol
            threshold: Z-score threshold for anomaly detection
            lookback_days: Number of days to look back

        Returns:
            Dictionary with volume anomaly detection results
        """
        logger.info(f"Detecting volume anomalies for {coin}")

        # Get historical data
        df = self.api.get_ohlcv(coin, interval="day")
        if df is None or len(df) < lookback_days:
            logger.warning(f"Insufficient data for {coin}")
            return {"error": "Insufficient data"}

        # Use last N days
        df = df.tail(lookback_days)

        # Calculate volume statistics
        mean_volume = df['volume'].mean()
        std_volume = df['volume'].std()
        df['volume_z_score'] = (df['volume'] - mean_volume) / std_volume

        current_volume = df['volume'].iloc[-1]
        current_z_score = df['volume_z_score'].iloc[-1]

        is_anomaly = abs(current_z_score) > threshold

        result = {
            "coin": coin,
            "current_volume": current_volume,
            "mean_volume": mean_volume,
            "volume_z_score": current_z_score,
            "is_anomaly": is_anomaly,
            "anomaly_type": "high_volume" if current_z_score > threshold else
                           "low_volume" if current_z_score < -threshold else "normal",
            "severity": self._calculate_severity(current_z_score),
            "volume_ratio": current_volume / mean_volume if mean_volume > 0 else 0
        }

        if is_anomaly:
            logger.warning(
                f"⚠️ Volume anomaly detected for {coin}! "
                f"Current: {current_volume:,.0f}, Mean: {mean_volume:,.0f}, "
                f"Z-score: {current_z_score:.2f}"
            )

        return result

    def detect_strategy_performance_anomalies(
        self,
        trades: List[Dict[str, Any]],
        lookback_trades: int = 20
    ) -> Dict[str, Any]:
        """Detect anomalies in strategy performance.

        Args:
            trades: List of trade dictionaries
            lookback_trades: Number of recent trades to analyze

        Returns:
            Performance anomaly detection results
        """
        logger.info(f"Analyzing strategy performance for {len(trades)} trades")

        if len(trades) < 10:
            return {
                "error": "Insufficient trades for analysis",
                "num_trades": len(trades)
            }

        # Extract profits from trades
        profits = [trade.get("profit", 0) for trade in trades[-lookback_trades:]]
        profits_array = np.array(profits)

        # Calculate metrics
        mean_profit = np.mean(profits_array)
        std_profit = np.std(profits_array)
        win_rate = len([p for p in profits if p > 0]) / len(profits) * 100

        # Detect consecutive losses
        consecutive_losses = self._count_consecutive_losses(profits)
        max_consecutive_losses = self._max_consecutive_losses(profits)

        # Detect drawdown
        cumulative_profit = np.cumsum(profits_array)
        running_max = np.maximum.accumulate(cumulative_profit)
        drawdown = (cumulative_profit - running_max)
        max_drawdown = np.min(drawdown) if len(drawdown) > 0 else 0
        current_drawdown = drawdown[-1] if len(drawdown) > 0 else 0

        # Anomaly flags
        is_performance_degrading = (
            consecutive_losses >= 5 or
            win_rate < 30 or
            abs(current_drawdown) > abs(mean_profit) * 10
        )

        result = {
            "num_trades_analyzed": len(profits),
            "mean_profit": mean_profit,
            "std_profit": std_profit,
            "win_rate": win_rate,
            "consecutive_losses": consecutive_losses,
            "max_consecutive_losses": max_consecutive_losses,
            "current_drawdown": current_drawdown,
            "max_drawdown": max_drawdown,
            "is_anomaly": is_performance_degrading,
            "severity": self._calculate_performance_severity(
                consecutive_losses, win_rate, current_drawdown
            ),
            "recommendation": self._get_performance_recommendation(
                consecutive_losses, win_rate, current_drawdown
            )
        }

        if is_performance_degrading:
            logger.warning(
                f"⚠️ Strategy performance anomaly detected! "
                f"Win rate: {win_rate:.1f}%, "
                f"Consecutive losses: {consecutive_losses}, "
                f"Current drawdown: {current_drawdown:,.0f} KRW"
            )

        return result

    def comprehensive_anomaly_check(
        self,
        coin: str,
        trades: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Run comprehensive anomaly detection.

        Args:
            coin: Coin symbol
            trades: Optional list of trades for performance analysis

        Returns:
            Comprehensive anomaly detection results
        """
        logger.info(f"Running comprehensive anomaly check for {coin}")

        results = {
            "coin": coin,
            "timestamp": datetime.now().isoformat(),
            "price_anomaly": self.detect_price_anomalies(coin),
            "volume_anomaly": self.detect_volume_anomalies(coin),
        }

        if trades:
            results["performance_anomaly"] = self.detect_strategy_performance_anomalies(trades)

        # Calculate overall risk level
        risk_level = self._calculate_overall_risk(results)
        results["overall_risk_level"] = risk_level
        results["should_pause_trading"] = risk_level in ["high", "critical"]

        return results

    def _classify_anomaly(self, z_score: float, threshold: float) -> str:
        """Classify type of price anomaly.

        Args:
            z_score: Z-score value
            threshold: Threshold value

        Returns:
            Anomaly type string
        """
        if z_score > threshold:
            return "sudden_spike"
        elif z_score < -threshold:
            return "sudden_drop"
        else:
            return "normal"

    def _calculate_severity(self, z_score: float) -> str:
        """Calculate severity level based on z-score.

        Args:
            z_score: Z-score value

        Returns:
            Severity level (low, medium, high, critical)
        """
        abs_z = abs(z_score)
        if abs_z < 2:
            return "low"
        elif abs_z < 3:
            return "medium"
        elif abs_z < 4:
            return "high"
        else:
            return "critical"

    def _get_recommendation(self, z_score: float, threshold: float) -> str:
        """Get recommendation based on anomaly detection.

        Args:
            z_score: Z-score value
            threshold: Threshold value

        Returns:
            Recommendation string
        """
        if z_score > threshold:
            if z_score > threshold * 1.5:
                return "CRITICAL: Extreme price spike detected. Consider pausing trading."
            return "WARNING: Unusual price increase. Monitor closely before buying."
        elif z_score < -threshold:
            if z_score < -threshold * 1.5:
                return "CRITICAL: Extreme price drop detected. Consider emergency exit."
            return "WARNING: Unusual price decrease. Avoid buying, consider stop-loss."
        else:
            return "Normal market conditions. Continue with strategy."

    def _count_consecutive_losses(self, profits: List[float]) -> int:
        """Count current consecutive losses.

        Args:
            profits: List of profit values

        Returns:
            Number of consecutive losses
        """
        count = 0
        for profit in reversed(profits):
            if profit < 0:
                count += 1
            else:
                break
        return count

    def _max_consecutive_losses(self, profits: List[float]) -> int:
        """Find maximum consecutive losses.

        Args:
            profits: List of profit values

        Returns:
            Maximum consecutive losses
        """
        max_count = 0
        current_count = 0
        for profit in profits:
            if profit < 0:
                current_count += 1
                max_count = max(max_count, current_count)
            else:
                current_count = 0
        return max_count

    def _calculate_performance_severity(
        self,
        consecutive_losses: int,
        win_rate: float,
        current_drawdown: float
    ) -> str:
        """Calculate performance severity.

        Args:
            consecutive_losses: Number of consecutive losses
            win_rate: Win rate percentage
            current_drawdown: Current drawdown amount

        Returns:
            Severity level
        """
        severity_score = 0

        # Consecutive losses contribution
        if consecutive_losses >= 7:
            severity_score += 3
        elif consecutive_losses >= 5:
            severity_score += 2
        elif consecutive_losses >= 3:
            severity_score += 1

        # Win rate contribution
        if win_rate < 25:
            severity_score += 3
        elif win_rate < 35:
            severity_score += 2
        elif win_rate < 45:
            severity_score += 1

        # Drawdown contribution (arbitrary threshold)
        if abs(current_drawdown) > 100000:
            severity_score += 3
        elif abs(current_drawdown) > 50000:
            severity_score += 2
        elif abs(current_drawdown) > 20000:
            severity_score += 1

        if severity_score >= 7:
            return "critical"
        elif severity_score >= 5:
            return "high"
        elif severity_score >= 3:
            return "medium"
        else:
            return "low"

    def _get_performance_recommendation(
        self,
        consecutive_losses: int,
        win_rate: float,
        current_drawdown: float
    ) -> str:
        """Get performance-based recommendation.

        Args:
            consecutive_losses: Number of consecutive losses
            win_rate: Win rate percentage
            current_drawdown: Current drawdown amount

        Returns:
            Recommendation string
        """
        if consecutive_losses >= 7 or win_rate < 25 or abs(current_drawdown) > 100000:
            return "CRITICAL: Strategy performance severely degraded. Pause trading and review parameters."
        elif consecutive_losses >= 5 or win_rate < 35 or abs(current_drawdown) > 50000:
            return "WARNING: Strategy underperforming. Consider parameter re-optimization."
        elif consecutive_losses >= 3 or win_rate < 45:
            return "CAUTION: Monitor strategy closely. May need adjustment soon."
        else:
            return "Strategy performance is acceptable. Continue monitoring."

    def _calculate_overall_risk(self, results: Dict[str, Any]) -> str:
        """Calculate overall risk level from all anomaly checks.

        Args:
            results: Combined anomaly detection results

        Returns:
            Overall risk level
        """
        risk_score = 0

        # Price anomaly contribution
        price_anomaly = results.get("price_anomaly", {})
        if price_anomaly.get("is_anomaly"):
            severity = price_anomaly.get("severity", "low")
            if severity == "critical":
                risk_score += 4
            elif severity == "high":
                risk_score += 3
            elif severity == "medium":
                risk_score += 2
            else:
                risk_score += 1

        # Volume anomaly contribution
        volume_anomaly = results.get("volume_anomaly", {})
        if volume_anomaly.get("is_anomaly"):
            severity = volume_anomaly.get("severity", "low")
            if severity == "critical":
                risk_score += 3
            elif severity == "high":
                risk_score += 2
            elif severity == "medium":
                risk_score += 1

        # Performance anomaly contribution
        perf_anomaly = results.get("performance_anomaly", {})
        if perf_anomaly.get("is_anomaly"):
            severity = perf_anomaly.get("severity", "low")
            if severity == "critical":
                risk_score += 4
            elif severity == "high":
                risk_score += 3
            elif severity == "medium":
                risk_score += 2
            else:
                risk_score += 1

        # Map score to risk level
        if risk_score >= 8:
            return "critical"
        elif risk_score >= 5:
            return "high"
        elif risk_score >= 3:
            return "medium"
        elif risk_score >= 1:
            return "low"
        else:
            return "minimal"