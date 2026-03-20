"""Binance exchange client

Binance is one of the largest cryptocurrency exchanges globally.
API Documentation: https://binance-docs.github.io/apidocs/futures/en/
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from src.clients.base import BaseExchangeClient
from src.models.market import MarketData, ExchangeType, TradingPair, SymbolData


class BinanceClient(BaseExchangeClient):
    """Client for Binance Futures API

    Fetches perpetual futures market data including volume, open interest,
    and funding rates from Binance USDⓈ-M Futures.

    API Endpoints:
        - /fapi/v1/ticker/24hr - 24h ticker data
        - /fapi/v1/fundingRate - Funding rate history
        - /fapi/v1/openInterest - Open interest data
        - /futures/data/globalLongShortAccountRatio - Long/short account ratio
        - /futures/data/topLongShortAccountRatio - Top trader L/S ratio
    """

    @property
    def exchange_type(self) -> ExchangeType:
        """Return exchange type"""
        return ExchangeType.BINANCE

    @property
    def base_url(self) -> str:
        """Binance Futures API base URL"""
        return "https://fapi.binance.com"

    def fetch_volume(self) -> MarketData:
        """Fetch 24h volume and market data from Binance

        Returns:
            MarketData object with volume, open interest, and top pairs

        Raises:
            requests.RequestException: If API request fails after retries
        """
        # Fetch 24h ticker data for all symbols
        tickers = self._get("/fapi/v1/ticker/24hr")

        # Calculate total volume (in USDT)
        total_volume = 0.0
        total_oi = 0.0
        pairs_with_volume = []
        btc_funding = None

        for ticker in tickers:
            symbol = ticker.get('symbol', '')

            # Only include USDT perpetual futures
            if not symbol.endswith('USDT'):
                continue

            # Volume in quote currency (USDT)
            volume = float(ticker.get('quoteVolume', 0))
            total_volume += volume

            # Store pair with volume for top pairs calculation
            if volume > 0:
                pairs_with_volume.append({
                    'symbol': symbol,
                    'volume': volume
                })

        # Get BTC funding rate
        try:
            funding_data = self._get("/fapi/v1/premiumIndex", params={'symbol': 'BTCUSDT'})
            if funding_data:
                btc_funding = float(funding_data.get('lastFundingRate', 0))
        except Exception:
            # Funding rate is optional, continue without it
            pass

        # Get total open interest
        try:
            oi_data = self._get("/fapi/v1/openInterest", params={'symbol': 'BTCUSDT'})
            if oi_data:
                # This is just BTC OI, we'd need to aggregate all symbols for total
                # For now, fetch a few major symbols
                major_symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'XRPUSDT']
                for symbol in major_symbols:
                    try:
                        oi_response = self._get("/fapi/v1/openInterest", params={'symbol': symbol})
                        # Get current price to convert to USD
                        price_data = next((t for t in tickers if t.get('symbol') == symbol), None)
                        if oi_response and price_data:
                            oi_contracts = float(oi_response.get('openInterest', 0))
                            price = float(price_data.get('lastPrice', 0))
                            total_oi += oi_contracts * price
                    except Exception:
                        continue
        except Exception:
            # OI is optional
            pass

        # Get top 10 pairs by volume
        top_pairs = sorted(pairs_with_volume, key=lambda x: x['volume'], reverse=True)[:10]
        top_pairs_models = [
            TradingPair(
                symbol=pair['symbol'],
                volume=pair['volume']
            )
            for pair in top_pairs
        ]

        return MarketData(
            exchange=self.exchange_type,
            volume_24h=total_volume,
            open_interest=total_oi if total_oi > 0 else None,
            funding_rate=btc_funding,
            market_count=len(pairs_with_volume),
            top_pairs=top_pairs_models,
        )

    def fetch_symbol(self, symbol: str) -> Optional[SymbolData]:
        """Fetch data for a specific symbol on Binance

        Args:
            symbol: Trading pair symbol (e.g., 'BTCUSDT')

        Returns:
            SymbolData object with price, volume, OI, funding rate
            None if symbol not found or error occurs
        """
        try:
            # Get ticker data
            ticker = self._get("/fapi/v1/ticker/24hr", params={'symbol': symbol})

            if not ticker:
                return None

            # Get funding rate
            funding_rate = None
            try:
                funding_data = self._get("/fapi/v1/premiumIndex", params={'symbol': symbol})
                if funding_data:
                    funding_rate = float(funding_data.get('lastFundingRate', 0))
            except Exception:
                pass

            # Get open interest
            open_interest = None
            try:
                oi_data = self._get("/fapi/v1/openInterest", params={'symbol': symbol})
                if oi_data:
                    oi_contracts = float(oi_data.get('openInterest', 0))
                    price = float(ticker.get('lastPrice', 0))
                    open_interest = oi_contracts * price
            except Exception:
                pass

            return SymbolData(
                exchange=self.exchange_type,
                symbol=symbol,
                price=float(ticker.get('lastPrice', 0)),
                volume_24h=float(ticker.get('quoteVolume', 0)),
                price_change_24h_pct=float(ticker.get('priceChangePercent', 0)),
                open_interest=open_interest,
                funding_rate=funding_rate,
                num_trades=int(ticker.get('count', 0))
            )

        except Exception as e:
            # Return None if symbol not found or any error occurs
            return None

    def fetch_long_short_ratio(
        self,
        symbol: str = "BTCUSDT",
        period: str = "1h",
        limit: int = 1
    ) -> Dict[str, Any]:
        """Fetch global long/short account ratio from Binance

        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')
            period: Time period (5m, 15m, 30m, 1h, 2h, 4h, 6h, 12h, 1d)
            limit: Number of data points (max 500)

        Returns:
            Dict with long/short ratio data:
                - symbol: Trading pair
                - long_short_ratio: Ratio of longs to shorts
                - long_account_pct: Percentage of long accounts
                - short_account_pct: Percentage of short accounts
                - timestamp: Data timestamp

        Raises:
            ValueError: If API returns error
            requests.RequestException: If request fails
        """
        response = self._get(
            "/futures/data/globalLongShortAccountRatio",
            params={
                "symbol": symbol,
                "period": period,
                "limit": limit
            }
        )

        if not response:
            raise ValueError(f"No long/short ratio data for {symbol}")

        # Response is a list, get most recent
        latest = response[0] if isinstance(response, list) else response

        long_account = float(latest.get('longAccount', 0))
        short_account = float(latest.get('shortAccount', 0))
        lsr = float(latest.get('longShortRatio', 0))

        return {
            'symbol': symbol,
            'timestamp': datetime.fromtimestamp(int(latest.get('timestamp', 0)) / 1000),
            'long_short_ratio': lsr,
            'long_account_pct': long_account * 100,
            'short_account_pct': short_account * 100,
            'source': 'binance'
        }

    def fetch_top_trader_long_short_ratio(
        self,
        symbol: str = "BTCUSDT",
        period: str = "1h",
        limit: int = 1
    ) -> Dict[str, Any]:
        """Fetch top trader long/short account ratio (top 20% by margin)

        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')
            period: Time period (5m, 15m, 30m, 1h, 2h, 4h, 6h, 12h, 1d)
            limit: Number of data points (max 500)

        Returns:
            Dict with top trader long/short ratio data
        """
        response = self._get(
            "/futures/data/topLongShortAccountRatio",
            params={
                "symbol": symbol,
                "period": period,
                "limit": limit
            }
        )

        if not response:
            raise ValueError(f"No top trader L/S ratio data for {symbol}")

        latest = response[0] if isinstance(response, list) else response

        long_account = float(latest.get('longAccount', 0))
        short_account = float(latest.get('shortAccount', 0))
        lsr = float(latest.get('longShortRatio', 0))

        return {
            'symbol': symbol,
            'timestamp': datetime.fromtimestamp(int(latest.get('timestamp', 0)) / 1000),
            'long_short_ratio': lsr,
            'long_account_pct': long_account * 100,
            'short_account_pct': short_account * 100,
            'trader_type': 'top_20_pct',
            'source': 'binance'
        }

    def fetch_open_interest(
        self,
        symbol: str = "BTCUSDT"
    ) -> Dict[str, Any]:
        """Fetch current open interest for a symbol

        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')

        Returns:
            Dict with open interest data in USD
        """
        # Get current OI
        oi_data = self._get("/fapi/v1/openInterest", params={'symbol': symbol})

        if not oi_data:
            raise ValueError(f"No open interest data for {symbol}")

        # Get current price to convert to USD
        ticker = self._get("/fapi/v1/ticker/price", params={'symbol': symbol})
        price = float(ticker.get('price', 0)) if ticker else 0

        oi_contracts = float(oi_data.get('openInterest', 0))
        oi_usd = oi_contracts * price

        return {
            'symbol': symbol,
            'open_interest_contracts': oi_contracts,
            'open_interest_usd': oi_usd,
            'price': price,
            'source': 'binance'
        }

    def fetch_open_interest_history(
        self,
        symbol: str = "BTCUSDT",
        period: str = "1h",
        limit: int = 1
    ) -> Dict[str, Any]:
        """Fetch historical open interest statistics

        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')
            period: Time period (5m, 15m, 30m, 1h, 2h, 4h, 6h, 12h, 1d)
            limit: Number of data points (max 500)

        Returns:
            Dict with open interest history data
        """
        response = self._get(
            "/futures/data/openInterestHist",
            params={
                "symbol": symbol,
                "period": period,
                "limit": limit
            }
        )

        if not response:
            raise ValueError(f"No open interest history for {symbol}")

        latest = response[0] if isinstance(response, list) else response

        return {
            'symbol': symbol,
            'timestamp': datetime.fromtimestamp(int(latest.get('timestamp', 0)) / 1000),
            'open_interest_contracts': float(latest.get('sumOpenInterest', 0)),
            'open_interest_usd': float(latest.get('sumOpenInterestValue', 0)),
            'source': 'binance'
        }

    def fetch_taker_buy_sell_ratio(
        self,
        symbol: str = "BTCUSDT",
        period: str = "1h",
        limit: int = 1
    ) -> Dict[str, Any]:
        """Fetch taker buy/sell volume ratio

        Shows the ratio of taker buy volume to taker sell volume.
        Values > 1 indicate more aggressive buying, < 1 more aggressive selling.

        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')
            period: Time period (5m, 15m, 30m, 1h, 2h, 4h, 6h, 12h, 1d)
            limit: Number of data points (max 500)

        Returns:
            Dict with taker buy/sell ratio data
        """
        response = self._get(
            "/futures/data/takerlongshortRatio",
            params={
                "symbol": symbol,
                "period": period,
                "limit": limit
            }
        )

        if not response:
            raise ValueError(f"No taker buy/sell data for {symbol}")

        latest = response[0] if isinstance(response, list) else response

        buy_vol = float(latest.get('buyVol', 0))
        sell_vol = float(latest.get('sellVol', 0))
        ratio = float(latest.get('buySellRatio', 0))

        return {
            'symbol': symbol,
            'timestamp': datetime.fromtimestamp(int(latest.get('timestamp', 0)) / 1000),
            'buy_sell_ratio': ratio,
            'buy_volume': buy_vol,
            'sell_volume': sell_vol,
            'net_volume': buy_vol - sell_vol,
            'aggressor': 'buyers' if ratio > 1 else 'sellers' if ratio < 1 else 'neutral',
            'source': 'binance'
        }

    def fetch_liquidations(
        self,
        symbol: str = "BTCUSDT",
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Fetch recent forced liquidation orders

        Args:
            symbol: Trading pair (e.g., 'BTCUSDT')
            limit: Number of liquidations to fetch (max 1000)

        Returns:
            List of liquidation orders
        """
        response = self._get(
            "/fapi/v1/forceOrders",
            params={
                "symbol": symbol,
                "limit": limit
            }
        )

        if not response:
            return []

        liquidations = []
        for liq in response:
            liquidations.append({
                'symbol': liq.get('symbol'),
                'side': liq.get('side'),  # BUY = short liquidated, SELL = long liquidated
                'price': float(liq.get('price', 0)),
                'quantity': float(liq.get('origQty', 0)),
                'value_usd': float(liq.get('price', 0)) * float(liq.get('origQty', 0)),
                'time': datetime.fromtimestamp(int(liq.get('time', 0)) / 1000),
                'source': 'binance'
            })

        return liquidations

    def __repr__(self) -> str:
        """String representation"""
        return f"BinanceClient(timeout={self.timeout}s)"
