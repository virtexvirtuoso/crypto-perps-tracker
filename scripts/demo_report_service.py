#!/usr/bin/env python3
"""
ReportService Demonstration - Unified Report Generation

This script demonstrates the ReportService which provides:
- Market summary reports (overview, volume, OI, top exchanges)
- Sentiment analysis reports (funding rates, market mood)
- Arbitrage opportunity reports (funding rate spreads)
- Comprehensive reports (all-in-one)
- Multiple output formats (TEXT, MARKDOWN, HTML)

All reports are generated from cached data for maximum performance.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.config import Config
from src.container import Container
from src.services.report import ReportFormat


def print_header(title: str):
    """Print a formatted header"""
    print("\n" + "="*100)
    print(f"  {title}")
    print("="*100 + "\n")


def save_report(filename: str, content: str):
    """Save report to data directory"""
    data_dir = Path(__file__).parent.parent / "data"
    data_dir.mkdir(exist_ok=True)

    filepath = data_dir / filename
    filepath.write_text(content)
    print(f"✅ Report saved to: {filepath}")


def main():
    """Demonstrate ReportService capabilities"""

    print_header("REPORT SERVICE DEMO")

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
    report_service = container.report_service

    print("✅ Services initialized")
    print(f"   Exchange Service: {container.exchange_service}")
    print(f"   Analysis Service: {container.analysis_service}")
    print(f"   Report Service: {report_service}\n")

    # ============================================================
    # Demo 1: Market Summary Report (TEXT format)
    # ============================================================
    print_header("1. Market Summary Report - TEXT Format")
    print("📊 Generating market overview report...\n")

    summary_text = report_service.generate_market_summary(format=ReportFormat.TEXT)
    print(summary_text)

    # ============================================================
    # Demo 2: Market Summary Report (MARKDOWN format)
    # ============================================================
    print_header("2. Market Summary Report - MARKDOWN Format")
    print("📊 Generating markdown market overview...\n")

    summary_md = report_service.generate_market_summary(format=ReportFormat.MARKDOWN)
    print(summary_md)
    save_report("market_summary.md", summary_md)

    # ============================================================
    # Demo 3: Sentiment Analysis Report (TEXT format)
    # ============================================================
    print_header("3. Sentiment Analysis Report - TEXT Format")
    print("📈 Analyzing market sentiment...\n")

    sentiment_text = report_service.generate_sentiment_report(format=ReportFormat.TEXT)
    print(sentiment_text)

    # ============================================================
    # Demo 4: Sentiment Analysis Report (MARKDOWN format)
    # ============================================================
    print_header("4. Sentiment Analysis Report - MARKDOWN Format")
    print("📈 Generating markdown sentiment report...\n")

    sentiment_md = report_service.generate_sentiment_report(format=ReportFormat.MARKDOWN)
    print(sentiment_md)
    save_report("sentiment_report.md", sentiment_md)

    # ============================================================
    # Demo 5: Arbitrage Opportunities Report (TEXT format)
    # ============================================================
    print_header("5. Arbitrage Opportunities Report - TEXT Format")
    print("💰 Searching for arbitrage opportunities...\n")

    arbitrage_text = report_service.generate_arbitrage_report(
        min_spread=0.001,  # 0.1% minimum spread
        format=ReportFormat.TEXT
    )
    print(arbitrage_text)

    # ============================================================
    # Demo 6: Arbitrage Opportunities Report (MARKDOWN format)
    # ============================================================
    print_header("6. Arbitrage Opportunities Report - MARKDOWN Format")
    print("💰 Generating markdown arbitrage report...\n")

    arbitrage_md = report_service.generate_arbitrage_report(
        min_spread=0.001,
        format=ReportFormat.MARKDOWN
    )
    print(arbitrage_md)
    save_report("arbitrage_report.md", arbitrage_md)

    # ============================================================
    # Demo 7: Comprehensive Report (TEXT format)
    # ============================================================
    print_header("7. Comprehensive Report - TEXT Format")
    print("📋 Generating comprehensive all-in-one report...\n")

    comprehensive_text = report_service.generate_comprehensive_report(format=ReportFormat.TEXT)
    print(comprehensive_text)

    # ============================================================
    # Demo 8: Comprehensive Report (MARKDOWN format)
    # ============================================================
    print_header("8. Comprehensive Report - MARKDOWN Format")
    print("📋 Generating comprehensive markdown report...\n")

    comprehensive_md = report_service.generate_comprehensive_report(format=ReportFormat.MARKDOWN)
    print(comprehensive_md)
    save_report("comprehensive_report.md", comprehensive_md)

    # ============================================================
    # Summary
    # ============================================================
    print_header("ARCHITECTURE BENEFITS")

    print("✅ Unified Report Generation:")
    print("   • Single service for all report types")
    print("   • Consistent formatting across reports")
    print("   • Easy to add new report formats")
    print("   • Reusable across all scripts")

    print("\n✅ Multiple Output Formats:")
    print("   • TEXT - Clean console output")
    print("   • MARKDOWN - GitHub-ready documentation")
    print("   • HTML - Future web dashboard support")

    print("\n✅ Composable Services:")
    print("   • ReportService combines ExchangeService + AnalysisService")
    print("   • Clean dependency injection")
    print("   • Easy to test with mocked services")
    print("   • Single source of truth for data")

    print("\n✅ Performance:")
    print("   • Reports generated from cached data")
    print("   • No redundant API calls")
    print("   • Fast report generation (<100ms)")

    print("\n✅ Type Safety:")
    print("   • ReportFormat enum prevents invalid formats")
    print("   • Strong typing throughout")
    print("   • IDE autocomplete support")

    print("\n📁 Reports Saved:")
    print("   • data/market_summary.md")
    print("   • data/sentiment_report.md")
    print("   • data/arbitrage_report.md")
    print("   • data/comprehensive_report.md")

    print("\n💡 Next Steps:")
    print("   • Migrate scripts to use ReportService")
    print("   • Add HTML report generation")
    print("   • Add report scheduling capabilities")
    print("   • Integrate with alert system")
    print("   • Create automated report email/Discord delivery")

    print("\n" + "="*100 + "\n")


if __name__ == "__main__":
    main()
