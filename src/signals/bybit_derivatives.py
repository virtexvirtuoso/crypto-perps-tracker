"""Bybit V5 Derivatives Data Client

Fetches derivatives market data from Bybit V5 public endpoints:
- Funding rates
- Open interest
- Long/Short ratios
- Liquidations
- Options IV
- Spot/Perp prices

All endpoints are public and don't require API keys.
Rate limit: 120 requests/minute
"""

import requests
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging
from functools import lru_cache
import time


class BybitDerivativesClient:
    """Client for Bybit V5 derivatives market data"""

    BASE_URL = "https://api.bybit.com"
    RATE_LIMIT_PER_MIN = 120

    def __init__(self, timeout: int = 10):
        """Initialize client

        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout
        self._session = requests.Session()
        self._logger = logging.getLogger(self.__class__.__name__)
        self._request_times: List[float] = []

    def _rate_limit_check(self):
        """Check and enforce rate limits"""
        now = time.time()
        # Remove requests older than 60 seconds
        self._request_times = [t for t in self._request_times if now - t < 60]

        if len(self._request_times) >= self.RATE_LIMIT_PER_MIN:
            sleep_time = 60 - (now - self._request_times[0])
            if sleep_time > 0:
                self._logger.warning(f"Rate limit reached, sleeping {sleep_time:.2f}s")
                time.sleep(sleep_time)

        self._request_times.append(now)

    def _get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make GET request with rate limiting

        Args:
            endpoint: API endpoint
            params: Query parameters

        Returns:
            JSON response

        Raises:
            requests.RequestException: On API error
        """
        self._rate_limit_check()

        url = f"{self.BASE_URL}{endpoint}"
        try:
            response = self._session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()

            if data.get('retCode') != 0:
                raise requests.RequestException(f"API error: {data.get('retMsg')}")

            return data
        except requests.RequestException as e:
            self._logger.error(f"Request failed for {endpoint}: {e}")
            raise

    def get_funding_rate(self, symbol: str = "BTCUSDT") -> Dict[str, Any]:
        """Get current funding rate

        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')

        Returns:
            Dict with funding_rate, next_funding_time, etc.
        """
        data = self._get("/v5/market/tickers", params={
            'category': 'linear',
            'symbol': symbol
        })

        ticker = data['result']['list'][0]
        funding_rate = float(ticker.get('fundingRate', 0))
        next_funding_time = int(ticker.get('nextFundingTime', 0))

        return {
            'symbol': symbol,
            'funding_rate': funding_rate,
            'funding_rate_8h': funding_rate * 3,  # Bybit uses 8-hour periods (3 per day)
            'next_funding_time': datetime.fromtimestamp(next_funding_time / 1000) if next_funding_time else None,
            'last_price': float(ticker.get('lastPrice', 0)),
            'timestamp': datetime.utcnow()
        }

    def get_open_interest_history(
        self,
        symbol: str = "BTCUSDT",
        interval: str = "1h",
        limit: int = 25
    ) -> List[Dict[str, Any]]:
        """Get open interest historical data

        Args:
            symbol: Trading pair
            interval: Time interval (5min, 15min, 30min, 1h, 4h, 1d)
            limit: Number of data points (max 200)

        Returns:
            List of OI data points
        """
        data = self._get("/v5/market/open-interest", params={
            'category': 'linear',
            'symbol': symbol,
            'intervalTime': interval,
            'limit': limit
        })

        oi_list = []
        for item in data['result']['list']:
            oi_list.append({
                'timestamp': datetime.fromtimestamp(int(item['timestamp']) / 1000),
                'open_interest': float(item['openInterest']),
                'symbol': symbol
            })

        return sorted(oi_list, key=lambda x: x['timestamp'])

    def get_long_short_ratio(
        self,
        symbol: str = "BTCUSDT",
        period: str = "1h"
    ) -> Dict[str, Any]:
        """Get long/short account ratio

        Args:
            symbol: Trading pair
            period: Time period (5min, 15min, 30min, 1h, 4h, 1d)

        Returns:
            Dict with long/short ratio data
        """
        data = self._get("/v5/market/account-ratio", params={
            'category': 'linear',
            'symbol': symbol,
            'period': period,
            'limit': 1
        })

        if not data['result']['list']:
            raise ValueError(f"No long/short ratio data for {symbol}")

        item = data['result']['list'][0]
        buy_ratio = float(item['buyRatio'])
        sell_ratio = float(item['sellRatio'])

        # Calculate long/short ratio
        lsr = buy_ratio / sell_ratio if sell_ratio > 0 else float('inf')

        return {
            'symbol': symbol,
            'timestamp': datetime.fromtimestamp(int(item['timestamp']) / 1000),
            'long_ratio': buy_ratio,
            'short_ratio': sell_ratio,
            'long_short_ratio': lsr,
            'long_account_pct': buy_ratio * 100,
            'short_account_pct': sell_ratio * 100
        }

    def get_recent_trades(
        self,
        symbol: str = "BTCUSDT",
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """Get recent public trades for CVD calculation

        Args:
            symbol: Trading pair
            limit: Number of trades (max 1000)

        Returns:
            List of trade data
        """
        data = self._get("/v5/market/recent-trade", params={
            'category': 'linear',
            'symbol': symbol,
            'limit': limit
        })

        trades = []
        for trade in data['result']['list']:
            trades.append({
                'timestamp': datetime.fromtimestamp(int(trade['time']) / 1000),
                'price': float(trade['price']),
                'size': float(trade['size']),
                'side': trade['side'],  # 'Buy' or 'Sell'
                'symbol': symbol
            })

        return sorted(trades, key=lambda x: x['timestamp'])

    def get_spot_price(self, symbol: str = "BTCUSDT") -> float:
        """Get spot price

        Args:
            symbol: Trading pair

        Returns:
            Current spot price
        """
        data = self._get("/v5/market/tickers", params={
            'category': 'spot',
            'symbol': symbol
        })

        if not data['result']['list']:
            raise ValueError(f"No spot price data for {symbol}")

        return float(data['result']['list'][0]['lastPrice'])

    def get_perp_price(self, symbol: str = "BTCUSDT") -> float:
        """Get perpetual futures price

        Args:
            symbol: Trading pair

        Returns:
            Current perp price
        """
        data = self._get("/v5/market/tickers", params={
            'category': 'linear',
            'symbol': symbol
        })

        if not data['result']['list']:
            raise ValueError(f"No perp price data for {symbol}")

        return float(data['result']['list'][0]['lastPrice'])

    def get_options_iv(
        self,
        base_coin: str = "BTC",
        option_type: str = "Call",
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Get options implied volatility data

        Args:
            base_coin: Base coin (BTC, ETH)
            option_type: Call or Put
            limit: Number of results

        Returns:
            List of options with IV data
        """
        try:
            # Note: 'limit' param not valid for options ticker endpoint
            data = self._get("/v5/market/tickers", params={
                'category': 'option',
                'baseCoin': base_coin,
            })

            options = []
            for item in data['result']['list']:
                # Filter by option type: symbols contain -C or -P
                # Formats: BTC-26DEC25-90000-C (coin), BTC-25SEP26-180000-C-USDT (USDT)
                symbol = item['symbol']
                if option_type:
                    marker = '-C' if option_type.lower() == 'call' else '-P'
                    # Match -C or -C- (for -C-USDT format)
                    if marker not in symbol:
                        continue
                    # Exclude wrong type: if looking for -C, exclude -P symbols
                    wrong_marker = '-P' if option_type.lower() == 'call' else '-C'
                    if wrong_marker in symbol:
                        continue

                # Use markIv field (mark implied volatility) from Bybit API
                iv = float(item.get('markIv', 0) or 0)
                delta = float(item.get('delta', 0) or 0)

                options.append({
                    'symbol': symbol,
                    'iv': iv,
                    'delta': delta,
                    'underlying_price': float(item.get('underlyingPrice', 0) or 0),
                    'mark_price': float(item.get('markPrice', 0) or 0),
                    'timestamp': datetime.utcnow()
                })

            # Apply limit after filtering
            return options[:limit] if limit else options
        except Exception as e:
            self._logger.warning(f"Options IV data unavailable: {e}")
            return []

    def get_kline_data(
        self,
        symbol: str = "BTCUSDT",
        interval: str = "60",  # minutes
        limit: int = 200
    ) -> List[Dict[str, Any]]:
        """Get kline/candlestick data for EMA calculations

        Args:
            symbol: Trading pair
            interval: Interval in minutes (1, 3, 5, 15, 30, 60, 120, 240, 360, 720, D, W, M)
            limit: Number of candles (max 1000)

        Returns:
            List of kline data
        """
        data = self._get("/v5/market/kline", params={
            'category': 'linear',
            'symbol': symbol,
            'interval': interval,
            'limit': limit
        })

        klines = []
        for item in data['result']['list']:
            klines.append({
                'timestamp': datetime.fromtimestamp(int(item[0]) / 1000),
                'open': float(item[1]),
                'high': float(item[2]),
                'low': float(item[3]),
                'close': float(item[4]),
                'volume': float(item[5]),
                'turnover': float(item[6])
            })

        return sorted(klines, key=lambda x: x['timestamp'])

    def calculate_ema(self, prices: List[float], period: int) -> Optional[float]:
        """Calculate Exponential Moving Average

        Args:
            prices: List of prices (oldest first)
            period: EMA period (e.g., 200)

        Returns:
            Current EMA value or None if insufficient data
        """
        if len(prices) < period:
            return None

        multiplier = 2 / (period + 1)
        ema = sum(prices[:period]) / period  # Start with SMA

        for price in prices[period:]:
            ema = (price - ema) * multiplier + ema

        return ema

    def get_open_interest(self, symbol: str = "BTCUSDT") -> Dict[str, Any]:
        """Get current open interest for a symbol

        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')

        Returns:
            Dict with open interest data
        """
        data = self._get("/v5/market/tickers", params={
            'category': 'linear',
            'symbol': symbol
        })

        if not data['result']['list']:
            raise ValueError(f"No data for {symbol}")

        ticker = data['result']['list'][0]
        oi = float(ticker.get('openInterest', 0))
        price = float(ticker.get('lastPrice', 0))

        return {
            'symbol': symbol,
            'open_interest_contracts': oi,
            'open_interest_usd': oi * price,
            'price': price,
            'timestamp': datetime.utcnow(),
            'source': 'bybit'
        }

    def get_liquidations(
        self,
        symbol: str = "BTCUSDT",
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get recent liquidation orders

        Note: Bybit public API doesn't expose liquidation history directly,
        but we can detect large market orders that are likely liquidations
        from the recent trades endpoint.

        Args:
            symbol: Trading pair
            limit: Number of trades to analyze

        Returns:
            List of likely liquidation events
        """
        # Bybit doesn't have a public liquidation endpoint
        # We detect liquidations from recent trades (large market orders)
        trades = self.get_recent_trades(symbol, limit=limit)

        # Calculate average trade size
        if not trades:
            return []

        avg_size = sum(t['size'] for t in trades) / len(trades)

        # Flag trades that are 5x larger than average as potential liquidations
        liquidations = []
        for trade in trades:
            if trade['size'] > avg_size * 5:
                liquidations.append({
                    'symbol': symbol,
                    'side': 'SELL' if trade['side'] == 'Buy' else 'BUY',  # Inverse
                    'price': trade['price'],
                    'quantity': trade['size'],
                    'value_usd': trade['price'] * trade['size'],
                    'time': trade['timestamp'],
                    'type': 'likely_liquidation',
                    'source': 'bybit'
                })

        return liquidations

    def get_taker_buy_sell_volume(
        self,
        symbol: str = "BTCUSDT",
        limit: int = 500
    ) -> Dict[str, Any]:
        """Calculate taker buy/sell volume from recent trades

        Args:
            symbol: Trading pair
            limit: Number of trades to analyze

        Returns:
            Dict with buy/sell volume data
        """
        trades = self.get_recent_trades(symbol, limit=limit)

        if not trades:
            raise ValueError(f"No trade data for {symbol}")

        buy_volume = sum(t['size'] * t['price'] for t in trades if t['side'] == 'Buy')
        sell_volume = sum(t['size'] * t['price'] for t in trades if t['side'] == 'Sell')

        ratio = buy_volume / sell_volume if sell_volume > 0 else 1.0

        return {
            'symbol': symbol,
            'buy_volume': buy_volume,
            'sell_volume': sell_volume,
            'buy_sell_ratio': ratio,
            'net_volume': buy_volume - sell_volume,
            'aggressor': 'buyers' if ratio > 1 else 'sellers' if ratio < 1 else 'neutral',
            'trade_count': len(trades),
            'source': 'bybit'
        }

    def get_basis(self, symbol: str = "BTCUSDT") -> Dict[str, Any]:
        """Calculate basis (perp - spot spread)

        Args:
            symbol: Trading pair

        Returns:
            Dict with basis data
        """
        perp_price = self.get_perp_price(symbol)
        spot_price = self.get_spot_price(symbol)

        basis = perp_price - spot_price
        basis_pct = (basis / spot_price) * 100 if spot_price > 0 else 0

        return {
            'symbol': symbol,
            'perp_price': perp_price,
            'spot_price': spot_price,
            'basis': basis,
            'basis_pct': basis_pct,
            'sentiment': 'bullish' if basis_pct > 0.05 else 'bearish' if basis_pct < -0.05 else 'neutral',
            'timestamp': datetime.utcnow(),
            'source': 'bybit'
        }
