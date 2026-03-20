"""
Sector Rotation Data Models - Multi-Exchange Version

Enhanced dataclasses for sector rotation analysis across 8 exchanges
covering 91.7% of perpetual futures market volume.

Migrated from Virtuoso_ccxt with multi-exchange aggregation support.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum


class SignalStrength(Enum):
    """Classification of rotation signal strength."""
    WEAK = "weak"           # 40 <= score < 55
    MODERATE = "moderate"   # 55 <= score < 70
    STRONG = "strong"       # score >= 70


class OIPriceSignal(Enum):
    """Open Interest + Price interpretation."""
    NEW_LONGS = "new_longs"               # OI rising + price rising
    NEW_SHORTS = "new_shorts"             # OI rising + price falling
    SHORT_COVER = "short_cover"           # OI falling + price rising
    LONG_LIQUIDATION = "long_liquidation" # OI falling + price falling
    NEUTRAL = "neutral"                   # No significant change


class SampleSizeFlag(Enum):
    """Data quality flag for sector sample size."""
    NORMAL = "normal"           # >= 5 symbols
    SMALL = "small"             # 3-4 symbols
    INSUFFICIENT = "insufficient"  # < 3 symbols


class ExchangeCategory(Enum):
    """Exchange categorization for CEX/DEX flow analysis."""
    CEX = "cex"
    DEX = "dex"


# ============================================================================
# Exchange Configuration - 91.7% Market Coverage
# ============================================================================

EXCHANGE_CONFIG = {
    'binance': {
        'weight': 0.35,
        'type': ExchangeCategory.CEX,
        'daily_volume': 92_000_000_000,  # $92B
        'symbol_suffix': 'USDT',
        'enabled': True,
    },
    'okx': {
        'weight': 0.18,
        'type': ExchangeCategory.CEX,
        'daily_volume': 42_000_000_000,  # $42B
        'symbol_suffix': '-USDT-SWAP',
        'enabled': True,
    },
    'bybit': {
        'weight': 0.15,
        'type': ExchangeCategory.CEX,
        'daily_volume': 36_000_000_000,  # $36B
        'symbol_suffix': 'USDT',
        'enabled': True,
    },
    'gateio': {
        'weight': 0.12,
        'type': ExchangeCategory.CEX,
        'daily_volume': 28_000_000_000,  # $28B
        'symbol_suffix': '_USDT',
        'enabled': True,
    },
    'bitget': {
        'weight': 0.07,
        'type': ExchangeCategory.CEX,
        'daily_volume': 16_000_000_000,  # $16B
        'symbol_suffix': 'USDT',
        'enabled': True,
    },
    'hyperliquid': {
        'weight': 0.06,
        'type': ExchangeCategory.DEX,
        'daily_volume': 12_000_000_000,  # $12B
        'symbol_suffix': '',  # Just base symbol
        'enabled': True,
    },
    'asterdex': {
        'weight': 0.05,
        'type': ExchangeCategory.DEX,
        'daily_volume': 12_000_000_000,  # $12B
        'symbol_suffix': '',
        'enabled': True,
    },
    'dydx': {
        'weight': 0.02,
        'type': ExchangeCategory.DEX,
        'daily_volume': 260_000_000,  # $260M
        'symbol_suffix': '-USD',
        'enabled': True,
    },
}

# Pre-calculated weights
CEX_TOTAL_WEIGHT = sum(
    cfg['weight'] for cfg in EXCHANGE_CONFIG.values()
    if cfg['type'] == ExchangeCategory.CEX and cfg['enabled']
)
DEX_TOTAL_WEIGHT = sum(
    cfg['weight'] for cfg in EXCHANGE_CONFIG.values()
    if cfg['type'] == ExchangeCategory.DEX and cfg['enabled']
)


# ============================================================================
# Symbol Mapping - Base symbols to exchange-specific formats
# ============================================================================

# Base symbols (without exchange-specific suffixes)
# Multi-exchange availability verified
SECTOR_CONFIG = {
    'DEFI': ['AAVE', 'COMP', 'SNX', 'CRV', '1INCH'],
    'DEX': ['HYPE', 'DYDX', 'UNI', 'JUP', 'GMX', 'SUSHI', 'CAKE'],
    'L1': ['ETH', 'SOL', 'AVAX', 'ADA', 'DOT', 'NEAR', 'TON', 'SUI', 'APT'],
    'L2': ['POL', 'OP', 'ARB', 'MNT', 'ZK'],
    'MEME': ['DOGE', 'SHIB', 'PEPE', 'WIF', 'BONK', 'FLOKI'],
    'AI': ['RENDER', 'TAO', 'ICP', 'GRT', 'WLD', 'AKT', 'FET'],
    'GAMING': ['AXS', 'SAND', 'MANA', 'IMX', 'GALA', 'BEAM'],
    'RWA': ['ONDO', 'OM', 'QNT', 'ALGO', 'XLM'],
    'DEPIN': ['FIL', 'AR', 'HNT', 'IOTX', 'THETA'],
    'RESTAKING': ['LDO', 'PENDLE', 'EIGEN', 'ETHFI'],
    'MODULAR': ['TIA', 'DYM', 'SAGA'],
    'BTC_ECOSYSTEM': ['STX', 'ORDI', 'RUNE'],
    'EXCHANGE': ['BNB', 'CRO', 'OKB'],
    'PRIVACY': ['XMR', 'ZEC', 'DASH'],
    'INTEROP': ['LINK', 'W', 'ZRO'],
}

# Exchange-specific symbol transformations
# Maps base symbol to exchange format where it differs from default
EXCHANGE_SYMBOL_MAP = {
    'binance': {
        # Binance uses 1000X for small tokens
        'SHIB': '1000SHIB',
        'PEPE': '1000PEPE',
        'BONK': '1000BONK',
        'FLOKI': '1000FLOKI',
        'POL': 'MATIC',  # Legacy naming
    },
    'bybit': {
        # Bybit uses different multipliers
        'SHIB': 'SHIB1000',
        'PEPE': '1000PEPE',
        'BONK': '1000BONK',
        'FLOKI': '1000FLOKI',
    },
    'okx': {
        'SHIB': '1000SHIB',
        'PEPE': '1000PEPE',
        'BONK': '1000BONK',
        'FLOKI': '1000FLOKI',
    },
    'hyperliquid': {
        # HyperLiquid uses kXXX format
        'SHIB': 'kSHIB',
        'PEPE': 'kPEPE',
        'BONK': 'kBONK',
        'FLOKI': 'kFLOKI',
    },
    'dydx': {
        # dYdX limited symbol support
    },
    'gateio': {
        'SHIB': '1000SHIB',
        'PEPE': '1000PEPE',
    },
    'bitget': {
        'SHIB': '1000SHIB',
        'PEPE': '1000PEPE',
    },
    'asterdex': {},
}

# Sectors with fewer than 5 symbols (need confidence adjustment)
SMALL_SAMPLE_SECTORS = ['MODULAR', 'EXCHANGE', 'PRIVACY', 'INTEROP', 'RESTAKING', 'BTC_ECOSYSTEM']

# Sector display names and emojis
SECTOR_METADATA = {
    'DEFI': {'name': 'DeFi', 'emoji': '🏦'},
    'DEX': {'name': 'DEX', 'emoji': '🔄'},
    'L1': {'name': 'Layer 1', 'emoji': '🏗️'},
    'L2': {'name': 'Layer 2', 'emoji': '⚡'},
    'MEME': {'name': 'Meme', 'emoji': '🐸'},
    'AI': {'name': 'AI & ML', 'emoji': '🤖'},
    'GAMING': {'name': 'Gaming', 'emoji': '🎮'},
    'RWA': {'name': 'RWA', 'emoji': '🏠'},
    'DEPIN': {'name': 'DePIN', 'emoji': '📡'},
    'RESTAKING': {'name': 'Restaking', 'emoji': '🔒'},
    'MODULAR': {'name': 'Modular', 'emoji': '🧱'},
    'BTC_ECOSYSTEM': {'name': 'BTC Eco', 'emoji': '₿'},
    'EXCHANGE': {'name': 'Exchange', 'emoji': '🏛️'},
    'PRIVACY': {'name': 'Privacy', 'emoji': '🔐'},
    'INTEROP': {'name': 'Interop', 'emoji': '🔗'},
}


# ============================================================================
# Data Classes - Multi-Exchange Enhanced
# ============================================================================

@dataclass
class ExchangeBreakdown:
    """Per-exchange metrics for a sector snapshot."""
    exchange: str = ""
    volume_24h: float = 0.0
    open_interest: float = 0.0
    avg_funding_rate: float = 0.0
    symbol_count: int = 0
    data_quality: float = 1.0  # 0-1, completeness of data

    def to_dict(self) -> Dict[str, Any]:
        return {
            'exchange': self.exchange,
            'volume_24h': self.volume_24h,
            'open_interest': self.open_interest,
            'avg_funding_rate': self.avg_funding_rate,
            'symbol_count': self.symbol_count,
            'data_quality': self.data_quality,
        }


@dataclass
class SectorSnapshot:
    """
    A point-in-time snapshot of sector metrics aggregated across exchanges.

    Enhanced from single-exchange version with:
    - Multi-exchange aggregation
    - CEX vs DEX flow metrics
    - Cross-exchange funding spread
    """
    # Identifiers
    id: Optional[int] = None
    sector_code: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)

    # Volume metrics (aggregated across exchanges)
    total_volume_24h: float = 0.0
    volume_share_pct: float = 0.0          # % of total market volume
    volume_share_zscore: float = 0.0       # Statistical significance
    volume_change_4h: float = 0.0          # % change from prior snapshot

    # Price metrics
    avg_price_change_4h: float = 0.0       # Volume-weighted avg
    avg_price_change_24h: float = 0.0
    momentum_24h: float = 0.0              # Cumulative momentum
    momentum_persistence: float = 0.0      # % periods with same sign

    # Open Interest metrics (aggregated)
    total_oi: float = 0.0
    oi_change_4h: float = 0.0
    oi_change_zscore: float = 0.0
    oi_price_signal: str = OIPriceSignal.NEUTRAL.value

    # Funding metrics (volume-weighted average across exchanges)
    avg_funding_rate: float = 0.0
    funding_zscore: float = 0.0

    # NEW: Cross-exchange funding spread (max - min)
    funding_spread: float = 0.0
    funding_spread_zscore: float = 0.0

    # Correlation metrics
    btc_correlation: float = 0.0           # Rolling 72h correlation
    btc_correlation_zscore: float = 0.0    # Breakdown detection
    sector_beta: float = 0.0               # cov(sector, btc) / var(btc)

    # Breadth metrics
    symbols_up: int = 0
    symbols_down: int = 0
    breadth_ratio: float = 0.0             # Simple up/total
    weighted_breadth: float = 0.0          # Volume-weighted breadth

    # Flow metrics
    net_flow_ratio: float = 0.0            # (buy - sell) / total

    # NEW: CEX vs DEX flow metrics
    cex_volume_share: float = 0.0          # CEX volume / total volume
    dex_volume_share: float = 0.0          # DEX volume / total volume
    cex_oi_share: float = 0.0              # CEX OI / total OI
    dex_oi_share: float = 0.0              # DEX OI / total OI
    cex_dex_flow_score: float = 0.0        # -1 (DEX favored) to +1 (CEX favored)
    cex_dex_flow_zscore: float = 0.0       # Statistical significance of shift

    # Composite metrics
    rotation_score: float = 0.0            # 0-100 composite score
    signal_strength: str = SignalStrength.WEAK.value

    # Data quality
    symbol_count: int = 0
    exchange_count: int = 0                # Number of exchanges with data
    data_quality_score: float = 0.0        # 0-1, data completeness
    confidence_level: float = 0.0          # 0-1, statistical confidence
    sample_size_flag: str = SampleSizeFlag.NORMAL.value

    # Relative strength
    sector_rs: float = 0.0                 # vs BTC performance
    sector_rs_zscore: float = 0.0          # Statistical significance

    # NEW: Per-exchange breakdown (JSON serialized)
    exchange_breakdown: List[ExchangeBreakdown] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'sector_code': self.sector_code,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            # Volume
            'total_volume_24h': self.total_volume_24h,
            'volume_share_pct': self.volume_share_pct,
            'volume_share_zscore': self.volume_share_zscore,
            'volume_change_4h': self.volume_change_4h,
            # Price
            'avg_price_change_4h': self.avg_price_change_4h,
            'avg_price_change_24h': self.avg_price_change_24h,
            'momentum_24h': self.momentum_24h,
            'momentum_persistence': self.momentum_persistence,
            # OI
            'total_oi': self.total_oi,
            'oi_change_4h': self.oi_change_4h,
            'oi_change_zscore': self.oi_change_zscore,
            'oi_price_signal': self.oi_price_signal,
            # Funding
            'avg_funding_rate': self.avg_funding_rate,
            'funding_zscore': self.funding_zscore,
            'funding_spread': self.funding_spread,
            'funding_spread_zscore': self.funding_spread_zscore,
            # Correlation
            'btc_correlation': self.btc_correlation,
            'btc_correlation_zscore': self.btc_correlation_zscore,
            'sector_beta': self.sector_beta,
            # Breadth
            'symbols_up': self.symbols_up,
            'symbols_down': self.symbols_down,
            'breadth_ratio': self.breadth_ratio,
            'weighted_breadth': self.weighted_breadth,
            # Flow
            'net_flow_ratio': self.net_flow_ratio,
            # CEX/DEX
            'cex_volume_share': self.cex_volume_share,
            'dex_volume_share': self.dex_volume_share,
            'cex_oi_share': self.cex_oi_share,
            'dex_oi_share': self.dex_oi_share,
            'cex_dex_flow_score': self.cex_dex_flow_score,
            'cex_dex_flow_zscore': self.cex_dex_flow_zscore,
            # Composite
            'rotation_score': self.rotation_score,
            'signal_strength': self.signal_strength,
            # Quality
            'symbol_count': self.symbol_count,
            'exchange_count': self.exchange_count,
            'data_quality_score': self.data_quality_score,
            'confidence_level': self.confidence_level,
            'sample_size_flag': self.sample_size_flag,
            # RS
            'sector_rs': self.sector_rs,
            'sector_rs_zscore': self.sector_rs_zscore,
            # Breakdown
            'exchange_breakdown': [eb.to_dict() for eb in self.exchange_breakdown],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SectorSnapshot':
        """Create instance from dictionary."""
        if isinstance(data.get('timestamp'), str):
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])

        # Handle exchange breakdown
        if 'exchange_breakdown' in data and isinstance(data['exchange_breakdown'], list):
            data['exchange_breakdown'] = [
                ExchangeBreakdown(**eb) if isinstance(eb, dict) else eb
                for eb in data['exchange_breakdown']
            ]

        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class SectorSignal:
    """
    A detected rotation signal with confirmation status.

    Signals require 2+ consecutive snapshots at MODERATE+ strength
    before being considered confirmed.
    """
    id: Optional[int] = None
    sector_code: str = ""
    signal_type: str = ""                  # inflow, outflow, rotation
    signal_strength: str = SignalStrength.WEAK.value
    rotation_score: float = 0.0

    # Confirmation
    first_detected: datetime = field(default_factory=datetime.utcnow)
    last_confirmed: datetime = field(default_factory=datetime.utcnow)
    confirmation_count: int = 1            # Consecutive periods confirmed
    is_confirmed: bool = False             # 2+ periods = confirmed

    # Context
    from_sector: Optional[str] = None      # For rotation pairs
    to_sector: Optional[str] = None
    volume_zscore: float = 0.0
    btc_correlation: float = 0.0
    oi_signal: str = ""
    breadth: float = 0.0

    # NEW: Multi-exchange context
    funding_spread: float = 0.0            # Cross-exchange funding spread
    cex_dex_flow: float = 0.0              # CEX vs DEX flow direction
    exchange_consensus: float = 0.0        # % of exchanges agreeing on direction

    # Confidence
    confidence_level: float = 0.0

    # Status
    is_active: bool = True
    expired_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'sector_code': self.sector_code,
            'signal_type': self.signal_type,
            'signal_strength': self.signal_strength,
            'rotation_score': self.rotation_score,
            'first_detected': self.first_detected.isoformat() if self.first_detected else None,
            'last_confirmed': self.last_confirmed.isoformat() if self.last_confirmed else None,
            'confirmation_count': self.confirmation_count,
            'is_confirmed': self.is_confirmed,
            'from_sector': self.from_sector,
            'to_sector': self.to_sector,
            'volume_zscore': self.volume_zscore,
            'btc_correlation': self.btc_correlation,
            'oi_signal': self.oi_signal,
            'breadth': self.breadth,
            'funding_spread': self.funding_spread,
            'cex_dex_flow': self.cex_dex_flow,
            'exchange_consensus': self.exchange_consensus,
            'confidence_level': self.confidence_level,
            'is_active': self.is_active,
            'expired_at': self.expired_at.isoformat() if self.expired_at else None,
        }


@dataclass
class SectorCorrelation:
    """Cross-sector correlation for cluster detection."""
    snapshot_id: int = 0
    sector_a: str = ""
    sector_b: str = ""
    correlation: float = 0.0
    is_significant: bool = False           # |corr| > threshold
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'snapshot_id': self.snapshot_id,
            'sector_a': self.sector_a,
            'sector_b': self.sector_b,
            'correlation': self.correlation,
            'is_significant': self.is_significant,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
        }


# ============================================================================
# Helper Functions
# ============================================================================

def get_sector_for_symbol(base_symbol: str) -> Optional[str]:
    """Look up which sector a base symbol belongs to."""
    for sector, symbols in SECTOR_CONFIG.items():
        if base_symbol in symbols:
            return sector
    return None


def get_all_base_symbols() -> List[str]:
    """Get flat list of all base symbols across all sectors."""
    symbols = []
    for sector_symbols in SECTOR_CONFIG.values():
        symbols.extend(sector_symbols)
    return symbols


def format_symbol_for_exchange(base_symbol: str, exchange: str) -> str:
    """
    Convert base symbol to exchange-specific format.

    Args:
        base_symbol: Base symbol like 'ETH', 'BTC', 'PEPE'
        exchange: Exchange name like 'binance', 'bybit', 'dydx'

    Returns:
        Exchange-formatted symbol like 'ETHUSDT', 'ETH-USDT-SWAP', 'ETH-USD'
    """
    config = EXCHANGE_CONFIG.get(exchange, {})
    if not config:
        return base_symbol

    # Check for exchange-specific symbol mapping
    exchange_map = EXCHANGE_SYMBOL_MAP.get(exchange, {})
    mapped_symbol = exchange_map.get(base_symbol, base_symbol)

    # Add exchange suffix
    suffix = config.get('symbol_suffix', '')
    return f"{mapped_symbol}{suffix}"


def get_enabled_exchanges() -> List[str]:
    """Get list of enabled exchange names."""
    return [name for name, cfg in EXCHANGE_CONFIG.items() if cfg.get('enabled', True)]


def get_cex_exchanges() -> List[str]:
    """Get list of CEX exchange names."""
    return [
        name for name, cfg in EXCHANGE_CONFIG.items()
        if cfg.get('enabled', True) and cfg.get('type') == ExchangeCategory.CEX
    ]


def get_dex_exchanges() -> List[str]:
    """Get list of DEX exchange names."""
    return [
        name for name, cfg in EXCHANGE_CONFIG.items()
        if cfg.get('enabled', True) and cfg.get('type') == ExchangeCategory.DEX
    ]


def get_exchange_weight(exchange: str) -> float:
    """Get volume weight for an exchange."""
    return EXCHANGE_CONFIG.get(exchange, {}).get('weight', 0.0)


def get_sector_metadata(sector_code: str) -> Dict[str, str]:
    """Get display name and emoji for a sector."""
    return SECTOR_METADATA.get(sector_code, {'name': sector_code, 'emoji': '📊'})
