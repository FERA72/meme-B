"""
Scanner for detecting newly minted tokens on Solana.

Coordinates ingestion, enrichment, filtering, and watchlist management for
every new mint received from the different data feeds.
"""

from __future__ import annotations

import heapq
import time
from datetime import datetime
from threading import Event, Lock, Thread
from typing import Any, Dict, Optional

from core.http_client import HttpError
from core.data_collector import DataCollector
from core.filters import TokenFilter
from core.logger import get_logger
from core.metrics import METRICS
from core.scoring import calculate_score
from db.database import Database

try:
    from core.gpt_agent import GPTScorer
except Exception:  # pragma: no cover - optional dependency
    GPTScorer = None


class TokenScanner:
    """
    Orchestrates token discovery, enrichment, filtering, and persistence.
    """

    def __init__(self, database: Database, collector: DataCollector, token_filter: TokenFilter, gpt_scorer: Optional["GPTScorer"] = None):
        self.db = database
        self.collector = collector
        self.filter = token_filter
        self.gpt_scorer = gpt_scorer if GPTScorer else None
        self.processed_mints: set[str] = set()
        self.inflight_mints: set[str] = set()
        self.retry_base_delay = 20  # seconds
        self.retry_max_delay = 300  # seconds
        self.retry_max_attempts = 4
        self._retry_heap: list[tuple[float, int, Dict[str, Any]]] = []
        self._retry_counter: int = 0
        self._scheduled_retries: Dict[str, int] = {}
        self.telemetry: Dict[str, int] = {
            "processed": 0,
            "failures": 0,
            "retries_scheduled": 0,
            "retries_executed": 0,
        }
        self._retry_stop = Event()
        self._retry_thread: Optional[Thread] = None
        self._retry_lock = Lock()
        self.log = get_logger("scanner")

    # ------------------------------------------------------------------ #
    # Utility helpers
    # ------------------------------------------------------------------ #
    def is_duplicate(self, mint_address: str) -> bool:
        """
        Detect whether a mint was already processed (either in-memory or stored).
        """
        if self.db.is_blacklisted(mint_address):
            self.log.debug("Mint %s is blacklisted, skipping", mint_address)
            return True

        if mint_address in self.inflight_mints:
            self.log.debug("Mint %s currently in-flight, skipping", mint_address)
            return True

        if mint_address in self.processed_mints:
            return True

        existing = self.db.get_token(mint_address)
        if existing:
            self.processed_mints.add(mint_address)
            return True

        return False

    # ------------------------------------------------------------------ #
    # Main entry point
    # ------------------------------------------------------------------ #
    def process_mint_event(self, mint_address: str, context: Optional[Dict] = None) -> Optional[Dict]:
        """
        Handle a freshly discovered mint.

        Args:
            mint_address: Token mint address
            context: Optional contextual payload (webhook, pump.fun event, etc.)
        """
        context = context or {}
        self.drain_retry_queue()
        metadata_hint = context.get("metadata_hint") or {}
        hinted_label = metadata_hint.get("symbol") or metadata_hint.get("name") or ""

        self.log.info("New mint detected %s %s", mint_address, f'({hinted_label})' if hinted_label else "")
        return self._process_token(mint_address, context, attempt=context.get("retry_attempt", 0), from_retry=False)

    def _process_token(
        self,
        mint_address: str,
        context: Dict[str, Any],
        *,
        attempt: int = 0,
        from_retry: bool = False,
    ) -> Optional[Dict]:
        if self.is_duplicate(mint_address):
            if from_retry:
                self._scheduled_retries.pop(mint_address, None)
            self.log.debug("Mint %s already processed or in-flight", mint_address)
            return None

        self.inflight_mints.add(mint_address)
        start = time.perf_counter()
        context = dict(context or {})
        if attempt:
            context["retry_attempt"] = attempt

        try:
            self.log.debug("Collecting token data for %s (attempt=%s)", mint_address, attempt + 1)
            token_data = self.collector.collect_full_data(mint_address, context=context)
            if not token_data:
                raise RuntimeError("collector_returned_none")

            self.log.debug("Running safety filters for %s", mint_address)
            filter_results = self.filter.apply_all_filters(token_data)

            token_data["is_safe"] = filter_results["passed"]
            token_data["risk_flags"] = filter_results["failed_filters"]
            token_data["is_graduated"] = False

            score = self._apply_score(token_data, context)
            gpt_result = self._maybe_eval_with_gpt(token_data, context)

            self.db.save_token(token_data)
            self.db.log_filter_result(
                mint_address=mint_address,
                passed=filter_results["passed"],
                failed_filters=filter_results["failed_filters"],
                details=token_data,
            )
            self.db.save_snapshot(mint_address, token_data)

            symbol = token_data.get("symbol", "UNKNOWN")
            name = token_data.get("name", "Unknown Token")

            metadata_for_watchlist = {
                "symbol": symbol,
                "name": name,
                "risk_level": filter_results["risk_level"],
                "context_source": context.get("source"),
                "score": score,
            }
            if gpt_result:
                metadata_for_watchlist["gpt_analysis"] = gpt_result

            self.log.info(
                "Mint processed %s (%s) | safety=%s filter_score=%s/%s composite=%.2f liquidity=$%.2f holders=%s",
                mint_address,
                symbol or name,
                "SAFE" if filter_results["passed"] else "UNSAFE",
                filter_results["safe_score"],
                filter_results["total_filters"],
                score,
                token_data.get("liquidity_usd", 0),
                token_data.get("holder_count", 0),
            )

            if not filter_results["passed"]:
                failed_list = ", ".join(filter_results["failed_filters"])
                self.log.debug("Mint %s failed filters: %s", mint_address, failed_list)
                self.db.add_to_watchlist(
                    mint_address,
                    "blacklist",
                    reason=failed_list or "failed_filters",
                    details={**metadata_for_watchlist, "failed_filters": filter_results["failed_filters"]},
                )
            else:
                self.db.add_to_watchlist(
                    mint_address,
                    "whitelist",
                    reason="passed_initial_filters",
                    details=metadata_for_watchlist,
                )
            update_details = {"score": score}
            if gpt_result:
                update_details["gpt_analysis"] = gpt_result
            self.db.update_watchlist_details(mint_address, update_details)

            self.telemetry["processed"] += 1
            self.processed_mints.add(mint_address)
            self._scheduled_retries.pop(mint_address, None)
            latency = (time.perf_counter() - start) * 1000
            METRICS.record("scanner:process", 200, latency)

            return {
                "mint_address": mint_address,
                "symbol": symbol,
                "name": name,
                "is_safe": filter_results["passed"],
                "filter_results": filter_results,
                "token_data": token_data,
                "score": score,
            }

        except HttpError as exc:
            latency = (time.perf_counter() - start) * 1000
            status = exc.status or 0
            METRICS.record("scanner:process", status, latency, err=str(exc))
            transient = status in {0, 408, 429, 500, 502, 503, 504, 530}
            if transient:
                self._schedule_retry(mint_address, context, attempt, f"http_error:{status}")
            else:
                self.telemetry["failures"] += 1
                self.log.warning("Mint %s failed permanently with status %s: %s", mint_address, status, exc)
            return None

        except Exception as exc:  # pragma: no cover - defensive logging
            latency = (time.perf_counter() - start) * 1000
            METRICS.record("scanner:process", None, latency, err=str(exc))
            self.telemetry["failures"] += 1
            self.log.exception("Error processing mint %s: %s", mint_address, exc)
            self._schedule_retry(mint_address, context, attempt, "exception")
            return None

        finally:
            self.inflight_mints.discard(mint_address)

    def _schedule_retry(self, mint_address: str, context: Dict[str, Any], attempt: int, reason: str):
        next_attempt = attempt + 1
        if next_attempt > self.retry_max_attempts:
            self.telemetry["failures"] += 1
            self.log.error(
                "Retry limit reached for %s after %s attempts (reason=%s)",
                mint_address,
                next_attempt,
                reason,
            )
            return

        backoff = min(self.retry_base_delay * (2 ** attempt), self.retry_max_delay)
        due = time.time() + backoff
        payload = {
            "mint_address": mint_address,
            "context": dict(context),
            "attempt": next_attempt,
        }

        with self._retry_lock:
            self._retry_counter += 1
            heapq.heappush(self._retry_heap, (due, self._retry_counter, payload))
            self._scheduled_retries[mint_address] = next_attempt

        self.telemetry["retries_scheduled"] += 1
        self.log.info(
            "Scheduled retry for %s attempt=%s in %.0fs (%s)",
            mint_address,
            next_attempt,
            backoff,
            reason,
        )
        self._ensure_retry_worker()

    def _ensure_retry_worker(self):
        if self._retry_thread and self._retry_thread.is_alive():
            return
        self._retry_stop.clear()
        self._retry_thread = Thread(target=self._retry_worker, daemon=True, name="ScannerRetryLoop")
        self._retry_thread.start()

    def _retry_worker(self):
        while not self._retry_stop.is_set():
            processed = self.drain_retry_queue()
            wait_time = 0.5 if processed else self._next_retry_delay()
            self._retry_stop.wait(wait_time)

    def _next_retry_delay(self) -> float:
        with self._retry_lock:
            if not self._retry_heap:
                return 2.0
            next_due = self._retry_heap[0][0]
        delay = max(0.2, next_due - time.time())
        return min(delay, 5.0)

    def drain_retry_queue(self) -> int:
        processed = 0
        while True:
            with self._retry_lock:
                if not self._retry_heap or self._retry_heap[0][0] > time.time():
                    break
                _, _, payload = heapq.heappop(self._retry_heap)
            mint = payload["mint_address"]
            context = payload["context"]
            attempt = payload["attempt"]
            self.telemetry["retries_executed"] += 1
            self._scheduled_retries.pop(mint, None)
            context["retry_attempt"] = attempt
            self.log.debug("Retrying mint %s (attempt=%s)", mint, attempt)
            self._process_token(mint, context, attempt=attempt, from_retry=True)
            processed += 1
        return processed

    def shutdown(self):
        """Stop retry worker thread."""
        self._retry_stop.set()
        if self._retry_thread and self._retry_thread.is_alive():
            self._retry_thread.join(timeout=2)
        self._retry_thread = None
    # ------------------------------------------------------------------ #
    # Webhook processing
    # ------------------------------------------------------------------ #
    def process_webhook_payload(self, payload: Dict) -> Optional[Dict]:
        """
        Extract the mint address from a Helius webhook payload and process it.
        """
        try:
            context = {
                "source": "helius_webhook",
                "webhook_payload": payload,
            }

            transaction = payload.get("transaction")
            if isinstance(transaction, dict):
                for instruction in transaction.get("instructions", []):
                    if instruction.get("programId") == "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA":
                        if instruction.get("type") == "initializeMint":
                            mint_address = instruction.get("mint")
                            if mint_address:
                                return self.process_mint_event(mint_address, context)

            for account in payload.get("accountData", []) or []:
                if account.get("account") and account.get("nativeBalanceChange", 0) == 0:
                    mint_address = account.get("account")
                    if mint_address:
                        return self.process_mint_event(mint_address, context)

            if "mint" in payload:
                return self.process_mint_event(payload["mint"], context)

            self.log.debug("Could not extract mint address from webhook payload: %s", payload)
            return None

        except Exception as exc:  # pragma: no cover - defensive logging
            self.log.exception("Error processing webhook payload: %s", exc)
            return None

    # ------------------------------------------------------------------ #
    # Misc helpers
    # ------------------------------------------------------------------ #
    def process_trade_event(self, payload: Dict):
        """
        Incorporate trade events from PumpPortal.
        """
        mint = (
            payload.get("mint")
            or payload.get("tokenAddress")
            or payload.get("tokenMint")
            or payload.get("token")
        )
        if not mint:
            self.log.debug("Trade payload missing mint: %s", payload)
            return

        token = self.db.get_token(mint)
        if not token:
            self.log.debug("Trade event for unknown mint %s, attempting backfill", mint)
            self.process_mint_event(mint, {"source": "pump_portal_trade", "trade_event": payload})
            token = self.db.get_token(mint)
            if not token:
                return

        metadata = dict(token.token_metadata or {})
        trades = metadata.get("trades") or {
            "buy_count": 0,
            "sell_count": 0,
            "other_count": 0,
            "sol_volume": 0.0,
            "last_trade": None,
        }

        tx_type = (payload.get("txType") or "").lower()
        sol_amount = float(
            payload.get("solAmount")
            or payload.get("amountSol")
            or payload.get("solAmountIn")
            or 0
        )

        if tx_type == "buy":
            trades["buy_count"] += 1
        elif tx_type == "sell":
            trades["sell_count"] += 1
        else:
            trades["other_count"] = trades.get("other_count", 0) + 1

        trades["sol_volume"] += sol_amount
        trades["last_trade"] = {
            "type": payload.get("txType"),
            "signature": payload.get("signature"),
            "solAmount": sol_amount,
            "timestamp": payload.get("timestamp") or datetime.utcnow().isoformat(),
        }

        metadata["trades"] = trades

        snapshot = {
            "mint_address": mint,
            "liquidity_usd": token.liquidity_usd or 0,
            "market_cap": token.market_cap or 0,
            "volume_24h": token.volume_24h or 0,
            "holder_count": token.holder_count or 0,
            "top_holder_percentage": token.top_holder_percentage or 0,
            "token_metadata": metadata,
            "first_seen": token.first_seen,
        }

        context = {"source": "pump_portal_trade", "trade_event": payload}
        score = self._apply_score(snapshot, context)
        gpt_result = self._maybe_eval_with_gpt(snapshot, context)

        update = {
            "mint_address": mint,
            "token_metadata": metadata,
            "growth_rate": score,
        }

        self.db.save_token(update)
        watch_updates = {"score": score, "trades": trades}
        if gpt_result:
            watch_updates["gpt_analysis"] = gpt_result
        self.db.update_watchlist_details(mint, watch_updates)
        self.log.debug(
            "Trade update %s | type=%s sol=%.4f score=%.2f buys=%s sells=%s",
            mint,
            tx_type,
            sol_amount,
            score,
            trades.get("buy_count"),
            trades.get("sell_count"),
        )

    def process_migration_event(self, payload: Dict):
        """
        Track migration events from PumpPortal (e.g., bonding curve completion).
        """
        mint = (
            payload.get("mint")
            or payload.get("token")
            or payload.get("tokenAddress")
            or payload.get("newTokenAddress")
        )
        if not mint:
            self.log.debug("Migration payload missing mint: %s", payload)
            return

        token = self.db.get_token(mint)
        if not token:
            self.log.debug("Migration event for unknown mint %s - skipping", mint)
            return

        metadata = dict(token.token_metadata or {})
        migration_info = {
            "status": payload.get("status") or payload.get("type") or "migrated",
            "payload": payload,
            "updated_at": datetime.utcnow().isoformat(),
        }
        metadata["migration"] = migration_info

        snapshot = {
            "mint_address": mint,
            "liquidity_usd": token.liquidity_usd or 0,
            "market_cap": token.market_cap or 0,
            "volume_24h": token.volume_24h or 0,
            "holder_count": token.holder_count or 0,
            "top_holder_percentage": token.top_holder_percentage or 0,
            "token_metadata": metadata,
            "first_seen": token.first_seen,
        }

        context = {"source": "pump_portal_migration", "migration_event": payload}
        score = self._apply_score(snapshot, context)
        gpt_result = self._maybe_eval_with_gpt(snapshot, context)
        update = {
            "mint_address": mint,
            "token_metadata": metadata,
            "growth_rate": score,
        }
        self.db.save_token(update)
        update_details = {"score": score, "migration": migration_info}
        if gpt_result:
            update_details["gpt_analysis"] = gpt_result
        self.db.update_watchlist_details(mint, update_details)
        self.log.info("Migration update %s status=%s score=%.2f", mint, migration_info["status"], score)

    def scan_recent_transactions(self, limit: int = 10):
        """
        Placeholder for a proactive RPC-based scanner.
        """
        self.log.debug("scan_recent_transactions called with limit=%s (not implemented)", limit)

    def get_stats(self) -> Dict:
        """
        Return high-level scanner statistics.
        """
        with self._retry_lock:
            retry_backlog = len(self._retry_heap)
        metrics_snapshot = METRICS.snapshot()
        return {
            "processed_count": len(self.processed_mints),
            "total_tokens": len(self.db.get_all_tokens()),
            "safe_tokens": len(self.db.get_safe_tokens()),
            "graduated_tokens": len(self.db.get_graduated_tokens()),
            "inflight": len(self.inflight_mints),
            "retry_backlog": retry_backlog,
            "telemetry": dict(self.telemetry),
            "metrics": metrics_snapshot,
        }

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _maybe_eval_with_gpt(self, token_data: Dict, context: Dict) -> Optional[Dict]:
        if not getattr(self, "gpt_scorer", None):
            return None

        try:
            result = self.gpt_scorer.evaluate(token_data)
            if result:
                token_data.setdefault("token_metadata", {})["gpt_analysis"] = result
            return result
        except Exception as exc:  # pragma: no cover - external dependency
            self.log.debug("GPT scoring failed for %s: %s", token_data.get("mint_address"), exc)
            return None

    def _apply_score(self, token_data: Dict, context: Optional[Dict] = None) -> float:
        """
        Apply composite score to token_data, storing breakdown in metadata.
        """
        score, breakdown = calculate_score(token_data, context)
        metadata = token_data.setdefault("token_metadata", {})
        metadata["performance"] = {
            "score": score,
            "breakdown": breakdown,
            "updated_at": datetime.utcnow().isoformat(),
        }
        token_data["growth_rate"] = score
        return score
