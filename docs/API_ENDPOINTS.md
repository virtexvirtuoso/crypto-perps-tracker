# API Endpoints Reference

Complete reference for all API endpoints used by Crypto Perps Tracker.

---

## Centralized Exchanges (CEX)

### 1. Binance
**Base URL:** `https://fapi.binance.com`

| Endpoint | Purpose | Rate Limit |
|----------|---------|------------|
| `/fapi/v1/ticker/24hr` | Get 24h ticker data for all perpetuals | 2400/min |
| `/fapi/v1/openInterest?symbol={symbol}` | Get open interest for specific symbol | 1200/min |
| `/fapi/v1/premiumIndex?symbol={symbol}` | Get funding rate and mark price | 1200/min |

**Documentation:** https://developers.binance.com/docs/derivatives/usds-margined-futures

---

### 2. Bybit
**Base URL:** `https://api.bybit.com`

| Endpoint | Purpose | Rate Limit |
|----------|---------|------------|
| `/v5/market/tickers?category=linear` | Get all linear perpetual tickers | 600/min |
| `/v5/market/open-interest?category=linear&symbol={symbol}` | Get open interest | 600/min |
| `/v5/market/funding/history?category=linear&symbol={symbol}` | Get funding rate history | 600/min |

**Documentation:** https://bybit-exchange.github.io/docs/v5/intro

---

### 3. OKX
**Base URL:** `https://www.okx.com/api/v5`

| Endpoint | Purpose | Rate Limit |
|----------|---------|------------|
| `/market/tickers?instType=SWAP` | Get all perpetual swap tickers | 300/min |
| `/public/funding-rate?instId={symbol}` | Get funding rate | 300/min |

**Documentation:** https://www.okx.com/docs-v5/en/

---

### 4. Bitget
**Base URL:** `https://api.bitget.com`

| Endpoint | Purpose | Rate Limit |
|----------|---------|------------|
| `/api/mix/v1/market/tickers?productType=umcbl` | Get USDT-M perpetual tickers | 600/min |
| `/api/v2/mix/market/open-interest?symbol={symbol}&productType=usdt-futures` | Get open interest | 600/min |

**Documentation:** https://www.bitget.com/api-doc/contract/intro

---

### 5. Gate.io
**Base URL:** `https://api.gateio.ws/api/v4`

| Endpoint | Purpose | Rate Limit |
|----------|---------|------------|
| `/futures/usdt/tickers` | Get all USDT perpetual tickers | 900/min |

**Documentation:** https://www.gate.io/docs/developers/apiv4/en/

---

## Decentralized Exchanges (DEX)

### 6. HyperLiquid
**Base URL:** `https://api.hyperliquid.xyz`

| Endpoint | Purpose | Rate Limit |
|----------|---------|------------|
| POST `/info` with `{"type":"metaAndAssetCtxs"}` | Get all market data including OI, funding | No limit |

**Documentation:** https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api

---

### 7. AsterDEX
**Base URL:** `https://fapi.asterdex.com`

| Endpoint | Purpose | Rate Limit |
|----------|---------|------------|
| `/fapi/v1/ticker/24hr` | Get 24h ticker data for all perpetuals | 1200/min |

**Documentation:** https://github.com/asterdex/api-docs

---

### 8. dYdX v4
**Base URL:** `https://indexer.dydx.trade`

| Endpoint | Purpose | Rate Limit |
|----------|---------|------------|
| `/v4/perpetualMarkets` | Get all perpetual markets data | No limit |

**Documentation:** https://docs.dydx.trade/developers/indexer/indexer_api

---

## Response Formats

### Common Fields Across Exchanges

| Field | Description | Example |
|-------|-------------|---------|
| `symbol` / `contract` | Trading pair identifier | "BTCUSDT", "BTC_USDT" |
| `last` / `lastPrice` | Last traded price | 108000.00 |
| `volume24h` / `quoteVolume` | 24h volume in USD | 22000000000 |
| `priceChangePercent` / `change_percentage` | 24h price change % | -3.82 |
| `fundingRate` | Current funding rate | 0.000044 |
| `openInterest` / `total_size` | Open interest | 25000.00 |

---

## Rate Limiting Best Practices

1. **Respect Rate Limits:** Never exceed documented limits
2. **Use Delays:** Add 1-2 second delays between requests
3. **Parallel Requests:** Fetch different exchanges in parallel
4. **Error Handling:** Implement exponential backoff for failures
5. **Cache Data:** Don't re-fetch data more often than necessary

---

## Error Handling

### Common HTTP Status Codes

| Code | Meaning | Action |
|------|---------|--------|
| 200 | Success | Process response |
| 403 | Forbidden | Check IP/location restrictions |
| 429 | Rate Limited | Wait and retry with exponential backoff |
| 500 | Server Error | Retry after delay |
| 503 | Service Unavailable | Exchange maintenance, retry later |

---

## Notes

- **No Authentication Required:** All endpoints used are public
- **Geo-Restrictions:** Some exchanges block certain countries (run from VPS if needed)
- **Data Freshness:** Most endpoints provide real-time data (<1 second delay)
- **Consistency:** Field names vary across exchanges, normalization required

---

**Last Updated:** October 2025
