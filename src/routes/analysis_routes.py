"""
Quantitative Analysis API Routes for Crypto Perps Tracker

Provides advanced analytics endpoints for:
- Tier 1: Direct Alpha (funding-arbitrage, oi-price-divergence, funding-extremity)
- Tier 2: Risk & Sentiment (liquidation-risk-heatmap, market-sentiment-index, oi-concentration)
- Tier 3: Flow Analysis (dex-cex-flow-dynamics, exchange-flow-migration, volume-anomaly-detector)
"""

from flask import jsonify
from datetime import datetime, timezone
from collections import defaultdict
import math


def register_analysis_routes(server, container):
    """Register all quantitative analysis routes with the Flask server"""

    # DEX exchanges for classification
    DEX_EXCHANGES = {'hyperliquid', 'dydx', 'asterdex', 'jupiter', 'drift'}

    def is_dex(exchange_name):
        """Check if exchange is a DEX"""
        return any(d in exchange_name.lower() for d in DEX_EXCHANGES)

    # ========================================
    # TIER 1: DIRECT ALPHA OPPORTUNITIES
    # ========================================

    @server.route('/api/analysis/funding-arbitrage')
    def funding_arbitrage():
        """
        Cross-exchange funding rate spreads for delta-neutral arbitrage.

        Returns opportunities where you can be long on negative-funding exchange
        and short on positive-funding exchange to harvest the spread.
        """
        try:
            markets = container.exchange_service.fetch_all_markets()

            # Group funding rates by base symbol
            symbol_funding = defaultdict(list)

            for market in markets:
                if market.funding_rate is not None:
                    # Extract base symbol (BTC from BTCUSDT, etc.)
                    exchange_name = str(market.exchange)

                    # Get top pairs for this exchange
                    if market.top_pairs:
                        for pair in market.top_pairs[:10]:
                            try:
                                # Safely get base symbol
                                base = getattr(pair, 'base', None)
                                if not base:
                                    symbol = getattr(pair, 'symbol', '')
                                    base = str(symbol).split('/')[0].split('-')[0] if symbol else None
                                if not base:
                                    continue
                                base = base.upper()

                                symbol_funding[base].append({
                                    'exchange': exchange_name,
                                    'funding_rate': market.funding_rate,
                                    'volume_24h': getattr(pair, 'volume', 0) or 0
                                })
                            except (AttributeError, TypeError):
                                continue

            # Calculate arbitrage opportunities
            opportunities = []

            for symbol, exchanges in symbol_funding.items():
                if len(exchanges) < 2:
                    continue

                # Find min and max funding
                sorted_by_funding = sorted(exchanges, key=lambda x: x['funding_rate'])
                min_funding = sorted_by_funding[0]
                max_funding = sorted_by_funding[-1]

                spread = max_funding['funding_rate'] - min_funding['funding_rate']

                # Only include if spread is meaningful (> 0.005% per 8h = ~5.5% annualized)
                if spread > 0.00005:
                    annualized = spread * 3 * 365 * 100  # Convert to percentage

                    opportunities.append({
                        'symbol': symbol,
                        'spread': spread,
                        'spread_pct': spread * 100,
                        'annualized_return_pct': round(annualized, 2),
                        'long_exchange': min_funding['exchange'],
                        'long_funding_pct': round(min_funding['funding_rate'] * 100, 4),
                        'short_exchange': max_funding['exchange'],
                        'short_funding_pct': round(max_funding['funding_rate'] * 100, 4),
                        'exchanges_count': len(exchanges)
                    })

            # Sort by annualized return
            opportunities.sort(key=lambda x: x['annualized_return_pct'], reverse=True)

            return jsonify({
                'status': 'success',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'opportunities_count': len(opportunities),
                'opportunities': opportunities[:20],  # Top 20
                'threshold_info': {
                    'min_spread_pct': 0.005,
                    'min_annualized_pct': 5.5
                }
            })

        except Exception as e:
            return jsonify({'status': 'error', 'error': str(e)}), 500

    @server.route('/api/analysis/oi-price-divergence')
    def oi_price_divergence():
        """
        Detect accumulation/distribution patterns when OI and price move
        in opposite directions.

        Signals:
        - OI up + Price down = Accumulation (bullish)
        - OI down + Price up = Distribution (bearish)
        - OI down + Price down = Capitulation (potential bottom)
        """
        try:
            # Fetch current data from all exchanges
            markets = container.exchange_service.fetch_all_markets()

            # Aggregate OI and calculate pseudo price from funding (market direction proxy)
            divergences = []

            for market in markets:
                exchange_name = str(market.exchange)

                # Use funding rate as a proxy for price momentum direction
                # Positive funding = longs paying shorts = price has been rising
                # Negative funding = shorts paying longs = price has been falling
                if market.funding_rate is not None and market.open_interest:
                    # We need historical data for proper divergence
                    # For now, use funding rate sign as price direction proxy
                    # and OI magnitude relative to volume as accumulation signal

                    oi = market.open_interest
                    volume = market.volume_24h
                    funding = market.funding_rate

                    if volume > 0:
                        # OI to Volume ratio - high ratio = positions being held
                        oi_volume_ratio = oi / volume

                        # Classify divergence based on funding (price proxy) vs OI/volume ratio
                        if funding > 0.0001 and oi_volume_ratio > 1:
                            # Price up (positive funding), high OI retention = confirmation
                            div_type = 'confirmation'
                            signal = 'neutral'
                        elif funding < -0.0001 and oi_volume_ratio > 1.5:
                            # Price down (negative funding), high OI retention = accumulation
                            div_type = 'accumulation'
                            signal = 'bullish'
                        elif funding > 0.0001 and oi_volume_ratio < 0.5:
                            # Price up, low OI retention = distribution
                            div_type = 'distribution'
                            signal = 'bearish'
                        elif funding < -0.0001 and oi_volume_ratio < 0.5:
                            # Price down, low OI = capitulation
                            div_type = 'capitulation'
                            signal = 'potential_bottom'
                        else:
                            div_type = 'neutral'
                            signal = 'neutral'

                        # Calculate divergence score
                        divergence_score = abs(funding * 1000) * oi_volume_ratio

                        if div_type != 'neutral':
                            divergences.append({
                                'exchange': exchange_name,
                                'divergence_type': div_type,
                                'signal': signal,
                                'divergence_score': round(divergence_score, 4),
                                'funding_rate_pct': round(funding * 100, 4),
                                'oi_volume_ratio': round(oi_volume_ratio, 2),
                                'open_interest': oi,
                                'volume_24h': volume
                            })

            # Sort by divergence score
            divergences.sort(key=lambda x: x['divergence_score'], reverse=True)

            # Aggregate signals
            signal_counts = defaultdict(int)
            for d in divergences:
                signal_counts[d['signal']] += 1

            dominant_signal = max(signal_counts, key=signal_counts.get) if signal_counts else 'neutral'

            return jsonify({
                'status': 'success',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'divergences_count': len(divergences),
                'divergences': divergences[:15],
                'market_summary': {
                    'dominant_signal': dominant_signal,
                    'signal_breakdown': dict(signal_counts)
                },
                'interpretation': {
                    'accumulation': 'Smart money buying - bullish',
                    'distribution': 'Smart money selling into strength - bearish',
                    'capitulation': 'Panic selling - potential bottom',
                    'confirmation': 'Trend continuing - follow direction'
                }
            })

        except Exception as e:
            return jsonify({'status': 'error', 'error': str(e)}), 500

    @server.route('/api/analysis/funding-extremity')
    def funding_extremity():
        """
        Calculate extremity of current funding rates using statistical analysis.

        Z-score interpretation:
        - Z > 2.0: Extremely positive, expect pullback (short bias)
        - Z < -2.0: Extremely negative, expect bounce (long bias)
        - Z between -1 and 1: Normal range, no signal
        """
        try:
            markets = container.exchange_service.fetch_all_markets()

            # Collect all funding rates
            funding_data = []
            all_rates = []

            for market in markets:
                if market.funding_rate is not None:
                    exchange_name = str(market.exchange)
                    rate = market.funding_rate

                    all_rates.append(rate)
                    funding_data.append({
                        'exchange': exchange_name,
                        'funding_rate': rate,
                        'volume_24h': market.volume_24h
                    })

            if not all_rates:
                return jsonify({'status': 'error', 'error': 'No funding rate data available'}), 503

            # Calculate statistics
            mean_funding = sum(all_rates) / len(all_rates)
            variance = sum((r - mean_funding) ** 2 for r in all_rates) / len(all_rates)
            std_funding = math.sqrt(variance) if variance > 0 else 0.0001

            # Calculate volume-weighted average
            total_volume = sum(d['volume_24h'] for d in funding_data)
            weighted_funding = sum(d['funding_rate'] * d['volume_24h'] for d in funding_data) / total_volume if total_volume > 0 else mean_funding

            extremes = []

            for data in funding_data:
                rate = data['funding_rate']
                z_score = (rate - mean_funding) / std_funding if std_funding > 0 else 0

                # Determine signal
                if z_score > 2.0:
                    signal = 'short'
                    signal_strength = 'strong' if z_score > 3.0 else 'moderate'
                elif z_score < -2.0:
                    signal = 'long'
                    signal_strength = 'strong' if z_score < -3.0 else 'moderate'
                else:
                    signal = 'neutral'
                    signal_strength = 'none'

                # Calculate percentile (simplified)
                percentile = sum(1 for r in all_rates if r <= rate) / len(all_rates) * 100

                extremes.append({
                    'exchange': data['exchange'],
                    'funding_rate_pct': round(rate * 100, 4),
                    'z_score': round(z_score, 2),
                    'percentile': round(percentile, 1),
                    'signal': signal,
                    'signal_strength': signal_strength,
                    'annualized_pct': round(rate * 100 * 3 * 365, 2)
                })

            # Sort by absolute z-score
            extremes.sort(key=lambda x: abs(x['z_score']), reverse=True)

            # Determine market-wide signal
            avg_z = sum(e['z_score'] for e in extremes) / len(extremes) if extremes else 0

            if avg_z > 1.5:
                market_signal = 'overbought'
            elif avg_z < -1.5:
                market_signal = 'oversold'
            else:
                market_signal = 'neutral'

            return jsonify({
                'status': 'success',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'market_signal': market_signal,
                'statistics': {
                    'mean_funding_pct': round(mean_funding * 100, 4),
                    'std_funding_pct': round(std_funding * 100, 4),
                    'weighted_avg_funding_pct': round(weighted_funding * 100, 4),
                    'avg_z_score': round(avg_z, 2)
                },
                'extremes_count': len([e for e in extremes if e['signal'] != 'neutral']),
                'extremes': extremes[:15],
                'interpretation': {
                    'z_above_2': 'Mean reversion SHORT opportunity',
                    'z_below_neg2': 'Mean reversion LONG opportunity',
                    'typical_reversion': '24-72 hours for funding to normalize'
                }
            })

        except Exception as e:
            return jsonify({'status': 'error', 'error': str(e)}), 500

    # ========================================
    # TIER 2: RISK & SENTIMENT INTELLIGENCE
    # ========================================

    @server.route('/api/analysis/liquidation-risk-heatmap')
    def liquidation_risk_heatmap():
        """
        Composite risk score indicating potential for liquidation cascades.

        Components:
        - Leverage proxy (OI/Volume ratio): 40% weight
        - Funding stress (|funding| / median): 30% weight
        - Implied volatility proxy: 30% weight
        """
        try:
            markets = container.exchange_service.fetch_all_markets()

            # Collect metrics for all exchanges
            risk_scores = []
            all_leverage_proxies = []
            all_funding_abs = []

            for market in markets:
                if market.volume_24h and market.volume_24h > 0:
                    oi = market.open_interest or 0
                    volume = market.volume_24h
                    funding = market.funding_rate or 0

                    leverage_proxy = oi / volume if volume > 0 else 0
                    all_leverage_proxies.append(leverage_proxy)
                    all_funding_abs.append(abs(funding))

            # Calculate medians for normalization
            median_leverage = sorted(all_leverage_proxies)[len(all_leverage_proxies) // 2] if all_leverage_proxies else 1
            median_funding = sorted(all_funding_abs)[len(all_funding_abs) // 2] if all_funding_abs else 0.0001

            for market in markets:
                if market.volume_24h and market.volume_24h > 0:
                    exchange_name = str(market.exchange)
                    oi = market.open_interest or 0
                    volume = market.volume_24h
                    funding = market.funding_rate or 0

                    # Component 1: Leverage proxy (capped at 5x median)
                    leverage_proxy = oi / volume if volume > 0 else 0
                    leverage_normalized = min(leverage_proxy / (median_leverage * 5), 1) * 100

                    # Component 2: Funding stress (capped at 3x median)
                    funding_stress = abs(funding) / median_funding if median_funding > 0 else 0
                    funding_normalized = min(funding_stress / 3, 1) * 100

                    # Component 3: Volume volatility proxy (high volume = potential volatility)
                    # Use volume relative to OI as volatility indicator
                    vol_proxy = volume / oi if oi > 0 else 1
                    vol_normalized = min(vol_proxy, 1) * 100

                    # Composite heat score
                    heat_score = (
                        leverage_normalized * 0.4 +
                        funding_normalized * 0.3 +
                        vol_normalized * 0.3
                    )

                    # Determine risk level
                    if heat_score > 80:
                        risk_level = 'critical'
                        recommendation = 'Reduce position size significantly, widen stops'
                    elif heat_score > 60:
                        risk_level = 'elevated'
                        recommendation = 'Consider reducing exposure, tighten risk management'
                    elif heat_score > 40:
                        risk_level = 'moderate'
                        recommendation = 'Normal risk, monitor closely'
                    else:
                        risk_level = 'low'
                        recommendation = 'Low liquidation risk environment'

                    risk_scores.append({
                        'exchange': exchange_name,
                        'heat_score': round(heat_score, 1),
                        'risk_level': risk_level,
                        'recommendation': recommendation,
                        'components': {
                            'leverage_proxy': round(leverage_normalized, 1),
                            'funding_stress': round(funding_normalized, 1),
                            'volatility_proxy': round(vol_normalized, 1)
                        },
                        'raw_metrics': {
                            'oi_volume_ratio': round(leverage_proxy, 2),
                            'funding_rate_pct': round(funding * 100, 4),
                            'open_interest': oi
                        }
                    })

            # Sort by heat score
            risk_scores.sort(key=lambda x: x['heat_score'], reverse=True)

            # Calculate market average
            avg_heat = sum(r['heat_score'] for r in risk_scores) / len(risk_scores) if risk_scores else 0

            # Count by risk level
            risk_distribution = defaultdict(int)
            for r in risk_scores:
                risk_distribution[r['risk_level']] += 1

            return jsonify({
                'status': 'success',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'market_avg_heat': round(avg_heat, 1),
                'market_risk_level': 'critical' if avg_heat > 70 else 'elevated' if avg_heat > 50 else 'moderate' if avg_heat > 30 else 'low',
                'risk_distribution': dict(risk_distribution),
                'exchanges_count': len(risk_scores),
                'heatmap': risk_scores[:15],
                'methodology': {
                    'leverage_weight': 0.4,
                    'funding_weight': 0.3,
                    'volatility_weight': 0.3,
                    'scale': '0-100 (higher = more risk)'
                }
            })

        except Exception as e:
            return jsonify({'status': 'error', 'error': str(e)}), 500

    @server.route('/api/analysis/market-sentiment-index')
    def market_sentiment_index():
        """
        OI-weighted aggregate funding rate representing market-wide positioning.

        Interpretation:
        - > 0.05%: Over-leveraged long, consider shorts
        - < -0.02%: Over-leveraged short, consider longs
        - Crossing zero: Regime shift
        """
        try:
            markets = container.exchange_service.fetch_all_markets()

            # Calculate OI-weighted funding
            weighted_sum = 0
            total_oi = 0

            funding_contributions = []

            for market in markets:
                if market.funding_rate is not None and market.open_interest:
                    exchange_name = str(market.exchange)
                    funding = market.funding_rate
                    oi = market.open_interest

                    weighted_sum += funding * oi
                    total_oi += oi

                    funding_contributions.append({
                        'exchange': exchange_name,
                        'funding_rate_pct': round(funding * 100, 4),
                        'open_interest': oi,
                        'contribution': funding * oi
                    })

            if total_oi == 0:
                return jsonify({'status': 'error', 'error': 'No OI data available'}), 503

            sentiment_index = weighted_sum / total_oi
            sentiment_pct = sentiment_index * 100

            # Determine market interpretation
            if sentiment_pct > 0.05:
                interpretation = 'extremely_bullish'
                contrarian_signal = 'Consider short positions - market over-leveraged long'
            elif sentiment_pct > 0.02:
                interpretation = 'bullish'
                contrarian_signal = 'Caution on new longs - elevated positioning'
            elif sentiment_pct < -0.02:
                interpretation = 'bearish'
                contrarian_signal = 'Caution on new shorts - elevated short positioning'
            elif sentiment_pct < -0.05:
                interpretation = 'extremely_bearish'
                contrarian_signal = 'Consider long positions - market over-leveraged short'
            else:
                interpretation = 'neutral'
                contrarian_signal = 'No extreme positioning detected'

            # Sort contributions by absolute contribution
            funding_contributions.sort(key=lambda x: abs(x['contribution']), reverse=True)

            return jsonify({
                'status': 'success',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'sentiment_index': round(sentiment_index, 6),
                'sentiment_pct': round(sentiment_pct, 4),
                'interpretation': interpretation,
                'contrarian_signal': contrarian_signal,
                'total_open_interest': total_oi,
                'top_contributors': funding_contributions[:10],
                'thresholds': {
                    'extremely_bullish': '>0.05%',
                    'bullish': '0.02% to 0.05%',
                    'neutral': '-0.02% to 0.02%',
                    'bearish': '-0.05% to -0.02%',
                    'extremely_bearish': '<-0.05%'
                }
            })

        except Exception as e:
            return jsonify({'status': 'error', 'error': str(e)}), 500

    @server.route('/api/analysis/oi-concentration')
    def oi_concentration():
        """
        Herfindahl-Hirschman Index (HHI) measuring OI concentration across exchanges.

        HHI interpretation:
        - > 0.40: High concentration (single exchange dominance, manipulation risk)
        - 0.25-0.40: Moderate concentration
        - < 0.25: Healthy distribution
        """
        try:
            markets = container.exchange_service.fetch_all_markets()

            # Aggregate OI by exchange
            exchange_oi = {}
            total_oi = 0

            for market in markets:
                if market.open_interest:
                    exchange_name = str(market.exchange)
                    exchange_oi[exchange_name] = market.open_interest
                    total_oi += market.open_interest

            if total_oi == 0:
                return jsonify({'status': 'error', 'error': 'No OI data available'}), 503

            # Calculate market shares and HHI
            market_shares = {}
            hhi = 0

            for exchange, oi in exchange_oi.items():
                share = oi / total_oi
                market_shares[exchange] = share
                hhi += share ** 2

            # Find dominant exchange
            dominant_exchange = max(market_shares, key=market_shares.get)
            dominant_share = market_shares[dominant_exchange]

            # Determine concentration level
            if hhi > 0.40:
                concentration_level = 'high'
                warning = f'Single exchange ({dominant_exchange}) has significant market power'
            elif hhi > 0.25:
                concentration_level = 'moderate'
                warning = 'Monitor for concentration increases'
            else:
                concentration_level = 'healthy'
                warning = None

            # Build exchange breakdown
            exchange_breakdown = [
                {
                    'exchange': ex,
                    'open_interest': exchange_oi[ex],
                    'market_share_pct': round(share * 100, 2),
                    'is_dex': is_dex(ex)
                }
                for ex, share in sorted(market_shares.items(), key=lambda x: x[1], reverse=True)
            ]

            # Calculate DEX vs CEX concentration
            dex_share = sum(share for ex, share in market_shares.items() if is_dex(ex))
            cex_share = 1 - dex_share

            return jsonify({
                'status': 'success',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'hhi': round(hhi, 4),
                'concentration_level': concentration_level,
                'warning': warning,
                'dominant_exchange': dominant_exchange,
                'dominant_share_pct': round(dominant_share * 100, 2),
                'total_open_interest': total_oi,
                'exchange_breakdown': exchange_breakdown,
                'dex_cex_split': {
                    'dex_share_pct': round(dex_share * 100, 2),
                    'cex_share_pct': round(cex_share * 100, 2)
                },
                'interpretation': {
                    'hhi_above_0.4': 'High concentration - manipulation/single-point-of-failure risk',
                    'hhi_0.25_to_0.4': 'Moderate concentration - some risk',
                    'hhi_below_0.25': 'Healthy distribution - lower systemic risk'
                }
            })

        except Exception as e:
            return jsonify({'status': 'error', 'error': str(e)}), 500

    # ========================================
    # TIER 3: FLOW ANALYSIS
    # ========================================

    @server.route('/api/analysis/dex-cex-flow-dynamics')
    def dex_cex_flow_dynamics():
        """
        DEX/CEX volume and OI ratio analysis for flow pattern detection.

        Signals:
        - Rising DEX ratio: Retail FOMO or regulatory arbitrage
        - Falling DEX ratio: Institutional CEX preference
        - Sudden DEX spike: Smart money avoiding surveillance
        """
        try:
            markets = container.exchange_service.fetch_all_markets()

            dex_volume = 0
            cex_volume = 0
            dex_oi = 0
            cex_oi = 0

            dex_exchanges = []
            cex_exchanges = []

            for market in markets:
                exchange_name = str(market.exchange)
                volume = market.volume_24h or 0
                oi = market.open_interest or 0

                if is_dex(exchange_name):
                    dex_volume += volume
                    dex_oi += oi
                    dex_exchanges.append({
                        'exchange': exchange_name,
                        'volume_24h': volume,
                        'open_interest': oi
                    })
                else:
                    cex_volume += volume
                    cex_oi += oi
                    cex_exchanges.append({
                        'exchange': exchange_name,
                        'volume_24h': volume,
                        'open_interest': oi
                    })

            total_volume = dex_volume + cex_volume
            total_oi = dex_oi + cex_oi

            # Calculate ratios
            dex_volume_ratio = dex_volume / cex_volume if cex_volume > 0 else 0
            dex_oi_ratio = dex_oi / cex_oi if cex_oi > 0 else 0

            # Volume and OI percentages
            dex_volume_pct = (dex_volume / total_volume * 100) if total_volume > 0 else 0
            dex_oi_pct = (dex_oi / total_oi * 100) if total_oi > 0 else 0

            # Determine trend (would need historical data for proper momentum)
            # For now, use OI vs Volume ratio as flow indicator
            if dex_oi_pct > dex_volume_pct + 2:
                flow_trend = 'dex_accumulating'
                interpretation = 'DEX OI outpacing volume - positions being built on DEX'
            elif dex_volume_pct > dex_oi_pct + 2:
                flow_trend = 'dex_trading'
                interpretation = 'DEX volume outpacing OI - active trading/closing on DEX'
            else:
                flow_trend = 'balanced'
                interpretation = 'DEX volume and OI proportionally balanced'

            return jsonify({
                'status': 'success',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'dex': {
                    'volume_24h': dex_volume,
                    'open_interest': dex_oi,
                    'volume_pct': round(dex_volume_pct, 2),
                    'oi_pct': round(dex_oi_pct, 2),
                    'exchange_count': len(dex_exchanges),
                    'exchanges': sorted(dex_exchanges, key=lambda x: x['volume_24h'], reverse=True)
                },
                'cex': {
                    'volume_24h': cex_volume,
                    'open_interest': cex_oi,
                    'volume_pct': round(100 - dex_volume_pct, 2),
                    'oi_pct': round(100 - dex_oi_pct, 2),
                    'exchange_count': len(cex_exchanges),
                    'exchanges': sorted(cex_exchanges, key=lambda x: x['volume_24h'], reverse=True)
                },
                'ratios': {
                    'dex_to_cex_volume': round(dex_volume_ratio, 4),
                    'dex_to_cex_oi': round(dex_oi_ratio, 4)
                },
                'flow_trend': flow_trend,
                'interpretation': interpretation,
                'totals': {
                    'volume_24h': total_volume,
                    'open_interest': total_oi
                }
            })

        except Exception as e:
            return jsonify({'status': 'error', 'error': str(e)}), 500

    @server.route('/api/analysis/exchange-flow-migration')
    def exchange_flow_migration():
        """
        Identify which exchanges are gaining or losing market share.

        Use cases:
        - Volume migrating = better liquidity opportunity
        - Sudden share loss = potential exchange issues
        - Track smart money movement
        """
        try:
            markets = container.exchange_service.fetch_all_markets()

            # Calculate current market shares
            total_volume = sum(m.volume_24h or 0 for m in markets)
            total_oi = sum(m.open_interest or 0 for m in markets)

            if total_volume == 0:
                return jsonify({'status': 'error', 'error': 'No volume data available'}), 503

            migrations = []

            for market in markets:
                exchange_name = str(market.exchange)
                volume = market.volume_24h or 0
                oi = market.open_interest or 0

                volume_share = volume / total_volume if total_volume > 0 else 0
                oi_share = oi / total_oi if total_oi > 0 else 0

                # Calculate efficiency (OI per unit volume - higher = more position retention)
                efficiency = oi / volume if volume > 0 else 0

                migrations.append({
                    'exchange': exchange_name,
                    'is_dex': is_dex(exchange_name),
                    'volume_24h': volume,
                    'open_interest': oi,
                    'volume_share_pct': round(volume_share * 100, 2),
                    'oi_share_pct': round(oi_share * 100, 2),
                    'efficiency_ratio': round(efficiency, 2),
                    'formatted_volume': f"${volume/1e9:.2f}B" if volume > 1e9 else f"${volume/1e6:.1f}M"
                })

            # Sort by volume share
            migrations.sort(key=lambda x: x['volume_share_pct'], reverse=True)

            # Identify leaders and laggards
            leaders = [m for m in migrations if m['volume_share_pct'] > 10]
            mid_tier = [m for m in migrations if 2 <= m['volume_share_pct'] <= 10]
            small = [m for m in migrations if m['volume_share_pct'] < 2]

            return jsonify({
                'status': 'success',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'total_volume_24h': total_volume,
                'total_open_interest': total_oi,
                'exchange_count': len(migrations),
                'market_leaders': leaders,
                'mid_tier': mid_tier,
                'small_exchanges': small,
                'full_breakdown': migrations,
                'insights': {
                    'most_efficient': max(migrations, key=lambda x: x['efficiency_ratio'])['exchange'] if migrations else None,
                    'highest_volume': migrations[0]['exchange'] if migrations else None,
                    'dex_total_share_pct': round(sum(m['volume_share_pct'] for m in migrations if m['is_dex']), 2)
                }
            })

        except Exception as e:
            return jsonify({'status': 'error', 'error': str(e)}), 500

    @server.route('/api/analysis/volume-anomaly-detector')
    def volume_anomaly_detector():
        """
        Statistical detection of unusual volume activity.

        Signals:
        - Z > 3.0: Extreme anomaly - investigate before trading
        - Z > 2.0: Elevated activity - tighten risk
        - Normal: Trade normally
        """
        try:
            markets = container.exchange_service.fetch_all_markets()

            # Collect volume data
            volumes = []
            volume_data = []

            for market in markets:
                if market.volume_24h and market.volume_24h > 0:
                    exchange_name = str(market.exchange)
                    volume = market.volume_24h
                    volumes.append(volume)
                    volume_data.append({
                        'exchange': exchange_name,
                        'volume_24h': volume,
                        'open_interest': market.open_interest or 0
                    })

            if not volumes:
                return jsonify({'status': 'error', 'error': 'No volume data available'}), 503

            # Calculate statistics
            mean_volume = sum(volumes) / len(volumes)
            variance = sum((v - mean_volume) ** 2 for v in volumes) / len(volumes)
            std_volume = math.sqrt(variance) if variance > 0 else 1

            # Calculate z-scores and anomalies
            anomalies = []
            for data in volume_data:
                volume = data['volume_24h']
                z_score = (volume - mean_volume) / std_volume if std_volume > 0 else 0

                # Determine anomaly level
                if abs(z_score) > 3.0:
                    anomaly_level = 'extreme'
                    action = 'Investigate before trading - potential news or manipulation'
                elif abs(z_score) > 2.0:
                    anomaly_level = 'elevated'
                    action = 'Tighten risk parameters'
                elif abs(z_score) > 1.5:
                    anomaly_level = 'notable'
                    action = 'Monitor closely'
                else:
                    anomaly_level = 'normal'
                    action = 'Normal trading conditions'

                anomalies.append({
                    'exchange': data['exchange'],
                    'volume_24h': volume,
                    'z_score': round(z_score, 2),
                    'anomaly_level': anomaly_level,
                    'action': action,
                    'volume_vs_mean_pct': round((volume / mean_volume - 1) * 100, 1),
                    'formatted_volume': f"${volume/1e9:.2f}B" if volume > 1e9 else f"${volume/1e6:.1f}M"
                })

            # Sort by absolute z-score
            anomalies.sort(key=lambda x: abs(x['z_score']), reverse=True)

            # Count anomalies by level
            anomaly_counts = defaultdict(int)
            for a in anomalies:
                anomaly_counts[a['anomaly_level']] += 1

            # Determine market-wide anomaly status
            extreme_count = anomaly_counts.get('extreme', 0)
            elevated_count = anomaly_counts.get('elevated', 0)

            if extreme_count > 2:
                market_status = 'high_anomaly'
                market_action = 'Multiple exchanges showing extreme volume - major market event likely'
            elif extreme_count > 0 or elevated_count > 3:
                market_status = 'elevated_activity'
                market_action = 'Unusual activity detected - exercise caution'
            else:
                market_status = 'normal'
                market_action = 'Volume within normal ranges'

            return jsonify({
                'status': 'success',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'market_status': market_status,
                'market_action': market_action,
                'statistics': {
                    'mean_volume': mean_volume,
                    'std_volume': std_volume,
                    'total_exchanges': len(anomalies)
                },
                'anomaly_distribution': dict(anomaly_counts),
                'anomalies': anomalies[:15],
                'interpretation': {
                    'z_above_3': 'Extreme - potential news/manipulation',
                    'z_2_to_3': 'Elevated - increased activity',
                    'z_1.5_to_2': 'Notable - worth monitoring',
                    'z_below_1.5': 'Normal range'
                }
            })

        except Exception as e:
            return jsonify({'status': 'error', 'error': str(e)}), 500

    print("✅ Analysis routes registered successfully (9 endpoints)")
