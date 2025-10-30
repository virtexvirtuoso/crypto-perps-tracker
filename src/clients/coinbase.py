"""Coinbase client for spot market data

Coinbase is a major US-based cryptocurrency exchange offering
spot trading in 550+ markets with competitive fees.

Note: This is for Coinbase spot markets. For futures, see coinbase_intx.py
"""

from typing import Dict, Any, Optional
from src.clients.base import BaseExchangeClient
from src.models.market import ExchangeType, MarketData, TradingPair, SymbolData


class CoinbaseClient(BaseExchangeClient):
    """Client for Coinbase Advanced Trade API (Spot Markets)

    API Documentation: https://docs.cloud.coinbase.com/advanced-trade-api/docs/welcome
    Base URL: https://api.coinbase.com/api/v3/brokerage
    """

    @property
    def exchange_type(self) -> ExchangeType:
        return ExchangeType.COINBASE

    @property
    def base_url(self) -> str:
        return "https://api.coinbase.com/api/v3/brokerage"

    def fetch_volume(self) -> MarketData:
        """Fetch 24h volume data from Coinbase spot markets

        Returns:
            MarketData with volume, top pairs, and market count
        """
        # Get all products (trading pairs)
        response = self._get("/products")

        if not isinstance(response, dict) or 'products' not in response:
            raise ValueError(f"Unexpected Coinbase API response: {response}")

        products = response.get('products', [])

        # Filter for active spot markets (exclude futures, options)
        spot_products = [
            p for p in products
            if p.get('status') == 'online'
            and p.get('trading_disabled') == False
            and not p.get('is_disabled', False)
            and p.get('product_type') == 'SPOT'
        ]

        # Get 24h stats for volume calculation
        volumes = []
        total_volume = 0

        for product in spot_products:
            product_id = product.get('product_id')

            if not product_id:
                continue

            try:
                # Get 24h stats for this product
                stats_response = self._get(f"/products/{product_id}/stats")

                if isinstance(stats_response, dict):
                    # Volume is in base currency, need to convert to USD
                    vol_24h = float(stats_response.get('volume', 0))
                    # Use mark_price or last trade price for conversion
                    price = float(stats_response.get('last', 0))

                    # Check if this is a USD/USDT/USDC pair
                    quote = product.get('quote_currency_id', '')
                    if quote in ['USD', 'USDT', 'USDC']:
                        vol_usd = vol_24h * price
                    else:
                        # For non-USD pairs, skip or approximate
                        continue

                    if vol_usd > 0:
                        volumes.append({
                            'product_id': product_id,
                            'volume': vol_usd,
                            'base': product.get('base_currency_id', 'N/A'),
                            'quote': quote
                        })
                        total_volume += vol_usd

            except Exception as e:
                # Skip products that error out
                self._logger.debug(f"Error getting stats for {product_id}: {e}")
                continue

        # Sort by volume to get top pairs
        volumes.sort(key=lambda x: x['volume'], reverse=True)

        top_pairs = [
            TradingPair(
                symbol=v['product_id'],
                base=v['base'],
                quote=v['quote'],
                volume=v['volume']
            )
            for v in volumes[:10]
        ]

        return MarketData(
            exchange=self.exchange_type,
            volume_24h=total_volume,
            top_pairs=top_pairs,
            market_count=len(spot_products),
            open_interest=None,  # Not applicable for spot markets
            funding_rate=None    # Not applicable for spot markets
        )

    def fetch_symbol(self, symbol: str) -> Optional[SymbolData]:
        """Fetch data for a specific symbol on Coinbase

        Args:
            symbol: Trading pair symbol (e.g., 'BTC-USD')

        Returns:
            SymbolData with price, volume, and available metrics
        """
        try:
            # Get product details
            product_response = self._get(f"/products/{symbol}")

            if not isinstance(product_response, dict):
                self._logger.error(f"Invalid product response for {symbol}")
                return None

            # Get 24h stats
            stats_response = self._get(f"/products/{symbol}/stats")

            if not isinstance(stats_response, dict):
                self._logger.error(f"Invalid stats response for {symbol}")
                return None

            # Extract data
            last_price = float(stats_response.get('last', 0))
            volume = float(stats_response.get('volume', 0))
            high = float(stats_response.get('high', 0))
            low = float(stats_response.get('low', 0))

            # Calculate volume in USD if needed
            quote = product_response.get('quote_currency_id', '')
            if quote in ['USD', 'USDT', 'USDC']:
                vol_usd = volume * last_price
            else:
                vol_usd = 0  # Can't calculate without conversion rate

            # Calculate 24h price change
            open_price = float(stats_response.get('open', 0))
            price_change = last_price - open_price if open_price > 0 else 0
            price_change_pct = (price_change / open_price * 100) if open_price > 0 else 0

            return SymbolData(
                exchange=self.exchange_type,
                symbol=symbol,
                price=last_price,
                volume_24h=vol_usd,
                price_change_24h=price_change,
                price_change_pct=price_change_pct,
                high_24h=high,
                low_24h=low,
                trades_24h=None,       # Not available in stats
                open_interest=None,    # Not applicable for spot
                funding_rate=None      # Not applicable for spot
            )

        except Exception as e:
            self._logger.error(f"Error fetching symbol {symbol}: {e}")
            return None
