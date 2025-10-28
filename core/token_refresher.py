"""
Background refresher that keeps token metrics up to date.

Periodically re-collects data for whitelisted tokens (and optionally the
newest safe tokens) so liquidity, holders, and scores reflect the current
state without manual intervention.
"""

from __future__ import annotations

import time
from datetime import datetime
from threading import Event, Thread
from typing import Optional

from core.data_collector import DataCollector
from core.http_client import HttpError
from core.logger import get_logger
from core.metrics import METRICS
from core.scoring import calculate_score
try:
    from core.gpt_agent import GPTScorer
except Exception:  # pragma: no cover - optional
    GPTScorer = None
from db.database import Database


class TokenRefresher:
    def __init__(
        self,
        database: Database,
        collector: DataCollector,
        *,
        interval: int = 120,
        per_token_delay: float = 1.0,
        gpt_scorer: Optional["GPTScorer"] = None,
    ):
        self.db = database
        self.collector = collector
        self.interval = interval
        self.per_token_delay = per_token_delay
        self.gpt_scorer = gpt_scorer

        self._stop_event = Event()
        self._thread: Thread | None = None
        self.log = get_logger("refresher")
        self._last_metrics_emit = 0.0
        self._metrics_emit_interval = 3600.0

    # ------------------------------------------------------------------ #
    def start(self):
        if self._thread and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = Thread(target=self._run, name="TokenRefresher", daemon=True)
        self._thread.start()
        self.log.info("Token refresher started (interval=%ss)", self.interval)

    def stop(self):
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)
        self.log.info("Token refresher stopped")

    # ------------------------------------------------------------------ #
    def _run(self):
        while not self._stop_event.is_set():
            try:
                self._refresh_cycle()
            except Exception as exc:  # pragma: no cover
                self.log.exception("Error during refresh cycle: %s", exc)

            self._stop_event.wait(self.interval)

    def _refresh_cycle(self):
        whitelist_entries = self.db.get_watchlist("whitelist")
        whitelist_mints = [entry.mint_address for entry in whitelist_entries]

        # Fallback to recently safe tokens if whitelist is empty
        if not whitelist_mints:
            safe_tokens = self.db.get_safe_tokens(limit=10)
            whitelist_mints = [token.mint_address for token in safe_tokens]

        tokens_map = self.db.get_tokens_by_mints(whitelist_mints)

        self.log.debug("Refreshing %s tokens", len(tokens_map))

        for mint, token in tokens_map.items():
            if self._stop_event.is_set():
                break

            try:
                context = {"source": "refresher"}
                token_data = self.collector.collect_full_data(mint, context=context)
                if not token_data:
                    continue

                token_data["first_seen"] = token.first_seen or datetime.utcnow()
                token_data["is_safe"] = token.is_safe
                token_data["is_graduated"] = token.is_graduated

                existing_meta = dict(token.token_metadata or {})
                new_meta = token_data.get("token_metadata", {}) or {}
                new_meta.setdefault("trades", existing_meta.get("trades", {}))
                new_meta.setdefault("migration", existing_meta.get("migration"))
                token_data["token_metadata"] = {**existing_meta, **new_meta}

                score, breakdown = calculate_score(token_data, context)
                token_data["token_metadata"]["performance"] = {
                    "score": score,
                    "breakdown": breakdown,
                    "updated_at": datetime.utcnow().isoformat(),
                }
                token_data["growth_rate"] = score

                if self.gpt_scorer and not token_data["token_metadata"].get("gpt_analysis"):
                    gpt_result = self.gpt_scorer.evaluate(token_data)
                    if gpt_result:
                        token_data["token_metadata"]["gpt_analysis"] = gpt_result
                        self.db.update_watchlist_details(mint, {"gpt_analysis": gpt_result})

                self.db.save_token(token_data)
                self.db.save_snapshot(mint, token_data)
                self.db.update_watchlist_details(mint, {"score": score})
                self.log.debug("Refreshed %s score=%.2f", mint, score)

                time.sleep(self.per_token_delay)
            except HttpError as exc:  # pragma: no cover - network handling
                if exc.status == 429:
                    self.log.debug("Refresher rate limited for %s; will retry next cycle", mint)
                else:
                    self.log.warning("Refresher HTTP error for %s: %s", mint, exc)
            except Exception as exc:  # pragma: no cover
                self.log.warning("Failed to refresh %s: %s", mint, exc)

        now = time.time()
        if now - self._last_metrics_emit >= self._metrics_emit_interval:
            metrics_snapshot = METRICS.snapshot()
            collector_metrics = {
                name: {
                    "success": stats.get("success"),
                    "rate_limited": stats.get("rate_limited"),
                    "exceptions": stats.get("exceptions"),
                    "last_error": stats.get("last_error"),
                }
                for name, stats in metrics_snapshot.items()
                if name.startswith("collector") or name.startswith("birdeye") or name.startswith("jupiter")
            }
            self.log.info("Collector metrics snapshot: %s", collector_metrics)
            self._last_metrics_emit = now
