#!/usr/bin/env python3
"""
Comprehensive unit tests for normalize_symbol() function
Tests all 37 normalization scenarios including PF prefix fixes
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from scripts.generate_symbol_report import normalize_symbol

def test_normalize_symbol():
    """Test all normalization scenarios"""
    
    test_cases = [
        # Fix #1: Kraken PF without underscore (PRIMARY FIX)
        ("PFSOL", "SOL", "Kraken PF prefix without underscore - SOL"),
        ("PFXRP", "XRP", "Kraken PF prefix without underscore - XRP"),
        ("PFADA", "ADA", "Kraken PF prefix without underscore - ADA"),
        ("PFSUI", "SUI", "Kraken PF prefix without underscore - SUI"),
        ("PFAVAX", "AVAX", "Kraken PF prefix without underscore - AVAX"),
        ("PFBTC", "BTC", "Kraken PF prefix without underscore - BTC"),
        
        # Kraken PF with underscore (existing functionality)
        ("PF_SOLUSD", "SOL", "Kraken PF_ prefix with USD"),
        ("PF_XRPUSD", "XRP", "Kraken PF_ prefix with USD"),
        ("PF_BTCUSD", "BTC", "Kraken PF_ prefix with USD"),
        
        # Kraken PI without underscore
        ("PISOL", "SOL", "Kraken PI prefix without underscore - SOL"),
        ("PIXRP", "XRP", "Kraken PI prefix without underscore - XRP"),
        ("PIBTC", "BTC", "Kraken PI prefix without underscore - BTC"),
        
        # Kraken PI with underscore (existing functionality)
        ("PI_XBTUSD", "BTC", "Kraken PI_ prefix with XBT"),
        ("PI_ETHUSD", "ETH", "Kraken PI_ prefix with ETH"),
        
        # Fix #2: Stablecoin normalization
        ("USDCUSDT", "USDC", "Stablecoin USDCUSDT -> USDC"),
        ("TUSDUSDT", "TUSD", "Stablecoin TUSDUSDT -> TUSD"),
        ("DAIUSDT", "DAI", "Stablecoin DAIUSDT -> DAI"),
        ("USDTUSDC", "USDT", "Stablecoin USDTUSDC -> USDT"),
        
        # Fix #3: KuCoin M suffix
        ("XBTUSDTM", "BTC", "KuCoin XBTUSDTM -> BTC"),
        ("ETHUSDTM", "ETH", "KuCoin ETHUSDTM -> ETH"),
        ("SOLUSDTM", "SOL", "KuCoin SOLUSDTM -> SOL"),
        ("BTCUSDCM", "BTC", "KuCoin BTCUSDCM -> BTC"),
        ("ETHUSDM", "ETH", "KuCoin ETHUSDM -> ETH"),
        
        # Regression tests: Standard formats
        ("BTCUSDT", "BTC", "Standard Binance format"),
        ("ETHUSDT", "ETH", "Standard Binance format"),
        ("SOLUSDT", "SOL", "Standard Binance format"),
        ("XRPUSDT", "XRP", "Standard Binance format"),
        
        # Regression tests: OKX format
        ("BTC-USDT-SWAP", "BTC", "OKX SWAP format"),
        ("ETH-USDT-SWAP", "ETH", "OKX SWAP format"),
        
        # Regression tests: Coinbase INTX format
        ("BTC-PERP", "BTC", "Coinbase INTX PERP format"),
        ("ETH-PERP", "ETH", "Coinbase INTX PERP format"),
        
        # Regression tests: Gate.io format
        ("BTC_USDT", "BTC", "Gate.io underscore format"),
        ("ETH_USDT", "ETH", "Gate.io underscore format"),
        
        # Regression tests: Bitget format
        ("BTCUSDT_UMCBL", "BTC", "Bitget UMCBL format"),
        ("ETHUSDT_UMCBL", "ETH", "Bitget UMCBL format"),
    ]
    
    passed = 0
    failed = 0
    failures = []
    
    print("\n" + "="*80)
    print("NORMALIZE_SYMBOL() COMPREHENSIVE TEST SUITE")
    print("="*80)
    print(f"Testing {len(test_cases)} normalization scenarios...\n")
    
    for input_symbol, expected, description in test_cases:
        result = normalize_symbol(input_symbol)
        status = "PASS" if result == expected else "FAIL"
        
        if result == expected:
            passed += 1
            print(f"✓ {status}: {description}")
            print(f"  Input: {input_symbol:20s} -> Output: {result:10s} (Expected: {expected})")
        else:
            failed += 1
            failures.append((input_symbol, expected, result, description))
            print(f"✗ {status}: {description}")
            print(f"  Input: {input_symbol:20s} -> Output: {result:10s} (Expected: {expected})")
    
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"Total Tests: {len(test_cases)}")
    print(f"Passed: {passed} ({passed/len(test_cases)*100:.1f}%)")
    print(f"Failed: {failed} ({failed/len(test_cases)*100:.1f}%)")
    
    if failures:
        print("\n" + "="*80)
        print("FAILED TESTS DETAILS")
        print("="*80)
        for input_sym, expected, actual, desc in failures:
            print(f"\nTest: {desc}")
            print(f"  Input:    {input_sym}")
            print(f"  Expected: {expected}")
            print(f"  Actual:   {actual}")
    
    print("\n" + "="*80)
    
    return failed == 0

if __name__ == "__main__":
    success = test_normalize_symbol()
    sys.exit(0 if success else 1)
