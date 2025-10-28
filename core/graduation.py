"""
Graduation watcher - monitors filtered tokens for growth and promotes the ones
that continue to perform well. Graduated tokens automatically move to the
whitelist so they stay on the radar for deeper monitoring and future models.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Dict

from core.data_collector import DataCollector
from core.http_client import HttpError
from core.logger import get_logger
from db.database import Database
from db.models import Token


class GraduationWatcher:
    """
    Continuously monitors tokens that passed initial filters. Watches for growth
    in liquidity, market cap, and holders, and marks tokens as graduated when
    they hit configured thresholds.
    """

    def __init__(self, database: Database, collector: DataCollector, config: Dict | None = None):
        self.db = database
        self.collector = collector
        self.config = config or {
            "min_liquidity_growth": 2.0,
            "min_market_cap": 100_000,
            "min_holder_growth": 1.5,
            "min_volume_24h": 10_000,
            "check_interval_seconds": 60,
        }
        self.running = False
        self.log = get_logger("graduation")

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def check_graduation_criteria(self, token: Token, fresh_data: Dict) -> bool:
        """
        Determine if a token meets graduation criteria.
        """
        current_liquidity = fresh_data.get("liquidity_usd", 0)
        initial_liquidity = token.initial_liquidity or 1
        liquidity_growth = current_liquidity / initial_liquidity

        current_holders = fresh_data.get("holder_count", 0)
        initial_holders = token.initial_holders or 1
        holder_growth = current_holders / initial_holders

        current_market_cap = fresh_data.get("market_cap", 0)
        current_volume = fresh_data.get("volume_24h", 0)

        checks = {
            "liquidity_growth": liquidity_growth >= self.config["min_liquidity_growth"],
            "market_cap": current_market_cap >= self.config["min_market_cap"],
            "holder_growth": holder_growth >= self.config["min_holder_growth"],
            "volume": current_volume >= self.config["min_volume_24h"],
        }

        if all(checks.values()):
            self.log.info(
                "Graduation criteria met for %s | liquidity_x=%.2f market_cap=$%.0f holder_x=%.2f volume24=$%.0f",
                token.symbol or token.mint_address,
                liquidity_growth,
                current_market_cap,
                holder_growth,
                current_volume,
            )
            return True

        return False

    def update_token_data(self, token: Token) -> Dict:
        """
        Fetch fresh data for a token and persist snapshot.
        """
        try:
            fresh_data = self.collector.collect_full_data(token.mint_address)
        except HttpError as exc:
            if exc.status == 429:
                self.log.debug("Graduation data fetch rate limited for %s, will retry later", token.mint_address)
            else:
                self.log.warning("Failed to refresh token %s for graduation: %s", token.mint_address, exc)
            return {}

        if fresh_data:
            update_dict = {
                "mint_address": token.mint_address,
                "liquidity_usd": fresh_data.get("liquidity_usd", 0),
                "market_cap": fresh_data.get("market_cap", 0),
                "price_usd": fresh_data.get("price_usd", 0),
                "holder_count": fresh_data.get("holder_count", 0),
                "volume_24h": fresh_data.get("volume_24h", 0),
                "last_updated": datetime.utcnow(),
            }

            if token.market_cap:
                delta = fresh_data.get("market_cap", 0) - token.market_cap
                update_dict["growth_rate"] = (delta / token.market_cap) * 100 if token.market_cap else 0

            self.db.save_token(update_dict)
            self.db.save_snapshot(token.mint_address, fresh_data)

        return fresh_data

    # ------------------------------------------------------------------ #
    # Monitoring loop
    # ------------------------------------------------------------------ #
    def watch_cycle(self):
        """
        Perform a single monitoring cycle.
        """
        self.log.debug("Running graduation check")

        with self.db.get_session() as session:
            tokens_to_watch = session.query(Token).filter_by(is_safe=True, is_graduated=False).all()

        self.log.debug("Monitoring %s tokens for graduation", len(tokens_to_watch))
        graduated_count = 0

        for token in tokens_to_watch:
            try:
                if self.db.is_blacklisted(token.mint_address):
                    continue

                fresh_data = self.update_token_data(token)
                if not fresh_data:
                    continue

                if self.check_graduation_criteria(token, fresh_data):
                    self.db.mark_as_graduated(token.mint_address)
                    graduated_count += 1
                    self.log.info("Token graduated: %s", token.symbol or token.mint_address)
                    self.db.add_to_watchlist(
                        token.mint_address,
                        "whitelist",
                        reason="graduated",
                        details={
                            "symbol": token.symbol,
                            "name": token.name,
                            "market_cap": fresh_data.get("market_cap"),
                            "liquidity_usd": fresh_data.get("liquidity_usd"),
                            "holder_count": fresh_data.get("holder_count"),
                        },
                    )

            except Exception as exc:
                self.log.exception("Error checking token %s: %s", token.mint_address, exc)

        if graduated_count:
            self.log.info("%s tokens graduated this cycle", graduated_count)

    def start(self):
        """
        Start continuous monitoring.
        """
        self.log.info("Graduation watcher started | interval=%ss criteria=%s", self.config["check_interval_seconds"], self.config)

        self.running = True

        while self.running:
            try:
                self.watch_cycle()
                time.sleep(self.config["check_interval_seconds"])
            except KeyboardInterrupt:
                self.log.info("Graduation watcher interrupted by user")
                self.running = False
            except Exception as exc:
                self.log.exception("Error in graduation watcher loop: %s", exc)
                time.sleep(10)

    def stop(self):
        """
        Stop monitoring.
        """
        self.log.info("Graduation watcher stopping")
        self.running = False

    def update_config(self, new_config: Dict):
        """
        Update thresholds at runtime.
        """
        self.config.update(new_config)
        self.log.info("Graduation config updated: %s", self.config)
