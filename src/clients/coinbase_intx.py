"""Coinbase International Exchange (INTX) client"""

from typing import Optional
from src.clients.base import BaseExchangeClient
from src.models.market import MarketData, ExchangeType, TradingPair, SymbolData


class CoinbaseINTXClient(BaseExchangeClient):
    """Client for Coinbase International Exchange (INTX) API

    Fetches trading volume, open interest, and market data from
    Coinbase INTX perpetual futures markets.
    """

    @property
    def exchange_type(self) -> ExchangeType:
        """Exchange type identifier"""
        return ExchangeType.COINBASE_INTX

    @property
    def base_url(self) -> str:
        """Base URL for Coinbase INTX API"""
        return "https://api.international.coinbase.com"

    def fetch_volume(self) -> MarketData:
        """Fetch 24h trading volume from Coinbase INTX

        Returns:
            MarketData object with volume information

        Raises:
            requests.RequestException: If API request fails
        """
        response = self._get("/api/v1/instruments")

        if not isinstance(response, list):
            raise ValueError("Unexpected response format from Coinbase INTX")

        # Filter for perpetual futures that are trading
        perps = [
            inst for inst in response
            if inst.get('type') == 'PERP' and inst.get('trading_state') == 'TRADING'
        ]

        # Calculate totals
        total_volume = sum(float(inst.get('notional_24hr', 0)) for inst in perps)

        total_oi = 0
        for inst in perps:
            quote = inst.get('quote', {})
            mark_price = float(quote.get('mark_price', 0))
            oi = float(inst.get('open_interest', 0))
            total_oi += oi * mark_price

        # Get BTC funding rate
        btc_funding = None
        for inst in perps:
            if 'BTC' in inst.get('symbol', ''):
                quote = inst.get('quote', {})
                btc_funding = float(quote.get('predicted_funding', 0))
                break

        # Get top pairs by volume
        top_pairs = self._get_top_pairs(perps, limit=10)

        return MarketData(
            exchange=self.exchange_type,
            volume_24h=total_volume,
            open_interest=total_oi,
            funding_rate=btc_funding,
            market_count=len(perps),
            top_pairs=top_pairs,
        )

    def _get_top_pairs(self, instruments: list, limit: int = 10) -> list[TradingPair]:
        """Extract top trading pairs by volume"""
        pairs_with_volume = []

        for inst in instruments:
            symbol = inst.get('symbol', '')
            volume = float(inst.get('notional_24hr', 0))

            # Parse symbol (e.g., "BTC-PERP" -> base: BTC, quote: USD)
            base = symbol.replace('-PERP', '').replace('PERP', '')
            quote = 'USD'

            pairs_with_volume.append({
                'symbol': symbol,
                'base': base,
                'quote': quote,
                'volume': volume
            })

        # Sort by volume
        pairs_with_volume.sort(key=lambda x: x['volume'], reverse=True)

        top_pairs = []
        for p in pairs_with_volume[:limit]:
            top_pairs.append(TradingPair(
                symbol=p['symbol'],
                base=p['base'],
                quote=p['quote'],
                volume=p['volume']
            ))

        return top_pairs

    def fetch_funding_rate(self, symbol: str = "BTC-PERP") -> float:
        """Fetch current funding rate for a symbol

        Args:
            symbol: Trading pair symbol (e.g., "BTC-PERP", "ETH-PERP")

        Returns:
            Current funding rate as decimal

        Raises:
            ValueError: If symbol not found
            requests.RequestException: If API request fails
        """
        response = self._get("/api/v1/instruments")

        if not isinstance(response, list):
            raise ValueError("Unexpected response format")

        for inst in response:
            if inst.get('symbol') == symbol and inst.get('type') == 'PERP':
                quote = inst.get('quote', {})
                return float(quote.get('predicted_funding', 0))

        raise ValueError(f"Symbol {symbol} not found")

    def fetch_symbol(self, symbol: str) -> Optional[SymbolData]:
        """Fetch data for a specific symbol on Coinbase INTX

        Args:
            symbol: Trading pair symbol (e.g., 'BTC-PERP', 'ETH-PERP', 'SOL-PERP')

        Returns:
            SymbolData object or None if not found
        """
        try:
            response = self._get("/api/v1/instruments")

            if not isinstance(response, list):
                return None

            for inst in response:
                if inst.get('symbol') == symbol and inst.get('type') == 'PERP':
                    quote = inst.get('quote', {})

                    mark_price = float(quote.get('mark_price', 0))
                    settlement_price = float(quote.get('settlement_price', 0))

                    # Calculate price change
                    price_change_pct = None
                    if settlement_price > 0:
                        price_change_pct = ((mark_price - settlement_price) / settlement_price) * 100

                    # Calculate OI
                    oi_value = float(inst.get('open_interest', 0)) * mark_price

                    return SymbolData(
                        exchange=self.exchange_type,
                        symbol=symbol,
                        price=mark_price,
                        volume_24h=float(inst.get('notional_24hr', 0)),
                        price_change_24h_pct=price_change_pct,
                        open_interest=oi_value,
                        funding_rate=float(quote.get('predicted_funding', 0)),
                        num_trades=int(float(inst.get('qty_24hr', 0)))
                    )

            return None

        except Exception:
            return None
