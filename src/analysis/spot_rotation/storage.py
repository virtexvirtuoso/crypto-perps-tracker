"""
Spot Rotation Data Models - CoinGecko Version

Dataclasses for spot market sector rotation analysis using CoinGecko data.
Distinct from perp rotation: no OI/funding, includes market cap metrics.

Key Differences from Perp Rotation:
- Uses market cap instead of OI
- Multi-timeframe price changes (1h, 24h, 7d, 30d)
- No funding rate metrics
- Extended sector coverage (stablecoins, NFT infra, etc.)
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


class SampleSizeFlag(Enum):
    """Data quality flag for sector sample size."""
    NORMAL = "normal"           # >= 5 tokens
    SMALL = "small"             # 3-4 tokens
    INSUFFICIENT = "insufficient"  # < 3 tokens


class MarketCapTier(Enum):
    """Market cap tier classification for tokens."""
    MEGA = "mega"         # > $50B
    LARGE = "large"       # $10B - $50B
    MID = "mid"           # $1B - $10B
    SMALL = "small"       # $100M - $1B
    MICRO = "micro"       # < $100M


# ============================================================================
# CoinGecko Configuration
# ============================================================================

# CoinGecko API rate limits (free tier)
COINGECKO_RATE_LIMIT = 30  # requests per minute
COINGECKO_BATCH_SIZE = 250  # max tokens per /coins/markets call
COLLECTION_INTERVAL_SECONDS = 900  # 15 minutes

# ============================================================================
# Spot Sector Configuration
# ============================================================================

# Token IDs mapped to CoinGecko IDs
# Extended sectors including tokens not on perp exchanges
SPOT_SECTOR_CONFIG = {
    # Core blockchain sectors
    'L1': [
        'ethereum', 'solana', 'avalanche-2', 'cardano', 'polkadot',
        'near', 'the-open-network', 'sui', 'aptos', 'cosmos',
        'internet-computer', 'hedera-hashgraph', 'algorand', 'tezos',
    ],
    'L2': [
        'matic-network', 'optimism', 'arbitrum', 'mantle', 'starknet',
        'immutable-x', 'base-protocol', 'zksync', 'scroll', 'linea',
    ],

    # DeFi sectors
    'DEFI': [
        'aave', 'compound-governance-token', 'havven', 'curve-dao-token',
        '1inch', 'maker', 'lido-dao', 'rocket-pool', 'frax-share',
        'pendle', 'ethena', 'morpho', 'eigenlayer',
    ],
    'DEX': [
        'uniswap', 'dydx', 'gmx', 'sushiswap', 'pancakeswap-token',
        'jupiter-exchange-solana', 'hyperliquid', 'raydium', 'orca',
        'thorchain', 'osmosis', 'aerodrome-finance',
    ],
    'LENDING': [
        'aave', 'compound-governance-token', 'benqi', 'radiant-capital',
        'maple', 'clearpool', 'spark',
    ],

    # Narrative sectors
    'MEME': [
        'dogecoin', 'shiba-inu', 'pepe', 'dogwifcoin', 'bonk',
        'floki', 'brett', 'popcat', 'mog-coin', 'turbo',
    ],
    'AI': [
        'render-token', 'bittensor', 'fetch-ai', 'the-graph',
        'worldcoin-wld', 'akash-network', 'ocean-protocol', 'singularitynet',
        'artificial-superintelligence-alliance', 'nosana',
    ],
    'GAMING': [
        'axie-infinity', 'the-sandbox', 'decentraland', 'gala',
        'illuvium', 'vulcan-forged', 'gods-unchained', 'beam-2',
        'immutable-x', 'ronin',
    ],

    # Infrastructure sectors
    'RWA': [
        'ondo-finance', 'mantra', 'quant-network', 'stellar', 'xdc-network',
        'chainlink', 'centrifuge', 'goldfinch', 'polymesh',
    ],
    'DEPIN': [
        'filecoin', 'arweave', 'helium', 'iotex', 'theta-token',
        'render-token', 'akash-network', 'hivemapper', 'io-net',
    ],
    'ORACLE': [
        'chainlink', 'band-protocol', 'api3', 'dia-data', 'uma',
        'pyth-network', 'redstone', 'tellor',
    ],

    # Ecosystem sectors
    'BTC_ECOSYSTEM': [
        'stacks', 'ordinals', 'thorchain', 'badger-dao', 'alex-lab',
        'lightning-bitcoin', 'bob', 'merlin-chain',
    ],
    'PRIVACY': [
        'monero', 'zcash', 'dash', 'secret', 'oasis-network',
        'iron-fish', 'aleph-zero',
    ],
    'RESTAKING': [
        'lido-dao', 'rocket-pool', 'frax-ether', 'eigenlayer', 'ether-fi',
        'puffer-finance', 'kelp-dao', 'renzo',
    ],
    'MODULAR': [
        'celestia', 'dymension', 'saga-2', 'eclipse', 'fuel-network',
        'manta-network', 'alt-layer',
    ],

    # Exchange & stablecoin sectors
    'EXCHANGE_TOKEN': [
        'binancecoin', 'crypto-com-chain', 'okb', 'kucoin-shares',
        'ftx-token', 'huobi-token', 'bitget-token', 'mx-token',
    ],
    'STABLECOIN': [
        'tether', 'usd-coin', 'dai', 'frax', 'true-usd', 'ethena-usde',
        'first-digital-usd', 'paypal-usd',
    ],
}

# Sector display metadata
SPOT_SECTOR_METADATA = {
    'L1': {'name': 'Layer 1', 'emoji': '🏗️', 'tier': 'core'},
    'L2': {'name': 'Layer 2', 'emoji': '⚡', 'tier': 'core'},
    'DEFI': {'name': 'DeFi', 'emoji': '🏦', 'tier': 'defi'},
    'DEX': {'name': 'DEX', 'emoji': '🔄', 'tier': 'defi'},
    'LENDING': {'name': 'Lending', 'emoji': '💰', 'tier': 'defi'},
    'MEME': {'name': 'Meme', 'emoji': '🐸', 'tier': 'narrative'},
    'AI': {'name': 'AI & ML', 'emoji': '🤖', 'tier': 'narrative'},
    'GAMING': {'name': 'Gaming', 'emoji': '🎮', 'tier': 'narrative'},
    'RWA': {'name': 'RWA', 'emoji': '🏠', 'tier': 'infra'},
    'DEPIN': {'name': 'DePIN', 'emoji': '📡', 'tier': 'infra'},
    'ORACLE': {'name': 'Oracle', 'emoji': '🔮', 'tier': 'infra'},
    'BTC_ECOSYSTEM': {'name': 'BTC Eco', 'emoji': '₿', 'tier': 'ecosystem'},
    'PRIVACY': {'name': 'Privacy', 'emoji': '🔐', 'tier': 'ecosystem'},
    'RESTAKING': {'name': 'Restaking', 'emoji': '🔒', 'tier': 'ecosystem'},
    'MODULAR': {'name': 'Modular', 'emoji': '🧱', 'tier': 'ecosystem'},
    'EXCHANGE_TOKEN': {'name': 'Exchange', 'emoji': '🏛️', 'tier': 'other'},
    'STABLECOIN': {'name': 'Stablecoin', 'emoji': '💵', 'tier': 'other'},
}

# Sectors with fewer than 5 tokens (need confidence adjustment)
SMALL_SAMPLE_SECTORS = ['LENDING', 'ORACLE', 'MODULAR']


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class TokenSnapshot:
    """Point-in-time metrics for a single token from CoinGecko."""
    coingecko_id: str = ""
    symbol: str = ""
    name: str = ""

    # Price metrics
    current_price: float = 0.0
    price_change_1h: float = 0.0
    price_change_24h: float = 0.0
    price_change_7d: float = 0.0
    price_change_30d: float = 0.0

    # Volume metrics
    volume_24h: float = 0.0
    volume_change_24h: float = 0.0

    # Market cap metrics
    market_cap: float = 0.0
    market_cap_rank: int = 0
    market_cap_change_24h: float = 0.0

    # Supply metrics
    circulating_supply: float = 0.0
    total_supply: float = 0.0
    max_supply: Optional[float] = None

    # Timestamps
    timestamp: datetime = field(default_factory=datetime.utcnow)
    last_updated: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'coingecko_id': self.coingecko_id,
            'symbol': self.symbol,
            'name': self.name,
            'current_price': self.current_price,
            'price_change_1h': self.price_change_1h,
            'price_change_24h': self.price_change_24h,
            'price_change_7d': self.price_change_7d,
            'price_change_30d': self.price_change_30d,
            'volume_24h': self.volume_24h,
            'volume_change_24h': self.volume_change_24h,
            'market_cap': self.market_cap,
            'market_cap_rank': self.market_cap_rank,
            'market_cap_change_24h': self.market_cap_change_24h,
            'circulating_supply': self.circulating_supply,
            'total_supply': self.total_supply,
            'max_supply': self.max_supply,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'last_updated': self.last_updated.isoformat() if self.last_updated else None,
        }


@dataclass
class SpotSectorSnapshot:
    """
    A point-in-time snapshot of spot sector metrics aggregated from CoinGecko.

    Key differences from perp SectorSnapshot:
    - Uses market cap instead of OI
    - Multi-timeframe price changes (1h, 24h, 7d, 30d)
    - No funding rate metrics
    - Token-level breakdown available
    """
    # Identifiers
    id: Optional[int] = None
    sector_code: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)

    # Market cap metrics (replaces OI from perps)
    total_market_cap: float = 0.0
    market_cap_share_pct: float = 0.0       # % of total crypto market cap
    market_cap_change_24h: float = 0.0      # % change
    market_cap_zscore: float = 0.0          # Statistical significance

    # Volume metrics
    total_volume_24h: float = 0.0
    volume_share_pct: float = 0.0
    volume_share_zscore: float = 0.0
    volume_mcap_ratio: float = 0.0          # Volume/MarketCap ratio (liquidity)

    # Multi-timeframe price metrics
    avg_price_change_1h: float = 0.0
    avg_price_change_24h: float = 0.0
    avg_price_change_7d: float = 0.0
    avg_price_change_30d: float = 0.0

    # Momentum metrics
    momentum_24h: float = 0.0               # Weighted price momentum
    momentum_7d: float = 0.0
    momentum_consistency: float = 0.0       # % of tokens moving same direction

    # Breadth metrics
    tokens_up_1h: int = 0
    tokens_up_24h: int = 0
    tokens_up_7d: int = 0
    tokens_down_24h: int = 0
    breadth_ratio_24h: float = 0.0          # up/total for 24h
    breadth_ratio_7d: float = 0.0           # up/total for 7d
    weighted_breadth: float = 0.0           # Market cap weighted breadth

    # Correlation metrics
    btc_correlation: float = 0.0
    btc_correlation_zscore: float = 0.0
    sector_beta: float = 0.0

    # Relative strength
    sector_rs_24h: float = 0.0              # RS vs BTC 24h
    sector_rs_7d: float = 0.0               # RS vs BTC 7d
    sector_rs_zscore: float = 0.0

    # Composite metrics
    rotation_score: float = 0.0             # 0-100 composite score
    signal_strength: str = SignalStrength.WEAK.value

    # Data quality
    token_count: int = 0
    data_quality_score: float = 0.0
    confidence_level: float = 0.0
    sample_size_flag: str = SampleSizeFlag.NORMAL.value

    # Market cap tier distribution
    mega_cap_pct: float = 0.0               # % of sector mcap in mega caps
    large_cap_pct: float = 0.0
    mid_cap_pct: float = 0.0
    small_cap_pct: float = 0.0
    micro_cap_pct: float = 0.0

    # Token breakdown (JSON serialized)
    token_snapshots: List[TokenSnapshot] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'sector_code': self.sector_code,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            # Market cap
            'total_market_cap': self.total_market_cap,
            'market_cap_share_pct': self.market_cap_share_pct,
            'market_cap_change_24h': self.market_cap_change_24h,
            'market_cap_zscore': self.market_cap_zscore,
            # Volume
            'total_volume_24h': self.total_volume_24h,
            'volume_share_pct': self.volume_share_pct,
            'volume_share_zscore': self.volume_share_zscore,
            'volume_mcap_ratio': self.volume_mcap_ratio,
            # Price changes
            'avg_price_change_1h': self.avg_price_change_1h,
            'avg_price_change_24h': self.avg_price_change_24h,
            'avg_price_change_7d': self.avg_price_change_7d,
            'avg_price_change_30d': self.avg_price_change_30d,
            # Momentum
            'momentum_24h': self.momentum_24h,
            'momentum_7d': self.momentum_7d,
            'momentum_consistency': self.momentum_consistency,
            # Breadth
            'tokens_up_1h': self.tokens_up_1h,
            'tokens_up_24h': self.tokens_up_24h,
            'tokens_up_7d': self.tokens_up_7d,
            'tokens_down_24h': self.tokens_down_24h,
            'breadth_ratio_24h': self.breadth_ratio_24h,
            'breadth_ratio_7d': self.breadth_ratio_7d,
            'weighted_breadth': self.weighted_breadth,
            # Correlation
            'btc_correlation': self.btc_correlation,
            'btc_correlation_zscore': self.btc_correlation_zscore,
            'sector_beta': self.sector_beta,
            # RS
            'sector_rs_24h': self.sector_rs_24h,
            'sector_rs_7d': self.sector_rs_7d,
            'sector_rs_zscore': self.sector_rs_zscore,
            # Composite
            'rotation_score': self.rotation_score,
            'signal_strength': self.signal_strength,
            # Quality
            'token_count': self.token_count,
            'data_quality_score': self.data_quality_score,
            'confidence_level': self.confidence_level,
            'sample_size_flag': self.sample_size_flag,
            # Tier distribution
            'mega_cap_pct': self.mega_cap_pct,
            'large_cap_pct': self.large_cap_pct,
            'mid_cap_pct': self.mid_cap_pct,
            'small_cap_pct': self.small_cap_pct,
            'micro_cap_pct': self.micro_cap_pct,
            # Tokens
            'token_snapshots': [t.to_dict() for t in self.token_snapshots],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SpotSectorSnapshot':
        """Create instance from dictionary."""
        if isinstance(data.get('timestamp'), str):
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])

        # Handle token snapshots
        if 'token_snapshots' in data and isinstance(data['token_snapshots'], list):
            data['token_snapshots'] = [
                TokenSnapshot(**ts) if isinstance(ts, dict) else ts
                for ts in data['token_snapshots']
            ]

        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class SpotSectorSignal:
    """
    A detected spot market rotation signal with confirmation status.

    Similar to perp SectorSignal but with spot-specific context.
    """
    id: Optional[int] = None
    sector_code: str = ""
    signal_type: str = ""                   # inflow, outflow, rotation
    signal_strength: str = SignalStrength.WEAK.value
    rotation_score: float = 0.0

    # Confirmation
    first_detected: datetime = field(default_factory=datetime.utcnow)
    last_confirmed: datetime = field(default_factory=datetime.utcnow)
    confirmation_count: int = 1
    is_confirmed: bool = False              # 2+ periods = confirmed

    # Context
    from_sector: Optional[str] = None       # For rotation pairs
    to_sector: Optional[str] = None
    volume_zscore: float = 0.0
    market_cap_zscore: float = 0.0          # Instead of OI
    btc_correlation: float = 0.0
    breadth_24h: float = 0.0
    breadth_7d: float = 0.0

    # Confidence
    confidence_level: float = 0.0

    # Status
    is_active: bool = True
    expired_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
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
            'market_cap_zscore': self.market_cap_zscore,
            'btc_correlation': self.btc_correlation,
            'breadth_24h': self.breadth_24h,
            'breadth_7d': self.breadth_7d,
            'confidence_level': self.confidence_level,
            'is_active': self.is_active,
            'expired_at': self.expired_at.isoformat() if self.expired_at else None,
        }


@dataclass
class SpotPerpDivergence:
    """
    Tracks divergence between spot and perp sector signals.

    Useful for detecting:
    - Smart money accumulation (spot leading perps)
    - Retail speculation (perps leading spot)
    - Funding arbitrage opportunities
    """
    sector_code: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)

    # Scores
    spot_rotation_score: float = 0.0
    perp_rotation_score: float = 0.0
    divergence_score: float = 0.0           # spot - perp score

    # Direction
    spot_signal_type: str = ""              # inflow, outflow, neutral
    perp_signal_type: str = ""

    # Is divergent (opposite signals or >20 point difference)
    is_divergent: bool = False
    divergence_type: str = ""               # spot_leading, perp_leading, aligned

    # Context
    spot_volume_zscore: float = 0.0
    perp_volume_zscore: float = 0.0
    perp_funding_rate: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'sector_code': self.sector_code,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'spot_rotation_score': self.spot_rotation_score,
            'perp_rotation_score': self.perp_rotation_score,
            'divergence_score': self.divergence_score,
            'spot_signal_type': self.spot_signal_type,
            'perp_signal_type': self.perp_signal_type,
            'is_divergent': self.is_divergent,
            'divergence_type': self.divergence_type,
            'spot_volume_zscore': self.spot_volume_zscore,
            'perp_volume_zscore': self.perp_volume_zscore,
            'perp_funding_rate': self.perp_funding_rate,
        }


# ============================================================================
# Helper Functions
# ============================================================================

def get_sector_for_token(coingecko_id: str) -> Optional[str]:
    """Look up which sector a CoinGecko token ID belongs to."""
    for sector, tokens in SPOT_SECTOR_CONFIG.items():
        if coingecko_id in tokens:
            return sector
    return None


def get_all_token_ids() -> List[str]:
    """Get flat list of all CoinGecko token IDs across all sectors."""
    tokens = []
    for sector_tokens in SPOT_SECTOR_CONFIG.values():
        tokens.extend(sector_tokens)
    return list(set(tokens))  # Remove duplicates


def get_sector_metadata(sector_code: str) -> Dict[str, str]:
    """Get display name, emoji, and tier for a sector."""
    return SPOT_SECTOR_METADATA.get(
        sector_code,
        {'name': sector_code, 'emoji': '📊', 'tier': 'other'}
    )


def classify_market_cap_tier(market_cap: float) -> MarketCapTier:
    """Classify a market cap value into a tier."""
    if market_cap >= 50_000_000_000:  # $50B+
        return MarketCapTier.MEGA
    elif market_cap >= 10_000_000_000:  # $10B+
        return MarketCapTier.LARGE
    elif market_cap >= 1_000_000_000:  # $1B+
        return MarketCapTier.MID
    elif market_cap >= 100_000_000:  # $100M+
        return MarketCapTier.SMALL
    else:
        return MarketCapTier.MICRO


def get_sectors_by_tier(tier: str) -> List[str]:
    """Get all sector codes belonging to a specific tier."""
    return [
        code for code, meta in SPOT_SECTOR_METADATA.items()
        if meta.get('tier') == tier
    ]
