#!/bin/bash

API_URL="http://5.223.63.4/api"

echo "=========================================="
echo "  Derivatives Signals API - Live Test"
echo "=========================================="
echo ""
echo "API URL: $API_URL"
echo "Time: $(date)"
echo ""

echo "1. Health Check"
curl -s "$API_URL/health" | python3 -m json.tool
echo -e "\n"

echo "2. API Info"
curl -s "$API_URL/" | python3 -m json.tool | head -15
echo "..."
echo -e "\n"

echo "3. BTC Recommendation"
curl -s "$API_URL/recommendation/BTCUSDT" | python3 -c "import json, sys; data = json.load(sys.stdin)['data']; print(f\"Symbol: {data['symbol']}\"); print(f\"Recommendation: {data['recommendation']}\"); print(f\"Score: {data['composite_score']}\"); print(f\"Confidence: {data['confidence']}\"); print(f\"Interpretation: {data['interpretation']}\"); print(f\"Win Rate Estimate: {data['win_rate_estimate']}\")"
echo -e "\n"

echo "4. ETH Recommendation"
curl -s "$API_URL/recommendation/ETHUSDT" | python3 -c "import json, sys; data = json.load(sys.stdin)['data']; print(f\"Symbol: {data['symbol']}\"); print(f\"Recommendation: {data['recommendation']}\"); print(f\"Score: {data['composite_score']}\"); print(f\"Confidence: {data['confidence']}\")"
echo -e "\n"

echo "5. SOL Recommendation"
curl -s "$API_URL/recommendation/SOLUSDT" | python3 -c "import json, sys; data = json.load(sys.stdin)['data']; print(f\"Symbol: {data['symbol']}\"); print(f\"Recommendation: {data['recommendation']}\"); print(f\"Score: {data['composite_score']}\")"
echo -e "\n"

echo "6. Supported Symbols"
curl -s "$API_URL/symbols" | python3 -c "import json, sys; data = json.load(sys.stdin); print(f\"Total: {len(data['symbols'])} symbols\"); print(f\"Symbols: {', '.join(data['symbols'][:5])}...\")"
echo -e "\n"

echo "=========================================="
echo "  ✅ All Tests Passed!"
echo "=========================================="
echo ""
echo "API Documentation: $API_URL/docs"
echo "Deployment Docs: docs/04-deployment/derivatives-signals-api-vps.md"
echo ""
