# Dashboard Performance Optimization Guide

## Current Performance Bottlenecks

### Identified Issues:
1. **60s auto-refresh** - Fetches all data every minute (heavy)
2. **30s cache TTL** - Too short, causes frequent API calls
3. **Debug mode enabled** - Adds overhead in production
4. **Synchronous data loading** - All tabs load data on page load
5. **No persistent storage** - Historical data fetched from API every time
6. **Large dataset sizes** - Analyzing 30+ symbols with 12h historical data

## Optimization Strategies

### 1. **Immediate Wins (< 1 hour)**

#### A. Increase Cache TTLs
**Current:**
```python
@cached(ttl_seconds=30)  # Too short!
def get_symbol_analytics_cached(...)
```

**Optimized:**
```python
# Symbol analytics: 2 minutes (market data doesn't change that fast)
@cached(ttl_seconds=120)
def get_symbol_analytics_cached(...)

# Performance chart: 10 minutes (historical data is expensive)
@cached(ttl_seconds=600)
def get_performance_chart_plotly(...)
```

#### B. Increase Auto-Refresh Interval
**Current:**
```python
dcc.Interval(
    id='interval-component',
    interval=60*1000,  # 60 seconds
    n_intervals=0
)
```

**Optimized:**
```python
dcc.Interval(
    id='interval-component',
    interval=120*1000,  # 120 seconds (2 minutes)
    n_intervals=0
)
```

#### C. Disable Debug Mode in Production
**Current:**
```python
app.run(
    debug=True,  # Don't use in production!
    host='0.0.0.0',
    port=8050
)
```

**Optimized:**
```python
import os
app.run(
    debug=os.getenv('DASH_DEBUG', 'false').lower() == 'true',
    host='0.0.0.0',
    port=8050
)
```

#### D. Reduce Initial Data Load
**Current:**
```python
analyses = get_symbol_analytics(container, top_n=15)
```

**Optimized:**
```python
# Load fewer symbols on initial page load
analyses = get_symbol_analytics(container, top_n=10)  # Was 15
```

---

### 2. **Medium Impact (2-4 hours)**

#### A. Implement Lazy Tab Loading

**Problem:** Currently all tabs potentially fetch data even when not visible.

**Solution:** Only load tab data when tab is selected (ALREADY DONE! Your tabs use value matching which is good)

#### B. Add Loading States

**Add to each tab:**
```python
from dash import dcc

# Wrap content in Loading component
dcc.Loading(
    id="loading-tab",
    type="cube",  # or "circle", "dot"
    children=[
        html.Div(id='tab-content')
    ],
    color="#FFA500"
)
```

#### C. Use ExchangeService Cache More Effectively

**Current:** Your Container initializes with cache, but callbacks don't leverage it well.

**Optimized:** Initialize container once globally (ALREADY DONE!) and ensure `use_cache=True` everywhere:

```python
# Always use cache in dashboard
markets = container.exchange_service.fetch_all_markets(use_cache=True)
```

#### D. Reduce Chart Complexity

```python
# Reduce data points in charts
vol_chart_limit = 10  # Was 12
beta_chart_limit = 12  # Was 15
performance_chart_symbols = 20  # Was 30
```

---

### 3. **High Impact (4-8 hours)**

#### A. Use Production WSGI Server (Gunicorn)

**Current:** Using Flask development server
```bash
python dashboard/app.py
```

**Optimized:** Use Gunicorn with multiple workers
```bash
# Install gunicorn
pip install gunicorn

# Run with 4 workers
gunicorn --workers 4 --bind 0.0.0.0:8050 --timeout 120 dashboard.app:server
```

**Update dashboard/app.py:**
```python
# Add this line after app = dash.Dash(...)
server = app.server  # Expose Flask server for gunicorn
```

#### B. Implement Redis Caching (Shared Cache)

**Install:**
```bash
pip install redis flask-caching
```

**Update dashboard/utils/cache.py:**
```python
from flask_caching import Cache
import os

# Initialize Flask-Caching with Redis
cache_config = {
    'CACHE_TYPE': 'RedisCache',
    'CACHE_REDIS_URL': os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
    'CACHE_DEFAULT_TIMEOUT': 120  # 2 minutes
}

# Alternative: Use simple cache if Redis not available
if not os.getenv('REDIS_URL'):
    cache_config = {
        'CACHE_TYPE': 'SimpleCache',
        'CACHE_DEFAULT_TIMEOUT': 120
    }

cache = Cache(config=cache_config)

# Initialize in app.py
cache.init_app(app.server)

# Use in functions
@cache.memoize(timeout=120)
def get_symbol_analytics(container, top_n=20):
    ...
```

#### C. Add Database for Historical Data

**Problem:** Performance chart fetches 12h of data from API every time (expensive!)

**Solution:** Store historical snapshots in database

```python
# scripts/historical_data_logger.py
import sqlite3
import time
from datetime import datetime

def log_market_snapshot():
    """Log market data every 5 minutes"""
    conn = sqlite3.connect('data/market_history.db')
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS market_snapshots (
            timestamp INTEGER,
            symbol TEXT,
            price REAL,
            volume_24h REAL,
            PRIMARY KEY (timestamp, symbol)
        )
    ''')

    # Fetch current data
    markets = container.exchange_service.fetch_all_markets()
    timestamp = int(time.time())

    for market in markets:
        for pair in market.top_pairs:
            cursor.execute('''
                INSERT OR REPLACE INTO market_snapshots
                (timestamp, symbol, price, volume_24h)
                VALUES (?, ?, ?, ?)
            ''', (timestamp, pair.symbol, pair.price, pair.volume))

    conn.commit()
    conn.close()

# Add to crontab: */5 * * * * (every 5 minutes)
```

**Then query from database in dashboard:**
```python
def fetch_historical_from_db(symbols, hours=12):
    """Fetch historical data from local database (FAST!)"""
    conn = sqlite3.connect('data/market_history.db')
    cursor = conn.cursor()

    cutoff = int(time.time()) - (hours * 3600)

    results = {}
    for symbol in symbols:
        cursor.execute('''
            SELECT timestamp, price
            FROM market_snapshots
            WHERE symbol = ? AND timestamp > ?
            ORDER BY timestamp
        ''', (symbol, cutoff))

        results[symbol] = cursor.fetchall()

    conn.close()
    return results
```

---

### 4. **Advanced Optimizations (8+ hours)**

#### A. Implement Client-Side Callbacks

Move simple state management to JavaScript (no server roundtrip):

```python
# Example: Toggle visibility without server callback
app.clientside_callback(
    """
    function(n_clicks) {
        return n_clicks % 2 === 0 ? 'block' : 'none';
    }
    """,
    Output('some-div', 'style'),
    Input('toggle-button', 'n_clicks'),
    prevent_initial_call=True
)
```

#### B. Progressive Data Loading

Load basic data first, then enrich:

```python
# Phase 1: Load basic stats (fast)
@app.callback(Output('quick-stats', 'children'), ...)
def load_quick_stats(n):
    return get_cached_summary()  # Very fast

# Phase 2: Load detailed charts (slower)
@app.callback(Output('detailed-charts', 'children'), ..., background=True)
def load_detailed_data(n):
    return generate_expensive_charts()  # Can take longer
```

#### C. Use Background Callbacks (Dash 2.6+)

```python
from dash import DiskcacheManager
import diskcache

cache = diskcache.Cache("./cache")
background_callback_manager = DiskcacheManager(cache)

app = Dash(__name__, background_callback_manager=background_callback_manager)

@app.callback(
    output=Output("paragraph_id", "children"),
    inputs=Input("button_id", "n_clicks"),
    background=True,  # Runs in background!
    running=[
        (Output("button_id", "disabled"), True, False),
    ],
    progress=[Output("progress_bar", "value"), Output("progress_bar", "max")],
)
def update_progress(set_progress, n_clicks):
    # Long-running operation
    for i in range(100):
        set_progress((str(i+1), "100"))
        time.sleep(0.1)
    return f"Processed {n_clicks} clicks"
```

#### D. Pre-Warm Cache on Startup

```python
# In app.py, after container initialization
def prewarm_cache():
    """Pre-populate cache on startup"""
    print("🔥 Pre-warming cache...")
    try:
        # Trigger cache population
        get_symbol_analytics(container, top_n=10)
        print("✅ Cache pre-warmed")
    except Exception as e:
        print(f"⚠️  Cache pre-warm failed: {e}")

# Call before app.run()
if __name__ == '__main__':
    prewarm_cache()
    app.run(...)
```

---

## Implementation Priority

### Phase 1: Quick Wins (Do First)
1. ✅ Increase cache TTLs (120s analytics, 600s charts)
2. ✅ Increase auto-refresh to 120s
3. ✅ Disable debug mode in production
4. ✅ Reduce top_n from 15→10
5. ✅ Add loading spinners

### Phase 2: Medium Impact
1. ⚠️ Use Gunicorn with 4 workers
2. ⚠️ Reduce chart complexity (fewer symbols)
3. ⚠️ Ensure use_cache=True everywhere

### Phase 3: High Impact
1. 🔴 Implement Redis caching
2. 🔴 Add database for historical data
3. 🔴 Create historical data logger cron job

### Phase 4: Advanced
1. 🔵 Client-side callbacks for UI interactions
2. 🔵 Background callbacks for long operations
3. 🔵 Progressive loading strategy

---

## Expected Performance Improvements

| Optimization | Initial Load Time | Subsequent Loads | API Calls | Memory Usage |
|--------------|-------------------|------------------|-----------|--------------|
| **Before** | ~8-12s | ~5-8s | High | Moderate |
| **Phase 1** | ~6-8s | ~3-5s | 50% less | Same |
| **Phase 2** | ~4-6s | ~2-3s | 70% less | +20% |
| **Phase 3** | ~3-5s | ~1-2s | 90% less | +30% |
| **Phase 4** | ~2-3s | <1s | 95% less | +40% |

---

## Monitoring & Metrics

Add performance tracking:

```python
import time
from functools import wraps

def timing_decorator(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        duration = time.time() - start
        print(f"⏱️  {func.__name__}: {duration:.2f}s")
        return result
    return wrapper

# Apply to callbacks
@app.callback(...)
@timing_decorator
def update_tab_content(...):
    ...
```

Add Dash Dev Tools (development only):
```python
app = dash.Dash(__name__, dev_tools_ui=True, dev_tools_props_check=False)
```

---

## Production Deployment

### Run with Gunicorn:
```bash
# Create gunicorn config
cat > gunicorn_config.py <<EOF
workers = 4
bind = "0.0.0.0:8050"
timeout = 120
worker_class = "sync"
max_requests = 1000
max_requests_jitter = 50
preload_app = True
EOF

# Run
gunicorn -c gunicorn_config.py dashboard.app:server
```

### Systemd Service:
```bash
sudo tee /etc/systemd/system/crypto-dashboard.service <<EOF
[Unit]
Description=Crypto Perps Dashboard
After=network.target

[Service]
Type=notify
User=$USER
WorkingDirectory=/home/$USER/crypto-perps-tracker
Environment="PATH=/home/$USER/crypto-perps-tracker/venv/bin"
ExecStart=/home/$USER/crypto-perps-tracker/venv/bin/gunicorn -c gunicorn_config.py dashboard.app:server
Restart=always

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable crypto-dashboard
sudo systemctl start crypto-dashboard
```

---

## Configuration File

Create `dashboard/config.py`:
```python
import os

class DashboardConfig:
    # Cache settings
    CACHE_TYPE = os.getenv('CACHE_TYPE', 'SimpleCache')
    CACHE_REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    CACHE_DEFAULT_TIMEOUT = int(os.getenv('CACHE_TIMEOUT', '120'))

    # Data settings
    SYMBOL_ANALYTICS_TTL = int(os.getenv('SYMBOL_TTL', '120'))
    PERFORMANCE_CHART_TTL = int(os.getenv('PERFORMANCE_TTL', '600'))
    AUTO_REFRESH_INTERVAL = int(os.getenv('REFRESH_INTERVAL', '120'))

    # Display settings
    TOP_SYMBOLS_COUNT = int(os.getenv('TOP_SYMBOLS', '10'))
    CHART_SYMBOL_LIMIT = int(os.getenv('CHART_SYMBOLS', '20'))

    # Server settings
    DEBUG = os.getenv('DASH_DEBUG', 'false').lower() == 'true'
    HOST = os.getenv('DASH_HOST', '0.0.0.0')
    PORT = int(os.getenv('DASH_PORT', '8050'))
```

---

## Next Steps

1. **Review this document** with your team
2. **Implement Phase 1** optimizations first (< 1 hour)
3. **Test performance** improvements
4. **Deploy to production** with Gunicorn
5. **Monitor metrics** and iterate

Would you like me to implement any of these optimizations now?
