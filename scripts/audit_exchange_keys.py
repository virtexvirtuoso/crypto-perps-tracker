#!/usr/bin/env python3
"""
Exchange API Key Auditor
Fetches sample data from each exchange and audits the keys/fields returned
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import requests
from datetime import datetime

def audit_okx():
    """Audit OKX API response"""
    print("\n" + "="*80)
    print("🔍 AUDITING OKX API")
    print("="*80)

    try:
        url = "https://www.okx.com/api/v5/market/tickers?instType=SWAP"
        response = requests.get(url, timeout=10)
        data = response.json()

        if data.get('code') == '0' and data.get('data'):
            sample = data['data'][0]
            print(f"\n✅ Status: SUCCESS")
            print(f"📊 Sample ticker (first result):")
            print(json.dumps(sample, indent=2))

            print(f"\n🔑 Available Keys:")
            for key in sorted(sample.keys()):
                value = sample[key]
                value_type = type(value).__name__
                print(f"   - {key:<20} : {value_type:<10} = {value}")

            # Check for price change field
            price_change_fields = [k for k in sample.keys() if 'change' in k.lower() or 'pct' in k.lower()]
            print(f"\n💹 Price Change Related Fields:")
            for field in price_change_fields:
                print(f"   - {field}: {sample[field]}")

        else:
            print(f"❌ Error: {data}")

    except Exception as e:
        print(f"❌ Exception: {e}")


def audit_binance():
    """Audit Binance API response"""
    print("\n" + "="*80)
    print("🔍 AUDITING BINANCE API")
    print("="*80)

    try:
        url = "https://fapi.binance.com/fapi/v1/ticker/24hr"
        response = requests.get(url, timeout=10)

        if response.status_code == 451:
            print("❌ Binance API blocked (451 Unavailable For Legal Reasons)")
            print("   This is expected in some regions")
            return

        data = response.json()

        if isinstance(data, list) and len(data) > 0:
            sample = data[0]
            print(f"\n✅ Status: SUCCESS")
            print(f"📊 Sample ticker (first result):")
            print(json.dumps(sample, indent=2))

            print(f"\n🔑 Available Keys:")
            for key in sorted(sample.keys()):
                value = sample[key]
                value_type = type(value).__name__
                print(f"   - {key:<25} : {value_type:<10} = {value}")

            # Check for price change field
            price_change_fields = [k for k in sample.keys() if 'change' in k.lower() or 'pct' in k.lower()]
            print(f"\n💹 Price Change Related Fields:")
            for field in price_change_fields:
                print(f"   - {field}: {sample[field]}")

        else:
            print(f"❌ Unexpected response format: {data}")

    except Exception as e:
        print(f"❌ Exception: {e}")


def audit_bybit():
    """Audit Bybit API response"""
    print("\n" + "="*80)
    print("🔍 AUDITING BYBIT API")
    print("="*80)

    try:
        url = "https://api.bybit.com/v5/market/tickers?category=linear"
        response = requests.get(url, timeout=10)
        data = response.json()

        if data.get('retCode') == 0 and data.get('result', {}).get('list'):
            sample = data['result']['list'][0]
            print(f"\n✅ Status: SUCCESS")
            print(f"📊 Sample ticker (first result):")
            print(json.dumps(sample, indent=2))

            print(f"\n🔑 Available Keys:")
            for key in sorted(sample.keys()):
                value = sample[key]
                value_type = type(value).__name__
                print(f"   - {key:<25} : {value_type:<10} = {value}")

            # Check for price change field
            price_change_fields = [k for k in sample.keys() if 'change' in k.lower() or 'pct' in k.lower() or '24h' in k.lower()]
            print(f"\n💹 Price Change Related Fields:")
            for field in price_change_fields:
                print(f"   - {field}: {sample[field]}")

        else:
            print(f"❌ Error: {data}")

    except Exception as e:
        print(f"❌ Exception: {e}")


def audit_kraken():
    """Audit Kraken API response"""
    print("\n" + "="*80)
    print("🔍 AUDITING KRAKEN API")
    print("="*80)

    try:
        url = "https://futures.kraken.com/derivatives/api/v3/tickers"
        response = requests.get(url, timeout=10)
        data = response.json()

        if data.get('result') == 'success' and data.get('tickers'):
            sample = data['tickers'][0]
            print(f"\n✅ Status: SUCCESS")
            print(f"📊 Sample ticker (first result):")
            print(json.dumps(sample, indent=2))

            print(f"\n🔑 Available Keys:")
            for key in sorted(sample.keys()):
                value = sample[key]
                value_type = type(value).__name__
                print(f"   - {key:<25} : {value_type:<10} = {value}")

            # Check for price change field
            price_change_fields = [k for k in sample.keys() if 'change' in k.lower() or 'pct' in k.lower() or '24h' in k.lower()]
            print(f"\n💹 Price Change Related Fields:")
            for field in price_change_fields:
                print(f"   - {field}: {sample[field]}")

        else:
            print(f"❌ Error: {data}")

    except Exception as e:
        print(f"❌ Exception: {e}")


def audit_coinbase():
    """Audit Coinbase API response"""
    print("\n" + "="*80)
    print("🔍 AUDITING COINBASE API")
    print("="*80)

    try:
        url = "https://api.coinbase.com/api/v3/brokerage/products"
        response = requests.get(url, timeout=10)

        if response.status_code == 401:
            print("❌ Coinbase API requires authentication (401 Unauthorized)")
            print("   This exchange may not be accessible without API keys")
            return

        data = response.json()

        if isinstance(data, dict) and 'products' in data:
            sample = data['products'][0]
            print(f"\n✅ Status: SUCCESS")
            print(f"📊 Sample product (first result):")
            print(json.dumps(sample, indent=2))

            print(f"\n🔑 Available Keys:")
            for key in sorted(sample.keys()):
                value = sample[key]
                value_type = type(value).__name__
                print(f"   - {key:<25} : {value_type:<10} = {value}")

        else:
            print(f"❌ Unexpected response: {response.status_code}")

    except Exception as e:
        print(f"❌ Exception: {e}")


def main():
    """Run audit on all exchanges"""
    print(f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                      EXCHANGE API KEY AUDIT TOOL                             ║
║                                                                              ║
║  Purpose: Audit each exchange API to understand:                            ║
║  1. What keys/fields are returned                                           ║
║  2. How price change data is structured                                     ║
║  3. Field naming conventions per exchange                                   ║
╚══════════════════════════════════════════════════════════════════════════════╝

Running audit at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
""")

    # Audit each exchange
    audit_okx()
    audit_binance()
    audit_bybit()
    audit_kraken()
    audit_coinbase()

    print("\n" + "="*80)
    print("✅ AUDIT COMPLETE")
    print("="*80)
    print("\nNext Steps:")
    print("1. Review the price change field names for each exchange")
    print("2. Update src/services/exchange.py mappings if needed")
    print("3. Ensure proper null handling for missing fields")
    print("="*80 + "\n")


if __name__ == '__main__':
    main()
