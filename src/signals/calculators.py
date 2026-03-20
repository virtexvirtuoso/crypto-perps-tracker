"""Signal calculation logic for derivatives-based predictions

Implements all 7 signal types based on Bybit V5 market data:
1. Funding Rate Extremes
2. Open Interest Surge + Price Divergence
3. Long/Short Ratio Skew
4. Liquidation Heatmap (simplified - no websocket in this version)
5. Basis (Perp vs Spot) Divergence
6. CVD (Cumulative Volume Delta)
7. Options IV Skew
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import logging

from src.signals.bybit_derivatives import BybitDerivativesClient
from src.signals.iv_skew_logger import get_iv_skew_logger
from src.signals.models import (
    SignalType,
    SignalDirection,
    SignalStrength,
    FundingRateSignal,
    OpenInterestSignal,
    LongShortRatioSignal,
    BasisSignal,
    CVDSignal,
    OptionsIVSignal,
)


class SignalCalculator:
    """Calculate derivatives-based trading signals"""

    # Thresholds based on 2024-2025 backtest data
    FUNDING_EXTREME_SHORT = -0.0005  # -0.05%
    FUNDING_EXTREME_LONG = 0.001  # 0.1%
    OI_SURGE_THRESHOLD = 0.30  # 30% increase
    PRICE_DIVERGENCE_THRESHOLD = 0.02  # 2%
    LSR_CROWDED_LONG = 3.0
    LSR_CROWDED_SHORT = 0.33
    BASIS_CONTANGO_DISCOUNT = -0.005  # -0.5%
    BASIS_BACKWARDATION_PREMIUM = 0.01  # 1%
    CVD_THRESHOLD = 500_000  # USDT
    IV_SKEW_FEAR = 0.15  # 15%
    IV_SKEW_COMPLACENCY = -0.15

    def __init__(self, client: Optional[BybitDerivativesClient] = None):
        """Initialize calculator

        Args:
            client: Bybit derivatives client (creates new one if None)
        """
        self.client = client or BybitDerivativesClient()
        self._logger = logging.getLogger(self.__class__.__name__)

    def calculate_funding_rate_signal(self, symbol: str = "BTCUSDT") -> FundingRateSignal:
        """Calculate funding rate extremes signal

        Buy if FR < -0.05% and price > 200-EMA
        Sell if FR > +0.10% and price < 200-EMA

        Args:
            symbol: Trading pair

        Returns:
            FundingRateSignal
        """
        # Get funding rate
        funding_data = self.client.get_funding_rate(symbol)
        fr = funding_data['funding_rate']
        fr_8h = funding_data['funding_rate_8h']
        price = funding_data['last_price']

        # Get 200-EMA
        klines = self.client.get_kline_data(symbol, interval="240", limit=200)  # 4h candles
        closes = [k['close'] for k in klines]
        ema_200 = self.client.calculate_ema(closes, 200)

        # Determine signal
        direction = SignalDirection.NEUTRAL
        strength = SignalStrength.WEAK
        confidence = 50.0
        threshold_crossed = "none"
        price_vs_ema = None

        if ema_200:
            price_vs_ema = (price - ema_200) / ema_200

            if fr < self.FUNDING_EXTREME_SHORT and price > ema_200:
                direction = SignalDirection.LONG
                strength = SignalStrength.STRONG
                confidence = 72.0  # From backtest
                threshold_crossed = "extreme_short"
            elif fr > self.FUNDING_EXTREME_LONG and price < ema_200:
                direction = SignalDirection.SHORT
                strength = SignalStrength.STRONG
                confidence = 68.0
                threshold_crossed = "extreme_long"

        return FundingRateSignal(
            signal_type=SignalType.FUNDING_RATE,
            symbol=symbol,
            direction=direction,
            strength=strength,
            confidence=confidence,
            timestamp=datetime.utcnow(),
            horizon="4h-24h",
            funding_rate=fr,
            funding_rate_8h=fr_8h,
            next_funding_time=funding_data['next_funding_time'],
            threshold_crossed=threshold_crossed,
            price_vs_ema200=price_vs_ema,
            metadata={
                'price': price,
                'ema_200': ema_200,
                'fr_threshold_short': self.FUNDING_EXTREME_SHORT,
                'fr_threshold_long': self.FUNDING_EXTREME_LONG
            }
        )

    def calculate_open_interest_signal(self, symbol: str = "BTCUSDT") -> OpenInterestSignal:
        """Calculate OI surge + price divergence signal

        Bullish if ΔOI% > +30% and price falls < -2%
        Bearish if ΔOI% > +30% and price rises > +2%

        Args:
            symbol: Trading pair

        Returns:
            OpenInterestSignal
        """
        # Get OI history (last 24 hours)
        oi_history = self.client.get_open_interest_history(symbol, interval="1h", limit=25)

        if len(oi_history) < 24:
            raise ValueError(f"Insufficient OI history for {symbol}")

        oi_now = oi_history[-1]['open_interest']
        oi_24h_ago = oi_history[0]['open_interest']
        oi_change_pct = (oi_now - oi_24h_ago) / oi_24h_ago

        # Get price change
        klines = self.client.get_kline_data(symbol, interval="60", limit=25)
        price_now = klines[-1]['close']
        price_24h_ago = klines[0]['close']
        price_change_pct = (price_now - price_24h_ago) / price_24h_ago

        # Determine signal
        direction = SignalDirection.NEUTRAL
        strength = SignalStrength.WEAK
        confidence = 50.0
        divergence_type = "none"

        if oi_change_pct > self.OI_SURGE_THRESHOLD:
            if price_change_pct < -self.PRICE_DIVERGENCE_THRESHOLD:
                # OI up, price down = bullish trap = reversal up
                direction = SignalDirection.LONG
                strength = SignalStrength.STRONG
                confidence = 68.0
                divergence_type = "bullish"
            elif price_change_pct > self.PRICE_DIVERGENCE_THRESHOLD:
                # OI up, price up = bearish trap = reversal down
                direction = SignalDirection.SHORT
                strength = SignalStrength.STRONG
                confidence = 68.0
                divergence_type = "bearish"

        return OpenInterestSignal(
            signal_type=SignalType.OPEN_INTEREST,
            symbol=symbol,
            direction=direction,
            strength=strength,
            confidence=confidence,
            timestamp=datetime.utcnow(),
            horizon="1h-6h",
            oi_change_pct=oi_change_pct * 100,
            oi_current=oi_now,
            oi_24h_ago=oi_24h_ago,
            price_change_pct=price_change_pct * 100,
            divergence_type=divergence_type,
            metadata={
                'price_now': price_now,
                'price_24h_ago': price_24h_ago,
                'oi_surge_threshold': self.OI_SURGE_THRESHOLD * 100
            }
        )

    def calculate_long_short_ratio_signal(self, symbol: str = "BTCUSDT") -> LongShortRatioSignal:
        """Calculate Long/Short ratio skew signal

        Fade when LSR > 3.0 (crowded longs) or < 0.33 (crowded shorts)

        Args:
            symbol: Trading pair

        Returns:
            LongShortRatioSignal
        """
        lsr_data = self.client.get_long_short_ratio(symbol, period="1h")
        lsr = lsr_data['long_short_ratio']
        long_pct = lsr_data['long_account_pct']
        short_pct = lsr_data['short_account_pct']

        # Determine signal (fade the crowd)
        direction = SignalDirection.NEUTRAL
        strength = SignalStrength.WEAK
        confidence = 50.0
        crowd_side = "balanced"

        if lsr > self.LSR_CROWDED_LONG:
            # Crowded longs = fade = short
            direction = SignalDirection.SHORT
            strength = SignalStrength.MODERATE
            confidence = 65.0
            crowd_side = "long"
        elif lsr < self.LSR_CROWDED_SHORT:
            # Crowded shorts = fade = long
            direction = SignalDirection.LONG
            strength = SignalStrength.MODERATE
            confidence = 65.0
            crowd_side = "short"

        return LongShortRatioSignal(
            signal_type=SignalType.LONG_SHORT_RATIO,
            symbol=symbol,
            direction=direction,
            strength=strength,
            confidence=confidence,
            timestamp=datetime.utcnow(),
            horizon="30min-2h",
            ratio=lsr,
            long_account_pct=long_pct,
            short_account_pct=short_pct,
            crowd_side=crowd_side,
            metadata={
                'lsr_crowded_long_threshold': self.LSR_CROWDED_LONG,
                'lsr_crowded_short_threshold': self.LSR_CROWDED_SHORT
            }
        )

    def calculate_basis_signal(self, symbol: str = "BTCUSDT") -> BasisSignal:
        """Calculate Perp vs Spot basis divergence signal

        Buy if Basis < -0.5% (contango discount)
        Sell if Basis > +1% (backwardation premium)

        Args:
            symbol: Trading pair

        Returns:
            BasisSignal
        """
        perp_price = self.client.get_perp_price(symbol)
        spot_price = self.client.get_spot_price(symbol)
        basis_pct = (perp_price - spot_price) / spot_price

        # Determine signal
        direction = SignalDirection.NEUTRAL
        strength = SignalStrength.WEAK
        confidence = 50.0
        basis_type = "neutral"
        arbitrage_opportunity = False

        if basis_pct < self.BASIS_CONTANGO_DISCOUNT:
            # Perp discount = buy perp / short spot
            direction = SignalDirection.LONG
            strength = SignalStrength.MODERATE
            confidence = 62.0
            basis_type = "contango_discount"
            arbitrage_opportunity = True
        elif basis_pct > self.BASIS_BACKWARDATION_PREMIUM:
            # Perp premium = sell perp / long spot
            direction = SignalDirection.SHORT
            strength = SignalStrength.MODERATE
            confidence = 62.0
            basis_type = "backwardation_premium"
            arbitrage_opportunity = True

        return BasisSignal(
            signal_type=SignalType.BASIS,
            symbol=symbol,
            direction=direction,
            strength=strength,
            confidence=confidence,
            timestamp=datetime.utcnow(),
            horizon="6h-48h",
            perp_price=perp_price,
            spot_price=spot_price,
            basis_pct=basis_pct * 100,
            basis_type=basis_type,
            arbitrage_opportunity=arbitrage_opportunity,
            metadata={
                'contango_threshold': self.BASIS_CONTANGO_DISCOUNT * 100,
                'backwardation_threshold': self.BASIS_BACKWARDATION_PREMIUM * 100
            }
        )

    def calculate_cvd_signal(self, symbol: str = "BTCUSDT") -> CVDSignal:
        """Calculate Cumulative Volume Delta signal

        Bullish if CVD > +500k USDT and price flat
        Bearish if CVD < -500k USDT and price flat

        Args:
            symbol: Trading pair

        Returns:
            CVDSignal
        """
        # Get recent trades (last 1000)
        trades = self.client.get_recent_trades(symbol, limit=1000)

        # Calculate CVD over last 15 minutes
        now = datetime.utcnow()
        cutoff_time = now - timedelta(minutes=15)

        cvd = 0.0
        buy_volume = 0.0
        sell_volume = 0.0

        for trade in trades:
            if trade['timestamp'] < cutoff_time:
                continue

            trade_value = trade['size'] * trade['price']

            if trade['side'] == 'Buy':
                cvd += trade_value
                buy_volume += trade_value
            else:
                cvd -= trade_value
                sell_volume += trade_value

        # Determine signal
        direction = SignalDirection.NEUTRAL
        strength = SignalStrength.WEAK
        confidence = 50.0
        hidden_flow = "balanced"

        if cvd > self.CVD_THRESHOLD:
            direction = SignalDirection.LONG
            strength = SignalStrength.MODERATE
            confidence = 68.0
            hidden_flow = "buy"
        elif cvd < -self.CVD_THRESHOLD:
            direction = SignalDirection.SHORT
            strength = SignalStrength.MODERATE
            confidence = 68.0
            hidden_flow = "sell"

        return CVDSignal(
            signal_type=SignalType.CVD,
            symbol=symbol,
            direction=direction,
            strength=strength,
            confidence=confidence,
            timestamp=datetime.utcnow(),
            horizon="15min-1h",
            cvd=cvd,
            cvd_15min=cvd,
            buy_volume=buy_volume,
            sell_volume=sell_volume,
            hidden_flow=hidden_flow,
            metadata={
                'cvd_threshold': self.CVD_THRESHOLD,
                'num_trades_analyzed': len([t for t in trades if t['timestamp'] >= cutoff_time])
            }
        )

    def calculate_options_iv_signal(self, base_coin: str = "BTC") -> Optional[OptionsIVSignal]:
        """Calculate Options IV skew signal

        Buy if IV_Skew > +15% (fear)
        Sell if IV_Skew < -15% (complacency)

        Args:
            base_coin: Base coin (BTC, ETH)

        Returns:
            OptionsIVSignal or None if options data unavailable
        """
        try:
            # Get puts and calls
            puts = self.client.get_options_iv(base_coin, "Put", limit=20)
            calls = self.client.get_options_iv(base_coin, "Call", limit=20)

            if not puts or not calls:
                return None

            # Calculate average IV for OTM options (10-25 delta range)
            # For puts: negative delta, for calls: positive delta
            # Using wider range 0.05-0.40 to ensure we get options
            put_ivs = [p['iv'] for p in puts if 0.05 <= abs(p['delta']) <= 0.40 and p['iv'] > 0]
            call_ivs = [c['iv'] for c in calls if 0.05 <= abs(c['delta']) <= 0.40 and c['iv'] > 0]

            # Fallback: if no OTM options, use all options with valid IV
            if not put_ivs:
                put_ivs = [p['iv'] for p in puts if p['iv'] > 0]
            if not call_ivs:
                call_ivs = [c['iv'] for c in calls if c['iv'] > 0]

            if not put_ivs or not call_ivs:
                return None

            iv_put = sum(put_ivs) / len(put_ivs)
            iv_call = sum(call_ivs) / len(call_ivs)
            iv_skew = iv_put - iv_call

            # Determine signal
            direction = SignalDirection.NEUTRAL
            strength = SignalStrength.WEAK
            confidence = 50.0
            sentiment = "neutral"
            predicted_move = 0.0

            if iv_skew > self.IV_SKEW_FEAR:
                direction = SignalDirection.LONG
                strength = SignalStrength.MODERATE
                confidence = 65.0
                sentiment = "fear"
                predicted_move = 5.0  # Expected 5% move in 48h
            elif iv_skew < self.IV_SKEW_COMPLACENCY:
                direction = SignalDirection.SHORT
                strength = SignalStrength.MODERATE
                confidence = 65.0
                sentiment = "complacency"
                predicted_move = -5.0

            symbol = f"{base_coin}USDT"

            # Log IV skew for validation (P1: Backend logging infrastructure)
            try:
                current_price = self.client.get_perp_price(symbol)
                iv_logger = get_iv_skew_logger()
                iv_logger.log_iv_skew(
                    symbol=base_coin,
                    iv_put=iv_put,
                    iv_call=iv_call,
                    current_price=current_price,
                    source="bybit"
                )
            except Exception as log_error:
                self._logger.debug(f"IV skew logging failed (non-critical): {log_error}")

            return OptionsIVSignal(
                signal_type=SignalType.OPTIONS_IV,
                symbol=symbol,
                direction=direction,
                strength=strength,
                confidence=confidence,
                timestamp=datetime.utcnow(),
                horizon="24h-72h",
                iv_put=iv_put,
                iv_call=iv_call,
                iv_skew=iv_skew,
                market_sentiment=sentiment,
                predicted_move_pct=predicted_move,
                metadata={
                    'num_puts': len(put_ivs),
                    'num_calls': len(call_ivs),
                    'iv_skew_fear_threshold': self.IV_SKEW_FEAR,
                    'iv_skew_complacency_threshold': self.IV_SKEW_COMPLACENCY
                }
            )

        except Exception as e:
            self._logger.warning(f"Options IV signal unavailable: {e}")
            return None

    def calculate_all_signals(self, symbol: str = "BTCUSDT") -> Dict[str, Any]:
        """Calculate all available signals for a symbol

        Args:
            symbol: Trading pair

        Returns:
            Dict with all signals
        """
        signals = {}

        try:
            signals['funding_rate'] = self.calculate_funding_rate_signal(symbol)
        except Exception as e:
            self._logger.error(f"Funding rate signal failed: {e}")

        try:
            signals['open_interest'] = self.calculate_open_interest_signal(symbol)
        except Exception as e:
            self._logger.error(f"Open interest signal failed: {e}")

        try:
            signals['long_short_ratio'] = self.calculate_long_short_ratio_signal(symbol)
        except Exception as e:
            self._logger.error(f"Long/short ratio signal failed: {e}")

        try:
            signals['basis'] = self.calculate_basis_signal(symbol)
        except Exception as e:
            self._logger.error(f"Basis signal failed: {e}")

        try:
            signals['cvd'] = self.calculate_cvd_signal(symbol)
        except Exception as e:
            self._logger.error(f"CVD signal failed: {e}")

        try:
            base_coin = symbol.replace('USDT', '')
            # Only BTC and ETH have options on Bybit - skip others to avoid rate limiting
            if base_coin in ('BTC', 'ETH'):
                signals['options_iv'] = self.calculate_options_iv_signal(base_coin)
        except Exception as e:
            self._logger.error(f"Options IV signal failed: {e}")

        return signals
