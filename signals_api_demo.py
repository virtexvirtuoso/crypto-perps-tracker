#!/usr/bin/env python3
"""
Derivatives Signals API Demo

This script demonstrates how to use the Derivatives Signals API
to get trading signals and make trading decisions.
"""

import requests
import time
from typing import Dict, Any
from datetime import datetime


class SignalsAPIClient:
    """Client for Derivatives Signals API"""

    def __init__(self, base_url: str = "http://localhost:8000"):
        """Initialize API client

        Args:
            base_url: API base URL
        """
        self.base_url = base_url
        self.session = requests.Session()

    def get_fusion_signal(self, symbol: str = "BTCUSDT") -> Dict[str, Any]:
        """Get fusion signal (highest edge)

        Args:
            symbol: Trading symbol

        Returns:
            Fusion signal data
        """
        url = f"{self.base_url}/signals/fusion/{symbol}"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def get_recommendation(self, symbol: str = "BTCUSDT") -> Dict[str, Any]:
        """Get human-readable recommendation

        Args:
            symbol: Trading symbol

        Returns:
            Recommendation data
        """
        url = f"{self.base_url}/recommendation/{symbol}"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def get_all_signals(self, symbol: str = "BTCUSDT") -> Dict[str, Any]:
        """Get all available signals

        Args:
            symbol: Trading symbol

        Returns:
            All signals data
        """
        url = f"{self.base_url}/signals/all/{symbol}"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def get_funding_rate(self, symbol: str = "BTCUSDT") -> Dict[str, Any]:
        """Get funding rate signal

        Args:
            symbol: Trading symbol

        Returns:
            Funding rate signal
        """
        url = f"{self.base_url}/signals/funding-rate/{symbol}"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()


def print_section(title: str):
    """Print section header"""
    print(f"\n{'=' * 80}")
    print(f"  {title}")
    print(f"{'=' * 80}\n")


def print_fusion_signal(data: Dict[str, Any]):
    """Pretty print fusion signal"""
    signal = data['signal']

    print(f"Symbol: {signal['symbol']}")
    print(f"Timestamp: {signal['timestamp']}")
    print(f"\n📊 SIGNAL ANALYSIS")
    print(f"   Direction: {signal['direction'].upper()}")
    print(f"   Strength: {signal['strength'].upper()}")
    print(f"   Confidence: {signal['confidence']:.1f}%")
    print(f"   Win Rate Estimate: {signal['win_rate_estimate']:.1f}%")
    print(f"\n🎯 COMPOSITE SCORE: {signal['score']}")
    print(f"   Funding Rate Contribution: {signal['funding_contribution']:+d}")
    print(f"   Open Interest Contribution: {signal['oi_contribution']:+d}")
    print(f"   Long/Short Ratio Contribution: {signal['lsr_contribution']:+d}")
    print(f"   CVD Contribution: {signal['cvd_contribution']:+d}")
    print(f"\n💡 RECOMMENDATION: {signal['entry_recommendation']}")
    print(f"   Horizon: {signal['horizon']}")


def print_recommendation(data: Dict[str, Any]):
    """Pretty print recommendation"""
    rec = data['data']

    print(f"Symbol: {rec['symbol']}")
    print(f"Timestamp: {rec['timestamp']}")
    print(f"\n🎯 RECOMMENDATION: {rec['recommendation']}")
    print(f"   Direction: {rec['direction'].upper()}")
    print(f"   Confidence: {rec['confidence']}")
    print(f"   Win Rate Estimate: {rec['win_rate_estimate']}")
    print(f"\n📈 SCORE BREAKDOWN:")
    for key, value in rec['score_breakdown'].items():
        print(f"   {key.replace('_', ' ').title()}: {value:+d}")
    print(f"\n💭 INTERPRETATION:")
    print(f"   {rec['interpretation']}")
    print(f"\n⚠️  RISK WARNING:")
    print(f"   {rec['risk_warning']}")


def demo_basic_usage():
    """Demo basic API usage"""
    print_section("Basic Usage: Get Fusion Signal")

    client = SignalsAPIClient()

    try:
        # Get fusion signal
        data = client.get_fusion_signal("BTCUSDT")
        print_fusion_signal(data)

    except Exception as e:
        print(f"❌ Error: {e}")


def demo_recommendation():
    """Demo recommendation endpoint"""
    print_section("Human-Readable Recommendation")

    client = SignalsAPIClient()

    try:
        # Get recommendation
        data = client.get_recommendation("BTCUSDT")
        print_recommendation(data)

    except Exception as e:
        print(f"❌ Error: {e}")


def demo_individual_signals():
    """Demo individual signal endpoints"""
    print_section("Individual Signals")

    client = SignalsAPIClient()

    try:
        # Funding rate signal
        print("🔹 FUNDING RATE SIGNAL")
        data = client.get_funding_rate("BTCUSDT")
        signal = data['signal']
        print(f"   Direction: {signal['direction'].upper()}")
        print(f"   Funding Rate: {signal['funding_rate']:.6f}")
        print(f"   Threshold Crossed: {signal['threshold_crossed']}")
        print(f"   Confidence: {signal['confidence']:.1f}%\n")

    except Exception as e:
        print(f"❌ Error: {e}")


def demo_trading_decision():
    """Demo making a trading decision"""
    print_section("Trading Decision Example")

    client = SignalsAPIClient()

    try:
        # Get fusion signal
        data = client.get_fusion_signal("BTCUSDT")
        signal = data['signal']

        score = signal['score']
        print(f"Analyzing {signal['symbol']}...")
        print(f"Composite Score: {score}\n")

        # Trading logic
        if score >= 3:
            print("✅ ACTION: ENTER LONG")
            print(f"   Confidence: {signal['confidence']:.1f}%")
            print(f"   Expected Win Rate: {signal['win_rate_estimate']:.1f}%")
            print(f"\n📋 TRADE PLAN:")
            print(f"   Entry: Market order")
            print(f"   Position Size: Standard (1-2% risk)")
            print(f"   Stop Loss: Recent swing low")
            print(f"   Take Profit: 2-3R")
            print(f"   Time Horizon: {signal['horizon']}")

        elif score <= -3:
            print("✅ ACTION: ENTER SHORT")
            print(f"   Confidence: {signal['confidence']:.1f}%")
            print(f"   Expected Win Rate: {signal['win_rate_estimate']:.1f}%")
            print(f"\n📋 TRADE PLAN:")
            print(f"   Entry: Market order")
            print(f"   Position Size: Standard (1-2% risk)")
            print(f"   Stop Loss: Recent swing high")
            print(f"   Take Profit: 2-3R")
            print(f"   Time Horizon: {signal['horizon']}")

        elif abs(score) == 2:
            print("⚠️  ACTION: CONSIDER POSITION (Reduced Size)")
            print(f"   Direction: {signal['direction'].upper()}")
            print(f"   Confidence: {signal['confidence']:.1f}%")
            print(f"\n📋 TRADE PLAN:")
            print(f"   Entry: Wait for confirmation")
            print(f"   Position Size: Reduced 50%")
            print(f"   Stop Loss: Tighter stops")
            print(f"   Take Profit: 1.5-2R")

        else:
            print("⏸️  ACTION: WAIT")
            print(f"   No clear signal (score: {score})")
            print(f"   Avoid FOMO - Better opportunities will come")

    except Exception as e:
        print(f"❌ Error: {e}")


def demo_multiple_symbols():
    """Demo checking multiple symbols"""
    print_section("Multi-Symbol Scan")

    client = SignalsAPIClient()
    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

    print("Scanning symbols for trading opportunities...\n")

    opportunities = []

    for symbol in symbols:
        try:
            data = client.get_fusion_signal(symbol)
            signal = data['signal']

            score = signal['score']
            direction = signal['direction']
            confidence = signal['confidence']

            # Find high-confidence opportunities
            if abs(score) >= 3:
                opportunities.append({
                    'symbol': symbol,
                    'score': score,
                    'direction': direction,
                    'confidence': confidence,
                    'recommendation': signal['entry_recommendation']
                })

            # Print summary
            status = "🟢" if abs(score) >= 3 else "🟡" if abs(score) == 2 else "⚪"
            print(f"{status} {symbol:12} Score: {score:+2d}  "
                  f"Direction: {direction.upper():8}  "
                  f"Confidence: {confidence:5.1f}%")

            # Respect rate limits
            time.sleep(0.5)

        except Exception as e:
            print(f"❌ {symbol:12} Error: {e}")

    # Print opportunities
    if opportunities:
        print(f"\n\n🎯 FOUND {len(opportunities)} HIGH-CONFIDENCE OPPORTUNITY(IES):\n")
        for opp in opportunities:
            print(f"   {opp['symbol']}: {opp['recommendation']}")
            print(f"      Score: {opp['score']:+d}, Confidence: {opp['confidence']:.1f}%\n")
    else:
        print("\n\n⏸️  NO HIGH-CONFIDENCE OPPORTUNITIES AT THIS TIME")


def main():
    """Run all demos"""
    print("\n" + "=" * 80)
    print("  DERIVATIVES SIGNALS API - DEMO")
    print("  Make sure the API is running: python api/main.py")
    print("=" * 80)

    # Check API health
    try:
        response = requests.get("http://localhost:8000/health")
        response.raise_for_status()
        print("\n✅ API is running\n")
    except Exception as e:
        print(f"\n❌ API is not running. Please start it first.")
        print(f"   Error: {e}\n")
        return

    # Run demos
    demo_basic_usage()
    time.sleep(1)

    demo_recommendation()
    time.sleep(1)

    demo_individual_signals()
    time.sleep(1)

    demo_trading_decision()
    time.sleep(1)

    demo_multiple_symbols()

    print("\n" + "=" * 80)
    print("  DEMO COMPLETED")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
