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
            # Get contract details
            contract_response = self._get(f"/api/v1/contracts/{symbol}")

            if contract_response.get('code') != '200000':
                self._logger.error(f"Contract not found: {symbol}")
                return None

            contract = contract_response.get('data', {})

            # Get ticker data
            ticker_response = self._get("/api/v1/ticker", params={"symbol": symbol})

            if ticker_response.get('code') != '200000':
                self._logger.error(f"Ticker data not found for {symbol}")
                return None

            ticker = ticker_response.get('data')

            if not ticker:
                return None

            # Calculate volume in USDT
            vol_base = float(ticker.get('volume', 0))
            last_price = float(ticker.get('price', 0))
            multiplier = float(contract.get('multiplier', 1))
            vol_usd = vol_base * last_price * multiplier

            # Calculate OI in USDT
            oi = float(ticker.get('openInterest', 0))
            oi_usd = oi * last_price * multiplier if oi > 0 else None

            # Get funding rate
            funding_rate = None
            try:
                funding_response = self._get(f"/api/v1/funding-rate/{symbol}/current")
                if funding_response.get('code') == '200000':
                    funding_data = funding_response.get('data', {})
                    funding_rate = float(funding_data.get('value', 0)) * 100
            except Exception:
                pass

            return SymbolData(
                exchange=self.exchange_type,
                symbol=symbol,
                price=last_price,
                volume_24h=vol_usd,
                price_change_24h=float(ticker.get('priceChg', 0)),
                price_change_pct=float(ticker.get('changeRate', 0)) * 100,
                high_24h=float(ticker.get('high', 0)),
                low_24h=float(ticker.get('low', 0)),
                trades_24h=None,  # Not available in ticker
                open_interest=oi_usd,
                funding_rate=funding_rate
            )

        except Exception as e:
            self._logger.error(f"Error fetching symbol {symbol}: {e}")
            return None
