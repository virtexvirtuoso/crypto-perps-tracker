"""Mock data fixtures for testing

Provides realistic mock data for exchange API responses and models.
"""

from datetime import datetime, timezone
from typing import Dict, Any, List
from src.models.market import MarketData, SymbolData, ExchangeType, TradingPair


def create_mock_market_data(
    exchange: ExchangeType = ExchangeType.BINANCE,
    volume_24h: float = 50_000_000_000.0,
    funding_rate: float = 0.0001,
    open_interest: float = 10_000_000_000.0,
    market_count: int = 350,
    top_pairs: List[TradingPair] = None,
) -> MarketData:
    """Create a mock MarketData object

    Args:
        exchange: Exchange type
        volume_24h: 24h trading volume in USD
        funding_rate: Current funding rate
        open_interest: Open interest in USD
        market_count: Number of active markets
        top_pairs: List of top trading pairs

    Returns:
        MarketData object
    """
    if top_pairs is None:
        top_pairs = [
            TradingPair(symbol="BTCUSDT", base="BTC", quote="USDT", volume=20_000_000_000.0),
            TradingPair(symbol="ETHUSDT", base="ETH", quote="USDT", volume=10_000_000_000.0),
            TradingPair(symbol="SOLUSDT", base="SOL", quote="USDT", volume=5_000_000_000.0),
        ]

    return MarketData(
        exchange=exchange,
        volume_24h=volume_24h,
        funding_rate=funding_rate,
        open_interest=open_interest,
        market_count=market_count,
        top_pairs=top_pairs,
        timestamp=datetime.now(timezone.utc),
    )


def create_mock_symbol_data(
    exchange: ExchangeType = ExchangeType.BINANCE,
    symbol: str = "BTCUSDT",
    price: float = 95000.0,
    volume_24h: float = 20_000_000_000.0,
    price_change_24h_pct: float = 2.5,
    open_interest: float = 5_000_000_000.0,
    funding_rate: float = 0.0001,
) -> SymbolData:
    """Create a mock SymbolData object

    Args:
        exchange: Exchange type
        symbol: Trading pair symbol
        price: Current price
        volume_24h: 24h volume in USD
        price_change_24h_pct: 24h price change percentage
        open_interest: Open interest in USD
        funding_rate: Current funding rate

    Returns:
        SymbolData object
    """
    return SymbolData(
        exchange=exchange,
        symbol=symbol,
        price=price,
        volume_24h=volume_24h,
        price_change_24h_pct=price_change_24h_pct,
        open_interest=open_interest,
        funding_rate=funding_rate,
        timestamp=datetime.now(timezone.utc),
    )


# Pre-built mock market data for all exchanges
MOCK_MARKET_DATA: Dict[str, MarketData] = {
    "binance": create_mock_market_data(
        exchange=ExchangeType.BINANCE,
        volume_24h=55_000_000_000.0,
        funding_rate=0.00012,
        open_interest=12_000_000_000.0,
        market_count=350,
    ),
    "bybit": create_mock_market_data(
        exchange=ExchangeType.BYBIT,
        volume_24h=25_000_000_000.0,
        funding_rate=0.00010,
        open_interest=8_000_000_000.0,
        market_count=280,
    ),
    "okx": create_mock_market_data(
        exchange=ExchangeType.OKX,
        volume_24h=18_000_000_000.0,
        funding_rate=0.00008,
        open_interest=6_000_000_000.0,
        market_count=220,
    ),
    "bitget": create_mock_market_data(
        exchange=ExchangeType.BITGET,
        volume_24h=12_000_000_000.0,
        funding_rate=0.00015,
        open_interest=4_000_000_000.0,
        market_count=180,
    ),
    "gateio": create_mock_market_data(
        exchange=ExchangeType.GATEIO,
        volume_24h=8_000_000_000.0,
        funding_rate=0.00005,
        open_interest=2_500_000_000.0,
        market_count=400,
    ),
    "hyperliquid": create_mock_market_data(
        exchange=ExchangeType.HYPERLIQUID,
        volume_24h=5_000_000_000.0,
        funding_rate=0.00020,
        open_interest=1_500_000_000.0,
        market_count=50,
    ),
    "dydx": create_mock_market_data(
        exchange=ExchangeType.DYDX,
        volume_24h=2_000_000_000.0,
        funding_rate=0.00007,
        open_interest=800_000_000.0,
        market_count=80,
    ),
    "coinbase_intx": create_mock_market_data(
        exchange=ExchangeType.COINBASE_INTX,
        volume_24h=1_000_000_000.0,
        funding_rate=0.00003,
        open_interest=500_000_000.0,
        market_count=30,
    ),
}


# Pre-built mock symbol data
MOCK_SYMBOL_DATA: Dict[str, Dict[str, SymbolData]] = {
    "binance": {
        "BTCUSDT": create_mock_symbol_data(
            exchange=ExchangeType.BINANCE,
            symbol="BTCUSDT",
            price=95000.0,
            volume_24h=20_000_000_000.0,
            price_change_24h_pct=2.5,
            funding_rate=0.00012,
        ),
        "ETHUSDT": create_mock_symbol_data(
            exchange=ExchangeType.BINANCE,
            symbol="ETHUSDT",
            price=3400.0,
            volume_24h=10_000_000_000.0,
            price_change_24h_pct=1.8,
            funding_rate=0.00010,
        ),
        "SOLUSDT": create_mock_symbol_data(
            exchange=ExchangeType.BINANCE,
            symbol="SOLUSDT",
            price=240.0,
            volume_24h=5_000_000_000.0,
            price_change_24h_pct=5.2,
            funding_rate=0.00025,
        ),
    },
    "bybit": {
        "BTCUSDT": create_mock_symbol_data(
            exchange=ExchangeType.BYBIT,
            symbol="BTCUSDT",
            price=95050.0,
            volume_24h=15_000_000_000.0,
            price_change_24h_pct=2.6,
            funding_rate=0.00011,
        ),
        "ETHUSDT": create_mock_symbol_data(
            exchange=ExchangeType.BYBIT,
            symbol="ETHUSDT",
            price=3405.0,
            volume_24h=8_000_000_000.0,
            price_change_24h_pct=1.9,
            funding_rate=0.00009,
        ),
    },
}


# Mock API responses for testing HTTP calls
MOCK_API_RESPONSES: Dict[str, Dict[str, Any]] = {
    "binance": {
        "ticker": [
            {
                "symbol": "BTCUSDT",
                "priceChange": "2350.00",
                "priceChangePercent": "2.50",
                "lastPrice": "95000.00",
                "volume": "210000.00",
                "quoteVolume": "20000000000.00",
            },
            {
                "symbol": "ETHUSDT",
                "priceChange": "60.00",
                "priceChangePercent": "1.80",
                "lastPrice": "3400.00",
                "volume": "2941176.47",
                "quoteVolume": "10000000000.00",
            },
        ],
        "funding_rate": [
            {
                "symbol": "BTCUSDT",
                "fundingRate": "0.00012000",
                "fundingTime": 1700000000000,
            },
            {
                "symbol": "ETHUSDT",
                "fundingRate": "0.00010000",
                "fundingTime": 1700000000000,
            },
        ],
        "open_interest": {
            "symbol": "BTCUSDT",
            "openInterest": "126315.789",
            "time": 1700000000000,
        },
    },
    "bybit": {
        "ticker": {
            "retCode": 0,
            "result": {
                "list": [
                    {
                        "symbol": "BTCUSDT",
                        "lastPrice": "95050.00",
                        "price24hPcnt": "0.026",
                        "turnover24h": "15000000000",
                        "openInterest": "157894.736",
                        "fundingRate": "0.00011",
                    },
                ],
            },
        },
    },
    "okx": {
        "ticker": {
            "code": "0",
            "data": [
                {
                    "instId": "BTC-USDT-SWAP",
                    "last": "95100.0",
                    "vol24h": "189473.68",
                    "volCcy24h": "18000000000",
                },
            ],
        },
    },
}
