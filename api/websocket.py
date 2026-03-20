"""WebSocket support for real-time signal streaming

Provides WebSocket endpoints for streaming live signal updates.
"""

from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, Set
import asyncio
import logging
import json
from datetime import datetime

from src.signals.calculators import SignalCalculator
from src.signals.fusion import SignalFusion

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manage WebSocket connections"""

    def __init__(self):
        """Initialize connection manager"""
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self.calculator = SignalCalculator()
        self.fusion_engine = SignalFusion(self.calculator)

    async def connect(self, websocket: WebSocket, symbol: str):
        """Accept and register a new WebSocket connection

        Args:
            websocket: WebSocket connection
            symbol: Trading symbol to subscribe to
        """
        await websocket.accept()

        if symbol not in self.active_connections:
            self.active_connections[symbol] = set()

        self.active_connections[symbol].add(websocket)
        logger.info(f"Client connected to {symbol}. Total: {len(self.active_connections[symbol])}")

    def disconnect(self, websocket: WebSocket, symbol: str):
        """Remove a WebSocket connection

        Args:
            websocket: WebSocket connection
            symbol: Trading symbol
        """
        if symbol in self.active_connections:
            self.active_connections[symbol].discard(websocket)
            logger.info(f"Client disconnected from {symbol}. Total: {len(self.active_connections[symbol])}")

            # Clean up empty sets
            if not self.active_connections[symbol]:
                del self.active_connections[symbol]

    async def broadcast_to_symbol(self, symbol: str, message: dict):
        """Broadcast message to all connections for a symbol

        Args:
            symbol: Trading symbol
            message: Message to broadcast
        """
        if symbol not in self.active_connections:
            return

        disconnected = set()

        for connection in self.active_connections[symbol]:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error sending to client: {e}")
                disconnected.add(connection)

        # Clean up disconnected clients
        for connection in disconnected:
            self.disconnect(connection, symbol)

    async def send_signal_update(self, symbol: str, signal_type: str = "fusion"):
        """Calculate and broadcast signal update

        Args:
            symbol: Trading symbol
            signal_type: Type of signal to send (fusion, funding_rate, etc.)
        """
        try:
            if signal_type == "fusion":
                signal = self.fusion_engine.calculate_fusion_signal(symbol)
            elif signal_type == "funding_rate":
                signal = self.calculator.calculate_funding_rate_signal(symbol)
            elif signal_type == "open_interest":
                signal = self.calculator.calculate_open_interest_signal(symbol)
            elif signal_type == "long_short_ratio":
                signal = self.calculator.calculate_long_short_ratio_signal(symbol)
            elif signal_type == "basis":
                signal = self.calculator.calculate_basis_signal(symbol)
            elif signal_type == "cvd":
                signal = self.calculator.calculate_cvd_signal(symbol)
            elif signal_type == "all":
                signals_dict = self.calculator.calculate_all_signals(symbol)
                signals_dict['fusion'] = self.fusion_engine.calculate_fusion_signal(symbol)

                message = {
                    "type": "signal_update",
                    "symbol": symbol,
                    "timestamp": datetime.utcnow().isoformat(),
                    "signals": {k: v.dict() if v else None for k, v in signals_dict.items()}
                }
                await self.broadcast_to_symbol(symbol, message)
                return
            else:
                raise ValueError(f"Unknown signal type: {signal_type}")

            message = {
                "type": "signal_update",
                "symbol": symbol,
                "signal_type": signal_type,
                "timestamp": datetime.utcnow().isoformat(),
                "signal": signal.dict() if signal else None
            }

            await self.broadcast_to_symbol(symbol, message)

        except Exception as e:
            logger.error(f"Error calculating signal for {symbol}: {e}")
            error_message = {
                "type": "error",
                "symbol": symbol,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
            await self.broadcast_to_symbol(symbol, error_message)


# Global connection manager instance
manager = ConnectionManager()


async def signal_stream_worker(symbol: str, interval: int = 60):
    """Background worker to stream signals at regular intervals

    Args:
        symbol: Trading symbol
        interval: Update interval in seconds (default: 60)
    """
    logger.info(f"Started signal stream worker for {symbol} (interval: {interval}s)")

    while True:
        try:
            if symbol in manager.active_connections and manager.active_connections[symbol]:
                await manager.send_signal_update(symbol, signal_type="all")
            else:
                logger.debug(f"No active connections for {symbol}, stopping worker")
                break

            await asyncio.sleep(interval)

        except asyncio.CancelledError:
            logger.info(f"Signal stream worker cancelled for {symbol}")
            break
        except Exception as e:
            logger.error(f"Error in signal stream worker for {symbol}: {e}")
            await asyncio.sleep(interval)


async def handle_websocket_connection(
    websocket: WebSocket,
    symbol: str,
    signal_type: str = "fusion",
    interval: int = 60
):
    """Handle a WebSocket connection

    Args:
        websocket: WebSocket connection
        symbol: Trading symbol
        signal_type: Type of signal to stream
        interval: Update interval in seconds
    """
    await manager.connect(websocket, symbol)

    # Start background worker if this is the first connection for this symbol
    worker_task = None
    if len(manager.active_connections[symbol]) == 1:
        worker_task = asyncio.create_task(signal_stream_worker(symbol, interval))

    try:
        # Send initial signal immediately
        await manager.send_signal_update(symbol, signal_type)

        # Keep connection alive and handle client messages
        while True:
            try:
                # Wait for messages from client (for config updates, etc.)
                data = await websocket.receive_text()
                message = json.loads(data)

                # Handle client commands
                if message.get("command") == "update_interval":
                    interval = int(message.get("interval", 60))
                    await websocket.send_json({
                        "type": "config_update",
                        "interval": interval,
                        "timestamp": datetime.utcnow().isoformat()
                    })

                elif message.get("command") == "change_signal_type":
                    signal_type = message.get("signal_type", "fusion")
                    await manager.send_signal_update(symbol, signal_type)

            except WebSocketDisconnect:
                logger.info(f"Client disconnected from {symbol}")
                break
            except json.JSONDecodeError:
                logger.warning("Received invalid JSON from client")
            except Exception as e:
                logger.error(f"Error handling client message: {e}")

    finally:
        manager.disconnect(websocket, symbol)

        # Cancel worker if no more connections
        if worker_task and symbol not in manager.active_connections:
            worker_task.cancel()
