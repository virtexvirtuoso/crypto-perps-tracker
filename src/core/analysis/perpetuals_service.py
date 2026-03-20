"""
Perpetuals Market Service

Integrates Phase 1 statistical aggregation and Phase 2 signal generation
for the perpetuals-pulse API endpoint.
"""

import time
import logging
from typing import Dict, List, Any
from collections import defaultdict

from .perps_aggregator import PerpetualsAggregator, ExchangeMetrics
from .funding_history_db import FundingHistoryDB
from .perps_signals import get_signal_generator
from .signal_alert_handler import get_signal_alert_handler


class PerpetualsMarketService:
    """
    Service layer for perpetuals market data aggregation and signal generation.

    Responsibilities:
    - Fetch L/S ratios from multiple exchanges
    - Build ExchangeMetrics from market data
    - Apply statistical aggregation (Phase 1)
    - Generate trading signals (Phase 2)
    - Store funding history
    - Return enhanced metrics with signals
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.aggregator = PerpetualsAggregator()
        self.funding_db = FundingHistoryDB()
        self.signal_generator = get_signal_generator()
        self.alert_handler = get_signal_alert_handler()

    def fetch_ls_ratios(self) -> List[Dict[str, float]]:
        """
        Fetch Long/Short ratios from OKX, Binance, and Bybit.

        Returns:
            List of dicts with 'exchange', 'long', 'short' keys
        """
        import requests
        ls_sources = []

        # OKX API
        try:
            okx_resp = requests.get(
                "https://www.okx.com/api/v5/rubik/stat/contracts/long-short-account-ratio",
                params={"ccy": "BTC"},
                timeout=5
            ).json()

            if okx_resp.get('code') == '0' and okx_resp.get('data'):
                ratio = float(okx_resp['data'][0][1])
                okx_long = ratio / (ratio + 1) * 100
                okx_short = 100 / (ratio + 1)
                ls_sources.append({
                    'exchange': 'OKX',
                    'long': okx_long,
                    'short': okx_short
                })
                self.logger.info(f"OKX L/S: {okx_long:.1f}% / {okx_short:.1f}%")
        except Exception as e:
            self.logger.warning(f"OKX L/S fetch failed: {e}")

        # Binance API
        try:
            binance_resp = requests.get(
                "https://fapi.binance.com/futures/data/globalLongShortAccountRatio",
                params={"symbol": "BTCUSDT", "period": "1h", "limit": 1},
                timeout=5
            ).json()

            if binance_resp and len(binance_resp) > 0:
                latest = binance_resp[0]
                binance_long = float(latest.get('longAccount', 0.5)) * 100
                binance_short = float(latest.get('shortAccount', 0.5)) * 100
                ls_sources.append({
                    'exchange': 'Binance',
                    'long': binance_long,
                    'short': binance_short
                })
                self.logger.info(f"Binance L/S: {binance_long:.1f}% / {binance_short:.1f}%")
        except Exception as e:
            self.logger.warning(f"Binance L/S fetch failed: {e}")

        # Bybit API
        try:
            bybit_resp = requests.get(
                "https://api.bybit.com/v5/market/account-ratio",
                params={"category": "linear", "symbol": "BTCUSDT", "period": "1h", "limit": 1},
                timeout=5
            ).json()

            if bybit_resp.get('retCode') == 0 and bybit_resp.get('result', {}).get('list'):
                latest = bybit_resp['result']['list'][0]
                bybit_long = float(latest.get('buyRatio', 0.5)) * 100
                bybit_short = float(latest.get('sellRatio', 0.5)) * 100
                ls_sources.append({
                    'exchange': 'Bybit',
                    'long': bybit_long,
                    'short': bybit_short
                })
                self.logger.info(f"Bybit L/S: {bybit_long:.1f}% / {bybit_short:.1f}%")
        except Exception as e:
            self.logger.warning(f"Bybit L/S fetch failed: {e}")

        return ls_sources

    def build_exchange_metrics(
        self,
        markets: List[Any],
        ls_sources: List[Dict[str, float]]
    ) -> List[ExchangeMetrics]:
        """
        Build ExchangeMetrics list from market data and L/S ratios.

        Args:
            markets: List of market objects with exchange, oi, volume, funding_rate
            ls_sources: List of L/S ratio dicts from fetch_ls_ratios()

        Returns:
            List of ExchangeMetrics ready for aggregation
        """
        timestamp = time.time()

        # Group markets by exchange
        exchange_data = defaultdict(lambda: {'oi': 0, 'volume': 0, 'funding': []})

        for m in markets:
            exchange_data[m.exchange]['oi'] += m.open_interest or 0
            exchange_data[m.exchange]['volume'] += m.volume_24h or 0
            if m.funding_rate is not None:
                exchange_data[m.exchange]['funding'].append(m.funding_rate)

        # Map L/S data by exchange name
        ls_dict = {src['exchange']: src for src in ls_sources}

        # Build ExchangeMetrics
        exchange_metrics = []
        for exchange_name, data in exchange_data.items():
            # Get L/S data if available, otherwise default to 50/50
            ls_data = ls_dict.get(exchange_name, {'long': 50.0, 'short': 50.0})

            # Calculate average funding for this exchange
            avg_funding = (
                sum(data['funding']) / len(data['funding'])
                if data['funding'] else 0.0
            )

            exchange_metrics.append(ExchangeMetrics(
                exchange=exchange_name,
                long_pct=ls_data['long'],
                short_pct=ls_data['short'],
                funding_rate=avg_funding,
                open_interest_usd=data['oi'],
                volume_24h_usd=data['volume'],
                timestamp=timestamp
            ))

        self.logger.info(f"Built {len(exchange_metrics)} ExchangeMetrics")
        return exchange_metrics

    def aggregate_and_store(
        self,
        exchange_metrics: List[ExchangeMetrics]
    ) -> Dict[str, float]:
        """
        Apply statistical aggregation and store funding history.

        Args:
            exchange_metrics: List of ExchangeMetrics

        Returns:
            Dict with aggregated metrics
        """
        # Apply aggregation
        aggregated = self.aggregator.aggregate_metrics(exchange_metrics)

        # Store funding rate in database for z-score history
        if aggregated['funding_rate'] != 0.0:
            try:
                self.funding_db.add_funding_rate(
                    funding_rate=aggregated['funding_rate'],
                    exchange='aggregated',
                    timestamp=exchange_metrics[0].timestamp if exchange_metrics else time.time()
                )
                self.logger.debug("Stored funding rate in history DB")
            except Exception as e:
                self.logger.error(f"Failed to store funding history: {e}")

        return aggregated

    def get_enhanced_metrics(self, markets: List[Any]) -> Dict[str, Any]:
        """
        Main entry point: Get enhanced perpetuals metrics with trading signals.

        Args:
            markets: List of market objects from exchange service

        Returns:
            Dict with aggregated metrics (Phase 1) and trading signals (Phase 2)
        """
        # Fetch L/S ratios
        ls_sources = self.fetch_ls_ratios()

        # Build exchange metrics
        exchange_metrics = self.build_exchange_metrics(markets, ls_sources)

        # Aggregate and store (Phase 1)
        aggregated = self.aggregate_and_store(exchange_metrics)

        # Add ls_sources for backward compatibility
        aggregated['ls_source_exchanges'] = [src['exchange'] for src in ls_sources]

        # Generate trading signals (Phase 2)
        try:
            signals = self.signal_generator.generate_signals(aggregated)
            aggregated['signals'] = [signal.to_dict() for signal in signals]
            aggregated['signal_count'] = len(signals)

            # Add signal summary for quick reference
            if signals:
                bullish_count = sum(1 for s in signals if s.direction.value == 'bullish')
                bearish_count = sum(1 for s in signals if s.direction.value == 'bearish')
                aggregated['signal_summary'] = {
                    'bullish': bullish_count,
                    'bearish': bearish_count,
                    'total': len(signals)
                }
            else:
                aggregated['signal_summary'] = {
                    'bullish': 0,
                    'bearish': 0,
                    'total': 0
                }

            self.logger.info(f"Generated {len(signals)} trading signals")

            # Send Discord alerts for qualifying signals
            if signals:
                try:
                    self.alert_handler.send_alert(signals)
                except Exception as alert_error:
                    self.logger.error(f"Alert sending failed: {alert_error}", exc_info=True)

        except Exception as e:
            self.logger.error(f"Signal generation failed: {e}", exc_info=True)
            aggregated['signals'] = []
            aggregated['signal_count'] = 0
            aggregated['signal_summary'] = {'bullish': 0, 'bearish': 0, 'total': 0}

        return aggregated


# Singleton instance for the Flask app to use
_service_instance = None

def get_perpetuals_service() -> PerpetualsMarketService:
    """Get or create singleton service instance."""
    global _service_instance
    if _service_instance is None:
        _service_instance = PerpetualsMarketService()
    return _service_instance
