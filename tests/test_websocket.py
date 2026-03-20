#!/usr/bin/env python3
"""Quick WebSocket test for Derivatives Signals API"""

import asyncio
import websockets
import json
from datetime import datetime

async def test_websocket():
    uri = "ws://5.223.63.4/api/ws/signals/BTCUSDT?signal_type=fusion&interval=30"

    print(f"Connecting to: {uri}")
    print(f"Time: {datetime.now()}\n")

    try:
        async with websockets.connect(uri) as websocket:
            print("✅ Connected successfully!")

            # Receive first message
            print("\nWaiting for initial signal...")
            message = await asyncio.wait_for(websocket.recv(), timeout=10)
            data = json.loads(message)

            print(f"\n📡 Received Signal:")
            print(f"Type: {data.get('type')}")
            print(f"Symbol: {data.get('symbol')}")
            print(f"Timestamp: {data.get('timestamp')}")

            if 'signals' in data and 'fusion' in data['signals']:
                fusion = data['signals']['fusion']
                print(f"\n🎯 Fusion Signal:")
                print(f"Direction: {fusion.get('direction')}")
                print(f"Confidence: {fusion.get('confidence')}%")
                print(f"Score breakdown: {fusion.get('metadata', {}).get('score_breakdown')}")

            print("\n✅ WebSocket test passed!")

    except asyncio.TimeoutError:
        print("❌ Timeout waiting for message")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_websocket())
