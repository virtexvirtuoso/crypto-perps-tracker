"""Exchange aggregation service

This service provides high-level operations for fetching and aggregating
data from multiple exchanges with caching support.
"""

from typing import List, Optional, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
from src.clients.factory import ClientFactory
from src.utils.cache import TTLCache
from src.models.market import MarketData, ExchangeType, SymbolData


class ExchangeService:
    """Service for aggregating exchange data with caching

    This service provides methods to fetch data from multiple exchanges
    in parallel, with automatic caching to reduce API calls.

    Usage:
        service = ExchangeService(cache, client_factory)

        # Fetch from all exchanges (cached)
        all_data = service.fetch_all_markets()

        # Fetch from specific exchange
        gateio_data = service.fetch_exchange('gateio')

        # Calculate total volume across all exchanges
        total = service.get_total_volume()
    """

    def __init__(
        self,
        cache: TTLCache,
        client_factory: ClientFactory,
        exchanges: Optional[List[str]] = None,
        blacklist: Optional[List[str]] = None
    ):
        """Initialize exchange service

        Args:
            cache: TTL cache instance for caching API responses
            client_factory: Factory for creating exchange clients
            exchanges: Optional list of exchanges to use. If None, uses all available.
            blacklist: Optional list of symbol patterns to exclude from results
        """
        self.cache = cache
        self.client_factory = client_factory
        self.blacklist = set(blacklist or [])

        # Use specified exchanges or all available
        if exchanges is None:
            exchanges = client_factory.available_exchanges

        # Create clients for specified exchanges
        self.clients = {
            exchange: client_factory.create(exchange)
            for exchange in exchanges
        }

    def _filter_blacklisted_symbols(self, market_data: MarketData) -> MarketData:
        """Filter blacklisted symbols from market data

        Args:
            market_data: MarketData object with potentially blacklisted symbols

        Returns:
            New MarketData object with blacklisted symbols removed from top_pairs
        """
        if not self.blacklist or not market_data.top_pairs:
            return market_data

        # Filter out blacklisted symbols
        filtered_pairs = [
            pair for pair in market_data.top_pairs
            if pair.symbol not in self.blacklist
        ]

        # Create new MarketData with filtered pairs
        data_dict = market_data.model_dump()
        data_dict['top_pairs'] = filtered_pairs
        return MarketData(**data_dict)

    def fetch_all_markets(self, use_cache: bool = True) -> List[MarketData]:
        """Fetch market data from all exchanges

        Fetches data from all configured exchanges in parallel, with
        optional caching to reduce API calls. Automatically filters
        out blacklisted symbols.

        Args:
            use_cache: Whether to use cached data if available

        Returns:
            List of MarketData objects, one per exchange

        Example:
            markets = service.fetch_all_markets()
            for market in markets:
                print(f"{market.exchange}: ${market.volume_24h:,.2f}")
        """
        cache_key = "all_markets"

        # Check cache first
        if use_cache:
            cached = self.cache.get(cache_key)
            if cached:
                return cached

        # Cache miss - fetch from all exchanges in parallel
        results = []

        # Use ThreadPoolExecutor for parallel fetching
        with ThreadPoolExecutor(max_workers=len(self.clients)) as executor:
            # Submit all fetch tasks
            future_to_exchange = {
                executor.submit(client.fetch_volume): exchange
                for exchange, client in self.clients.items()
            }

            # Collect results as they complete
            for future in as_completed(future_to_exchange):
                exchange = future_to_exchange[future]
                try:
                    data = future.result()
                    # Filter blacklisted symbols
                    filtered_data = self._filter_blacklisted_symbols(data)
                    results.append(filtered_data)
                except Exception as e:
                    # Log error but continue with other exchanges
                    print(f"Warning: Failed to fetch {exchange}: {e}")
                    continue

        # Cache results
        if use_cache and results:
            self.cache.set(cache_key, results)

        return results

    def fetch_exchange(
        self,
        exchange: str,
        use_cache: bool = True
    ) -> Optional[MarketData]:
        """Fetch data from a specific exchange

        Args:
            exchange: Exchange name (e.g., 'gateio', 'bitget')
            use_cache: Whether to use cached data if available

        Returns:
            MarketData object or None if exchange not found

        Example:
            gateio_data = service.fetch_exchange('gateio')
            if gateio_data:
                print(f"Volume: ${gateio_data.volume_24h:,.2f}")
        """
        cache_key = f"exchange_{exchange}"

        # Check cache
        if use_cache:
            cached = self.cache.get(cache_key)
            if cached:
                return cached

        # Fetch from exchange
        client = self.clients.get(exchange)
        if not client:
            return None

        try:
            data = client.fetch_volume()

            # Cache result
            if use_cache:
                self.cache.set(cache_key, data)

            return data
        except Exception as e:
            print(f"Error fetching {exchange}: {e}")
            return None

    def get_total_volume(self, use_cache: bool = True) -> float:
        """Calculate total 24h volume across all exchanges

        Args:
            use_cache: Whether to use cached data

        Returns:
            Total volume in USD
        """
        markets = self.fetch_all_markets(use_cache=use_cache)
        return sum(m.volume_24h for m in markets)

    def get_total_open_interest(self, use_cache: bool = True) -> float:
        """Calculate total open interest across all exchanges

        Args:
            use_cache: Whether to use cached data

        Returns:
            Total open interest in USD
        """
        markets = self.fetch_all_markets(use_cache=use_cache)
        return sum(m.open_interest or 0 for m in markets)

    def get_exchange_by_type(
        self,
        exchange_type: ExchangeType,
        use_cache: bool = True
    ) -> Optional[MarketData]:
        """Get data for a specific exchange by type

        Args:
            exchange_type: ExchangeType enum value
            use_cache: Whether to use cached data

        Returns:
            MarketData object or None
        """
        markets = self.fetch_all_markets(use_cache=use_cache)
        return next(
            (m for m in markets if m.exchange == exchange_type),
            None
        )

    def get_market_summary(self, use_cache: bool = True) -> Dict:
        """Get summary statistics across all markets

        Args:
            use_cache: Whether to use cached data

        Returns:
            Dictionary with summary statistics
        """
        markets = self.fetch_all_markets(use_cache=use_cache)

        return {
            'num_exchanges': len(markets),
            'total_volume_24h': sum(m.volume_24h for m in markets),
            'total_open_interest': sum(m.open_interest or 0 for m in markets),
            'total_markets': sum(m.market_count or 0 for m in markets),
            'exchanges': [
                m.exchange.value if hasattr(m.exchange, 'value') else str(m.exchange)
                for m in markets
            ],
        }

    def fetch_symbol_across_exchanges(self, symbol: str, use_cache: bool = True) -> List[SymbolData]:
        """Fetch specific symbol data from all exchanges

        Args:
            symbol: Trading pair symbol (format varies by exchange)
            use_cache: Whether to use cached data (default: True)

        Returns:
            List of SymbolData objects from exchanges that have the symbol

        Note:
            Symbol format varies by exchange:
            - Binance: 'BTCUSDT'
            - Bybit: 'BTCUSDT'
            - OKX: 'BTC-USDT-SWAP'
            - Bitget: 'BTCUSDT_UMCBL'
            - Gate.io: 'BTC_USDT'
        """
        # Skip blacklisted symbols
        if symbol in self.blacklist:
            return []

        cache_key = f"symbol_{symbol}"

        # Check cache first
        if use_cache:
            cached = self.cache.get(cache_key)
            if cached is not None:
                return cached

        results = []

        def fetch_from_exchange(exchange_name: str):
            """Fetch symbol from a single exchange"""
            try:
                client = self.clients[exchange_name]

                # Try to fetch the symbol
                symbol_data = client.fetch_symbol(symbol)

                if symbol_data:
                    return symbol_data

                return None

            except Exception as e:
                # Log error but continue with other exchanges
                return None

        # Fetch from all exchanges in parallel
        with ThreadPoolExecutor(max_workers=len(self.clients)) as executor:
            future_to_exchange = {
                executor.submit(fetch_from_exchange, exchange_name): exchange_name
                for exchange_name in self.clients
            }

            for future in as_completed(future_to_exchange):
                try:
                    result = future.result()
                    if result:
                        results.append(result)
                except Exception:
                    # Continue with other exchanges
                    pass

        # Cache results
        if results:
            self.cache.set(cache_key, results)

        return results

    def clear_cache(self):
        """Clear all cached data"""
        self.cache.clear()

    def __repr__(self) -> str:
        """String representation"""
        return (
            f"ExchangeService(exchanges={len(self.clients)}, "
            f"cache={self.cache})"
        )
