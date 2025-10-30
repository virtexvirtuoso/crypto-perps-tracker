"""Exchange API clients"""

from .base import BaseExchangeClient
from .factory import ClientFactory

# CEX Clients
from .binance import BinanceClient
from .bybit import BybitClient
from .gateio import GateioClient
from .bitget import BitgetClient
from .okx import OKXClient
from .coinbase_intx import CoinbaseINTXClient
from .kraken import KrakenClient
from .kucoin import KuCoinClient
from .coinbase import CoinbaseClient

# DEX Clients
from .hyperliquid import HyperLiquidClient
from .dydx import DYdXClient
from .asterdex import AsterDEXClient

__all__ = [
    # Base and Factory
    'BaseExchangeClient',
    'ClientFactory',
    # CEX Clients
    'BinanceClient',
    'BybitClient',
    'GateioClient',
    'BitgetClient',
    'OKXClient',
    'CoinbaseINTXClient',
    'KrakenClient',
    'KuCoinClient',
    'CoinbaseClient',
    # DEX Clients
    'HyperLiquidClient',
    'DYdXClient',
    'AsterDEXClient',
]
