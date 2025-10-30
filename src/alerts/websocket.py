"""
Websocket Manager for Real-Time Exchange Monitoring (Phase 3)
Monitors liquidations, funding rate changes, and price spikes in real-time
"""
import websocket
import json
import threading
import time
from typing import Dict, List, Callable, Optional
from datetime import datetime, timedelta
import logging


class WebSocketManager:
    """
    Manages websocket connections to multiple exchanges
    Provides real-time event-driven alerts for Tier 1 strategies
    """

    def __init__(self, on_event_callback: Callable):
        """
        Args:
            on_event_callback: Function to call when significant event detected
                              callback(exchange, event_type, data)
        """
        self.connections: Dict[str, websocket.WebSocketApp] = {}
        self.threads: Dict[str, threading.Thread] = {}
        self.running = False
        self.on_event = on_event_callback

        # Connection status tracking
        self.last_heartbeat: Dict[str, datetime] = {}
        self.reconnect_attempts: Dict[str, int] = {}
        self.max_reconnect_attempts = 5

        # Event thresholds for triggering alerts
        self.thresholds = {
            'liquidation_size_usd': 1_000_000,  # $1M+ liquidation
            'price_change_pct': 3.0,  # 3% price spike
            'funding_rate_change': 0.0005,  # 0.05% change
            'oi_change_pct': 10.0  # 10% OI change
        }

        self.logger = logging.getLogger(__name__)

    def start(self, exchanges: List[str]):
        """
        Start websocket connections to specified exchanges

        Args:
            exchanges: List of exchange names (e.g., ['binance', 'bybit'])
        """
        self.running = True

        for exchange in exchanges:
            self._start_exchange_connection(exchange)

        # Start monitoring thread
        monitor_thread = threading.Thread(target=self._monitor_connections, daemon=True)
        monitor_thread.start()

    def stop(self):
        """Stop all websocket connections"""
        self.running = False

        for exchange, ws in self.connections.items():
            try:
                ws.close()
            except Exception as e:
                self.logger.error(f"Error closing {exchange} websocket: {e}")

        # Wait for threads to finish
        for thread in self.threads.values():
            thread.join(timeout=5)

    def _start_exchange_connection(self, exchange: str):
        """Start websocket connection for an exchange"""
        if exchange == 'binance':
            self._connect_binance()
        elif exchange == 'bybit':
            self._connect_bybit()
        elif exchange == 'okx':
            self._connect_okx()
        # Add more exchanges as needed

    def _connect_binance(self):
        """Connect to Binance futures websocket"""
        # Liquidation orders stream
        url = "wss://fstream.binance.com/ws/!forceOrder@arr"

        def on_message(ws, message):
            data = json.loads(message)
            self._handle_binance_liquidation(data)

        def on_error(ws, error):
            self.logger.error(f"Binance websocket error: {error}")

        def on_close(ws, close_status_code, close_msg):
            self.logger.info(f"Binance websocket closed: {close_status_code}")
            if self.running:
                self._reconnect('binance')

        def on_open(ws):
            self.logger.info("Binance websocket connected")
            self.last_heartbeat['binance'] = datetime.now()
            self.reconnect_attempts['binance'] = 0

        ws = websocket.WebSocketApp(
            url,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
            on_open=on_open
        )

        self.connections['binance'] = ws

        # Run in separate thread
        thread = threading.Thread(target=ws.run_forever, daemon=True)
        thread.start()
        self.threads['binance'] = thread

    def _connect_bybit(self):
        """Connect to Bybit futures websocket"""
        url = "wss://stream.bybit.com/v5/public/linear"

        def on_message(ws, message):
            data = json.loads(message)
            # Handle Bybit liquidation data
            if 'topic' in data and 'liquidation' in data['topic']:
                self._handle_bybit_liquidation(data)

        def on_error(ws, error):
            self.logger.error(f"Bybit websocket error: {error}")

        def on_close(ws, close_status_code, close_msg):
            self.logger.info(f"Bybit websocket closed")
            if self.running:
                self._reconnect('bybit')

        def on_open(ws):
            self.logger.info("Bybit websocket connected")
            # Subscribe to liquidation updates
            subscribe_msg = {
                "op": "subscribe",
                "args": ["liquidation.BTCUSDT"]
            }
            ws.send(json.dumps(subscribe_msg))
            self.last_heartbeat['bybit'] = datetime.now()
            self.reconnect_attempts['bybit'] = 0

        ws = websocket.WebSocketApp(
            url,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
            on_open=on_open
        )

        self.connections['bybit'] = ws

        thread = threading.Thread(target=ws.run_forever, daemon=True)
        thread.start()
        self.threads['bybit'] = thread

    def _connect_okx(self):
        """Connect to OKX futures websocket"""
        url = "wss://ws.okx.com:8443/ws/v5/public"

        def on_message(ws, message):
            data = json.loads(message)
            # Handle OKX liquidation data
            if 'arg' in data and 'channel' in data['arg']:
                if 'liquidation-orders' in data['arg']['channel']:
                    self._handle_okx_liquidation(data)

        def on_error(ws, error):
            self.logger.error(f"OKX websocket error: {error}")

        def on_close(ws, close_status_code, close_msg):
            self.logger.info(f"OKX websocket closed")
            if self.running:
                self._reconnect('okx')

        def on_open(ws):
            self.logger.info("OKX websocket connected")
            # Subscribe to liquidation orders
            subscribe_msg = {
                "op": "subscribe",
                "args": [{
                    "channel": "liquidation-orders",
                    "instType": "SWAP",
                    "instId": "BTC-USDT-SWAP"
                }]
            }
            ws.send(json.dumps(subscribe_msg))
            self.last_heartbeat['okx'] = datetime.now()
            self.reconnect_attempts['okx'] = 0

        ws = websocket.WebSocketApp(
            url,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
            on_open=on_open
        )

        self.connections['okx'] = ws

        thread = threading.Thread(target=ws.run_forever, daemon=True)
        thread.start()
        self.threads['okx'] = thread

    def _handle_binance_liquidation(self, data: Dict):
        """Process Binance liquidation event"""
        try:
            order = data.get('o', {})
            symbol = order.get('s', '')
            side = order.get('S', '')
            price = float(order.get('p', 0))
            quantity = float(order.get('q', 0))
            value_usd = price * quantity

            # Only alert on large liquidations
            if value_usd >= self.thresholds['liquidation_size_usd']:
                event_data = {
                    'symbol': symbol,
                    'side': side,
                    'size_usd': value_usd,
                    'price': price,
                    'timestamp': datetime.now().isoformat()
                }
                self.on_event('binance', 'large_liquidation', event_data)

        except Exception as e:
            self.logger.error(f"Error processing Binance liquidation: {e}")

    def _handle_bybit_liquidation(self, data: Dict):
        """Process Bybit liquidation event"""
        try:
            if 'data' not in data:
                return

            for item in data['data']:
                symbol = item.get('symbol', '')
                side = item.get('side', '')
                price = float(item.get('price', 0))
                size = float(item.get('size', 0))
                value_usd = price * size

                if value_usd >= self.thresholds['liquidation_size_usd']:
                    event_data = {
                        'symbol': symbol,
                        'side': side,
                        'size_usd': value_usd,
                        'price': price,
                        'timestamp': datetime.now().isoformat()
                    }
                    self.on_event('bybit', 'large_liquidation', event_data)

        except Exception as e:
            self.logger.error(f"Error processing Bybit liquidation: {e}")

    def _handle_okx_liquidation(self, data: Dict):
        """Process OKX liquidation event"""
        try:
            if 'data' not in data:
                return

            for item in data['data']:
                symbol = item.get('instId', '')
                side = item.get('side', '')
                size_usd = float(item.get('sz', 0))

                if size_usd >= self.thresholds['liquidation_size_usd']:
                    event_data = {
                        'symbol': symbol,
                        'side': side,
                        'size_usd': size_usd,
                        'timestamp': datetime.now().isoformat()
                    }
                    self.on_event('okx', 'large_liquidation', event_data)

        except Exception as e:
            self.logger.error(f"Error processing OKX liquidation: {e}")

    def _monitor_connections(self):
        """Monitor websocket connections and trigger reconnects if needed"""
        while self.running:
            now = datetime.now()

            for exchange, last_hb in self.last_heartbeat.items():
                # Check if connection is stale (no data in 60 seconds)
                if now - last_hb > timedelta(seconds=60):
                    self.logger.warning(f"{exchange} connection stale, reconnecting...")
                    self._reconnect(exchange)

            time.sleep(30)  # Check every 30 seconds

    def _reconnect(self, exchange: str):
        """Attempt to reconnect to an exchange"""
        attempts = self.reconnect_attempts.get(exchange, 0)

        if attempts >= self.max_reconnect_attempts:
            self.logger.error(f"Max reconnect attempts reached for {exchange}, giving up")
            return

        self.reconnect_attempts[exchange] = attempts + 1

        # Close existing connection
        if exchange in self.connections:
            try:
                self.connections[exchange].close()
            except Exception:
                pass

        # Wait before reconnecting (exponential backoff)
        wait_time = min(60, 2 ** attempts)
        self.logger.info(f"Reconnecting to {exchange} in {wait_time}s (attempt {attempts + 1})")
        time.sleep(wait_time)

        # Reconnect
        self._start_exchange_connection(exchange)

    def is_healthy(self, exchange: str) -> bool:
        """Check if websocket connection is healthy"""
        if exchange not in self.last_heartbeat:
            return False

        age = datetime.now() - self.last_heartbeat[exchange]
        return age < timedelta(seconds=60)

    def get_status(self) -> Dict:
        """Get status of all connections"""
        return {
            exchange: {
                'connected': exchange in self.connections,
                'healthy': self.is_healthy(exchange),
                'last_heartbeat': self.last_heartbeat.get(exchange),
                'reconnect_attempts': self.reconnect_attempts.get(exchange, 0)
            }
            for exchange in self.connections.keys()
        }
