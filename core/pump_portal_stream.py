"""
Real-time listener for pump.fun token mints via PumpPortal.

This module connects to the PumpPortal websocket and forwards freshly
minted tokens to the TokenScanner so they are picked up immediately after
launch with the correct metadata.
"""

from __future__ import annotations

import asyncio
import json
from threading import Event, Thread
from typing import Dict, Optional

import websockets

from core.logger import get_logger
from core.scanner import TokenScanner


class PumpPortalStream:
    """
    Stream new pump.fun token mints from PumpPortal.

    PumpPortal exposes a websocket that pushes token creation events the
    instant they are minted on the bonding curve.  Each event already
    contains the human readable token name/symbol so we can avoid the
    "UNK" placeholders altogether.
    """

    def __init__(
        self,
        scanner: TokenScanner,
        *,
        url: str = "wss://pumpportal.fun/api/data",
        reconnect_delay: int = 5,
    ):
        self.scanner = scanner
        self.url = url
        self.reconnect_delay = reconnect_delay

        self._stop_event = Event()
        self._thread: Optional[Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._seen_mints: set[str] = set()
        self._tracked_tokens: set[str] = set()
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self.log = get_logger("pump_portal")

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def start(self):
        """Start the websocket stream in a background thread."""
        if self._thread and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = Thread(target=self._run_loop, daemon=True, name="PumpPortalStream")
        self._thread.start()
        self.log.info("PumpPortal stream started (listening for new pump.fun mints)")

    def stop(self):
        """Stop the websocket stream."""
        self._stop_event.set()

        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)
            self.log.info("PumpPortal stream stopped")

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _run_loop(self):
        """Spin up a dedicated asyncio loop for websocket handling."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        try:
            self._loop.run_until_complete(self._listen_forever())
        except RuntimeError as exc:
            self.log.debug("PumpPortal loop stopped: %s", exc)
        finally:
            pending = asyncio.all_tasks(loop=self._loop)
            for task in pending:
                task.cancel()
            self._loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            self._loop.close()

    async def _listen_forever(self):
        """Keep the websocket alive and reconnect on transient failures."""
        while not self._stop_event.is_set():
            try:
                await self._consume_stream()
            except Exception as exc:  # pragma: no cover - network failures
                self.log.warning("PumpPortal stream error: %s", exc)
                await asyncio.sleep(self.reconnect_delay)

    async def _consume_stream(self):
        """Handle an individual websocket session."""
        async with websockets.connect(self.url, ping_interval=20, ping_timeout=20) as ws:
            self._ws = ws
            await ws.send(json.dumps({"method": "subscribeNewToken"}))
            await ws.send(json.dumps({"method": "subscribeMigration"}))
            if self._tracked_tokens:
                await ws.send(
                    json.dumps({"method": "subscribeTokenTrade", "keys": list(self._tracked_tokens)})
                )

            self.log.info(
                "Subscribed to PumpPortal feeds (tracked_tokens=%s)",
                len(self._tracked_tokens),
            )

            async for raw in ws:
                if self._stop_event.is_set():
                    break

                try:
                    payload: Dict = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                await asyncio.to_thread(self._handle_message, payload)

        self._ws = None

    def _handle_message(self, payload: Dict):
        """Route PumpPortal events to the scanner."""
        if not isinstance(payload, dict):
            return

        tx_type = (payload.get("txType") or "").lower()
        if tx_type in {"buy", "sell", "swap"}:
            self.scanner.process_trade_event(payload)
            return

        if (
            payload.get("migration")
            or payload.get("eventType") == "migration"
            or (payload.get("type") or "").lower() == "migration"
        ):
            self.scanner.process_migration_event(payload)
            return

        if "mint" in payload:
            self._handle_new_mint(payload)

    def _handle_new_mint(self, payload: Dict):
        mint = payload.get("mint")
        if not mint:
            return

        if mint in self._seen_mints:
            return

        self._seen_mints.add(mint)

        metadata_hint = {
            "name": payload.get("name"),
            "symbol": payload.get("symbol"),
            "uri": payload.get("uri"),
        }

        context = {
            "source": "pump_portal",
            "pump_portal": payload,
            "metadata_hint": {k: v for k, v in metadata_hint.items() if v},
        }

        symbol = metadata_hint.get("symbol") or "???"
        name = metadata_hint.get("name") or "Unknown Pump Token"
        self.log.info("New mint detected %s (%s) -> %s", symbol, name, mint)
        self.scanner.process_mint_event(mint, context)
        self._subscribe_token_trades(mint)

    def _subscribe_token_trades(self, mint: str):
        if mint in self._tracked_tokens:
            return

        self._tracked_tokens.add(mint)

        if not self._loop or not self._ws or self._stop_event.is_set():
            return

        async def _send():
            if self._ws:
                await self._ws.send(
                    json.dumps({"method": "subscribeTokenTrade", "keys": [mint]})
                )

        asyncio.run_coroutine_threadsafe(_send(), self._loop)
        self.log.debug("Subscribed to trade feed for %s", mint)

    def add_tracked_tokens(self, tokens):
        new_tokens = [mint for mint in tokens if mint and mint not in self._tracked_tokens]
        if not new_tokens:
            return

        self._tracked_tokens.update(new_tokens)

        if not self._loop or not self._ws or self._stop_event.is_set():
            return

        async def _send():
            if self._ws:
                await self._ws.send(
                    json.dumps({"method": "subscribeTokenTrade", "keys": new_tokens})
                )

        asyncio.run_coroutine_threadsafe(_send(), self._loop)
        self.log.debug("Subscribed to %s tracked tokens", len(new_tokens))


__all__ = ["PumpPortalStream"]
