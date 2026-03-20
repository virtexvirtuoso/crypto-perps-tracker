"""Jupiter Perpetuals exchange client

Jupiter Perps is a decentralized perpetual futures DEX on Solana
with BTC, ETH, and SOL perpetual markets.
"""

from typing import Optional, List
from src.clients.base import BaseExchangeClient
from src.models.market import MarketData, ExchangeType, TradingPair, SymbolData


class JupiterClient(BaseExchangeClient):
    """Client for Jupiter Perpetuals API

    Jupiter Perps offers perpetual futures trading on Solana with
    up to 100x leverage on SOL, BTC, and ETH.
    
    API Documentation: https://perps-api.jup.ag/v1/docs
    """

    # Known token mints for Jupiter Perps markets
    TOKEN_MINTS = {
        'SOL': 'So11111111111111111111111111111111111111112',
        'ETH': '7vfCXTUXx5WJV5JADk17DUJ4ksgau7utNKj4b963voxs',
        'BTC': '3NZ9JMVBmGAqocybic2c7LQCJScmgsAZ6vQqTDzcqmJh',
    }

    @property
    def exchange_type(self) -> ExchangeType:
        """Exchange type identifier"""
        return ExchangeType.JUPITER

    @property
    def base_url(self) -> str:
        """Base URL for Jupiter Perps API"""
        return "https://perps-api.jup.ag/v1"

    def fetch_volume(self) -> MarketData:
        """Fetch 24h trading volume and market data from Jupiter Perps

        Returns:
            MarketData object with aggregated volume, OI, and funding rate
        """
        total_volume = 0.0
        total_oi_short = 0.0
        total_oi_long = 0.0
        top_pairs = []
        funding_rates = []

        # Fetch market stats for each token
        for symbol, mint in self.TOKEN_MINTS.items():
            try:
                stats = self._get(f"/market-stats?mint={mint}")
                volume = float(stats.get('volume', 0) or 0)
                total_volume += volume

                top_pairs.append(TradingPair(
                    symbol=f"{symbol}-PERP",
                    base=symbol,
                    quote='USD',
                    volume=volume
                ))
            except Exception as e:
                self._logger.warning(f"Failed to fetch {symbol} market stats: {e}")

        # Fetch JLP info for OI data
        try:
            jlp_info = self._get("/jlp-info")
            custodies = jlp_info.get('custodies', [])
            
            for custody in custodies:
                symbol = custody.get('symbol', '')
                if symbol in ['SOL', 'ETH', 'WBTC']:
                    # Short OI is in globalShortSizes (6 decimals)
                    short_size = float(custody.get('globalShortSizes', 0) or 0)
                    short_usd = short_size / 1e6
                    total_oi_short += short_usd
                    
                    # Long collateral is in guaranteedUsd (6 decimals)
                    # This represents collateral, not full position size
                    guaranteed = float(custody.get('guaranteedUsd', 0) or 0)
                    guaranteed_usd = guaranteed / 1e6
                    total_oi_long += guaranteed_usd
        except Exception as e:
            self._logger.warning(f"Failed to fetch JLP info: {e}")

        # Total OI = shorts + longs (estimate)
        # Note: Long OI is collateral-based, actual leveraged position is higher
        total_oi = total_oi_short + total_oi_long

        # Sort pairs by volume
        top_pairs.sort(key=lambda x: x.volume, reverse=True)

        return MarketData(
            exchange=self.exchange_type,
            volume_24h=total_volume if total_volume > 0 else 1.0,  # Ensure > 0
            open_interest=total_oi,
            funding_rate=None,  # Would need per-market funding
            market_count=len(self.TOKEN_MINTS),
            top_pairs=top_pairs[:10]
        )

    def fetch_symbol(self, symbol: str) -> Optional[SymbolData]:
        """Fetch data for a specific Jupiter Perps symbol

        Args:
            symbol: Trading pair (e.g., 'SOL', 'SOL-PERP', 'BTC-PERP')

        Returns:
            SymbolData with price, volume, OI for the symbol
            None if symbol not found
        """
        # Normalize symbol
        base = symbol.upper().replace('-PERP', '').replace('-USD', '')
        
        if base not in self.TOKEN_MINTS:
            self._logger.warning(f"Unknown symbol: {symbol}")
            return None

        mint = self.TOKEN_MINTS[base]

        try:
            stats = self._get(f"/market-stats?mint={mint}")
            
            price = float(stats.get('price', 0) or 0)
            volume = float(stats.get('volume', 0) or 0)
            price_change = float(stats.get('priceChange24H', 0) or 0)

            # Get pool info for utilization/liquidity
            pool_info = self._get(f"/pool-info?mint={mint}")
            
            return SymbolData(
                exchange=self.exchange_type,
                symbol=f"{base}-PERP",
                price=price,
                volume_24h=volume,
                price_change_24h_pct=price_change,
                open_interest=None,  # Per-symbol OI not directly available
                funding_rate=None,   # Would need to calculate from borrow rates
            )

        except Exception as e:
            self._logger.error(f"Failed to fetch {symbol} data: {e}")
            return None
