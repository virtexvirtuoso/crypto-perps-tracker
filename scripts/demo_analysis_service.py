#!/usr/bin/env python3
"""
AnalysisService Demonstration - Market Analysis & Sentiment

This script demonstrates the AnalysisService which provides:
- Market sentiment calculation from funding rates
- Volume anomaly detection
- OI/Volume ratio analysis
- Funding rate arbitrage opportunities
- Composite market health scoring

All analysis is performed on cached exchange data for maximum performance.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.config import Config
from src.container import Container


def print_header(title: str):
    """Print a formatted header"""
    print("\n" + "="*100)
    print(f"  {title}")
    print("="*100 + "\n")


def main():
    """Demonstrate AnalysisService capabilities"""

    print_header("MARKET ANALYSIS SERVICE DEMO")

    # Initialize container
    try:
        config = Config.from_yaml('config/config.yaml')
    except (FileNotFoundError, ValueError) as e:
        print(f"⚠️  Config error ({e}), using default configuration")
        config = Config(
            app_name="Crypto Perps Tracker",
            environment="development"
        )

    container = Container(config)
    analysis_service = container.analysis_service

    print("✅ Services initialized")
    print(f"   Exchange Service: {container.exchange_service}")
    print(f"   Analysis Service: {analysis_service}\n")

    # ============================================================
    # Demo 1: Market Sentiment Analysis
    # ============================================================
    print_header("1. Market Sentiment Analysis")
    print("📊 Analyzing funding rates across all exchanges...\n")

    sentiment = analysis_service.calculate_market_sentiment()

    print(f"Overall Sentiment: {sentiment['sentiment'].value.upper()}")
    print(f"Sentiment Score: {sentiment['score']:.2f} (range: -1 to +1)")
    print(f"Average Funding Rate: {sentiment['avg_funding_rate_pct']:.4f}%")
    print(f"\nExchange Breakdown:")
    print(f"   🟢 Bullish: {sentiment['bullish_exchanges']}")
    print(f"   🔴 Bearish: {sentiment['bearish_exchanges']}")
    print(f"   ⚪ Neutral: {sentiment['neutral_exchanges']}")
    print(f"   Total: {sentiment['total_exchanges']}")

    print(f"\n📈 Funding Rates by Exchange:")
    print(f"   {'Exchange':<15} {'Funding Rate':<15} {'Sentiment'}")
    print("   " + "-"*50)
    for exchange in sentiment['exchanges'][:5]:  # Top 5
        sentiment_icon = "🟢" if exchange['sentiment'] == 'bullish' else "🔴" if exchange['sentiment'] == 'bearish' else "⚪"
        print(f"   {exchange['exchange']:<15} {exchange['funding_rate_pct']:>8.4f}%      {sentiment_icon} {exchange['sentiment']}")

    # ============================================================
    # Demo 2: Volume Anomaly Detection
    # ============================================================
    print_header("2. Volume Anomaly Detection")
    print("🔍 Detecting exchanges with unusually high volume...\n")

    anomalies = analysis_service.detect_volume_anomalies(threshold_multiplier=1.5)

    if anomalies:
        print(f"Found {len(anomalies)} exchanges with high volume:\n")
        print(f"   {'Exchange':<15} {'Volume':<20} {'vs Average':<15} {'Deviation'}")
        print("   " + "-"*70)
        for anomaly in anomalies:
            print(
                f"   {anomaly['exchange']:<15} "
                f"${anomaly['volume_24h']/1e9:>7.2f}B        "
                f"{anomaly['volume_ratio']:>7.2f}x        "
                f"+{anomaly['deviation_pct']:>6.1f}%"
            )
    else:
        print("✅ No significant volume anomalies detected")
        print("   All exchanges are trading within normal ranges")

    # ============================================================
    # Demo 3: OI/Volume Ratio Analysis
    # ============================================================
    print_header("3. Open Interest / Volume Ratio Analysis")
    print("📊 Analyzing market conviction levels...\n")

    oi_analysis = analysis_service.analyze_oi_volume_ratios()

    print(f"Market Average OI/Vol Ratio: {oi_analysis['avg_ratio']:.2f}x")
    print(f"Total Open Interest: ${oi_analysis['total_oi']/1e9:,.2f}B")
    print(f"Total 24h Volume: ${oi_analysis['total_volume']/1e9:,.2f}B")

    print(f"\n📈 Exchange Analysis:")
    print(f"   {'Exchange':<15} {'OI/Vol Ratio':<15} {'Classification':<15} {'Interpretation'}")
    print("   " + "-"*90)

    for exchange in oi_analysis['exchanges'][:5]:  # Top 5
        ratio_icon = "🔥" if exchange['classification'] == 'very_high' else "📈" if exchange['classification'] == 'high' else "📊"
        print(
            f"   {exchange['exchange']:<15} "
            f"{exchange['oi_volume_ratio']:>7.2f}x        "
            f"{ratio_icon} {exchange['classification']:<12} "
            f"{exchange['interpretation']}"
        )

    print("\n💡 Interpretation:")
    print("   • High ratio (>2.0x) = Traders holding positions, high conviction")
    print("   • Low ratio (<0.5x) = Heavy day trading, low conviction")
    print("   • Moderate (0.5-2.0x) = Balanced market activity")

    # ============================================================
    # Demo 4: Funding Rate Arbitrage Opportunities
    # ============================================================
    print_header("4. Funding Rate Arbitrage Opportunities")
    print("💰 Searching for arbitrage opportunities...\n")

    opportunities = analysis_service.find_funding_arbitrage_opportunities(min_spread=0.001)

    if opportunities:
        print(f"Found {len(opportunities)} potential arbitrage opportunities:\n")
        print(f"   {'Long (Low FR)':<15} {'Short (High FR)':<15} {'Spread':<12} {'Est. Annual Return'}")
        print("   " + "-"*75)

        for opp in opportunities[:3]:  # Top 3
            print(
                f"   {opp['long_exchange']:<15} "
                f"{opp['short_exchange']:<15} "
                f"{opp['spread_pct']:>7.4f}%    "
                f"{opp['annual_return_estimate']:>6.2f}%"
            )

        print("\n💡 Strategy:")
        print("   • Long position on exchange with lower funding rate")
        print("   • Short position on exchange with higher funding rate")
        print("   • Collect funding rate spread (3x per day)")
        print("   ⚠️  Note: Estimates assume constant rates, real returns may vary")
    else:
        print("✅ No significant arbitrage opportunities")
        print("   Funding rates are well-aligned across exchanges")

    # ============================================================
    # Demo 5: Composite Market Health Score
    # ============================================================
    print_header("5. Composite Market Health Score")
    print("🏥 Calculating overall market health...\n")

    health = analysis_service.calculate_composite_score()

    print(f"Overall Market Health: {health['composite_score']:.1f}/100")
    print(f"Rating: {health['rating']}")

    print(f"\n📊 Score Breakdown:")
    components = health['components']
    print(f"   Volume Score:      {components['volume_score']:>5.1f}/25  (higher volume = better)")
    print(f"   Market Depth:      {components['depth_score']:>5.1f}/25  (optimal OI/Vol ratio)")
    print(f"   Efficiency:        {components['efficiency_score']:>5.1f}/25  (low funding spread)")
    print(f"   Diversity:         {components['diversity_score']:>5.1f}/25  (number of exchanges)")
    print(f"   {'─' * 50}")
    print(f"   Total:             {health['composite_score']:>5.1f}/100")

    print(f"\n📈 Market Metrics:")
    metrics = health['metrics']
    print(f"   Total Volume:      ${metrics['total_volume']/1e9:>8.2f}B")
    print(f"   Total OI:          ${metrics['total_oi']/1e9:>8.2f}B")
    print(f"   OI/Vol Ratio:      {metrics['avg_oi_volume_ratio']:>8.2f}x")
    print(f"   Active Exchanges:  {metrics['num_exchanges']:>8}")

    print(f"\n💡 Health Rating Guide:")
    print("   • 90-100: Excellent - Very healthy, liquid market")
    print("   • 75-89:  Good - Healthy market with good liquidity")
    print("   • 60-74:  Fair - Adequate market conditions")
    print("   • 40-59:  Poor - Thin liquidity or inefficiencies")
    print("   • 0-39:   Very Poor - Low liquidity, avoid trading")

    # ============================================================
    # Summary
    # ============================================================
    print_header("ARCHITECTURE BENEFITS")

    print("✅ Business Logic Separation:")
    print("   • All analysis logic in AnalysisService")
    print("   • Reusable across different scripts and interfaces")
    print("   • Easy to test with mocked ExchangeService")

    print("\n✅ Type Safety:")
    print("   • Strong typing with enums (MarketSentiment)")
    print("   • Clear return types for all methods")
    print("   • Pydantic validation on input data")

    print("\n✅ Performance:")
    print("   • Analysis uses cached exchange data")
    print("   • No redundant API calls")
    print("   • Fast computation on in-memory data")

    print("\n✅ Extensibility:")
    print("   • Easy to add new analysis methods")
    print("   • Can combine with other services (AlertService, ReportService)")
    print("   • Clean dependencies via constructor injection")

    print("\n💡 Next Steps:")
    print("   • Use AnalysisService in report generation")
    print("   • Integrate with AlertService for intelligent alerts")
    print("   • Add historical trend analysis")
    print("   • Create dashboard visualization")

    print("\n" + "="*100 + "\n")


if __name__ == "__main__":
    main()
