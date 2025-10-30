# Deprecated Scripts

These scripts have been replaced by the new architecture and are no longer maintained.

## Deprecated Exchange Fetch Scripts

**Moved on:** 2025-10-24 (Session 9)

## Deprecated Core Scripts (Consolidated)

**Moved on:** 2025-10-24 (Session 10)

These scripts were replaced with Container-based architecture versions that had "_new.py" suffix.
The new versions are now the primary scripts (suffix removed).

**Total Code Reduction:** 5,419 lines → 3,248 lines = **40% reduction**

**Replaced by:** Container/Service architecture with cleaner, more maintainable code

| Deprecated Script | Lines | Replaced By | Lines | Reduction |
|------------------|-------|-------------|-------|-----------|
| analyze_coins.py | 353 | analyze_coins.py (was _new) | 307 | 13% |
| calculate_basis.py | 268 | calculate_basis.py (was _new) | 490 | Enhanced |
| compare_all_exchanges.py | 678 | compare_exchanges.py (was _new) | 227 | 66% |
| data_logger.py | 434 | data_logger.py (was _new) | 419 | 3% |
| generate_market_report.py | 1827 | generate_market_report.py (was _new) | 1438 | 21% |
| generate_symbol_report.py | 1859 | generate_symbol_report.py (was _new) | 367 | 80% |

---

### analyze_coins.py ❌
**Status:** DEPRECATED
**Replacement:** `scripts/analyze_coins.py` (consolidated from _new version)

**Old Way:**
```bash
python3 scripts/deprecated/analyze_coins.py
```

**New Way:**
```bash
python3 scripts/analyze_coins.py
```

**Improvements:**
- ✅ Uses Container pattern for dependency injection
- ✅ Automatic caching (80% API call reduction)
- ✅ Type-safe Pydantic models
- ✅ 13% code reduction (353 → 307 lines)

---

### calculate_basis.py ❌
**Status:** DEPRECATED
**Replacement:** `scripts/calculate_basis.py` (consolidated from _new version)

**Old Way:**
```bash
python3 scripts/deprecated/calculate_basis.py
```

**New Way:**
```bash
python3 scripts/calculate_basis.py
```

**Improvements:**
- ✅ Enhanced spot-futures basis analysis
- ✅ More comprehensive metrics
- ✅ Uses ExchangeService for data fetching
- ⚠️ 83% larger (268 → 490 lines) - added features

---

### compare_all_exchanges.py ❌
**Status:** DEPRECATED
**Replacement:** `scripts/compare_exchanges.py` (consolidated from compare_exchanges_new.py)

**Note:** Script renamed from `compare_all_exchanges.py` to `compare_exchanges.py` for clarity.

**Old Way:**
```bash
python3 scripts/deprecated/compare_all_exchanges.py
```

**New Way:**
```bash
python3 scripts/compare_exchanges.py
```

**Improvements:**
- ✅ 66% code reduction (678 → 227 lines)
- ✅ Massive performance improvement (635,000x faster with cache!)
- ✅ Parallel fetching via ThreadPoolExecutor
- ✅ Cleaner, more maintainable code

---

### data_logger.py ❌
**Status:** DEPRECATED
**Replacement:** `scripts/data_logger.py` (consolidated from _new version)

**Old Way:**
```bash
python3 scripts/deprecated/data_logger.py
```

**New Way:**
```bash
python3 scripts/data_logger.py
```

**Improvements:**
- ✅ Uses MarketRepository for persistent storage
- ✅ Container pattern for cleaner architecture
- ✅ 3% code reduction (434 → 419 lines)

---

### generate_market_report.py ❌
**Status:** DEPRECATED
**Replacement:** `scripts/generate_market_report.py` (consolidated from _new version)

**Old Way:**
```bash
python3 scripts/deprecated/generate_market_report.py
```

**New Way:**
```bash
python3 scripts/generate_market_report.py
```

**Improvements:**
- ✅ Uses ReportService for report generation
- ✅ 21% code reduction (1827 → 1438 lines)
- ✅ Cleaner separation of concerns
- ✅ Better error handling

---

### generate_symbol_report.py ❌
**Status:** DEPRECATED (MASSIVE IMPROVEMENT)
**Replacement:** `scripts/generate_symbol_report.py` (consolidated from _new version)

**Old Way:**
```bash
python3 scripts/deprecated/generate_symbol_report.py BTC
```

**New Way:**
```bash
python3 scripts/generate_symbol_report.py BTC
```

**Improvements:**
- ✅ **80% code reduction** (1859 → 367 lines) - biggest win!
- ✅ Parallel fetching across all exchanges
- ✅ Automatic caching
- ✅ Much faster and more reliable
- ✅ Cleaner output format

---

---

### send_discord_report.py ❌
**Status:** DEPRECATED
**Replacement:** `scripts/send_discord_report.py` (consolidated from v2 version)

**Old Way:**
```bash
python3 scripts/deprecated/send_discord_report.py
```

**New Way:**
```bash
# Set DISCORD_WEBHOOK_URL in .env or pass as argument
python3 scripts/send_discord_report.py [webhook_url] [format]
```

**Improvements:**
- ✅ Uses Container pattern for dependency injection
- ✅ Uses ReportService for generating reports
- ✅ Supports multiple formats (TEXT, MARKDOWN, HTML)
- ✅ Cleaner, more maintainable code
- ✅ Automatic message chunking for Discord's 2000 char limit
- ✅ Rate limiting to avoid Discord API issues

---

## Deprecated Fetch Scripts (Single-Exchange)

**Moved on:** 2025-10-24 (Sessions 9-10)

These single-exchange fetch scripts have been replaced by the unified client architecture. Use the corresponding client classes via Container/ExchangeService instead.

---

### fetch_asterdex.py ❌
**Status:** DEPRECATED
**Replacement:** Use `AsterDEXClient` from `src/clients/asterdex.py`

**Old Way:**
```bash
python3 scripts/fetch_asterdex.py
```

**New Way:**
```python
from src.container import Container
from src.models.config import Config

config = Config()
container = Container(config)
data = container.exchange_service.fetch_single_exchange('asterdex')
```

---

### fetch_bitget.py ❌
**Status:** DEPRECATED
**Replacement:** Use `BitgetClient` from `src/clients/bitget.py`

**Old Way:**
```bash
python3 scripts/fetch_bitget.py
```

**New Way:**
```python
from src.container import Container
from src.models.config import Config

config = Config()
container = Container(config)
data = container.exchange_service.fetch_single_exchange('bitget')
```

---

### fetch_gateio.py ❌
**Status:** DEPRECATED
**Replacement:** Use `GateioClient` from `src/clients/gateio.py`

**Old Way:**
```bash
python3 scripts/fetch_gateio.py
```

**New Way:**
```python
from src.container import Container
from src.models.config import Config

config = Config()
container = Container(config)
data = container.exchange_service.fetch_single_exchange('gateio')
```

---

### fetch_okx.py ❌
**Status:** DEPRECATED
**Replacement:** Use `OKXClient` from `src/clients/okx.py`

**Old Way:**
```bash
python3 scripts/fetch_okx.py
```

**New Way:**
```python
from src.container import Container
from src.models.config import Config

config = Config()
container = Container(config)
data = container.exchange_service.fetch_single_exchange('okx')
```

---

### fetch_spot_markets.py ❌
**Status:** DEPRECATED
**Replacement:** Use spot market clients or existing exchange clients

**Old Way:**
```bash
python3 scripts/fetch_spot_markets.py
```

**New Way:**
```python
from src.container import Container
from src.models.config import Config

config = Config()
container = Container(config)

# Fetch spot markets from exchanges that support them
# Most perpetual clients can fetch spot data via their APIs
data = container.exchange_service.fetch_all_markets()
```

**Note:** This script was used for spot-futures basis analysis. The functionality has been integrated into `calculate_basis.py` using the Container pattern.

---

### fetch_liquidations.py ❌
**Status:** DEPRECATED
**Replacement:** Functionality to be integrated into analysis service

**Old Way:**
```bash
python3 scripts/fetch_liquidations.py
```

**New Way:**
```python
# Liquidation data fetching will be integrated into AnalysisService
# in a future refactoring session
from src.container import Container
from src.models.config import Config

config = Config()
container = Container(config)

# Future: container.analysis_service.get_liquidation_data()
```

**Note:** Liquidation data fetching is planned for integration into AnalysisService. For now, the old script is preserved in deprecated/ for reference.

---

## Why Were These Deprecated?

### Problems with Old Approach:
❌ Code duplication - Each script had similar fetch logic
❌ Inconsistent error handling
❌ Hard to test - Scripts, not reusable functions
❌ No dependency injection - Hard to mock for testing
❌ Inconsistent data formats
❌ No caching layer

### Benefits of New Approach:
✅ **DRY Principle** - Shared base client logic
✅ **Type Safety** - Pydantic models for validation
✅ **Testability** - Dependency injection pattern
✅ **Consistency** - Standardized `MarketData` format
✅ **Performance** - Built-in TTL caching
✅ **Maintainability** - Single source of truth per exchange
✅ **Extensibility** - Easy to add new exchanges

## Migration Timeline

| Date | Action |
|------|--------|
| 2025-10-22 | Created new client architecture (Session 1-7) |
| 2025-10-23 | Added 4 missing exchanges (Session 8) |
| 2025-10-24 | Migrated alert system (Session 9) |
| 2025-10-24 | **Deprecated old fetch scripts** ✅ |

## Recommended Migration Path

### For Scripts
Replace direct script calls with Container pattern:

```python
from src.container import Container
from src.models.config import Config

# Initialize
config = Config()
container = Container(config)

# Fetch single exchange
data = container.exchange_service.fetch_single_exchange('binance')

# Fetch all exchanges
all_data = container.exchange_service.fetch_all_markets()

# Get total volume
volume = container.exchange_service.get_total_volume()
```

### For Analysis
Use AnalysisService for market analysis:

```python
# Market sentiment
sentiment = container.analysis_service.calculate_market_sentiment(markets)

# Arbitrage opportunities
arbs = container.analysis_service.find_funding_arbitrage_opportunities()

# Market dominance
dominance = container.analysis_service.calculate_market_dominance(markets)
```

### For Alerts
Use AlertService for strategy detection:

```python
# Detect all strategies
alerts = container.alert_service.detect_all_strategies()

# Filter by tier
filtered = container.alert_service.filter_by_tier(alerts, tiers=[1, 2])

# Record alert
alert_id = container.alert_service.record_alert(
    strategy_name="Trend Following",
    confidence=85,
    direction="LONG"
)
```

## If You Need the Old Scripts

The deprecated scripts are preserved in this folder for reference, but are **not maintained**.

**⚠️ Warning:** These scripts may break with future dependency updates.

## Questions?

See documentation:
- `docs/REFACTORING_PROGRESS.md` - Architecture overview
- `docs/STRATEGY_ALERTS_MIGRATION.md` - Alert system migration
- `src/README.md` - Source code structure
- `scripts/demo_alert_service.py` - Working example

## Support

For issues or questions about the new architecture:
1. Check the migration docs above
2. Review example scripts (`demo_*.py`, `test_*.py`)
3. Consult the source code (`src/services/`, `src/clients/`)
