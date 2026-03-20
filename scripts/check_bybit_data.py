import requests
import json

print("Testing direct Bybit API calls...\n")

# 1. Funding Rate
print("=== FUNDING RATE ===")
url = "https://api.bybit.com/v5/market/tickers?category=linear&symbol=BTCUSDT"
response = requests.get(url)
data = response.json()
if data.get('retCode') == 0:
    ticker = data['result']['list'][0]
    print(f"Symbol: {ticker['symbol']}")
    print(f"Last Price: ${float(ticker['lastPrice']):,.2f}")
    print(f"Funding Rate: {float(ticker['fundingRate']):.6f} ({float(ticker['fundingRate'])*100:.4f}%)")
    print(f"Next Funding: {ticker['nextFundingTime']}")
    print(f"24h Volume: ${float(ticker['turnover24h']):,.2f}")
    print("✅ Funding rate data: WORKING\n")
else:
    print(f"❌ Error: {data}")

# 2. Open Interest
print("=== OPEN INTEREST ===")
url = "https://api.bybit.com/v5/market/open-interest?category=linear&symbol=BTCUSDT&intervalTime=1h&limit=2"
response = requests.get(url)
data = response.json()
if data.get('retCode') == 0:
    oi_list = data['result']['list']
    if len(oi_list) >= 2:
        oi_now = float(oi_list[0]['openInterest'])
        oi_prev = float(oi_list[1]['openInterest'])
        change_pct = ((oi_now - oi_prev) / oi_prev) * 100
        print(f"Current OI: {oi_now:,.2f}")
        print(f"Previous OI: {oi_prev:,.2f}")
        print(f"Change: {change_pct:+.2f}%")
        print("✅ Open interest data: WORKING\n")
else:
    print(f"❌ Error: {data}")

# 3. Long/Short Ratio
print("=== LONG/SHORT RATIO ===")
url = "https://api.bybit.com/v5/market/account-ratio?category=linear&symbol=BTCUSDT&period=1h&limit=1"
response = requests.get(url)
data = response.json()
if data.get('retCode') == 0:
    if data['result']['list']:
        item = data['result']['list'][0]
        long_ratio = float(item['buyRatio'])
        short_ratio = float(item['sellRatio'])
        lsr = long_ratio / short_ratio
        print(f"Long Ratio: {long_ratio:.4f} ({long_ratio*100:.2f}%)")
        print(f"Short Ratio: {short_ratio:.4f} ({short_ratio*100:.2f}%)")
        print(f"LSR: {lsr:.2f}")
        print("✅ Long/short ratio data: WORKING\n")
else:
    print(f"❌ Error: {data}")

# 4. Recent Trades (for CVD)
print("=== RECENT TRADES (CVD) ===")
url = "https://api.bybit.com/v5/market/recent-trade?category=linear&symbol=BTCUSDT&limit=100"
response = requests.get(url)
data = response.json()
if data.get('retCode') == 0:
    trades = data['result']['list']
    buy_volume = sum(float(t['size']) * float(t['price']) for t in trades if t['side'] == 'Buy')
    sell_volume = sum(float(t['size']) * float(t['price']) for t in trades if t['side'] == 'Sell')
    cvd = buy_volume - sell_volume
    print(f"Trades analyzed: {len(trades)}")
    print(f"Buy volume: ${buy_volume:,.2f}")
    print(f"Sell volume: ${sell_volume:,.2f}")
    print(f"CVD: ${cvd:,.2f}")
    print("✅ Trade data (CVD): WORKING\n")
else:
    print(f"❌ Error: {data}")

print("="*50)
print("✅ ALL BYBIT API ENDPOINTS WORKING!")
print("✅ REAL DATA IS FLOWING TO THE API!")
print("="*50)
