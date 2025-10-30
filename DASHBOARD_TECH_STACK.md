# Real-Time Crypto Dashboard Tech Stack

**Date**: October 28, 2025
**Project**: Crypto Perpetuals Tracker
**Purpose**: Continuously running web dashboard for real-time market monitoring

---

## Executive Summary

This document outlines the recommended technology stack for building a production-ready, real-time cryptocurrency dashboard that displays market data, funding rates, arbitrage opportunities, and trading signals with continuous live updates.

**Key Requirements**:
- Real-time data visualization (funding rates, OI, volume, beta analysis)
- Dark orange/gold theme matching existing HTML reports
- Low-latency updates (60-second refresh minimum)
- Integration with existing Container/Service architecture
- Production deployment on VPS
- Pure Python implementation (no JavaScript frameworks)

**Recommended Stack**: **Plotly Dash + Server-Sent Events + Redis**

---

## 🏆 Core Technology Decisions

### 1. Backend Framework: **Plotly Dash**

**Decision**: Use Dash as the primary web framework

**Rationale**:
- **Purpose-built** for financial and trading dashboards
- **Best-in-class performance** for large-scale data applications
- **Native Plotly integration** - seamless use of existing chart code
- **Enterprise-grade** - used by major financial institutions
- **Pure Python** - no JavaScript framework required
- **Built-in reactivity** via callback system

**Pros**:
- ✅ Excellent performance with complex visualizations
- ✅ Built-in real-time updates via `dcc.Interval` component
- ✅ Integrates seamlessly with existing Plotly.js charts
- ✅ Component-based architecture (clean, maintainable code)
- ✅ Production-ready with authentication, caching, and scalability features
- ✅ Active development and strong community (2025)

**Cons**:
- ⚠️ Steeper learning curve compared to Streamlit
- ⚠️ Some advanced features require Dash Enterprise (optional)
- ⚠️ More verbose code for simple prototypes

**Alternatives Considered**:
- **Streamlit**: Simpler but poor performance at scale, script re-run approach problematic
- **FastAPI + React**: Better performance but requires JavaScript expertise
- **Reflex**: Modern but immature ecosystem, smaller community

---

### 2. Visualization Library: **Plotly.js** (via Dash)

**Decision**: Use Plotly.js for all charts and visualizations

**Rationale**:
- **Industry leader** for financial dashboards in 2025
- **Already in use** - existing HTML reports use Plotly
- **40+ chart types** including financial-specific charts
- **WebGPU rendering** for million-point datasets (2025 feature)
- **Interactive by default** - zoom, filter, hover tooltips

**Key Features**:
- Interactive zooming, panning, and filtering
- Real-time updates without full page reload
- Responsive design (mobile-friendly)
- Export capabilities (PNG, SVG, CSV)
- Customizable styling (matches dark orange/gold theme)

**Alternatives Considered**:
- **Chart.js**: Better raw performance but less interactive
- **D3.js**: Maximum flexibility but requires extensive custom code
- **ApexCharts**: Good alternative but Python integration not as mature

---

### 3. Real-Time Updates: **Server-Sent Events (SSE)**

**Decision**: Use SSE for live data streaming from server to browser

**Rationale**:
- **Simpler than WebSockets** for one-way data flow (server → client)
- **30% less overhead** than WebSocket connections
- **Automatic reconnection** - built into browser EventSource API
- **Standard HTTP** - no special server configuration needed
- **Perfect for dashboards** - clients only consume updates

**Implementation**:
```python
# Dash native approach using dcc.Interval
dcc.Interval(
    id='interval-component',
    interval=60*1000,  # 60 seconds
    n_intervals=0
)
```

**Advantages**:
- ✅ Browser-native implementation (no external libraries)
- ✅ Works through firewalls and proxies (HTTP/HTTPS)
- ✅ Automatic retry with exponential backoff
- ✅ Event IDs for replay and synchronization
- ✅ Lower memory footprint than WebSockets

**When to Use WebSockets Instead**:
- ❌ Not needed: Dashboard is read-only (server pushes updates)
- Use WebSockets only if: Bidirectional communication required (e.g., user trading actions)

---

### 4. Data Caching: **Redis** (Optional but Recommended)

**Decision**: Use Redis for caching frequently accessed data

**Rationale**:
- **Fast data retrieval** (sub-millisecond latency)
- **Reduces API calls** to exchanges by 80-90%
- **Shared cache** across multiple dashboard instances
- **TTL support** - automatic cache expiration

**Use Cases**:
- Cache market data for 60 seconds (refresh interval)
- Store pre-computed analytics (beta values, sentiment scores)
- Session management for authentication
- Rate limit tracking

**Alternatives**:
- **In-memory cache** (works for single-instance deployment)
- **SQLite** (existing solution, but slower for high-frequency reads)

---

## 📊 Complete Architecture

```
┌───────────────────────────────────────────────────────────┐
│                    Browser (Client)                        │
│  ┌────────────────────────────────────────────────────┐   │
│  │  Dark Orange/Gold Theme (Custom CSS)               │   │
│  │  • Gradient backgrounds (#0a0a0a → #1a1a1a)        │   │
│  │  • Orange borders (#FFA500)                        │   │
│  │  • Gold text (#FFD700)                             │   │
│  └────────────────────────────────────────────────────┘   │
│  ┌────────────────────────────────────────────────────┐   │
│  │  Plotly.js Charts                                   │   │
│  │  • Funding Rate Time Series                        │   │
│  │  • Market Dominance Pie Chart                      │   │
│  │  • Bitcoin Beta Spaghetti Chart                    │   │
│  │  • Arbitrage Opportunities Table                   │   │
│  └────────────────────────────────────────────────────┘   │
│  ┌────────────────────────────────────────────────────┐   │
│  │  Auto-Refresh (dcc.Interval: 60s)                  │   │
│  └────────────────────────────────────────────────────┘   │
└───────────────────────────────────────────────────────────┘
                           ↕ HTTP/SSE
┌───────────────────────────────────────────────────────────┐
│                  Dash Application Server                   │
│  ┌────────────────────────────────────────────────────┐   │
│  │  Layout Components (dash.html, dash.dcc)           │   │
│  │  • Market Overview Tab                             │   │
│  │  • Symbol Analysis Tab                             │   │
│  │  • Arbitrage Scanner Tab                           │   │
│  │  • Strategy Alerts Tab                             │   │
│  └────────────────────────────────────────────────────┘   │
│  ┌────────────────────────────────────────────────────┐   │
│  │  Callbacks (Business Logic)                        │   │
│  │  • @app.callback decorators                        │   │
│  │  • Data fetching and processing                    │   │
│  │  • Chart generation                                │   │
│  └────────────────────────────────────────────────────┘   │
└───────────────────────────────────────────────────────────┘
                           ↕
┌───────────────────────────────────────────────────────────┐
│                    Data Layer (Existing)                   │
│  ┌────────────────────────────────────────────────────┐   │
│  │  Container (Dependency Injection)                   │   │
│  │  • ExchangeService (8+ exchanges)                  │   │
│  │  • AnalysisService (beta, sentiment)               │   │
│  │  • ReportService (formatting)                      │   │
│  │  • AlertRepository (SQLite)                        │   │
│  └────────────────────────────────────────────────────┘   │
│  ┌────────────────────────────────────────────────────┐   │
│  │  Data Sources                                       │   │
│  │  • SQLite (alert_state.db, market.db)              │   │
│  │  • Redis (optional cache)                          │   │
│  │  • Exchange APIs (live data)                       │   │
│  │  • Generated reports (market_report_*.txt)         │   │
│  └────────────────────────────────────────────────────┘   │
└───────────────────────────────────────────────────────────┘
```

---

## 🎯 Framework Comparison

### Performance Metrics

| Feature | **Dash** ✅ | Streamlit | FastAPI + React | Reflex |
|---------|-------------|-----------|-----------------|--------|
| **Python-Only** | ✅ Yes | ✅ Yes | ❌ No (React needed) | ✅ Yes |
| **Financial Dashboards** | ⭐⭐⭐ Excellent | ⭐ Basic | ⭐⭐ Good | ⭐⭐ Good |
| **Real-Time Updates** | Built-in (`dcc.Interval`) | Script re-run | Manual WebSocket | Built-in |
| **Scalability** | Excellent | Poor (RAM per user) | Excellent | Good (maturing) |
| **Learning Curve** | Medium | Easy | Hard | Medium |
| **Community/Ecosystem** | Mature (2025) | Large | Very Large | Growing |
| **Integration Ease** | Easy | Easy | Medium | Easy |
| **Production Ready** | ✅ Yes | ⚠️ Internal tools only | ✅ Yes | ⚠️ Maturing |

### When to Use Each

**Use Dash if**:
- ✅ Building production financial/trading dashboards
- ✅ Need enterprise-grade performance and scalability
- ✅ Require complex, interactive visualizations
- ✅ Want pure Python full-stack development
- ✅ Value strong Plotly.js integration

**Use Streamlit if**:
- Internal prototypes or data science demos
- Single-user or small team applications
- Rapid iteration more important than performance

**Use FastAPI + React if**:
- Team has strong JavaScript/React expertise
- Need maximum flexibility in frontend design
- Building a full web application (not just dashboards)

**Use Reflex if**:
- Want modern Python full-stack development
- Don't mind some rough edges in a newer framework
- Value cutting-edge features over ecosystem maturity

---

## 🛠️ Implementation Plan

### Phase 1: Foundation (Week 1)

**Goal**: Get basic dashboard running locally

1. **Install Dependencies**
   ```bash
   pip install dash plotly pandas redis flask-caching
   ```

2. **Create Dashboard App Structure**
   ```
   dashboard/
   ├── app.py                 # Main Dash application
   ├── layouts/
   │   ├── __init__.py
   │   ├── market_overview.py # Market overview tab
   │   ├── symbol_analysis.py # Symbol/beta tab
   │   ├── arbitrage.py       # Arbitrage scanner tab
   │   └── alerts.py          # Strategy alerts tab
   ├── callbacks/
   │   ├── __init__.py
   │   ├── market_callbacks.py
   │   ├── symbol_callbacks.py
   │   ├── arbitrage_callbacks.py
   │   └── alerts_callbacks.py
   ├── components/
   │   ├── __init__.py
   │   ├── charts.py          # Reusable chart functions
   │   ├── tables.py          # Data table components
   │   └── cards.py           # Metric card components
   ├── assets/
   │   ├── custom.css         # Dark orange/gold theme
   │   └── favicon.ico
   └── utils/
       ├── __init__.py
       ├── data_fetcher.py    # Integration with Container
       └── cache.py           # Redis/memory cache wrapper
   ```

3. **Implement Dark Orange/Gold Theme**
   - Copy styling from existing HTML reports
   - Customize Dash CSS variables
   - Create reusable component styles

4. **Build Market Overview Page**
   - Funding rate chart (all exchanges)
   - Market dominance pie chart
   - Total volume/OI metrics
   - Sentiment indicators

**Deliverable**: Working dashboard at `http://localhost:8050` with market overview tab

---

### Phase 2: Core Features (Week 2)

**Goal**: Add all dashboard pages and real-time updates

1. **Symbol Analysis Page**
   - Bitcoin beta spaghetti chart (reuse existing code)
   - Top movers table (volume, price change)
   - Correlation matrix
   - High-beta opportunities

2. **Arbitrage Scanner Page**
   - Live arbitrage opportunities table
   - Spot-futures basis chart
   - Funding arbitrage calculator
   - Exchange comparison

3. **Strategy Alerts Page**
   - Recent alerts timeline
   - Alert quality metrics
   - Suppression rate chart
   - Strategy effectiveness breakdown

4. **Auto-Refresh Implementation**
   ```python
   dcc.Interval(
       id='interval-component',
       interval=60*1000,  # 60 seconds
       n_intervals=0
   )

   @app.callback(
       Output('market-data', 'children'),
       Input('interval-component', 'n_intervals')
   )
   def update_market_data(n):
       # Fetch latest data from Container
       return generate_charts()
   ```

**Deliverable**: Fully functional multi-page dashboard with auto-refresh

---

### Phase 3: Optimization (Week 3)

**Goal**: Production-ready performance and caching

1. **Implement Redis Caching**
   ```python
   from flask_caching import Cache

   cache = Cache(app.server, config={
       'CACHE_TYPE': 'redis',
       'CACHE_REDIS_URL': 'redis://localhost:6379/0',
       'CACHE_DEFAULT_TIMEOUT': 60
   })

   @cache.memoize(timeout=60)
   def fetch_market_data():
       # Expensive data fetching
       return data
   ```

2. **Performance Optimization**
   - Lazy loading for large datasets
   - Pagination for tables
   - Debounce callbacks to prevent excessive updates
   - Optimize Plotly chart rendering

3. **Error Handling & Monitoring**
   - Graceful degradation when APIs fail
   - Error message components
   - Logging integration
   - Health check endpoint

**Deliverable**: Production-ready dashboard with caching and monitoring

---

### Phase 4: Deployment (Week 4)

**Goal**: Deploy to VPS and configure systemd service

1. **VPS Deployment**
   ```bash
   # On VPS
   cd ~/crypto-perps-tracker
   python -m venv venv_dashboard
   source venv_dashboard/bin/activate
   pip install -r requirements_dashboard.txt
   ```

2. **Systemd Service**
   ```ini
   [Unit]
   Description=Crypto Dashboard
   After=network.target

   [Service]
   Type=simple
   User=linuxuser
   WorkingDirectory=/home/linuxuser/crypto-perps-tracker
   Environment="PATH=/home/linuxuser/crypto-perps-tracker/venv_dashboard/bin"
   ExecStart=/home/linuxuser/crypto-perps-tracker/venv_dashboard/bin/python dashboard/app.py
   Restart=on-failure

   [Install]
   WantedBy=multi-user.target
   ```

3. **Nginx Reverse Proxy**
   ```nginx
   server {
       listen 80;
       server_name dashboard.your-domain.com;

       location / {
           proxy_pass http://127.0.0.1:8050;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
       }
   }
   ```

4. **Firewall Configuration**
   ```bash
   sudo ufw allow 8050/tcp  # Dashboard port
   sudo ufw allow 6379/tcp  # Redis (localhost only)
   ```

**Deliverable**: Dashboard running 24/7 on VPS with automatic restart

---

## 📦 Dependencies

### Required Python Packages

```txt
# Dashboard Framework
dash==2.17.0
dash-bootstrap-components==1.6.0

# Visualization
plotly==5.22.0

# Data Processing
pandas==2.2.2
numpy==1.26.4

# Caching (Optional but Recommended)
redis==5.0.4
flask-caching==2.1.0

# Existing Project Dependencies
pyyaml>=6.0
requests>=2.31.0
python-dotenv>=1.0.0
```

### System Dependencies

```bash
# Redis (for caching)
sudo apt install redis-server

# Nginx (for reverse proxy)
sudo apt install nginx
```

---

## 🚀 Quick Start Guide

### 1. Install Dependencies

```bash
cd ~/crypto-perps-tracker
pip install dash plotly pandas flask-caching redis
```

### 2. Create Minimal Dashboard

```python
# dashboard/app.py
import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.graph_objects as go
from src.container import Container
from src.models.config import Config

# Initialize Dash app
app = dash.Dash(__name__)

# Initialize Container
config = Config.from_yaml('config/config.yaml')
container = Container(config)

# Dark orange/gold theme
app.layout = html.Div([
    html.H1("Crypto Perps Dashboard",
            style={'color': '#FFA500', 'textAlign': 'center'}),

    dcc.Interval(id='interval', interval=60*1000, n_intervals=0),

    dcc.Graph(id='funding-chart')
], style={'backgroundColor': '#0a0a0a', 'padding': '20px'})

@app.callback(
    Output('funding-chart', 'figure'),
    Input('interval', 'n_intervals')
)
def update_chart(n):
    # Fetch data using existing Container
    markets = container.exchange_service.fetch_all_markets()

    # Create chart
    fig = go.Figure()
    for market in markets:
        fig.add_trace(go.Scatter(
            x=[market['exchange']],
            y=[market['funding_rate']],
            mode='markers+text',
            name=market['exchange']
        ))

    fig.update_layout(
        template='plotly_dark',
        paper_bgcolor='#0a0a0a',
        plot_bgcolor='#1a1a1a',
        font={'color': '#FFD700'}
    )

    return fig

if __name__ == '__main__':
    app.run_server(debug=True, host='0.0.0.0', port=8050)
```

### 3. Run Dashboard

```bash
python dashboard/app.py
```

### 4. Access Dashboard

- **Local**: `http://localhost:8050`
- **VPS**: `http://YOUR_VPS_IP:8050`

---

## 🎨 Styling Reference

### Color Palette (from existing HTML)

```css
/* Background Gradients */
--bg-primary: linear-gradient(135deg, #0a0a0a 0%, #1a1a1a 100%);
--bg-secondary: linear-gradient(135deg, #1a1a1a 0%, #2a2a2a 100%);

/* Colors */
--orange: #FFA500;      /* Primary accent */
--gold: #FFD700;        /* Text and highlights */
--light-orange: #FDB44B;
--red-orange: #FF6B35;

/* Borders */
--border-primary: 3px solid #FFA500;
--border-secondary: 2px solid #FDB44B;

/* Shadows */
--shadow-primary: 0 0 40px rgba(255, 165, 0, 0.4);
--shadow-secondary: 0 0 30px rgba(255, 165, 0, 0.3);
--text-shadow: 0 0 30px rgba(255, 165, 0, 1);
```

### Typography

```css
--font-primary: 'Courier New', monospace;
--font-size-h1: 2.8em;
--font-size-h2: 1.6em;
--font-size-body: 1em;
```

---

## 📊 Sample Dashboard Pages

### Market Overview Tab
- **Top Metrics Cards**: Total Volume, Total OI, Active Exchanges, Sentiment Score
- **Funding Rate Chart**: Time-series showing all exchanges
- **Market Dominance**: Pie chart of volume distribution
- **Top Movers**: Table of biggest price changes

### Symbol Analysis Tab
- **Bitcoin Beta Chart**: Spaghetti chart (reuse existing code)
- **Correlation Heatmap**: Inter-symbol correlations
- **High Beta Opportunities**: Table of amplified movers
- **Volume Leaders**: Bar chart of top volume symbols

### Arbitrage Scanner Tab
- **Opportunities Table**: Live arbitrage spreads
- **Basis Chart**: Spot-futures basis time-series
- **Funding Arbitrage**: Calculator and historical data
- **Exchange Comparison**: Price differences matrix

### Strategy Alerts Tab
- **Recent Alerts**: Timeline of last 24 hours
- **Alert Quality Metrics**: Score over time
- **Suppression Chart**: Alerts sent vs suppressed
- **Strategy Performance**: Breakdown by strategy tier

---

## 🔒 Security Considerations

### Authentication (Optional)

```python
import dash_auth

# Simple username/password
VALID_CREDENTIALS = {
    'admin': 'your-secure-password'
}

auth = dash_auth.BasicAuth(
    app,
    VALID_CREDENTIALS
)
```

### Best Practices

- ✅ Use environment variables for sensitive config
- ✅ Enable HTTPS via Nginx reverse proxy
- ✅ Implement rate limiting for API endpoints
- ✅ Sanitize user inputs (if adding interactive features)
- ✅ Regular security updates for dependencies

---

## 📈 Scalability Considerations

### Single VPS Deployment (Current)
- **Capacity**: ~100 concurrent users
- **Resources**: 2 CPU, 4GB RAM sufficient
- **Cost**: ~$10-20/month

### Multi-Instance Deployment (Future)
- **Load Balancer**: Nginx or HAProxy
- **Session Management**: Redis for shared sessions
- **Database**: Read replicas for SQLite or migrate to PostgreSQL
- **Monitoring**: Prometheus + Grafana

---

## 🧪 Testing Strategy

### Unit Tests
```python
# test_dashboard.py
def test_market_overview_layout():
    from dashboard.layouts.market_overview import create_layout
    layout = create_layout()
    assert layout is not None
```

### Integration Tests
```python
# test_callbacks.py
from dash.testing.application_runners import import_app

def test_auto_refresh(dash_duo):
    app = import_app("dashboard.app")
    dash_duo.start_server(app)
    dash_duo.wait_for_element("#funding-chart", timeout=10)
```

---

## 📚 Learning Resources

### Official Documentation
- **Dash**: https://dash.plotly.com/
- **Plotly**: https://plotly.com/python/
- **Flask-Caching**: https://flask-caching.readthedocs.io/

### Tutorials
- Dash for Beginners: https://dash.plotly.com/tutorial
- Real-Time Dashboards: https://dash.plotly.com/live-updates
- Financial Dashboards: https://plotly.com/python/financial-charts/

### Community
- Dash Community Forum: https://community.plotly.com/
- GitHub Issues: https://github.com/plotly/dash/issues

---

## 🔄 Maintenance and Updates

### Daily
- Monitor dashboard performance (response times)
- Check error logs
- Verify data refresh working

### Weekly
- Review cache hit rates
- Analyze user access patterns
- Update dependencies (security patches)

### Monthly
- Performance optimization review
- Evaluate new Dash/Plotly features
- User feedback integration

---

## 📝 Changelog

### Version 1.0 (Planned - November 2025)
- Initial release with 4 main tabs
- Auto-refresh every 60 seconds
- Dark orange/gold theme
- Integration with existing Container architecture

### Future Enhancements
- [ ] Mobile-responsive design
- [ ] User preferences and saved views
- [ ] Email/SMS alerts integration
- [ ] Historical data comparison
- [ ] AI-powered insights
- [ ] Multi-user authentication
- [ ] API endpoint for programmatic access

---

## 🎯 Success Metrics

### Performance Targets
- ⚡ Page load time: < 2 seconds
- 🔄 Data refresh latency: < 5 seconds
- 📊 Chart render time: < 1 second
- 💾 Memory usage: < 500MB per instance
- 🚀 Concurrent users: 50+ without degradation

### User Experience
- ✅ 99.9% uptime
- ✅ Zero data loss
- ✅ Intuitive navigation (< 3 clicks to any feature)
- ✅ Accessibility compliance (WCAG 2.1 AA)

---

## 🆘 Troubleshooting

### Common Issues

**Dashboard not loading**
```bash
# Check if process is running
ps aux | grep python | grep dashboard

# Check logs
tail -f logs/dashboard.log

# Restart service
sudo systemctl restart crypto-dashboard
```

**Slow performance**
- Check Redis connection: `redis-cli ping`
- Monitor CPU/RAM: `htop`
- Review callback efficiency
- Enable caching for expensive operations

**Charts not updating**
- Verify `dcc.Interval` component present
- Check callback inputs/outputs match
- Inspect browser console for errors
- Confirm data fetching working

---

## 📞 Support

### Internal Resources
- Architecture Documentation: `/docs/architecture.md`
- Container Service Docs: `/docs/container.md`
- API Reference: `/docs/api.md`

### External Resources
- Plotly Community: https://community.plotly.com/
- Stack Overflow: `[plotly-dash]` tag
- GitHub Issues: Project repository

---

## ✅ Next Steps

1. **Review this document** and confirm tech stack approval
2. **Set up development environment** with required dependencies
3. **Create minimal proof-of-concept** (1-2 days)
4. **Iteratively add features** following phased approach
5. **Deploy to VPS** and configure systemd service
6. **Monitor and optimize** based on real-world usage

---

**Status**: Ready for implementation
**Estimated Timeline**: 4 weeks to production
**Risk Level**: Low (proven technologies, clear architecture)

**Decision**: Proceed with Dash + Plotly.js + SSE implementation? ✅
