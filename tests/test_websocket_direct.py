#!/usr/bin/env python3
import asyncio
import websockets
import json

async def test():
    uri = "ws://5.223.63.4:8000/ws/signals/BTCUSDT?signal_type=fusion&interval=10"
    print(f"Testing direct connection: {uri}")
    try:
        async with websockets.connect(uri) as ws:
            print("✅ Connected!")
            msg = await asyncio.wait_for(ws.recv(), timeout=15)
            data = json.loads(msg)
            print(f"📡 Received: {data.get('type')}")
            print("✅ WebSocket works!")
    except Exception as e:
        print(f"❌ Error: {e}")

asyncio.run(test())
