"""OKX exchange client"""

from typing import List
from src.clients.base import BaseExchangeClient
from src.models.market import MarketData, ExchangeType, TradingPair, SymbolData


class OKXClient(BaseExchangeClient):
    """Client for OKX perpetual futures API

    Fetches trading volume, open interest, and market data from
    OKX SWAP (perpetual) markets.
    """

    @property
    def exchange_type(self) -> ExchangeType:
        """Exchange type identifier"""
        return ExchangeType.OKX

    @property
    def base_url(self) -> str:
        """Base URL for OKX API"""
        return "https://www.okx.com"

    def fetch_volume(self) -> MarketData:
        """Fetch 24h trading volume from OKX perpetual futures (SWAP)

        Returns:
            MarketData object with volume information

        Raises:
            requests.RequestException: If API request fails
            ValueError: If API returns error response
        """
        # Fetch all SWAP tickers
        response = self._get(
            "/api/v5/market/tickers",
            params={"instType": "SWAP"}
        )

        # Check for API error
        if response.get('code') != '0':
            raise ValueError(f"API error: {response.get('msg', 'Unknown error')}")

        tickers = response['data']

        # Calculate total volume (volCcy24h * last price for USD value)
        total_volume = 0
        pairs_with_volume = []

        for ticker in tickers:
            try:
                # volCcy24h is in base currency, convert to USD
                volume_base = float(ticker.get('volCcy24h', 0))
                last_price = float(ticker.get('last', 0))
                volume_usd = volume_base * last_price
                total_volume += volume_usd

                pairs_with_volume.append({
                    'ticker': ticker,
                    'volume_usd': volume_usd,
                })
            except (ValueError, KeyError):
                continue

        # Fetch open interest from separate endpoint
        total_oi = self._fetch_total_open_interest()

        # Get top pairs by volume
        top_pairs = self._get_top_pairs(pairs_with_volume, limit=10)

        # Get BTC funding rate (if available in tickers)
        btc_ticker = next(
            (t for t in tickers if t['instId'] == 'BTC-USDT-SWAP'),
            {}
        )
        # OKX doesn't return funding rate in tickers endpoint
        btc_funding = None

        return MarketData(
            exchange=self.exchange_type,
            volume_24h=total_volume,
            open_interest=total_oi,
            funding_rate=btc_funding,
            market_count=len(tickers),
            top_pairs=top_pairs,
        )

    def _fetch_total_open_interest(self) -> float:
        """Fetch total open interest from OKX

        Returns:
            Total open interest in USD
        """
        try:
            response = self._get(
                "/api/v5/public/open-interest",
                params={"instType": "SWAP"}
            )

            if response.get('code') == '0' and response.get('data'):
                # Sum all open interest values
                total_oi = sum(
                    float(item.get('oiUsd', 0))
                    for item in response['data']
                )
                return total_oi
        except Exception:
            pass

        return 0.0

    def _get_top_pairs(self, pairs_with_volume: List[dict], limit: int = 10) -> List[TradingPair]:
        """Extract top trading pairs by volume

        Args:
            pairs_with_volume: List of dicts with ticker and volume_usd
            limit: Number of top pairs to return

        Returns:
            List of TradingPair objects sorted by volume
        """
        # Sort by volume
        sorted_pairs = sorted(
            pairs_with_volume,
            key=lambda x: x['volume_usd'],
            reverse=True
        )

        top_pairs = []
        for pair_data in sorted_pairs[:limit]:
            ticker = pair_data['ticker']
            symbol = ticker['instId']  # e.g., "BTC-USDT-SWAP"

            # Extract base/quote from instId
            parts = symbol.split('-')
            base = parts[0] if len(parts) > 0 else 'UNKNOWN'
            quote = parts[1] if len(parts) > 1 else 'USDT'

            top_pairs.append(TradingPair(
                symbol=symbol,
                base=base,
                quote=quote,
                volume=pair_data['volume_usd']
            ))

        return top_pairs

    def fetch_funding_rate(self, symbol: str = "BTC-USDT-SWAP") -> float:
        """Fetch current funding rate for a symbol

        Args:
            symbol: Trading pair symbol (e.g., "BTC-USDT-SWAP")

        Returns:
            Current funding rate as decimal (e.g., 0.0001 = 0.01%)

        Raises:
            ValueError: If symbol not found or API error
            requests.RequestException: If API request fails
        """
        response = self._get(
            "/api/v5/public/funding-rate",
            params={"instId": symbol}
        )

        if response.get('code') != '0':
            raise ValueError(f"API error: {response.get('msg', 'Unknown error')}")

        data = response.get('data', [])
        if not data:
            raise ValueError(f"No funding rate data for {symbol}")

        return float(data[0].get('fundingRate', 0))

    def fetch_symbol(self, symbol: str):
        """Fetch data for a specific symbol on OKX"""
        from typing import Optional
        try:
            # Get ticker data
            ticker_resp = self._get("/api/v5/market/ticker", params={"instId": symbol})
            if ticker_resp.get('code') != '0' or not ticker_resp.get('data'):
                return None
            ticker = ticker_resp['data'][0]
            
            # Get OI
            oi_val = None
            try:
                oi_resp = self._get("/api/v5/public/open-interest", params={"instId": symbol})
                if oi_resp.get('code') == '0' and oi_resp.get('data'):
                    oi_val = float(oi_resp['data'][0].get('oiUsd', 0))
            except Exception:
                pass
            
            # Get funding
            funding = None
            try:
                funding_resp = self._get("/api/v5/public/funding-rate", params={"instId": symbol})
                if funding_resp.get('code') == '0' and funding_resp.get('data'):
                    funding = float(funding_resp['data'][0].get('fundingRate', 0))
            except Exception:
                pass
            
            last_price = float(ticker.get('last', 0))
            open_24h = float(ticker.get('open24h', 0))
            price_change_pct = ((last_price - open_24h) / open_24h) * 100 if open_24h > 0 else None
            
            return SymbolData(
                exchange=self.exchange_type,
                symbol=symbol,
                price=last_price,
                volume_24h=float(ticker.get('volCcy24h', 0)) * last_price,
                price_change_24h_pct=price_change_pct,
                open_interest=oi_val,
                funding_rate=funding,
                num_trades=None
            )
        except Exception:
            return None
