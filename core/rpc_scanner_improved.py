"""
Improved off-chain scanner that monitors public data sources for fresh mints.

We already rely on Helius webhooks for blockchain triggers, but off-chain data
feeds let us surface brand-new pools the second they appear on Solana DEXes.
This module polls GeckoTerminal's `/new_pools` endpoint and forwards anything
we have not seen before to the main TokenScanner.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from threading import Event
from typing import Dict, List, Optional

import requests

from core.logger import get_logger

class RPCScanner:
    """
    Scan GeckoTerminal for newly listed Solana pools and push them to the scanner.
    """

    GECKO_NEW_POOLS_URL = "https://api.geckoterminal.com/api/v2/networks/solana/new_pools"
    GECKO_TOKEN_URL = "https://api.geckoterminal.com/api/v2/networks/solana/tokens/{mint}"

    def __init__(self, helius_api_key: str):
        self.api_key = helius_api_key
        self.seen_tokens: set[str] = set()
        self.stop_event = Event()
        self.last_checked: Optional[float] = None
        self.log = get_logger("gecko_scanner")

        # Default headers to avoid bot detection
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
        }

    # ------------------------------------------------------------------ #
    # Polling loop
    # ------------------------------------------------------------------ #
    def start_polling(self, scanner_instance, interval: int = 30):
        """
        Continuously fetch new pools from GeckoTerminal and push them to the scanner.
        """
        self.log.info("GeckoTerminal polling started interval=%ss", interval)
        self.stop_event.clear()

        while not self.stop_event.is_set():
            try:
                self.log.debug("Checking GeckoTerminal for new pools")
                pools = self._fetch_new_pools()

                if pools:
                    self.log.info("Found %s GeckoTerminal pools worth scanning", len(pools))
                    for pool in pools:
                        mint = pool["base_mint"]
                        context = pool["context"]
                        scanner_instance.process_mint_event(mint, context)
                        time.sleep(1.5)
                else:
                    self.log.debug("No fresh GeckoTerminal pools detected")

            except Exception as exc:  # pragma: no cover - network issues
                self.log.warning("GeckoTerminal polling error: %s", exc)

            self.stop_event.wait(interval)

        self.log.info("GeckoTerminal polling stopped")

    def stop(self):
        """Signal the polling loop to exit."""
        self.stop_event.set()

    # ------------------------------------------------------------------ #
    # GeckoTerminal helpers
    # ------------------------------------------------------------------ #
    def _fetch_new_pools(self) -> List[Dict]:
        """
        Retrieve new pools and return formatted entries we haven't processed yet.
        """
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = requests.get(self.GECKO_NEW_POOLS_URL, headers=self.headers, timeout=10)

                # Check for HTML responses (Cloudflare protection)
                if response.text and response.text.strip().startswith(("<!DOCTYPE", "<html", "<!--")):
                    self.log.warning("Received HTML instead of JSON from GeckoTerminal (attempt %s/%s)", attempt + 1, max_retries)
                    if attempt < max_retries - 1:
                        time.sleep(2 ** attempt)  # Exponential backoff
                        continue
                    return []

                response.raise_for_status()
                break
            except (requests.RequestException, Exception) as exc:
                self.log.warning("GeckoTerminal request failed (attempt %s/%s): %s", attempt + 1, max_retries, exc)
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                    continue
                return []

        results = []
        data = response.json().get("data", [])
        now = datetime.now(timezone.utc)

        for entry in data:
            attributes = entry.get("attributes", {})
            relationships = entry.get("relationships", {})
            base_info = relationships.get("base_token", {}).get("data", {})

            base_id = base_info.get("id")
            if not base_id:
                continue

            dex_id = relationships.get("dex", {}).get("data", {}).get("id")
            if dex_id != "pump-fun":
                continue

            created_at = attributes.get("pool_created_at")
            if created_at:
                try:
                    created_dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                    age_seconds = (now - created_dt).total_seconds()
                    if age_seconds > 600:  # older than 10 minutes
                        continue
                except Exception:
                    pass

            mint = base_id.replace("solana_", "")
            if mint in self.seen_tokens:
                continue

            token_meta = self._fetch_token_metadata(mint)
            metadata_hint = {
                "name": token_meta.get("name"),
                "symbol": token_meta.get("symbol"),
                "decimals": token_meta.get("decimals"),
            }

            liquidity_usd = self._safe_float(attributes.get("reserve_in_usd"))
            fdv = self._safe_float(attributes.get("fdv_usd"))
            volume_value = attributes.get("volume_usd")
            if isinstance(volume_value, dict):
                volume_24h = self._safe_float(volume_value.get("h24"))
            else:
                volume_24h = self._safe_float(volume_value)

            context = {
                "source": "geckoterminal",
                "geckoterminal": {
                    "pool": entry,
                    "token": token_meta,
                },
                "metadata_hint": {k: v for k, v in metadata_hint.items() if v},
                "dex_hint": {
                    "liquidity_usd": liquidity_usd,
                    "fdv_usd": fdv,
                    "volume_24h": volume_24h,
                    "pool_name": attributes.get("name"),
                    "pool_address": entry.get("id", "").replace("solana_", ""),
                    "dex": relationships.get("dex", {}).get("data", {}).get("id"),
                },
            }

            self.seen_tokens.add(mint)
            results.append({"base_mint": mint, "context": context})

        return results

    def _fetch_token_metadata(self, mint: str) -> Dict:
        """
        Fetch token metadata from GeckoTerminal, returning a dictionary with
        useful fields. Falls back gracefully if metadata is missing.
        """
        max_retries = 2
        for attempt in range(max_retries):
            try:
                resp = requests.get(self.GECKO_TOKEN_URL.format(mint=mint), headers=self.headers, timeout=10)
                if resp.status_code != 200:
                    if attempt < max_retries - 1:
                        time.sleep(1)
                        continue
                    return {}

                # Check for HTML responses (Cloudflare protection)
                if resp.text and resp.text.strip().startswith(("<!DOCTYPE", "<html", "<!--")):
                    self.log.debug("Received HTML instead of JSON for token %s (attempt %s/%s)", mint, attempt + 1, max_retries)
                    if attempt < max_retries - 1:
                        time.sleep(1)
                        continue
                    return {}

                data = resp.json().get("data", {})
                attributes = data.get("attributes", {})

                return {
                    "name": attributes.get("name"),
                    "symbol": attributes.get("symbol"),
                    "decimals": attributes.get("decimals"),
                    "image_url": attributes.get("image_url"),
                    "market_cap_usd": self._safe_float(attributes.get("market_cap_usd")),
                    "fdv_usd": self._safe_float(attributes.get("fdv_usd")),
                }
            except Exception as exc:  # pragma: no cover - network issues
                self.log.debug("Gecko metadata fetch failed for %s (attempt %s/%s): %s", mint, attempt + 1, max_retries, exc)
                if attempt < max_retries - 1:
                    time.sleep(1)
                    continue
                return {}
        return {}

    @staticmethod
    def _safe_float(value) -> float:
        """Convert mixed string/float values into floats safely."""
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0
