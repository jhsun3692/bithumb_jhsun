"""Trading strategy implementations."""
from typing import Optional, Dict, Any
import pandas as pd
import numpy as np
from app.services.bithumb_api import BithumbAPI


class TradingStrategy:
    """Base class for trading strategies."""

    def __init__(self, api: BithumbAPI):
        """Initialize strategy with API client.

        Args:
            api: BithumbAPI instance
        """
        self.api = api

    def should_buy(self, coin: str) -> bool:
        """Determine if should buy a coin.

        Args:
            coin: Coin symbol

        Returns:
            True if should buy, False otherwise
        """
        raise NotImplementedError

    def should_sell(self, coin: str) -> bool:
        """Determine if should sell a coin.

        Args:
            coin: Coin symbol

        Returns:
            True if should sell, False otherwise
        """
        raise NotImplementedError


class MovingAverageStrategy(TradingStrategy):
    """Moving Average Crossover Strategy.

    Buy when short MA crosses above long MA (golden cross)
    Sell when short MA crosses below long MA (death cross)
    """

    def __init__(self, api: BithumbAPI, short_period: int = 5, long_period: int = 20):
        """Initialize moving average strategy.

        Args:
            api: BithumbAPI instance
            short_period: Short-term moving average period
            long_period: Long-term moving average period
        """
        super().__init__(api)
        self.short_period = short_period
        self.long_period = long_period

    def _get_moving_averages(self, coin: str) -> Optional[Dict[str, float]]:
        """Calculate moving averages for a coin.

        Args:
            coin: Coin symbol

        Returns:
            Dictionary with short and long MA values, or None if failed
        """
        try:
            # Get OHLCV data
            df = self.api.get_ohlcv(coin)
            if df is None or len(df) < self.long_period:
                return None

            # Calculate moving averages
            short_ma = df['close'].rolling(window=self.short_period).mean().iloc[-1]
            long_ma = df['close'].rolling(window=self.long_period).mean().iloc[-1]

            # Get previous values for crossover detection
            prev_short_ma = df['close'].rolling(window=self.short_period).mean().iloc[-2]
            prev_long_ma = df['close'].rolling(window=self.long_period).mean().iloc[-2]

            return {
                "short_ma": short_ma,
                "long_ma": long_ma,
                "prev_short_ma": prev_short_ma,
                "prev_long_ma": prev_long_ma,
            }
        except Exception as e:
            print(f"Error calculating moving averages for {coin}: {e}")
            return None

    def should_buy(self, coin: str) -> bool:
        """Check for golden cross (buy signal).

        Args:
            coin: Coin symbol

        Returns:
            True if golden cross detected
        """
        mas = self._get_moving_averages(coin)
        if not mas:
            return False

        # Golden cross: short MA crosses above long MA
        golden_cross = (
            mas["prev_short_ma"] <= mas["prev_long_ma"] and
            mas["short_ma"] > mas["long_ma"]
        )

        return golden_cross

    def should_sell(self, coin: str) -> bool:
        """Check for death cross (sell signal).

        Args:
            coin: Coin symbol

        Returns:
            True if death cross detected
        """
        mas = self._get_moving_averages(coin)
        if not mas:
            return False

        # Death cross: short MA crosses below long MA
        death_cross = (
            mas["prev_short_ma"] >= mas["prev_long_ma"] and
            mas["short_ma"] < mas["long_ma"]
        )

        return death_cross


class RSIStrategy(TradingStrategy):
    """RSI (Relative Strength Index) Strategy.

    Buy when RSI < oversold threshold (default 30)
    Sell when RSI > overbought threshold (default 70)
    """

    def __init__(self, api: BithumbAPI, period: int = 14, oversold: int = 30, overbought: int = 70):
        """Initialize RSI strategy.

        Args:
            api: BithumbAPI instance
            period: RSI calculation period
            oversold: Oversold threshold
            overbought: Overbought threshold
        """
        super().__init__(api)
        self.period = period
        self.oversold = oversold
        self.overbought = overbought

    def _calculate_rsi(self, coin: str) -> Optional[float]:
        """Calculate RSI for a coin.

        Args:
            coin: Coin symbol

        Returns:
            RSI value or None if failed
        """
        try:
            df = self.api.get_ohlcv(coin)
            if df is None or len(df) < self.period + 1:
                return None

            # Calculate price changes
            delta = df['close'].diff()

            # Separate gains and losses
            gains = delta.where(delta > 0, 0)
            losses = -delta.where(delta < 0, 0)

            # Calculate average gains and losses
            avg_gains = gains.rolling(window=self.period).mean()
            avg_losses = losses.rolling(window=self.period).mean()

            # Calculate RS and RSI
            rs = avg_gains / avg_losses
            rsi = 100 - (100 / (1 + rs))

            return rsi.iloc[-1]
        except Exception as e:
            print(f"Error calculating RSI for {coin}: {e}")
            return None

    def should_buy(self, coin: str) -> bool:
        """Check if RSI indicates oversold condition.

        Args:
            coin: Coin symbol

        Returns:
            True if RSI < oversold threshold
        """
        rsi = self._calculate_rsi(coin)
        if rsi is None:
            return False

        return rsi < self.oversold

    def should_sell(self, coin: str) -> bool:
        """Check if RSI indicates overbought condition.

        Args:
            coin: Coin symbol

        Returns:
            True if RSI > overbought threshold
        """
        rsi = self._calculate_rsi(coin)
        if rsi is None:
            return False

        return rsi > self.overbought


class BollingerBandStrategy(TradingStrategy):
    """Bollinger Band Strategy.

    Buy when price touches lower band and bounces back
    Sell when price touches upper band and falls back
    """

    def __init__(self, api: BithumbAPI, period: int = 20, std_dev: float = 2.0):
        """Initialize Bollinger Band strategy.

        Args:
            api: BithumbAPI instance
            period: Moving average period
            std_dev: Standard deviation multiplier (default 2.0)
        """
        super().__init__(api)
        self.period = period
        self.std_dev = std_dev

    def _calculate_bollinger_bands(self, coin: str) -> Optional[Dict[str, float]]:
        """Calculate Bollinger Bands for a coin.

        Args:
            coin: Coin symbol

        Returns:
            Dictionary with upper, middle, lower bands and current price, or None if failed
        """
        try:
            df = self.api.get_ohlcv(coin)
            if df is None or len(df) < self.period + 1:
                return None

            # Calculate middle band (SMA)
            middle_band = df['close'].rolling(window=self.period).mean()

            # Calculate standard deviation
            std = df['close'].rolling(window=self.period).std()

            # Calculate upper and lower bands
            upper_band = middle_band + (std * self.std_dev)
            lower_band = middle_band - (std * self.std_dev)

            # Get current and previous values
            current_price = df['close'].iloc[-1]
            prev_price = df['close'].iloc[-2]

            return {
                "current_price": current_price,
                "prev_price": prev_price,
                "upper_band": upper_band.iloc[-1],
                "middle_band": middle_band.iloc[-1],
                "lower_band": lower_band.iloc[-1],
                "prev_upper_band": upper_band.iloc[-2],
                "prev_middle_band": middle_band.iloc[-2],
                "prev_lower_band": lower_band.iloc[-2],
            }
        except Exception as e:
            print(f"Error calculating Bollinger Bands for {coin}: {e}")
            return None

    def should_buy(self, coin: str) -> bool:
        """Check if should buy based on Bollinger Bands.

        Buy signal: Price was below lower band and now crosses back above it

        Args:
            coin: Coin symbol

        Returns:
            True if buy signal detected
        """
        bb = self._calculate_bollinger_bands(coin)
        if not bb:
            return False

        # Buy when price crosses back above lower band from below
        was_below = bb["prev_price"] < bb["prev_lower_band"]
        is_above = bb["current_price"] >= bb["lower_band"]

        return was_below and is_above

    def should_sell(self, coin: str) -> bool:
        """Check if should sell based on Bollinger Bands.

        Sell signal: Price was above upper band and now crosses back below it

        Args:
            coin: Coin symbol

        Returns:
            True if sell signal detected
        """
        bb = self._calculate_bollinger_bands(coin)
        if not bb:
            return False

        # Sell when price crosses back below upper band from above
        was_above = bb["prev_price"] > bb["prev_upper_band"]
        is_below = bb["current_price"] <= bb["upper_band"]

        return was_above and is_below

    def get_bands_info(self, coin: str) -> Optional[Dict[str, float]]:
        """Get current Bollinger Bands information.

        Args:
            coin: Coin symbol

        Returns:
            Dictionary with band values and current price
        """
        return self._calculate_bollinger_bands(coin)


class MACDStrategy(TradingStrategy):
    """MACD (Moving Average Convergence Divergence) Strategy.

    Buy when MACD line crosses above signal line (bullish crossover)
    Sell when MACD line crosses below signal line (bearish crossover)
    """

    def __init__(
        self,
        api: BithumbAPI,
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9
    ):
        """Initialize MACD strategy.

        Args:
            api: BithumbAPI instance
            fast_period: Fast EMA period (default 12)
            slow_period: Slow EMA period (default 26)
            signal_period: Signal line period (default 9)
        """
        super().__init__(api)
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period

    def _calculate_macd(self, coin: str) -> Optional[Dict[str, float]]:
        """Calculate MACD values for a coin.

        Args:
            coin: Coin symbol

        Returns:
            Dictionary with MACD, signal line, and histogram values, or None if failed
        """
        try:
            df = self.api.get_ohlcv(coin)
            if df is None or len(df) < self.slow_period + self.signal_period:
                return None

            # Calculate EMAs
            fast_ema = df['close'].ewm(span=self.fast_period, adjust=False).mean()
            slow_ema = df['close'].ewm(span=self.slow_period, adjust=False).mean()

            # Calculate MACD line
            macd_line = fast_ema - slow_ema

            # Calculate signal line
            signal_line = macd_line.ewm(span=self.signal_period, adjust=False).mean()

            # Calculate histogram
            histogram = macd_line - signal_line

            return {
                "macd": macd_line.iloc[-1],
                "signal": signal_line.iloc[-1],
                "histogram": histogram.iloc[-1],
                "prev_macd": macd_line.iloc[-2],
                "prev_signal": signal_line.iloc[-2],
            }
        except Exception as e:
            print(f"Error calculating MACD for {coin}: {e}")
            return None

    def should_buy(self, coin: str) -> bool:
        """Check for bullish MACD crossover (buy signal).

        Args:
            coin: Coin symbol

        Returns:
            True if bullish crossover detected
        """
        macd = self._calculate_macd(coin)
        if not macd:
            return False

        # Bullish crossover: MACD crosses above signal line
        bullish_cross = (
            macd["prev_macd"] <= macd["prev_signal"] and
            macd["macd"] > macd["signal"]
        )

        return bullish_cross

    def should_sell(self, coin: str) -> bool:
        """Check for bearish MACD crossover (sell signal).

        Args:
            coin: Coin symbol

        Returns:
            True if bearish crossover detected
        """
        macd = self._calculate_macd(coin)
        if not macd:
            return False

        # Bearish crossover: MACD crosses below signal line
        bearish_cross = (
            macd["prev_macd"] >= macd["prev_signal"] and
            macd["macd"] < macd["signal"]
        )

        return bearish_cross


class StochasticStrategy(TradingStrategy):
    """Stochastic Oscillator Strategy.

    Buy when %K crosses above %D in oversold region
    Sell when %K crosses below %D in overbought region
    """

    def __init__(
        self,
        api: BithumbAPI,
        k_period: int = 14,
        d_period: int = 3,
        oversold: int = 20,
        overbought: int = 80
    ):
        """Initialize Stochastic strategy.

        Args:
            api: BithumbAPI instance
            k_period: %K period (default 14)
            d_period: %D smoothing period (default 3)
            oversold: Oversold threshold (default 20)
            overbought: Overbought threshold (default 80)
        """
        super().__init__(api)
        self.k_period = k_period
        self.d_period = d_period
        self.oversold = oversold
        self.overbought = overbought

    def _calculate_stochastic(self, coin: str) -> Optional[Dict[str, float]]:
        """Calculate Stochastic Oscillator values.

        Args:
            coin: Coin symbol

        Returns:
            Dictionary with %K and %D values, or None if failed
        """
        try:
            df = self.api.get_ohlcv(coin)
            if df is None or len(df) < self.k_period + self.d_period:
                return None

            # Calculate %K
            lowest_low = df['low'].rolling(window=self.k_period).min()
            highest_high = df['high'].rolling(window=self.k_period).max()

            k_percent = 100 * (df['close'] - lowest_low) / (highest_high - lowest_low)

            # Calculate %D (smoothed %K)
            d_percent = k_percent.rolling(window=self.d_period).mean()

            return {
                "k": k_percent.iloc[-1],
                "d": d_percent.iloc[-1],
                "prev_k": k_percent.iloc[-2],
                "prev_d": d_percent.iloc[-2],
            }
        except Exception as e:
            print(f"Error calculating Stochastic for {coin}: {e}")
            return None

    def should_buy(self, coin: str) -> bool:
        """Check for buy signal (bullish crossover in oversold region).

        Args:
            coin: Coin symbol

        Returns:
            True if buy signal detected
        """
        stoch = self._calculate_stochastic(coin)
        if not stoch:
            return False

        # Buy when %K crosses above %D in oversold region
        oversold_region = stoch["k"] < self.oversold
        bullish_cross = (
            stoch["prev_k"] <= stoch["prev_d"] and
            stoch["k"] > stoch["d"]
        )

        return oversold_region and bullish_cross

    def should_sell(self, coin: str) -> bool:
        """Check for sell signal (bearish crossover in overbought region).

        Args:
            coin: Coin symbol

        Returns:
            True if sell signal detected
        """
        stoch = self._calculate_stochastic(coin)
        if not stoch:
            return False

        # Sell when %K crosses below %D in overbought region
        overbought_region = stoch["k"] > self.overbought
        bearish_cross = (
            stoch["prev_k"] >= stoch["prev_d"] and
            stoch["k"] < stoch["d"]
        )

        return overbought_region and bearish_cross


class CompositeStrategy(TradingStrategy):
    """Composite Strategy that combines multiple strategies.

    Buy/sell signals are generated when multiple strategies agree.
    """

    def __init__(
        self,
        api: BithumbAPI,
        strategies: list,
        min_confirmations: int = 2
    ):
        """Initialize Composite strategy.

        Args:
            api: BithumbAPI instance
            strategies: List of strategy instances to combine
            min_confirmations: Minimum number of strategies that must agree (default 2)
        """
        super().__init__(api)
        self.strategies = strategies
        self.min_confirmations = min_confirmations

    def should_buy(self, coin: str) -> bool:
        """Check if enough strategies agree on buy signal.

        Args:
            coin: Coin symbol

        Returns:
            True if minimum confirmations met
        """
        buy_signals = sum(1 for strategy in self.strategies if strategy.should_buy(coin))
        return buy_signals >= self.min_confirmations

    def should_sell(self, coin: str) -> bool:
        """Check if enough strategies agree on sell signal.

        Args:
            coin: Coin symbol

        Returns:
            True if minimum confirmations met
        """
        sell_signals = sum(1 for strategy in self.strategies if strategy.should_sell(coin))
        return sell_signals >= self.min_confirmations