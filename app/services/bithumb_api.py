"""Bithumb API 2.0 integration service."""
import hashlib
import hmac
import time
import requests
import jwt
import uuid
import json
from typing import Optional, Dict, Any
from urllib.parse import urlencode
from app.core.config import get_settings
import pybithumb  # Keep for public API only (prices, OHLCV)

settings = get_settings()


class BithumbAPI:
    """Wrapper class for Bithumb API 2.0 operations."""

    BASE_URL = "https://api.bithumb.com"

    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None):
        """Initialize Bithumb API client.

        Args:
            api_key: Bithumb API access key (defaults to settings)
            api_secret: Bithumb API secret key (defaults to settings)
        """
        self.api_key = api_key or settings.bithumb_api_key
        self.api_secret = api_secret or settings.bithumb_api_secret

        print(f"Initializing Bithumb API 2.0...")
        print(f"API Key present: {bool(self.api_key)}")
        print(f"API Secret present: {bool(self.api_secret)}")

        if self.api_key and self.api_secret:
            print(f"Bithumb API 2.0 client initialized successfully")
        else:
            print("Warning: API credentials not provided, private features will be disabled")

    def _generate_signature(self, endpoint: str, params: Dict[str, Any]) -> str:
        """Generate HMAC-SHA512 signature for API authentication.

        Args:
            endpoint: API endpoint path
            params: Request parameters

        Returns:
            Signature string
        """
        # Add nonce (timestamp in microseconds)
        params['endpoint'] = endpoint

        # Create query string
        query_string = urlencode(params)

        # Create signature
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha512
        ).hexdigest()

        return signature

    def _call_private_api(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Call private API with HMAC-SHA512 authentication.

        Args:
            endpoint: API endpoint (e.g., '/info/balance')
            params: Request parameters

        Returns:
            API response dictionary
        """
        if not self.api_key or not self.api_secret:
            return {"status": "5100", "message": "API credentials not configured"}

        if params is None:
            params = {}

        # Add required parameters
        params['apiKey'] = self.api_key
        params['nonce'] = str(int(time.time() * 1000))

        # Generate signature
        signature = self._generate_signature(endpoint, params.copy())

        # Prepare headers
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Api-Key': self.api_key,
            'Api-Sign': signature,
            'Api-Nonce': params['nonce']
        }

        url = f"{self.BASE_URL}{endpoint}"

        try:
            response = requests.post(url, headers=headers, data=params, timeout=10)
            response.raise_for_status()
            result = response.json()
            print(f"API Response: {result}")
            return result
        except requests.exceptions.RequestException as e:
            print(f"API request error: {e}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_response = e.response.json()
                    print(f"Error response: {error_response}")
                    return error_response
                except:
                    return {"status": "5100", "message": str(e)}
            return {"status": "5100", "message": str(e)}

    def get_current_price(self, coin: str) -> Optional[float]:
        """Get current market price for a coin using pybithumb (public API).

        Args:
            coin: Coin symbol (e.g., "BTC", "ETH")

        Returns:
            Current price or None if failed
        """
        try:
            price = pybithumb.get_current_price(coin)
            return float(price) if price else None
        except Exception as e:
            print(f"Error getting current price for {coin}: {e}")
            return None

    def get_orderbook(self, coin: str) -> Optional[Dict[str, Any]]:
        """Get orderbook for a coin using pybithumb (public API).

        Args:
            coin: Coin symbol

        Returns:
            Orderbook data or None if failed
        """
        try:
            orderbook = pybithumb.get_orderbook(coin)
            return orderbook
        except Exception as e:
            print(f"Error getting orderbook for {coin}: {e}")
            return None

    def get_balance(self, coin: str = "BTC") -> Dict[str, float]:
        """Get balance for a specific coin using Bithumb API 2.0 (JWT method).

        Args:
            coin: Coin symbol

        Returns:
            Dictionary with total, available, and in_use amounts
        """
        print(f"Getting balance for {coin} via Bithumb API 2.0 (JWT)...")

        if not self.api_key or not self.api_secret:
            print("API credentials not configured")
            return {"total": 0.0, "available": 0.0, "in_use": 0.0, "avg_buy_price": None}

        try:
            # Create JWT payload (no query params for GET /v1/accounts)
            payload = {
                'access_key': self.api_key,
                'nonce': str(uuid.uuid4()),
                'timestamp': round(time.time() * 1000),
            }

            # Generate JWT token
            jwt_token = jwt.encode(payload, self.api_secret, algorithm='HS256')
            authorization_token = f'Bearer {jwt_token}'

            # Headers
            headers = {
                'Authorization': authorization_token,
            }

            # Call API
            url = f"{self.BASE_URL}/v1/accounts"
            response = requests.get(url, headers=headers, timeout=10)

            print(f"Response status: {response.status_code}")

            if response.status_code != 200:
                print(f"API Error: {response.status_code} - {response.text}")
                return {"total": 0.0, "available": 0.0, "in_use": 0.0, "avg_buy_price": None}

            accounts = response.json()
            print(f"DEBUG: Accounts response: {accounts}")

            # Find the account for this coin
            for account in accounts:
                # Match currency (BTC, ETH, KRW, etc.)
                if account.get("currency") == coin:
                    balance = float(account.get("balance", 0))
                    locked = float(account.get("locked", 0))
                    avg_buy_price = float(account.get("avg_buy_price", 0))

                    return {
                        "total": balance + locked,
                        "available": balance,
                        "in_use": locked,
                        "avg_buy_price": avg_buy_price if avg_buy_price > 0 else None,
                    }

            # Coin not found in accounts (no balance)
            return {
                "total": 0.0,
                "available": 0.0,
                "in_use": 0.0,
                "avg_buy_price": None,
            }

        except Exception as e:
            print(f"Error getting balance for {coin}: {e}")
            import traceback
            traceback.print_exc()
            return {"total": 0.0, "available": 0.0, "in_use": 0.0, "avg_buy_price": None}

    def get_krw_balance(self) -> Dict[str, float]:
        """Get KRW (Korean Won) balance.

        Returns:
            Dictionary with total, available, and in_use amounts
        """
        # Just call get_balance with "KRW"
        return self.get_balance("KRW")

    def buy_market_order(self, coin: str, amount: float) -> Optional[Dict[str, Any]]:
        """Place a market buy order using Bithumb API 2.0 (JWT method).

        Args:
            coin: Coin symbol (e.g., "BTC", "ETH")
            amount: Amount in KRW to spend

        Returns:
            Order result or None if failed
        """
        if not self.api_key or not self.api_secret:
            return {"status": "5100", "message": "API credentials not configured"}

        try:
            print(f"Placing market buy order for {coin}: {amount} KRW")

            # Request body (market buy order - price is KRW amount)
            request_body = {
                'market': f'KRW-{coin}',
                'side': 'bid',  # bid = buy
                'ord_type': 'price',  # market order by price (KRW amount)
                'price': int(amount)  # Amount in KRW as integer
            }

            # Generate query hash
            query = urlencode(request_body).encode()
            hash_obj = hashlib.sha512()
            hash_obj.update(query)
            query_hash = hash_obj.hexdigest()

            # Create JWT payload
            payload = {
                'access_key': self.api_key,
                'nonce': str(uuid.uuid4()),
                'timestamp': round(time.time() * 1000),
                'query_hash': query_hash,
                'query_hash_alg': 'SHA512',
            }

            # Generate JWT token
            jwt_token = jwt.encode(payload, self.api_secret, algorithm='HS256')
            authorization_token = f'Bearer {jwt_token}'

            # Headers
            headers = {
                'Authorization': authorization_token,
                'Content-Type': 'application/json'
            }

            # Call API
            url = f"{self.BASE_URL}/v1/orders"
            response = requests.post(url, data=json.dumps(request_body), headers=headers, timeout=10)

            print(f"Response status: {response.status_code}")
            result = response.json()
            print(f"Buy order result: {result}")

            # Convert to our standard format
            if response.status_code == 201 or response.status_code == 200:
                return {"status": "0000", "order_id": result.get("uuid"), "data": result}
            else:
                return {"status": "5100", "message": result.get("error", {}).get("message", "Unknown error")}

        except Exception as e:
            print(f"Error placing buy order for {coin}: {e}")
            import traceback
            traceback.print_exc()
            return {"status": "5100", "message": str(e)}

    def sell_market_order(self, coin: str, amount: float) -> Optional[Dict[str, Any]]:
        """Place a market sell order using Bithumb API 2.0 (JWT method).

        Args:
            coin: Coin symbol
            amount: Amount of coin to sell

        Returns:
            Order result or None if failed
        """
        if not self.api_key or not self.api_secret:
            return {"status": "5100", "message": "API credentials not configured"}

        try:
            print(f"Placing market sell order for {coin}: {amount} coins")

            # Request body (market sell order - volume is coin amount)
            request_body = {
                'market': f'KRW-{coin}',
                'side': 'ask',  # ask = sell
                'ord_type': 'market',  # market order
                'volume': amount  # Amount of coin to sell
            }

            # Generate query hash
            query = urlencode(request_body).encode()
            hash_obj = hashlib.sha512()
            hash_obj.update(query)
            query_hash = hash_obj.hexdigest()

            # Create JWT payload
            payload = {
                'access_key': self.api_key,
                'nonce': str(uuid.uuid4()),
                'timestamp': round(time.time() * 1000),
                'query_hash': query_hash,
                'query_hash_alg': 'SHA512',
            }

            # Generate JWT token
            jwt_token = jwt.encode(payload, self.api_secret, algorithm='HS256')
            authorization_token = f'Bearer {jwt_token}'

            # Headers
            headers = {
                'Authorization': authorization_token,
                'Content-Type': 'application/json'
            }

            # Call API
            url = f"{self.BASE_URL}/v1/orders"
            response = requests.post(url, data=json.dumps(request_body), headers=headers, timeout=10)

            print(f"Response status: {response.status_code}")
            result = response.json()
            print(f"Sell order result: {result}")

            # Convert to our standard format
            if response.status_code == 201 or response.status_code == 200:
                return {"status": "0000", "order_id": result.get("uuid"), "data": result}
            else:
                return {"status": "5100", "message": result.get("error", {}).get("message", "Unknown error")}

        except Exception as e:
            print(f"Error placing sell order for {coin}: {e}")
            import traceback
            traceback.print_exc()
            return {"status": "5100", "message": str(e)}

    def buy_limit_order(self, coin: str, price: float, amount: float) -> Optional[Dict[str, Any]]:
        """Place a limit buy order using Bithumb API 2.0 (JWT method).

        Args:
            coin: Coin symbol
            price: Price per coin
            amount: Amount of coin to buy

        Returns:
            Order result or None if failed
        """
        if not self.api_key or not self.api_secret:
            return {"status": "5100", "message": "API credentials not configured"}

        try:
            print(f"Placing limit buy order for {coin}: {amount} @ {price}")

            # Request body (limit buy order)
            request_body = {
                'market': f'KRW-{coin}',
                'side': 'bid',  # bid = buy
                'ord_type': 'limit',  # limit order
                'price': int(price),  # Price per coin
                'volume': amount  # Amount of coin to buy
            }

            # Generate query hash
            query = urlencode(request_body).encode()
            hash_obj = hashlib.sha512()
            hash_obj.update(query)
            query_hash = hash_obj.hexdigest()

            # Create JWT payload
            payload = {
                'access_key': self.api_key,
                'nonce': str(uuid.uuid4()),
                'timestamp': round(time.time() * 1000),
                'query_hash': query_hash,
                'query_hash_alg': 'SHA512',
            }

            # Generate JWT token
            jwt_token = jwt.encode(payload, self.api_secret, algorithm='HS256')
            authorization_token = f'Bearer {jwt_token}'

            # Headers
            headers = {
                'Authorization': authorization_token,
                'Content-Type': 'application/json'
            }

            # Call API
            url = f"{self.BASE_URL}/v1/orders"
            response = requests.post(url, data=json.dumps(request_body), headers=headers, timeout=10)

            print(f"Response status: {response.status_code}")
            result = response.json()
            print(f"Buy limit order result: {result}")

            # Convert to our standard format
            if response.status_code == 201 or response.status_code == 200:
                return {"status": "0000", "order_id": result.get("uuid"), "data": result}
            else:
                return {"status": "5100", "message": result.get("error", {}).get("message", "Unknown error")}

        except Exception as e:
            print(f"Error placing limit buy order for {coin}: {e}")
            import traceback
            traceback.print_exc()
            return {"status": "5100", "message": str(e)}

    def sell_limit_order(self, coin: str, price: float, amount: float) -> Optional[Dict[str, Any]]:
        """Place a limit sell order using Bithumb API 2.0 (JWT method).

        Args:
            coin: Coin symbol
            price: Price per coin
            amount: Amount of coin to sell

        Returns:
            Order result or None if failed
        """
        if not self.api_key or not self.api_secret:
            return {"status": "5100", "message": "API credentials not configured"}

        try:
            print(f"Placing limit sell order for {coin}: {amount} @ {price}")

            # Request body (limit sell order)
            request_body = {
                'market': f'KRW-{coin}',
                'side': 'ask',  # ask = sell
                'ord_type': 'limit',  # limit order
                'price': int(price),  # Price per coin
                'volume': amount  # Amount of coin to sell
            }

            # Generate query hash
            query = urlencode(request_body).encode()
            hash_obj = hashlib.sha512()
            hash_obj.update(query)
            query_hash = hash_obj.hexdigest()

            # Create JWT payload
            payload = {
                'access_key': self.api_key,
                'nonce': str(uuid.uuid4()),
                'timestamp': round(time.time() * 1000),
                'query_hash': query_hash,
                'query_hash_alg': 'SHA512',
            }

            # Generate JWT token
            jwt_token = jwt.encode(payload, self.api_secret, algorithm='HS256')
            authorization_token = f'Bearer {jwt_token}'

            # Headers
            headers = {
                'Authorization': authorization_token,
                'Content-Type': 'application/json'
            }

            # Call API
            url = f"{self.BASE_URL}/v1/orders"
            response = requests.post(url, data=json.dumps(request_body), headers=headers, timeout=10)

            print(f"Response status: {response.status_code}")
            result = response.json()
            print(f"Sell limit order result: {result}")

            # Convert to our standard format
            if response.status_code == 201 or response.status_code == 200:
                return {"status": "0000", "order_id": result.get("uuid"), "data": result}
            else:
                return {"status": "5100", "message": result.get("error", {}).get("message", "Unknown error")}

        except Exception as e:
            print(f"Error placing limit sell order for {coin}: {e}")
            import traceback
            traceback.print_exc()
            return {"status": "5100", "message": str(e)}

    def get_ohlcv(self, coin: str, interval: str = "day") -> Optional[Any]:
        """Get OHLCV (Open, High, Low, Close, Volume) data using pybithumb.

        Args:
            coin: Coin symbol
            interval: Time interval ("day", "hour", "minute")

        Returns:
            DataFrame with OHLCV data or None if failed
        """
        try:
            if interval == "day":
                df = pybithumb.get_ohlcv(coin)
            elif interval == "hour":
                df = pybithumb.get_ohlcv(coin, interval="1h")
            elif interval == "minute":
                df = pybithumb.get_ohlcv(coin, interval="1m")
            else:
                df = pybithumb.get_ohlcv(coin)
            return df
        except Exception as e:
            print(f"Error getting OHLCV data for {coin}: {e}")
            return None

    def get_available_coins(self) -> list:
        """Get list of all available coins on Bithumb.

        Returns:
            List of coin symbols (e.g., ["BTC", "ETH", "XRP", ...])
        """
        try:
            tickers = pybithumb.get_tickers()
            # Filter out 'date' if present and sort alphabetically
            coins = [ticker for ticker in tickers if ticker != 'date']
            coins.sort()
            print(f"Available coins: {len(coins)} coins found")
            return coins
        except Exception as e:
            print(f"Error getting available coins: {e}")
            # Return default list as fallback
            return ["BTC", "ETH", "XRP", "ADA", "DOGE", "SOL", "DOT", "AVAX", "LINK", "MATIC"]


# Global instance
bithumb_api = BithumbAPI()