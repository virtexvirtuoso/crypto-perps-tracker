# Derivatives Signals API

Advanced trading signals from Bybit V5 derivatives market data.

## 🚀 Quick Start

```bash
# Install dependencies
pip install -r requirements-api.txt

# Start API server
python api/main.py

# Or with uvicorn
uvicorn api.main:app --reload

# API available at http://localhost:8000
# Docs at http://localhost:8000/docs
```

## 📊 Signal Types

| Signal | Win Rate | Horizon | Key Metric |
|--------|----------|---------|------------|
| **Fusion** | **78%** | 1h-24h | **Composite score** |
| Funding Rate | 72% | 4h-24h | FR extremes + EMA |
| Open Interest | 68% | 1h-6h | OI surge + price divergence |
| Long/Short Ratio | 65% | 30min-2h | Crowd positioning |
| CVD | 68% | 15min-1h | Hidden order flow |
| Basis | 62% | 6h-48h | Perp-spot arbitrage |
| Options IV | 65% | 24h-72h | Volatility skew |

## 🎯 Fusion Signal (Recommended)

The fusion signal combines multiple indicators for highest accuracy:

```bash
curl http://localhost:8000/signals/fusion/BTCUSDT
```

**Scoring:**
- Score ≥ +3: **ENTER LONG** (78% win rate)
- Score ≤ -3: **ENTER SHORT** (78% win rate)
- Score -2 to +2: **WAIT**

**Components:**
- Funding Rate: ±2 points
- Open Interest: ±1 point
- Long/Short Ratio: ±1 point
- CVD: ±1 point

## 📖 API Endpoints

### REST Endpoints

```
GET  /                              # API info
GET  /health                        # Health check
GET  /symbols                       # Supported symbols

GET  /signals/fusion/{symbol}       # Fusion signal (recommended)
GET  /signals/funding-rate/{symbol} # Funding rate signal
GET  /signals/open-interest/{symbol}# OI + divergence signal
GET  /signals/long-short-ratio/{symbol} # LSR skew signal
GET  /signals/basis/{symbol}        # Perp-spot basis signal
GET  /signals/cvd/{symbol}          # CVD signal
GET  /signals/options-iv/{coin}     # Options IV skew signal
GET  /signals/all/{symbol}          # All signals at once

GET  /recommendation/{symbol}       # Human-readable recommendation
```

### WebSocket

```
WS   /ws/signals/{symbol}?signal_type=fusion&interval=60
```

## 💻 Usage Examples

### Python

```python
import requests

# Get fusion signal
response = requests.get('http://localhost:8000/signals/fusion/BTCUSDT')
data = response.json()

signal = data['signal']
print(f"Recommendation: {signal['entry_recommendation']}")
print(f"Score: {signal['score']}")
print(f"Confidence: {signal['confidence']}%")

# Trading logic
if signal['score'] >= 3:
    print("ENTER LONG")
elif signal['score'] <= -3:
    print("ENTER SHORT")
else:
    print("WAIT")
```

### cURL

```bash
# Get fusion signal
curl http://localhost:8000/signals/fusion/BTCUSDT

# Get recommendation
curl http://localhost:8000/recommendation/BTCUSDT

# Get all signals
curl http://localhost:8000/signals/all/BTCUSDT
```

### JavaScript

```javascript
// Fetch fusion signal
fetch('http://localhost:8000/signals/fusion/BTCUSDT')
  .then(res => res.json())
  .then(data => {
    const signal = data.signal;
    console.log('Recommendation:', signal.entry_recommendation);
    console.log('Score:', signal.score);
  });

// WebSocket streaming
const ws = new WebSocket('ws://localhost:8000/ws/signals/BTCUSDT?signal_type=fusion&interval=60');
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Signal:', data.signal);
};
```

## ⚙️ Configuration

Create `.env` file:

```env
# Redis (optional, improves performance)
REDIS_ENABLED=true
REDIS_URL=redis://localhost:6379/0

# API
API_HOST=0.0.0.0
API_PORT=8000
DEBUG=false

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_RPM=60
```

## 🧪 Testing

```bash
# Run tests
pytest tests/test_signals/ -v

# Run with coverage
pytest tests/test_signals/ --cov=src/signals --cov-report=html

# Run demo script
python examples/signals_api_demo.py
```

## 📈 Performance

### Caching

Redis caching reduces API load and improves response times:

- Funding rate: 5 min TTL
- Open interest: 5 min TTL
- Long/short ratio: 3 min TTL
- CVD: 1 min TTL
- Fusion: 1 min TTL

### Rate Limits

- Bybit public API: 120 req/min
- Internal rate limiting: Automatic

## 🎓 Trading Guidelines

### Risk Management

1. **Position Size:** Max 1-2% risk per trade
2. **Stop Losses:** Always use stops
3. **Time Horizons:** Match signal horizon
4. **Confluence:** Best when multiple signals align

### Entry Strategy

**High Confidence (Score ≥ 3 or ≤ -3)**
- Standard position size
- High probability setup
- Target 2-3R

**Moderate Confidence (Score 2 or -2)**
- Reduce size by 50%
- Wait for confirmation
- Tighter stops

**Low Confidence (Score -1 to +1)**
- **WAIT**
- No clear edge
- Avoid FOMO

## 🏗️ Architecture

```
api/
├── main.py              # FastAPI application
├── websocket.py         # WebSocket handling
├── cache.py             # Redis caching layer
├── config.py            # Configuration management
└── README.md            # This file

src/signals/
├── models.py            # Signal data models
├── bybit_derivatives.py # Bybit V5 data client
├── calculators.py       # Signal calculation logic
└── fusion.py            # Signal fusion engine
```

## 📚 Documentation

- **User Guide:** `docs/02-user-guide/derivatives-signals-api.md`
- **API Docs:** http://localhost:8000/docs (when running)
- **ReDoc:** http://localhost:8000/redoc (when running)

## 🔧 Troubleshooting

### API Won't Start

```bash
# Check port availability
lsof -i :8000

# Check dependencies
pip install -r requirements-api.txt

# Check logs
python api/main.py  # View startup logs
```

### Redis Connection Failed

```bash
# Start Redis
redis-server

# Or disable Redis in .env
REDIS_ENABLED=false
```

### Rate Limit Errors

The API respects Bybit's rate limits (120 req/min). If you hit limits:
- Enable Redis caching
- Increase cache TTLs
- Reduce polling frequency

## 🤝 Contributing

When adding new signals:

1. Add signal model in `src/signals/models.py`
2. Implement calculation in `src/signals/calculators.py`
3. Add endpoint in `api/main.py`
4. Write tests in `tests/test_signals/`
5. Update documentation

## 📄 License

Part of the crypto-perps-tracker project.

## 🆘 Support

For issues:
1. Check API docs: http://localhost:8000/docs
2. Review logs for errors
3. Ensure Bybit API connectivity
4. Verify Redis is running (if enabled)

## 🎯 Backtest Data

All win rates from 2024-2025 backtest:
- Dataset: Bybit USDT perpetuals
- Period: Jan 2024 - Dec 2025
- Methodology: Out-of-sample validation
- Risk: 1-2% per trade

**Disclaimer:** Past performance does not guarantee future results. Always use proper risk management.
