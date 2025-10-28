"""
Multi-source token discovery system - collects EVERY new memecoin from ALL sources.

This system discovers tokens from multiple sources and enriches them with comprehensive data.
NO FILTERING - we want EVERYTHING so ML can learn what's bullshit.

Sources:
1. Discovery: DexScreener, GeckoTerminal, Pump.fun, Helius webhooks
2. Enrichment: DexScreener, Birdeye, Helius, RugCheck, SolanaFM, Solscan

Rate limits:
- DexScreener: ~60 req/min (free)
- GeckoTerminal: ~30 req/min (free)
- Helius: depends on plan
- Birdeye: ~100 req/min (public)
- RugCheck: ~20 req/min (free)
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
import aiohttp

from core.http_client import HttpClient, HttpError
from core.logger import get_logger


class MultiSourceDiscovery:
    """
    Discovers new tokens from multiple sources with rate-limit awareness.
    """

    def __init__(self, helius_api_key: str = None):
        self.log = get_logger("multi_discovery")
        self.http = HttpClient("multi_discovery")
        self.helius_key = helius_api_key

        # Track discovered tokens to avoid duplicates
        self.discovered_tokens: Set[str] = set()

        # Rate limiting (requests per minute)
        self.rate_limits = {
            "dexscreener": {"rpm": 60, "last_call": 0, "calls_this_minute": 0},
            "geckoterminal": {"rpm": 30, "last_call": 0, "calls_this_minute": 0},
            "birdeye": {"rpm": 100, "last_call": 0, "calls_this_minute": 0},
            "rugcheck": {"rpm": 20, "last_call": 0, "calls_this_minute": 0},
            "solscan": {"rpm": 30, "last_call": 0, "calls_this_minute": 0},
        }

        self.log.info("Multi-source discovery initialized")

    async def _check_rate_limit(self, source: str):
        """Check and enforce rate limits"""
        limits = self.rate_limits.get(source)
        if not limits:
            return

        now = time.time()

        # Reset counter every minute
        if now - limits["last_call"] > 60:
            limits["calls_this_minute"] = 0
            limits["last_call"] = now

        # If we've hit the limit, wait
        if limits["calls_this_minute"] >= limits["rpm"]:
            wait_time = 60 - (now - limits["last_call"])
            if wait_time > 0:
                self.log.debug(f"Rate limit for {source}, waiting {wait_time:.1f}s")
                await asyncio.sleep(wait_time)
                limits["calls_this_minute"] = 0
                limits["last_call"] = time.time()

        limits["calls_this_minute"] += 1

    # ============================================================================
    # DISCOVERY SOURCES - Find new tokens
    # ============================================================================

    async def discover_from_dexscreener_latest(
        self, session: aiohttp.ClientSession
    ) -> List[Dict]:
        """
        Discover NEWLY CREATED tokens from DexScreener.
        Gets tokens created in the LAST FEW HOURS - TRUE real-time discovery!
        """
        await self._check_rate_limit("dexscreener")

        tokens = []

        # METHOD 1: Get latest pairs sorted by creation time
        try:
            # This gets pairs sorted by age (newest first)
            data = await self.http.get_json(
                "https://api.dexscreener.com/latest/dex/pairs/solana",
                session=session,
                metrics_tag="dexscreener:latest_pairs"
            )

            pairs = data.get("pairs", [])[:50]  # Get 50 newest

            for pair in pairs:
                base_token = pair.get("baseToken", {})
                token_address = base_token.get("address")

                # Skip if we've seen it before
                if not token_address or token_address in self.discovered_tokens:
                    continue

                # Get pair age
                pair_created = pair.get("pairCreatedAt", 0)
                import time
                age_hours = (time.time() * 1000 - pair_created) / (1000 * 60 * 60) if pair_created else 999

                # Only tokens created in last 2 HOURS (fresh new tokens only!)
                if age_hours > 2:
                    continue

                tokens.append({
                    "mint_address": token_address,
                    "source": "dexscreener_latest_pairs",
                    "discovered_at": datetime.utcnow().isoformat(),
                    "age_hours": age_hours,
                    "metadata_hint": {
                        "symbol": base_token.get("symbol"),
                        "name": base_token.get("name"),
                        "price_usd": pair.get("priceUsd"),
                        "liquidity_usd": pair.get("liquidity", {}).get("usd"),
                        "volume_24h": pair.get("volume", {}).get("h24"),
                        "price_change_24h": pair.get("priceChange", {}).get("h24"),
                        "pair_address": pair.get("pairAddress"),
                        "pair_created_at": pair_created,
                    }
                })
                self.discovered_tokens.add(token_address)

            if tokens:
                self.log.info(f"DexScreener latest pairs: found {len(tokens)} new tokens")
                return tokens

        except Exception as e:
            self.log.warning(f"DexScreener latest pairs failed: {e}")

        # METHOD 2: Search for recent Solana activity
        try:
            # Search returns active tokens
            data = await self.http.get_json(
                "https://api.dexscreener.com/latest/dex/search?q=SOL",
                session=session,
                metrics_tag="dexscreener:search"
            )

            pairs = data.get("pairs", [])[:30]  # Get top 30

            for pair in pairs:
                if pair.get("chainId") != "solana":
                    continue

                base_token = pair.get("baseToken", {})
                token_address = base_token.get("address")

                if token_address and token_address not in self.discovered_tokens:
                    tokens.append({
                        "mint_address": token_address,
                        "source": "dexscreener_search",
                        "discovered_at": datetime.utcnow().isoformat(),
                        "metadata_hint": {
                            "symbol": base_token.get("symbol"),
                            "name": base_token.get("name"),
                            "price_usd": pair.get("priceUsd"),
                            "liquidity_usd": pair.get("liquidity", {}).get("usd"),
                        }
                    })
                    self.discovered_tokens.add(token_address)

            if tokens:
                self.log.info(f"DexScreener search: found {len(tokens)} tokens")

        except Exception as e2:
            self.log.warning(f"DexScreener search also failed: {e2}")

        return tokens

    async def discover_from_geckoterminal_new_pools(
        self, session: aiohttp.ClientSession
    ) -> List[Dict]:
        """
        Discover new pools from GeckoTerminal.
        Backup/second source for discovery.
        """
        await self._check_rate_limit("geckoterminal")

        try:
            data = await self.http.get_json(
                "https://api.geckoterminal.com/api/v2/networks/solana/new_pools",
                session=session,
                params={"page": 1},
                metrics_tag="geckoterminal:new_pools"
            )

            tokens = []
            pools = data.get("data", [])

            for pool in pools:
                attributes = pool.get("attributes", {})
                base_token = attributes.get("base_token_price_quote_token")
                token_address = attributes.get("base_token_address")

                if token_address and token_address not in self.discovered_tokens:
                    tokens.append({
                        "mint_address": token_address,
                        "source": "geckoterminal_new_pools",
                        "discovered_at": datetime.utcnow().isoformat(),
                        "metadata_hint": attributes
                    })
                    self.discovered_tokens.add(token_address)

            self.log.info(f"GeckoTerminal: found {len(tokens)} new tokens")
            return tokens

        except Exception as e:
            self.log.warning(f"GeckoTerminal discovery failed: {e}")
            return []

    async def discover_from_birdeye_new_listings(
        self, session: aiohttp.ClientSession
    ) -> List[Dict]:
        """
        Discover newly listed tokens from Birdeye.
        """
        await self._check_rate_limit("birdeye")

        try:
            # Birdeye has a "new listings" endpoint
            data = await self.http.get_json(
                "https://public-api.birdeye.so/defi/tokenlist",
                session=session,
                params={
                    "sort_by": "created_at",
                    "sort_type": "desc",
                    "limit": 50
                },
                headers={"X-API-KEY": "public"},
                metrics_tag="birdeye:new_listings"
            )

            tokens = []
            items = data.get("data", {}).get("tokens", [])

            for item in items:
                token_address = item.get("address")
                if token_address and token_address not in self.discovered_tokens:
                    tokens.append({
                        "mint_address": token_address,
                        "source": "birdeye_new_listings",
                        "discovered_at": datetime.utcnow().isoformat(),
                        "metadata_hint": item
                    })
                    self.discovered_tokens.add(token_address)

            self.log.info(f"Birdeye: found {len(tokens)} new tokens")
            return tokens

        except Exception as e:
            self.log.warning(f"Birdeye discovery failed: {e}")
            return []

    # ============================================================================
    # ENRICHMENT SOURCES - Get detailed data for each token
    # ============================================================================

    async def enrich_with_rugcheck(
        self, mint_address: str, session: aiohttp.ClientSession
    ) -> Optional[Dict]:
        """
        Get safety scan from RugCheck API.
        This tells us if it's a rug BEFORE we invest.
        """
        await self._check_rate_limit("rugcheck")

        try:
            data = await self.http.get_json(
                f"https://api.rugcheck.xyz/v1/tokens/{mint_address}/report",
                session=session,
                metrics_tag="rugcheck:report"
            )

            # Extract key safety metrics
            return {
                "rugcheck_score": data.get("score"),
                "rugcheck_risks": data.get("risks", []),
                "mint_authority_status": data.get("mintAuthority"),
                "freeze_authority_status": data.get("freezeAuthority"),
                "lp_locked": data.get("lpLocked", False),
                "lp_burn_pct": data.get("lpBurnPct", 0),
                "top_holders": data.get("topHolders", []),
                "is_rugpull": data.get("rugpull", False),
                "raw": data
            }

        except Exception as e:
            self.log.debug(f"RugCheck failed for {mint_address}: {e}")
            return None

    async def enrich_with_solscan(
        self, mint_address: str, session: aiohttp.ClientSession
    ) -> Optional[Dict]:
        """
        Get token info from Solscan as backup/verification.
        """
        await self._check_rate_limit("solscan")

        try:
            data = await self.http.get_json(
                f"https://api.solscan.io/token/meta",
                session=session,
                params={"token": mint_address},
                metrics_tag="solscan:meta"
            )

            return {
                "holder_count": data.get("holder"),
                "supply": data.get("supply"),
                "decimals": data.get("decimals"),
                "price": data.get("price"),
                "volume_24h": data.get("volume24h"),
                "raw": data
            }

        except Exception as e:
            self.log.debug(f"Solscan failed for {mint_address}: {e}")
            return None

    # ============================================================================
    # MAIN DISCOVERY LOOP
    # ============================================================================

    async def discover_all_sources(self) -> List[Dict]:
        """
        Run discovery from ALL sources in parallel.
        Returns list of new tokens to process.
        """
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            # Run all discovery sources in parallel
            tasks = [
                self.discover_from_dexscreener_latest(session),
                self.discover_from_geckoterminal_new_pools(session),
                self.discover_from_birdeye_new_listings(session),
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Flatten results
            all_tokens = []
            for result in results:
                if isinstance(result, list):
                    all_tokens.extend(result)
                elif isinstance(result, Exception):
                    self.log.warning(f"Discovery task failed: {result}")

            # Remove duplicates (same token from multiple sources)
            unique_tokens = {}
            for token in all_tokens:
                mint = token["mint_address"]
                if mint not in unique_tokens:
                    unique_tokens[mint] = token
                else:
                    # Merge sources if token found in multiple places
                    existing = unique_tokens[mint]
                    if "sources" not in existing:
                        existing["sources"] = [existing["source"]]
                    existing["sources"].append(token["source"])

            return list(unique_tokens.values())

    async def enrich_token_comprehensive(
        self, mint_address: str
    ) -> Optional[Dict]:
        """
        Enrich a single token with data from ALL sources.
        This gets EVERYTHING we can about a token.
        """
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            # Run all enrichment sources in parallel
            tasks = [
                self.enrich_with_rugcheck(mint_address, session),
                self.enrich_with_solscan(mint_address, session),
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            enrichment = {}
            for i, result in enumerate(results):
                if isinstance(result, dict):
                    source = ["rugcheck", "solscan"][i]
                    enrichment[source] = result
                elif isinstance(result, Exception):
                    self.log.debug(f"Enrichment task {i} failed: {result}")

            return enrichment if enrichment else None

    def run_discovery_sync(self) -> List[Dict]:
        """Synchronous wrapper for discovery"""
        try:
            return asyncio.run(self.discover_all_sources())
        except RuntimeError:
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(self.discover_all_sources())
            finally:
                loop.close()

    def enrich_token_sync(self, mint_address: str) -> Optional[Dict]:
        """Synchronous wrapper for enrichment"""
        try:
            return asyncio.run(self.enrich_token_comprehensive(mint_address))
        except RuntimeError:
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(
                    self.enrich_token_comprehensive(mint_address)
                )
            finally:
                loop.close()


# ============================================================================
# DISCOVERY SCHEDULER - Orchestrates polling from all sources
# ============================================================================


class DiscoveryScheduler:
    """
    Schedules discovery from multiple sources with different intervals.

    Strategy:
    - High priority (every 30s): DexScreener latest, Pump.fun
    - Medium priority (every 2m): GeckoTerminal new pools
    - Low priority (every 5m): Birdeye new listings
    """

    def __init__(self, discovery: MultiSourceDiscovery, callback):
        self.discovery = discovery
        self.callback = callback  # Function to call with new tokens
        self.log = get_logger("discovery_scheduler")
        self.running = False

        # Last run times
        self.last_runs = {
            "high_priority": 0,
            "medium_priority": 0,
            "low_priority": 0,
        }

    async def run_forever(self):
        """Run discovery scheduler forever"""
        self.running = True
        self.log.info("Discovery scheduler started")
        print("[Discovery Scheduler] Starting continuous discovery...")

        # Track when we last cleared the cache
        last_cache_clear = time.time()

        while self.running:
            now = time.time()

            # Clear discovery cache every 5 minutes to allow re-discovering trending tokens
            if now - last_cache_clear > 300:  # 5 minutes
                cache_size = len(self.discovery.discovered_tokens)
                self.discovery.discovered_tokens.clear()
                print(f"[Discovery Scheduler] Cleared {cache_size} tokens from cache - will re-discover trending ones!")
                last_cache_clear = now

            # High priority sources (every 30 seconds)
            if now - self.last_runs["high_priority"] >= 30:
                print(f"[Discovery Scheduler] Running high-priority discovery (DexScreener)...")
                async with aiohttp.ClientSession() as session:
                    tokens = await self.discovery.discover_from_dexscreener_latest(session)
                    if tokens:
                        print(f"[Discovery Scheduler] Found {len(tokens)} new tokens!")
                        await self.callback(tokens)
                    else:
                        print(f"[Discovery Scheduler] No new tokens this round (already seen or none available)")
                self.last_runs["high_priority"] = now

            # Medium priority sources (every 1 minute - increased from 2)
            if now - self.last_runs["medium_priority"] >= 60:
                print(f"[Discovery Scheduler] Running medium-priority discovery (GeckoTerminal)...")
                async with aiohttp.ClientSession() as session:
                    tokens = await self.discovery.discover_from_geckoterminal_new_pools(session)
                    if tokens:
                        print(f"[Discovery Scheduler] Found {len(tokens)} new tokens!")
                        await self.callback(tokens)
                self.last_runs["medium_priority"] = now

            # Low priority sources (every 2 minutes - increased from 5)
            if now - self.last_runs["low_priority"] >= 120:
                print(f"[Discovery Scheduler] Running low-priority discovery (Birdeye)...")
                async with aiohttp.ClientSession() as session:
                    tokens = await self.discovery.discover_from_birdeye_new_listings(session)
                    if tokens:
                        print(f"[Discovery Scheduler] Found {len(tokens)} new tokens!")
                        await self.callback(tokens)
                self.last_runs["low_priority"] = now

            # Sleep for 1 second between checks
            await asyncio.sleep(1)

    def start_background(self):
        """Start scheduler in background thread"""
        import threading

        def run_loop():
            try:
                asyncio.run(self.run_forever())
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self.run_forever())

        thread = threading.Thread(target=run_loop, daemon=True)
        thread.start()
        self.log.info("Scheduler running in background")

    def stop(self):
        """Stop the scheduler"""
        self.running = False
        self.log.info("Scheduler stopped")
