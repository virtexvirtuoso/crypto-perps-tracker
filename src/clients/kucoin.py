"""KuCoin Futures client for perpetual futures data

KuCoin Futures is a cryptocurrency derivatives exchange offering
USDT-margined and coin-margined perpetual contracts.
"""

from typing import Dict, Any, Optional
from src.clients.base import BaseExchangeClient
from src.models.market import ExchangeType, MarketData, TradingPair, SymbolData


class KuCoinClient(BaseExchangeClient):
    """Client for KuCoin Futures API

    API Documentation: https://www.kucoin.com/docs-new/rest/futures-trading/introduction
    Base URL: https://api-futures.kucoin.com
    """

    @property
    def exchange_type(self) -> ExchangeType:
        return ExchangeType.KUCOIN

    @property
    def base_url(self) -> str:
        return "https://api-futures.kucoin.com"

    def fetch_volume(self) -> MarketData:
        """Fetch 24h volume data from KuCoin Futures

        Returns:
            MarketData with volume, top pairs, and market count
        """
        # Get all active contracts
        response = self._get("/api/v1/contracts/active")

        if not isinstance(response, dict) or response.get('code') != '200000':
            raise ValueError(f"KuCoin API error: {response}")

        contracts = response.get('data', [])

        # Filter for USDT-margined perpetual contracts
        perp_contracts = [
            c for c in contracts
            if c.get('type') == 'FFWCSX'  # Perpetual contract type
            and c.get('quoteCurrency') == 'USDT'
            and c.get('status') == 'Open'
        ]

        # Note: KuCoin /api/v1/ticker requires symbol parameter
        # We'll use contract turnover data which includes 24h volume in USDT
        # This is less precise but avoids making hundreds of API calls

        volumes = []
        total_volume = 0
        total_oi = 0

        for contract in perp_contracts:
            symbol = contract.get('symbol')

            # Get turnover (24h volume in USDT)
            turnover = float(contract.get('turnoverOf24h', 0))

            # KuCoin provides direct USDT volume in turnoverOf24h
            vol_usd = turnover

            if vol_usd > 0:
                volumes.append({
                    'symbol': symbol,
                    'volume': vol_usd,
                    'base': contract.get('baseCurrency', 'N/A'),
                    'quote': contract.get('quoteCurrency', 'USDT')
                })

                total_volume += vol_usd

            # Calculate open interest if available
            # Note: Contract data doesn't include current OI, would need separate API call
            # Skipping OI for now to avoid excessive API calls

        # Sort by volume to get top pairs
        volumes.sort(key=lambda x: x['volume'], reverse=True)

        top_pairs = [
            TradingPair(
                symbol=v['symbol'],
                base=v['base'],
                quote=v['quote'],
                volume=v['volume']
            )
            for v in volumes[:10]
        ]

        # Note: Funding rate and OI skipped to minimize API calls
        # Can be added later with individual contract queries if needed

        return MarketData(
            exchange=self.exchange_type,
            volume_24h=total_volume,
            top_pairs=top_pairs,
            market_count=len(perp_contracts),
            open_interest=None,  # Would require additional API calls
            funding_rate=None    # Would require additional API calls
        )

    def fetch_symbol(self, symbol: str) -> Optional[SymbolData]:
        """Fetch data for a specific symbol on KuCoin Futures

        Args:
            symbol: Trading pair symbol (e.g., 'XBTUSDTM')

        Returns:
            SymbolData with price, volume, and available metrics
        """
        try:
            # Get contract details - this endpoint has all the data we need!
            contract_response = self._get(f"/api/v1/contracts/{symbol}")

            if contract_response.get('code') != '200000':
                self._logger.error(f"Contract not found: {symbol}")
                return None

            contract = contract_response.get('data', {})

            # Extract data from contract endpoint
            last_price = float(contract.get('lastTradePrice', contract.get('markPrice', 0)))
            multiplier = float(contract.get('multiplier', 1))

            # Volume: KuCoin provides turnoverOf24h in USDT directly
            vol_usd = float(contract.get('turnoverOf24h', 0))

            # Open Interest: Convert contracts to USDT
            oi_contracts = float(contract.get('openInterest', 0))
            oi_usd = oi_contracts * last_price * multiplier if oi_contracts > 0 else None

            # Funding rate: Convert from decimal to percentage
            funding_fee_rate = contract.get('fundingFeeRate')
            funding_rate = float(funding_fee_rate) * 100 if funding_fee_rate is not None else None

            # Price change: KuCoin provides priceChgPct as decimal (e.g., 0.0166 = 1.66%)
            price_chg_pct = contract.get('priceChgPct')
            price_change_pct = float(price_chg_pct) * 100 if price_chg_pct is not None else None

            return SymbolData(
                exchange=self.exchange_type,
                symbol=symbol,
                price=last_price,
                volume_24h=vol_usd,
                price_change_24h_pct=price_change_pct,
                open_interest=oi_usd,
                funding_rate=funding_rate,
                num_trades=None  # Not available in KuCoin contract data
            )

        except Exception as e:
            self._logger.error(f"Error fetching symbol {symbol}: {e}")
            return None
