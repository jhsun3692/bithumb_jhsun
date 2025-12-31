"""Coin synchronization service for updating coin data from external API."""
import requests
from sqlalchemy.orm import Session
from typing import List, Dict
import logging

from app.models.coin import Coin
from app.services.bithumb_api import bithumb_api

logger = logging.getLogger(__name__)

# Major coins to display at the top
MAJOR_COINS = ["BTC", "ETH", "XRP", "ADA", "SOL", "DOGE", "DOT", "AVAX", "MATIC", "LINK"]


def fetch_coin_data_from_upbit() -> List[Dict]:
    """Fetch coin market data from Upbit API.

    Upbit provides comprehensive Korean/English names for cryptocurrencies.
    We use this as a reference for coin names.

    Returns:
        List of coin dictionaries with market, korean_name, and english_name
    """
    try:
        url = "https://api.upbit.com/v1/market/all?isDetails=false"
        headers = {"accept": "application/json"}

        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        coins = response.json()
        logger.info(f"Fetched {len(coins)} coins from Upbit API")
        return coins

    except Exception as e:
        logger.error(f"Error fetching coin data from Upbit: {e}")
        return []


def sync_coins_to_db(db: Session) -> Dict[str, int]:
    """Synchronize coin data to database.

    Fetches coin data from Upbit API and updates the database.
    Only includes coins that are available on Bithumb.

    Args:
        db: Database session

    Returns:
        Dictionary with sync statistics (added, updated, total)
    """
    stats = {"added": 0, "updated": 0, "total": 0}

    # Fetch coin data from Upbit
    upbit_coins = fetch_coin_data_from_upbit()
    if not upbit_coins:
        logger.warning("No coin data fetched from Upbit")
        return stats

    # Get available coins from Bithumb
    bithumb_coins = bithumb_api.get_available_coins()
    bithumb_coin_set = set(bithumb_coins)

    logger.info(f"Bithumb has {len(bithumb_coin_set)} available coins")

    # Filter Upbit data to only include KRW markets that exist on Bithumb
    for coin_data in upbit_coins:
        market = coin_data.get("market", "")

        # Only process KRW markets
        if not market.startswith("KRW-"):
            continue

        # Extract symbol (e.g., "BTC" from "KRW-BTC")
        symbol = market.replace("KRW-", "")

        # Skip if not available on Bithumb
        if symbol not in bithumb_coin_set:
            continue

        korean_name = coin_data.get("korean_name", "")
        english_name = coin_data.get("english_name", "")

        # Check if coin already exists in DB
        existing_coin = db.query(Coin).filter(Coin.symbol == symbol).first()

        if existing_coin:
            # Update existing coin
            existing_coin.korean_name = korean_name
            existing_coin.english_name = english_name
            existing_coin.market = market
            existing_coin.is_active = True
            existing_coin.is_major = symbol in MAJOR_COINS
            stats["updated"] += 1
        else:
            # Create new coin
            new_coin = Coin(
                symbol=symbol,
                korean_name=korean_name,
                english_name=english_name,
                market=market,
                is_active=True,
                is_major=symbol in MAJOR_COINS
            )
            db.add(new_coin)
            stats["added"] += 1

        stats["total"] += 1

    # Commit all changes
    db.commit()

    logger.info(
        f"Coin sync complete: {stats['added']} added, "
        f"{stats['updated']} updated, {stats['total']} total"
    )

    return stats


def get_coins_from_db(db: Session, active_only: bool = True) -> List[Coin]:
    """Get all coins from database.

    Args:
        db: Database session
        active_only: If True, only return active coins

    Returns:
        List of Coin objects, sorted with major coins first
    """
    query = db.query(Coin)

    if active_only:
        query = query.filter(Coin.is_active == True)

    # Order by is_major (descending) then symbol (ascending)
    # This puts major coins first, then alphabetical
    coins = query.order_by(Coin.is_major.desc(), Coin.symbol.asc()).all()

    return coins


def get_coin_names_dict(db: Session) -> Dict[str, Dict[str, str]]:
    """Get dictionary mapping coin symbols to their names.

    Args:
        db: Database session

    Returns:
        Dictionary with format: {
            "BTC": {"korean": "비트코인", "english": "Bitcoin"},
            ...
        }
    """
    coins = get_coins_from_db(db, active_only=True)

    coin_dict = {}
    for coin in coins:
        coin_dict[coin.symbol] = {
            "korean": coin.korean_name or "",
            "english": coin.english_name or ""
        }

    return coin_dict