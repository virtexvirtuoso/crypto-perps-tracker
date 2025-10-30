"""Report generation service

This service generates various types of reports combining market data
and analysis. Supports multiple output formats (text, markdown, HTML).
"""

from typing import Optional, List, Dict
from datetime import datetime, timezone
from enum import Enum
from src.services.exchange import ExchangeService
from src.services.analysis import AnalysisService, MarketSentiment


class ReportFormat(str, Enum):
    """Report output formats"""
    TEXT = "text"
    MARKDOWN = "markdown"
    HTML = "html"


class ReportService:
    """Service for generating market reports

    This service combines ExchangeService and AnalysisService to generate
    comprehensive market reports in various formats.

    Usage:
        report_service = ReportService(exchange_service, analysis_service)
        summary = report_service.generate_market_summary(format=ReportFormat.TEXT)
        print(summary)
    """

    def __init__(
        self,
        exchange_service: ExchangeService,
        analysis_service: AnalysisService
    ):
        """Initialize report service

        Args:
            exchange_service: ExchangeService instance
            analysis_service: AnalysisService instance
        """
        self.exchange_service = exchange_service
        self.analysis_service = analysis_service

    def generate_market_summary(
        self,
        format: ReportFormat = ReportFormat.TEXT,
        use_cache: bool = True
    ) -> str:
        """Generate comprehensive market summary report

        Includes volume, open interest, funding rates, and top exchanges.

        Args:
            format: Output format (text, markdown, html)
            use_cache: Whether to use cached data

        Returns:
            Formatted market summary report

        Example:
            >>> report = service.generate_market_summary(ReportFormat.TEXT)
            >>> print(report)
        """
        # Fetch data
        markets = self.exchange_service.fetch_all_markets(use_cache=use_cache)
        summary = self.exchange_service.get_market_summary(use_cache=use_cache)

        # Sort by volume
        markets = sorted(markets, key=lambda m: m.volume_24h, reverse=True)

        # Generate report based on format
        if format == ReportFormat.MARKDOWN:
            return self._format_market_summary_markdown(markets, summary)
        elif format == ReportFormat.HTML:
            return self._format_market_summary_html(markets, summary)
        else:
            return self._format_market_summary_text(markets, summary)

    def generate_sentiment_report(
        self,
        format: ReportFormat = ReportFormat.TEXT,
        use_cache: bool = True
    ) -> str:
        """Generate market sentiment analysis report

        Analyzes funding rates and market sentiment across exchanges.

        Args:
            format: Output format
            use_cache: Whether to use cached data

        Returns:
            Formatted sentiment report
        """
        sentiment = self.analysis_service.calculate_market_sentiment(use_cache=use_cache)

        if format == ReportFormat.MARKDOWN:
            return self._format_sentiment_markdown(sentiment)
        elif format == ReportFormat.HTML:
            return self._format_sentiment_html(sentiment)
        else:
            return self._format_sentiment_text(sentiment)

    def generate_arbitrage_report(
        self,
        min_spread: float = 0.01,
        format: ReportFormat = ReportFormat.TEXT,
        use_cache: bool = True
    ) -> str:
        """Generate funding rate arbitrage opportunities report

        Args:
            min_spread: Minimum spread percentage to report
            format: Output format
            use_cache: Whether to use cached data

        Returns:
            Formatted arbitrage opportunities report
        """
        opportunities = self.analysis_service.find_funding_arbitrage_opportunities(
            min_spread=min_spread,
            use_cache=use_cache
        )

        if format == ReportFormat.MARKDOWN:
            return self._format_arbitrage_markdown(opportunities, min_spread)
        elif format == ReportFormat.HTML:
            return self._format_arbitrage_html(opportunities, min_spread)
        else:
            return self._format_arbitrage_text(opportunities, min_spread)

    def generate_comprehensive_report(
        self,
        format: ReportFormat = ReportFormat.TEXT,
        use_cache: bool = True
    ) -> str:
        """Generate comprehensive market report

        Combines market summary, sentiment analysis, and arbitrage opportunities
        into a single comprehensive report.

        Args:
            format: Output format
            use_cache: Whether to use cached data

        Returns:
            Complete market report with all analyses
        """
        # Get all data
        markets = self.exchange_service.fetch_all_markets(use_cache=use_cache)
        summary = self.exchange_service.get_market_summary(use_cache=use_cache)
        sentiment = self.analysis_service.calculate_market_sentiment(use_cache=use_cache)
        health = self.analysis_service.calculate_composite_score(use_cache=use_cache)
        arbitrage = self.analysis_service.find_funding_arbitrage_opportunities(use_cache=use_cache)

        if format == ReportFormat.MARKDOWN:
            return self._format_comprehensive_markdown(markets, summary, sentiment, health, arbitrage)
        elif format == ReportFormat.HTML:
            return self._format_comprehensive_html(markets, summary, sentiment, health, arbitrage)
        else:
            return self._format_comprehensive_text(markets, summary, sentiment, health, arbitrage)

    # ============================================================
    # Text Formatting Methods
    # ============================================================

    def _format_market_summary_text(self, markets: List, summary: Dict) -> str:
        """Format market summary as plain text"""
        lines = []
        timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')

        lines.append("=" * 80)
        lines.append("PERPETUAL FUTURES MARKET SUMMARY")
        lines.append(f"Generated: {timestamp}")
        lines.append("=" * 80)
        lines.append("")

        # Exchange table
        lines.append("EXCHANGES BY VOLUME")
        lines.append("-" * 80)
        lines.append(f"{'Rank':<6}{'Exchange':<15}{'24h Volume':<20}{'Open Interest':<20}{'Markets'}")
        lines.append("-" * 80)

        for i, market in enumerate(markets, 1):
            exchange_name = market.exchange.value if hasattr(market.exchange, 'value') else str(market.exchange)
            volume_str = f"${market.volume_24h/1e9:.2f}B"
            oi_str = f"${market.open_interest/1e9:.2f}B" if market.open_interest else "N/A"

            lines.append(
                f"{i:<6}{exchange_name:<15}{volume_str:<20}{oi_str:<20}{market.market_count or 0}"
            )

        # Summary statistics
        lines.append("")
        lines.append("MARKET TOTALS")
        lines.append("-" * 80)
        lines.append(f"Total 24h Volume:     ${summary['total_volume_24h']:,.0f}")
        lines.append(f"Total Open Interest:  ${summary['total_open_interest']:,.0f}")
        lines.append(f"Total Markets:        {summary['total_markets']:,}")
        lines.append(f"Active Exchanges:     {summary['num_exchanges']}")

        if summary['total_volume_24h'] > 0:
            oi_vol_ratio = summary['total_open_interest'] / summary['total_volume_24h']
            lines.append(f"OI/Volume Ratio:      {oi_vol_ratio:.2f}x")

        lines.append("=" * 80)
        return "\n".join(lines)

    def _format_sentiment_text(self, sentiment: Dict) -> str:
        """Format sentiment analysis as plain text"""
        lines = []
        timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')

        lines.append("=" * 80)
        lines.append("MARKET SENTIMENT ANALYSIS")
        lines.append(f"Generated: {timestamp}")
        lines.append("=" * 80)
        lines.append("")

        # Overall sentiment
        sentiment_emoji = {
            MarketSentiment.EXTREME_BULLISH: "🚀",
            MarketSentiment.BULLISH: "🟢",
            MarketSentiment.NEUTRAL: "⚪",
            MarketSentiment.BEARISH: "🔴",
            MarketSentiment.EXTREME_BEARISH: "💀"
        }.get(sentiment['sentiment'], "⚪")

        lines.append(f"Overall Sentiment: {sentiment_emoji} {sentiment['sentiment'].value.upper()}")
        lines.append(f"Sentiment Score: {sentiment['score']:.2f} (range: -1 to +1)")
        lines.append(f"Average Funding Rate: {sentiment['avg_funding_rate_pct']:.4f}%")
        lines.append("")

        # Breakdown
        lines.append("EXCHANGE BREAKDOWN")
        lines.append("-" * 80)
        lines.append(f"Bullish Exchanges: {sentiment['bullish_exchanges']}")
        lines.append(f"Bearish Exchanges: {sentiment['bearish_exchanges']}")
        lines.append(f"Neutral Exchanges: {sentiment['neutral_exchanges']}")
        lines.append("")

        # Exchange details
        lines.append("FUNDING RATES BY EXCHANGE")
        lines.append("-" * 80)
        lines.append(f"{'Exchange':<15}{'Funding Rate':<15}{'Sentiment'}")
        lines.append("-" * 80)

        for exchange in sentiment['exchanges']:
            sentiment_icon = "🟢" if exchange['sentiment'] == 'bullish' else "🔴" if exchange['sentiment'] == 'bearish' else "⚪"
            lines.append(
                f"{exchange['exchange']:<15}{exchange['funding_rate_pct']:>8.4f}%      "
                f"{sentiment_icon} {exchange['sentiment']}"
            )

        lines.append("=" * 80)
        return "\n".join(lines)

    def _format_arbitrage_text(self, opportunities: List[Dict], min_spread: float) -> str:
        """Format arbitrage opportunities as plain text"""
        lines = []
        timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')

        lines.append("=" * 80)
        lines.append("FUNDING RATE ARBITRAGE OPPORTUNITIES")
        lines.append(f"Generated: {timestamp}")
        lines.append(f"Minimum Spread: {min_spread:.4f}%")
        lines.append("=" * 80)
        lines.append("")

        if opportunities:
            lines.append(f"Found {len(opportunities)} opportunities")
            lines.append("")
            lines.append("OPPORTUNITIES (sorted by profitability)")
            lines.append("-" * 80)
            lines.append(f"{'Long Exchange':<15}{'Short Exchange':<15}{'Spread %':<12}{'Est. Annual %'}")
            lines.append("-" * 80)

            for opp in opportunities:
                lines.append(
                    f"{opp['long_exchange']:<15}"
                    f"{opp['short_exchange']:<15}"
                    f"{opp['spread_pct']:>7.4f}%    "
                    f"{opp['annual_return_estimate']:>6.2f}%"
                )

            lines.append("")
            lines.append("STRATEGY:")
            lines.append("• Long position on exchange with lower funding rate")
            lines.append("• Short position on exchange with higher funding rate")
            lines.append("• Collect spread 3x per day (every 8 hours)")
            lines.append("⚠️  Estimates assume constant rates and ignore fees")
        else:
            lines.append("No arbitrage opportunities found")
            lines.append("Funding rates are well-aligned across exchanges")

        lines.append("=" * 80)
        return "\n".join(lines)

    def _format_comprehensive_text(
        self,
        markets: List,
        summary: Dict,
        sentiment: Dict,
        health: Dict,
        arbitrage: List[Dict]
    ) -> str:
        """Format comprehensive report as plain text"""
        lines = []
        timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')

        lines.append("=" * 100)
        lines.append(" " * 30 + "COMPREHENSIVE MARKET REPORT")
        lines.append(f"{timestamp:^100}")
        lines.append("=" * 100)
        lines.append("")

        # Executive Summary
        lines.append("📊 EXECUTIVE SUMMARY")
        lines.append("-" * 100)

        sentiment_emoji = {
            MarketSentiment.EXTREME_BULLISH: "🚀 EXTREME BULLISH",
            MarketSentiment.BULLISH: "🟢 BULLISH",
            MarketSentiment.NEUTRAL: "⚪ NEUTRAL",
            MarketSentiment.BEARISH: "🔴 BEARISH",
            MarketSentiment.EXTREME_BEARISH: "💀 EXTREME BEARISH"
        }.get(sentiment['sentiment'], "⚪ NEUTRAL")

        lines.append(f"Market Sentiment: {sentiment_emoji}")
        lines.append(f"Market Health: {health['composite_score']:.1f}/100 ({health['rating']})")
        lines.append(f"Total Volume (24h): ${summary['total_volume_24h']/1e9:.2f}B")
        lines.append(f"Total Open Interest: ${summary['total_open_interest']/1e9:.2f}B")
        lines.append(f"Active Exchanges: {summary['num_exchanges']}")
        lines.append("")

        # Top Exchanges
        lines.append("🏆 TOP EXCHANGES BY VOLUME")
        lines.append("-" * 100)

        markets_sorted = sorted(markets, key=lambda m: m.volume_24h, reverse=True)
        for i, market in enumerate(markets_sorted[:5], 1):
            exchange_name = market.exchange.value if hasattr(market.exchange, 'value') else str(market.exchange)
            lines.append(
                f"{i}. {exchange_name:<15} ${market.volume_24h/1e9:>6.2f}B volume  "
                f"${(market.open_interest or 0)/1e9:>6.2f}B OI  "
                f"{market.market_count or 0} markets"
            )
        lines.append("")

        # Market Sentiment Details
        lines.append("📈 MARKET SENTIMENT")
        lines.append("-" * 100)
        lines.append(f"Sentiment Score: {sentiment['score']:.2f} (range: -1 to +1)")
        lines.append(f"Avg Funding Rate: {sentiment['avg_funding_rate_pct']:.4f}%")
        lines.append(f"Bullish: {sentiment['bullish_exchanges']} | "
                    f"Neutral: {sentiment['neutral_exchanges']} | "
                    f"Bearish: {sentiment['bearish_exchanges']}")
        lines.append("")

        # Market Health
        lines.append("🏥 MARKET HEALTH SCORE")
        lines.append("-" * 100)
        components = health['components']
        lines.append(f"Volume Score:     {components['volume_score']:>5.1f}/25")
        lines.append(f"Market Depth:     {components['depth_score']:>5.1f}/25")
        lines.append(f"Efficiency:       {components['efficiency_score']:>5.1f}/25")
        lines.append(f"Diversity:        {components['diversity_score']:>5.1f}/25")
        lines.append(f"{'─' * 30}")
        lines.append(f"Total:            {health['composite_score']:>5.1f}/100  ({health['rating']})")
        lines.append("")

        # Arbitrage Opportunities
        lines.append("💰 ARBITRAGE OPPORTUNITIES")
        lines.append("-" * 100)

        if arbitrage:
            lines.append(f"Found {len(arbitrage)} opportunities:")
            for i, opp in enumerate(arbitrage[:3], 1):
                lines.append(
                    f"{i}. Long {opp['long_exchange']}, Short {opp['short_exchange']} → "
                    f"{opp['spread_pct']:.4f}% spread ({opp['annual_return_estimate']:.2f}% annual)"
                )
        else:
            lines.append("No significant arbitrage opportunities detected")

        lines.append("")
        lines.append("=" * 100)
        lines.append("")
        lines.append("⚠️  DISCLAIMER: This report is for informational purposes only.")
        lines.append("   Not financial advice. Always do your own research.")
        lines.append("")

        return "\n".join(lines)

    # ============================================================
    # Markdown Formatting Methods
    # ============================================================

    def _format_market_summary_markdown(self, markets: List, summary: Dict) -> str:
        """Format market summary as markdown"""
        lines = []
        timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')

        lines.append("# Perpetual Futures Market Summary")
        lines.append(f"*Generated: {timestamp}*")
        lines.append("")

        # Exchange table
        lines.append("## Exchanges by Volume")
        lines.append("")
        lines.append("| Rank | Exchange | 24h Volume | Open Interest | Markets |")
        lines.append("|------|----------|------------|---------------|---------|")

        for i, market in enumerate(markets, 1):
            exchange_name = market.exchange.value if hasattr(market.exchange, 'value') else str(market.exchange)
            volume_str = f"${market.volume_24h/1e9:.2f}B"
            oi_str = f"${market.open_interest/1e9:.2f}B" if market.open_interest else "N/A"

            lines.append(
                f"| {i} | {exchange_name} | {volume_str} | {oi_str} | {market.market_count or 0} |"
            )

        # Summary
        lines.append("")
        lines.append("## Market Totals")
        lines.append("")
        lines.append(f"- **Total 24h Volume:** ${summary['total_volume_24h']:,.0f}")
        lines.append(f"- **Total Open Interest:** ${summary['total_open_interest']:,.0f}")
        lines.append(f"- **Total Markets:** {summary['total_markets']:,}")
        lines.append(f"- **Active Exchanges:** {summary['num_exchanges']}")

        return "\n".join(lines)

    def _format_sentiment_markdown(self, sentiment: Dict) -> str:
        """Format sentiment as markdown"""
        lines = []
        timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')

        lines.append("# Market Sentiment Analysis")
        lines.append(f"*Generated: {timestamp}*")
        lines.append("")

        sentiment_emoji = {
            MarketSentiment.EXTREME_BULLISH: "🚀",
            MarketSentiment.BULLISH: "🟢",
            MarketSentiment.NEUTRAL: "⚪",
            MarketSentiment.BEARISH: "🔴",
            MarketSentiment.EXTREME_BEARISH: "💀"
        }.get(sentiment['sentiment'], "⚪")

        lines.append(f"## Overall: {sentiment_emoji} {sentiment['sentiment'].value.upper()}")
        lines.append("")
        lines.append(f"- **Score:** {sentiment['score']:.2f} (range: -1 to +1)")
        lines.append(f"- **Avg Funding Rate:** {sentiment['avg_funding_rate_pct']:.4f}%")
        lines.append("")

        # Exchange table
        lines.append("## Funding Rates by Exchange")
        lines.append("")
        lines.append("| Exchange | Funding Rate | Sentiment |")
        lines.append("|----------|--------------|-----------|")

        for exchange in sentiment['exchanges']:
            sentiment_icon = "🟢" if exchange['sentiment'] == 'bullish' else "🔴" if exchange['sentiment'] == 'bearish' else "⚪"
            lines.append(
                f"| {exchange['exchange']} | {exchange['funding_rate_pct']:.4f}% | "
                f"{sentiment_icon} {exchange['sentiment']} |"
            )

        return "\n".join(lines)

    def _format_arbitrage_markdown(self, opportunities: List[Dict], min_spread: float) -> str:
        """Format arbitrage opportunities as markdown"""
        lines = []
        timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')

        lines.append("# Funding Rate Arbitrage Opportunities")
        lines.append(f"*Generated: {timestamp}*")
        lines.append(f"*Minimum Spread: {min_spread:.4f}%*")
        lines.append("")

        if opportunities:
            lines.append(f"Found **{len(opportunities)} opportunities**")
            lines.append("")
            lines.append("| Long Exchange | Short Exchange | Spread % | Est. Annual % |")
            lines.append("|---------------|----------------|----------|---------------|")

            for opp in opportunities:
                lines.append(
                    f"| {opp['long_exchange']} | {opp['short_exchange']} | "
                    f"{opp['spread_pct']:.4f}% | {opp['annual_return_estimate']:.2f}% |"
                )
        else:
            lines.append("No arbitrage opportunities found.")

        return "\n".join(lines)

    def _format_comprehensive_markdown(
        self,
        markets: List,
        summary: Dict,
        sentiment: Dict,
        health: Dict,
        arbitrage: List[Dict]
    ) -> str:
        """Format comprehensive report as markdown"""
        # Combine all markdown sections
        sections = []

        sections.append("# Comprehensive Market Report")
        sections.append(f"*Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}*")
        sections.append("")

        sections.append(self._format_market_summary_markdown(markets, summary))
        sections.append("")
        sections.append(self._format_sentiment_markdown(sentiment))
        sections.append("")
        sections.append(self._format_arbitrage_markdown(arbitrage, 0.001))

        return "\n".join(sections)

    # ============================================================
    # HTML Formatting Methods (Simplified)
    # ============================================================

    def _format_market_summary_html(self, markets: List, summary: Dict) -> str:
        """Format market summary as HTML"""
        # Simplified HTML - could be enhanced with CSS
        return f"<h1>Market Summary</h1><p>Use markdown or text format for now</p>"

    def _format_sentiment_html(self, sentiment: Dict) -> str:
        """Format sentiment as HTML"""
        return f"<h1>Sentiment Analysis</h1><p>Use markdown or text format for now</p>"

    def _format_arbitrage_html(self, opportunities: List[Dict], min_spread: float) -> str:
        """Format arbitrage as HTML"""
        return f"<h1>Arbitrage Opportunities</h1><p>Use markdown or text format for now</p>"

    def _format_comprehensive_html(
        self,
        markets: List,
        summary: Dict,
        sentiment: Dict,
        health: Dict,
        arbitrage: List[Dict]
    ) -> str:
        """Format comprehensive report as HTML"""
        return f"<h1>Comprehensive Report</h1><p>Use markdown or text format for now</p>"

    def __repr__(self) -> str:
        """String representation"""
        return (
            f"ReportService("
            f"exchange_service={self.exchange_service}, "
            f"analysis_service={self.analysis_service})"
        )
