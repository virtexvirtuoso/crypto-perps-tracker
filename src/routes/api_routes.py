"""
REST API Routes for Crypto Perps Tracker

Provides JSON endpoints for:
- Market overview and aggregated data
- Per-exchange data
- Symbol lookups across exchanges
- DEX vs CEX analysis
"""

from flask import jsonify, request
from datetime import datetime, timezone


def register_api_routes(server, container):
    """Register all API routes with the Flask server"""
    
    # ========================================
    # Health & Status
    # ========================================
    
    @server.route('/api/health')
    def api_health():
        """Health check endpoint"""
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'exchanges': len(container.client_factory.available_exchanges)
        })
    
    @server.route('/api/status')
    def api_status():
        """Detailed system status"""
        try:
            markets = container.exchange_service.fetch_all_markets()
            return jsonify({
                'status': 'operational',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'exchanges': {
                    'available': container.client_factory.available_exchanges,
                    'active': len(markets),
                    'total': len(container.client_factory.available_exchanges)
                },
                'cache': {
                    'ttl': container.config.cache.ttl
                }
            })
        except Exception as e:
            return jsonify({'status': 'error', 'error': str(e)}), 500
    
    # ========================================
    # Market Overview
    # ========================================
    
    @server.route('/api/markets')
    def api_markets():
        """Get all market data from all exchanges"""
        try:
            markets = container.exchange_service.fetch_all_markets()
            return jsonify({
                'status': 'success',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'count': len(markets),
                'markets': [
                    {
                        'exchange': m.exchange,
                        'volume_24h': m.volume_24h,
                        'open_interest': m.open_interest,
                        'funding_rate': m.funding_rate,
                        'market_count': m.market_count,
                        'top_pairs': [
                            {'symbol': p.symbol, 'volume': p.volume}
                            for p in (m.top_pairs or [])[:5]
                        ]
                    }
                    for m in markets
                ]
            })
        except Exception as e:
            return jsonify({'status': 'error', 'error': str(e)}), 500
    
    @server.route('/api/markets/summary')
    def api_markets_summary():
        """Get aggregated market summary"""
        try:
            summary = container.exchange_service.get_market_summary()
            return jsonify({
                'status': 'success',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                **summary
            })
        except Exception as e:
            return jsonify({'status': 'error', 'error': str(e)}), 500
    
    @server.route('/api/markets/volume')
    def api_total_volume():
        """Get total 24h volume across all exchanges"""
        try:
            volume = container.exchange_service.get_total_volume()
            return jsonify({
                'status': 'success',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'total_volume_24h': volume,
                'formatted': f"${volume/1e9:.2f}B"
            })
        except Exception as e:
            return jsonify({'status': 'error', 'error': str(e)}), 500
    
    @server.route('/api/markets/open-interest')
    def api_total_oi():
        """Get total open interest across all exchanges"""
        try:
            oi = container.exchange_service.get_total_open_interest()
            return jsonify({
                'status': 'success',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'total_open_interest': oi,
                'formatted': f"${oi/1e9:.2f}B"
            })
        except Exception as e:
            return jsonify({'status': 'error', 'error': str(e)}), 500
    
    # ========================================
    # Per-Exchange Data
    # ========================================
    
    @server.route('/api/exchanges')
    def api_exchanges():
        """List all available exchanges"""
        return jsonify({
            'status': 'success',
            'exchanges': container.client_factory.available_exchanges,
            'count': len(container.client_factory.available_exchanges)
        })
    
    @server.route('/api/exchanges/<exchange>')
    def api_exchange_data(exchange):
        """Get data for a specific exchange"""
        try:
            if not container.client_factory.is_supported(exchange):
                return jsonify({
                    'status': 'error',
                    'error': f'Exchange not supported: {exchange}',
                    'available': container.client_factory.available_exchanges
                }), 404
            
            data = container.exchange_service.fetch_exchange(exchange)
            if not data:
                return jsonify({
                    'status': 'error',
                    'error': f'Failed to fetch data from {exchange}'
                }), 503
            
            return jsonify({
                'status': 'success',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'exchange': data.exchange,
                'volume_24h': data.volume_24h,
                'open_interest': data.open_interest,
                'funding_rate': data.funding_rate,
                'market_count': data.market_count,
                'top_pairs': [
                    {'symbol': p.symbol, 'base': p.base, 'quote': p.quote, 'volume': p.volume}
                    for p in (data.top_pairs or [])
                ]
            })
        except Exception as e:
            return jsonify({'status': 'error', 'error': str(e)}), 500
    
    # ========================================
    # Symbol Lookup
    # ========================================
    
    @server.route('/api/symbol/<symbol>')
    def api_symbol(symbol):
        """Get data for a symbol across all exchanges"""
        try:
            results = container.exchange_service.fetch_symbol_across_exchanges(symbol.upper())
            
            if not results:
                return jsonify({
                    'status': 'not_found',
                    'symbol': symbol.upper(),
                    'message': 'Symbol not found on any exchange'
                }), 404
            
            return jsonify({
                'status': 'success',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'symbol': symbol.upper(),
                'exchanges': len(results),
                'data': [
                    {
                        'exchange': r.exchange,
                        'symbol': r.symbol,
                        'price': r.price,
                        'volume_24h': r.volume_24h,
                        'open_interest': r.open_interest,
                        'funding_rate': r.funding_rate,
                        'price_change_24h_pct': r.price_change_24h_pct
                    }
                    for r in results
                ]
            })
        except Exception as e:
            return jsonify({'status': 'error', 'error': str(e)}), 500
    
    # ========================================
    # DEX vs CEX Analysis
    # ========================================
    
    @server.route('/api/dex-cex')
    def api_dex_cex():
        """Get DEX vs CEX volume/OI breakdown"""
        try:
            markets = container.exchange_service.fetch_all_markets()
            
            dex_names = {'hyperliquid', 'dydx', 'asterdex', 'jupiter', 'drift'}
            
            def is_dex(exchange_name):
                return any(d in exchange_name.lower() for d in dex_names)
            
            cex_markets = [m for m in markets if not is_dex(m.exchange)]
            dex_markets = [m for m in markets if is_dex(m.exchange)]
            
            cex_volume = sum(m.volume_24h for m in cex_markets)
            dex_volume = sum(m.volume_24h for m in dex_markets)
            cex_oi = sum(m.open_interest or 0 for m in cex_markets)
            dex_oi = sum(m.open_interest or 0 for m in dex_markets)
            
            total_volume = cex_volume + dex_volume
            total_oi = cex_oi + dex_oi
            
            return jsonify({
                'status': 'success',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'cex': {
                    'exchanges': [m.exchange for m in cex_markets],
                    'count': len(cex_markets),
                    'volume_24h': cex_volume,
                    'open_interest': cex_oi,
                    'volume_pct': (cex_volume / total_volume * 100) if total_volume > 0 else 0,
                    'oi_pct': (cex_oi / total_oi * 100) if total_oi > 0 else 0
                },
                'dex': {
                    'exchanges': [m.exchange for m in dex_markets],
                    'count': len(dex_markets),
                    'volume_24h': dex_volume,
                    'open_interest': dex_oi,
                    'volume_pct': (dex_volume / total_volume * 100) if total_volume > 0 else 0,
                    'oi_pct': (dex_oi / total_oi * 100) if total_oi > 0 else 0
                },
                'totals': {
                    'volume_24h': total_volume,
                    'open_interest': total_oi
                }
            })
        except Exception as e:
            return jsonify({'status': 'error', 'error': str(e)}), 500
    
    # ========================================
    # Funding Rates
    # ========================================
    
    @server.route('/api/funding')
    def api_funding():
        """Get funding rates from all exchanges"""
        try:
            markets = container.exchange_service.fetch_all_markets()
            
            funding_data = []
            for m in markets:
                if m.funding_rate is not None:
                    funding_data.append({
                        'exchange': m.exchange,
                        'funding_rate': m.funding_rate,
                        'funding_rate_pct': m.funding_rate * 100,
                        'annualized_pct': m.funding_rate * 100 * 3 * 365,  # 8h funding
                        'volume_24h': m.volume_24h
                    })
            
            # Sort by funding rate
            funding_data.sort(key=lambda x: x['funding_rate'], reverse=True)
            
            # Calculate volume-weighted average
            weighted_sum = sum(f['funding_rate'] * f['volume_24h'] for f in funding_data)
            total_volume = sum(f['volume_24h'] for f in funding_data)
            avg_funding = (weighted_sum / total_volume) if total_volume > 0 else 0
            
            return jsonify({
                'status': 'success',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'average_funding_rate': avg_funding,
                'average_funding_pct': avg_funding * 100,
                'exchanges': funding_data
            })
        except Exception as e:
            return jsonify({'status': 'error', 'error': str(e)}), 500
    
    print("✅ API routes registered successfully")

    # ========================================
    # API Documentation
    # ========================================
    
    @server.route('/api/docs')
    def api_docs():
        """Serve API documentation page"""
        from flask import send_from_directory
        import os
        static_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'dashboard', 'static')
        return send_from_directory(static_dir, 'api_docs.html')
