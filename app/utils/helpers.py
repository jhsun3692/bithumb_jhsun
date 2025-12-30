"""Utility helper functions."""
from typing import Optional
from datetime import datetime


def format_currency(amount: float, currency: str = "KRW") -> str:
    """Format currency amount.

    Args:
        amount: Amount to format
        currency: Currency code

    Returns:
        Formatted currency string
    """
    if currency == "KRW":
        return f"{amount:,.0f} {currency}"
    else:
        return f"{amount:,.8f} {currency}"


def calculate_profit_percentage(buy_price: float, sell_price: float) -> float:
    """Calculate profit percentage.

    Args:
        buy_price: Purchase price
        sell_price: Sell price

    Returns:
        Profit percentage
    """
    if buy_price == 0:
        return 0.0
    return ((sell_price - buy_price) / buy_price) * 100


def format_timestamp(dt: datetime) -> str:
    """Format datetime to string.

    Args:
        dt: Datetime object

    Returns:
        Formatted datetime string
    """
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def validate_coin_symbol(coin: str) -> bool:
    """Validate coin symbol format.

    Args:
        coin: Coin symbol

    Returns:
        True if valid, False otherwise
    """
    # Basic validation - uppercase letters only, 2-10 characters
    return coin.isalpha() and coin.isupper() and 2 <= len(coin) <= 10