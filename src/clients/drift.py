"""Drift Protocol exchange client

Drift is a decentralized perpetual futures DEX on Solana
with 140+ perpetual markets.
"""

from typing import Optional, List
from src.clients.base import BaseExchangeClient
from src.models.market import MarketData, ExchangeType, TradingPair, SymbolData


class DriftClient(BaseExchangeClient):
    """Client for Drift Protocol Data API

    Drift is the leading perp DEX on Solana with 140+ perpetual markets.
    
    API Documentation: https://data.api.drift.trade
    """

    @property
    def exchange_type(self) -> ExchangeType:
        """Exchange type identifier"""
        return ExchangeType.DRIFT

    @property
    def base_url(self) -> str:
        """Base URL for Drift Data API"""
        return "https://data.api.drift.trade"

    def fetch_volume(self) -> MarketData:
        """Fetch 24h trading volume and market data from Drift

        Returns:
            MarketData object with aggregated volume, OI, and market stats
        """
        total_volume = 0.0
        total_oi = 0.0
        top_pairs = []
        market_count = 0

        try:
            # Fetch all contracts data
            response = self._get("/contracts")
            contracts = response.get('contracts', [])

            for contract in contracts:
                ticker = contract.get('ticker_id', '')
                
                # Skip non-perp markets
                if not ticker.endswith('-PERP'):
                    continue

                try:
                    # Get OI in base currency and price
                    oi_str = contract.get('open_interest', '0')
                    price_str = contract.get('last_price', '0')
                    volume_str = contract.get('quote_volume', '0')
                    
                    # Handle N/A values
                    if oi_str in ('N/A', '', None):
                        oi_str = '0'
                    if price_str in ('N/A', '', None):
                        price_str = '0'
                    if volume_str in ('N/A', '', None):
                        volume_str = '0'
                    
                    oi_base = float(oi_str)
                    price = float(price_str)
                    volume = float(volume_str)
                    
                    # Calculate OI in USD
                    oi_usd = oi_base * price
                    
                    total_volume += volume
                    total_oi += oi_usd
                    market_count += 1

                    # Add to top pairs if significant
                    if volume > 10000:  # > $10k volume
                        base = contract.get('base_currency', ticker.replace('-PERP', ''))
                        top_pairs.append(TradingPair(
                            symbol=ticker,
                            base=base,
                            quote='USDC',
                            volume=volume
                        ))

                except (ValueError, TypeError) as e:
                    self._logger.debug(f"Skipping {ticker}: {e}")
                    continue

        except Exception as e:
            self._logger.error(f"Failed to fetch Drift contracts: {e}")
            # Return minimal valid data
            return MarketData(
                exchange=self.exchange_type,
                volume_24h=1.0,
                open_interest=0.0,
                market_count=0,
                top_pairs=[]
            )

        # Sort pairs by volume
        top_pairs.sort(key=lambda x: x.volume, reverse=True)

        return MarketData(
            exchange=self.exchange_type,
            volume_24h=total_volume if total_volume > 0 else 1.0,
            open_interest=total_oi,
            funding_rate=None,  # Would need separate API call per market
            market_count=market_count,
            top_pairs=top_pairs[:15]
        )

    def fetch_symbol(self, symbol: str) -> Optional[SymbolData]:
        """Fetch data for a specific Drift symbol

        Args:
            symbol: Trading pair (e.g., 'SOL-PERP', 'BTC-PERP')

        Returns:
            SymbolData with price, volume, OI for the symbol
            None if symbol not found
        """
        # Normalize symbol
        if not symbol.upper().endswith('-PERP'):
            symbol = f"{symbol.upper()}-PERP"
        else:
            symbol = symbol.upper()

        try:
            # Fetch all contracts and find the matching one
            response = self._get("/contracts")
            contracts = response.get('contracts', [])

            for contract in contracts:
                ticker = contract.get('ticker_id', '')
                if ticker.upper() == symbol:
                    try:
                        oi_str = contract.get('open_interest', '0')
                        price_str = contract.get('last_price', '0')
                        volume_str = contract.get('quote_volume', '0')
                        funding_str = contract.get('funding_rate', '0')
                        
                        # Handle N/A values
                        for var in [oi_str, price_str, volume_str, funding_str]:
                            if var in ('N/A', '', None):
                                var = '0'
                        
                        oi_base = float(oi_str) if oi_str not in ('N/A', '', None) else 0
                        price = float(price_str) if price_str not in ('N/A', '', None) else 0
                        volume = float(volume_str) if volume_str not in ('N/A', '', None) else 0
                        funding = float(funding_str) if funding_str not in ('N/A', '', None) else None
                        
                        oi_usd = oi_base * price

                        # Calculate price change
                        high = float(contract.get('high', price) or price)
                        low = float(contract.get('low', price) or price)
                        
                        return SymbolData(
                            exchange=self.exchange_type,
                            symbol=ticker,
                            price=price if price > 0 else 0.01,
                            volume_24h=volume,
                            price_change_24h_pct=None,  # Not directly available
                            open_interest=oi_usd,
                            funding_rate=funding,
                        )
                    except (ValueError, TypeError) as e:
                        self._logger.warning(f"Error parsing {symbol}: {e}")
                        return None

            self._logger.warning(f"Symbol not found: {symbol}")
            return None

        except Exception as e:
            self._logger.error(f"Failed to fetch {symbol} data: {e}")
            return None
