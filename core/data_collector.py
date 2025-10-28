"""
Data collector responsible for enriching freshly discovered Solana tokens.

Fetches metadata, liquidity, authority, and holder intelligence from multiple
providers with parallel async requests, retry/backoff semantics, and basic
caching to avoid hammering upstream APIs.
"""

from __future__ import annotations

import asyncio
import threading
import time
from datetime import datetime
from typing import Any, Awaitable, Dict, List, Optional, Tuple

import aiohttp

from core.birdeye_client import BirdeyeClient
from core.http_client import HttpClient, HttpError
from core.logger import get_logger


class DataCollector:
    """
    Fetches detailed information about Solana tokens using Helius + public APIs.
    """

    def __init__(self, helius_api_key: str, *, birdeye_api_key: Optional[str] = None):
        self.api_key = helius_api_key
        self.base_url = "https://api.helius.xyz/v0"
        self.rpc_url = f"https://mainnet.helius-rpc.com/?api-key={helius_api_key}"
        self.log = get_logger("collector")
        self.http = HttpClient("collector")
        self._cache: Dict[str, Dict[str, Tuple[float, Any]]] = {}
        self._cache_lock = threading.Lock()
        self.birdeye_key = birdeye_api_key
        self._birdeye_client = BirdeyeClient(birdeye_api_key, self.http) if birdeye_api_key else None

    # ------------------------------------------------------------------ #
    # Cache helpers
    # ------------------------------------------------------------------ #
    def _cache_get(self, bucket: str, key: str) -> Any:
        with self._cache_lock:
            bucket_map = self._cache.get(bucket)
            if not bucket_map:
                return None
            entry = bucket_map.get(key)
            if not entry:
                return None
            expires, value = entry
            if expires < time.time():
                bucket_map.pop(key, None)
                return None
            return value

    def _cache_set(self, bucket: str, key: str, value: Any, ttl: float):
        with self._cache_lock:
            bucket_map = self._cache.setdefault(bucket, {})
            bucket_map[key] = (time.time() + ttl, value)

    def _trim_payload(self, payload: Any, depth: int = 0, max_depth: int = 3, max_items: int = 25) -> Any:
        """
        Reduce payload size for storage in metadata while keeping structure.
        """
        if payload is None:
            return None
        if depth >= max_depth:
            if isinstance(payload, (dict, list, tuple)):
                return "[truncated]"
            if isinstance(payload, str) and len(payload) > 256:
                return payload[:256] + "...(truncated)"
            return payload

        if isinstance(payload, dict):
            trimmed: Dict[str, Any] = {}
            for idx, (key, value) in enumerate(payload.items()):
                if idx >= max_items:
                    trimmed["..."] = "truncated"
                    break
                trimmed[key] = self._trim_payload(value, depth + 1, max_depth, max_items)
            return trimmed

        if isinstance(payload, list):
            trimmed_list = [
                self._trim_payload(item, depth + 1, max_depth, max_items)
                for item in payload[:max_items]
            ]
            if len(payload) > max_items:
                trimmed_list.append("...(truncated)")
            return trimmed_list

        if isinstance(payload, str) and len(payload) > 256:
            return payload[:256] + "...(truncated)"

        return payload

    def _safe_float(self, value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def _resolve_task(self, source: str, result: Any, mint_address: str):
        if isinstance(result, HttpError):
            if result.status == 429:
                raise result
            self.log.warning("%s fetch failed for %s: %s", source, mint_address, result)
            return None
        if isinstance(result, Exception):
            self.log.warning("%s fetch error for %s: %s", source, mint_address, result)
            return None
        return result

    # ------------------------------------------------------------------ #
    # Async fetch helpers
    # ------------------------------------------------------------------ #
    async def _fetch_helius_metadata(
        self, mint_address: str, session: aiohttp.ClientSession
    ) -> Optional[Dict[str, Any]]:
        cached = self._cache_get("helius_metadata", mint_address)
        if cached:
            return cached

        payload = {
            "mintAccounts": [mint_address],
            "includeOffChain": True,
            "disableCache": False,
        }
        post_url = f"{self.base_url}/token-metadata?api-key={self.api_key}"

        try:
            data = await self.http.post_json(
                post_url,
                payload,
                session=session,
                metrics_tag="helius:token_metadata:post",
            )
        except HttpError as exc:
            if exc.status in {400, 404, 405}:
                try:
                    data = await self.http.get_json(
                        f"{self.base_url}/token-metadata",
                        session=session,
                        params={"api-key": self.api_key, "mint-accounts": mint_address},
                        metrics_tag="helius:token_metadata:get",
                    )
                except HttpError as fallback_exc:
                    if fallback_exc.status == 429:
                        raise
                    self.log.warning(
                        "Helius metadata fallback failed for %s: %s",
                        mint_address,
                        fallback_exc,
                    )
                    return None
            elif exc.status == 429:
                raise
            else:
                self.log.warning("Helius metadata fetch failed for %s: %s", mint_address, exc)
                return None

        if not data:
            return None

        account_data: Dict[str, Any] = {}
        if isinstance(data, list) and data:
            account_data = data[0].get("account", {}).get("data", {}) or {}
            raw_payload = data[0]
        elif isinstance(data, dict):
            account_data = data.get("account", {}).get("data", {}) or {}
            raw_payload = data
        else:
            raw_payload = data

        metadata = {
            "name": account_data.get("name"),
            "symbol": account_data.get("symbol"),
            "decimals": account_data.get("decimals"),
            "supply": account_data.get("supply"),
            "raw": self._trim_payload(raw_payload),
        }
        self._cache_set("helius_metadata", mint_address, metadata, ttl=180)
        return metadata

    async def _fetch_gecko_metadata(
        self, mint_address: str, session: aiohttp.ClientSession
    ) -> Optional[Dict[str, Any]]:
        cached = self._cache_get("gecko_metadata", mint_address)
        if cached:
            return cached

        url = f"https://api.geckoterminal.com/api/v2/networks/solana/tokens/{mint_address}"
        try:
            data = await self.http.get_json(
                url,
                session=session,
                metrics_tag="gecko:token",
            )
        except HttpError as exc:
            if exc.status == 429:
                raise
            self.log.debug("Gecko metadata fetch failed for %s: %s", mint_address, exc)
            return None

        attributes = data.get("data", {}).get("attributes", {})
        metadata = {
            "name": attributes.get("name"),
            "symbol": attributes.get("symbol"),
            "decimals": attributes.get("decimals"),
            "market_cap_usd": self._safe_float(attributes.get("market_cap_usd")),
            "fdv_usd": self._safe_float(attributes.get("fdv_usd")),
            "raw": self._trim_payload(attributes),
        }
        self._cache_set("gecko_metadata", mint_address, metadata, ttl=180)
        return metadata

    async def _fetch_dex_data(
        self, mint_address: str, session: aiohttp.ClientSession
    ) -> Optional[Dict[str, Any]]:
        cached = self._cache_get("dex_data", mint_address)
        if cached:
            return cached

        url = f"https://api.dexscreener.com/latest/dex/tokens/{mint_address}"
        headers = {
            "accept": "application/json",
            "user-agent": "Mozilla/5.0 (meme-beta.5)",
        }
        try:
            data = await self.http.get_json(
                url,
                session=session,
                metrics_tag="dexscreener:token",
                headers=headers,
            )
        except HttpError as exc:
            if exc.status == 429:
                raise
            self.log.debug("DexScreener fetch failed for %s: %s", mint_address, exc)
            return None

        pairs = data.get("pairs") or []
        if not pairs:
            return None

        best_pair = max(
            pairs,
            key=lambda item: self._safe_float(item.get("liquidity", {}).get("usd")),
        )

        # Extract trade data for ML analysis
        txns = best_pair.get("txns", {}) or {}
        h24_txns = txns.get("h24", {}) or {}
        m5_txns = txns.get("m5", {}) or {}

        # Get buy/sell counts from different timeframes
        buy_count_24h = int(self._safe_float(h24_txns.get("buys", 0)))
        sell_count_24h = int(self._safe_float(h24_txns.get("sells", 0)))
        buy_count_5m = int(self._safe_float(m5_txns.get("buys", 0)))
        sell_count_5m = int(self._safe_float(m5_txns.get("sells", 0)))

        dex_info = {
            "liquidity_usd": self._safe_float(best_pair.get("liquidity", {}).get("usd")),
            "price_usd": self._safe_float(best_pair.get("priceUsd")),
            "volume_24h": self._safe_float(best_pair.get("volume", {}).get("h24")),
            "volume_5m": self._safe_float(best_pair.get("volume", {}).get("m5")),
            "market_cap": self._safe_float(best_pair.get("fdv")),
            "pool_address": best_pair.get("pairAddress"),
            "dex_name": best_pair.get("dexId", "unknown"),
            "price_change_24h": self._safe_float(best_pair.get("priceChange", {}).get("h24")),
            "price_change_5m": self._safe_float(best_pair.get("priceChange", {}).get("m5")),

            # Trade counts - CRITICAL for quick-profit detection
            "buy_count_24h": buy_count_24h,
            "sell_count_24h": sell_count_24h,
            "buy_count_5m": buy_count_5m,
            "sell_count_5m": sell_count_5m,
            "total_trades_24h": buy_count_24h + sell_count_24h,
            "buy_sell_ratio_24h": buy_count_24h / max(sell_count_24h, 1) if sell_count_24h > 0 else buy_count_24h,

            "raw": self._trim_payload(best_pair),
        }
        self._cache_set("dex_data", mint_address, dex_info, ttl=45)
        return dex_info

    async def _rpc_post(
        self,
        method: str,
        params: List[Any],
        session: aiohttp.ClientSession,
    ) -> Dict[str, Any]:
        payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        return await self.http.post_json(
            self.rpc_url,
            payload,
            session=session,
            metrics_tag=f"solana_rpc:{method}",
        )

    async def _fetch_token_supply(
        self, mint_address: str, session: aiohttp.ClientSession
    ) -> Tuple[float, Dict[str, Any]]:
        cached = self._cache_get("token_supply", mint_address)
        if cached:
            return cached

        data = await self._rpc_post("getTokenSupply", [mint_address], session)
        value = data.get("result", {}).get("value", {}) or {}
        supply = self._safe_float(value.get("uiAmount"))
        result = (supply, self._trim_payload(value))
        self._cache_set("token_supply", mint_address, result, ttl=120)
        return result

    async def _fetch_token_accounts(
        self, mint_address: str, session: aiohttp.ClientSession
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        cached = self._cache_get("token_accounts", mint_address)
        if cached:
            return cached

        data = await self._rpc_post("getTokenLargestAccounts", [mint_address], session)
        accounts = data.get("result", {}).get("value", []) or []
        result = (accounts, self._trim_payload(accounts))
        self._cache_set("token_accounts", mint_address, result, ttl=60)
        return result

    async def check_mint_authority_async(
        self, mint_address: str, session: aiohttp.ClientSession
    ) -> Dict[str, Any]:
        cached = self._cache_get("mint_authority", mint_address)
        if cached:
            return cached

        data = await self._rpc_post(
            "getAccountInfo",
            [mint_address, {"encoding": "jsonParsed"}],
            session,
        )
        parsed = data.get("result", {}).get("value", {}) or {}
        info = parsed.get("data", {}).get("parsed", {}).get("info", {}) or {}
        result = {
            "mint_authority": info.get("mintAuthority"),
            "freeze_authority": info.get("freezeAuthority"),
            "raw": self._trim_payload(info),
        }
        self._cache_set("mint_authority", mint_address, result, ttl=180)
        return result

    async def _fetch_holder_data(
        self, mint_address: str, session: aiohttp.ClientSession
    ) -> Dict[str, Any]:
        """
        Fetch holder data - FIXED VERSION

        IMPORTANT: getTokenLargestAccounts only returns TOP holders (max 20),
        NOT the total holder count! We need to use getProgramAccounts or external APIs.
        """
        try:
            accounts, accounts_raw = await self._fetch_token_accounts(mint_address, session)
        except HttpError as exc:
            if exc.status == 429:
                raise
            self.log.debug("Holder accounts fetch failed for %s: %s", mint_address, exc)
            accounts, accounts_raw = [], {}

        try:
            supply, supply_raw = await self._fetch_token_supply(mint_address, session)
        except HttpError as exc:
            if exc.status == 429:
                raise
            self.log.debug("Token supply fetch failed for %s: %s", mint_address, exc)
            supply, supply_raw = 0.0, {}

        # Try to get ACTUAL holder count using getProgramAccounts
        actual_holder_count = await self._get_actual_holder_count(mint_address, session)

        if not accounts:
            return {
                "holder_count": actual_holder_count or 0,
                "top_holder_percentage": 0.0,
                "supply": supply,
                "raw": {"accounts": accounts_raw, "supply": supply_raw},
                "holder_count_source": "rpc_program_accounts" if actual_holder_count else "none"
            }

        total_known = sum(self._safe_float(acc.get("uiAmount")) for acc in accounts)
        effective_supply = supply or total_known
        if effective_supply <= 0:
            top_pct = 0.0
        else:
            top_holder = max(accounts, key=lambda acc: self._safe_float(acc.get("uiAmount")))
            top_pct = (self._safe_float(top_holder.get("uiAmount")) / effective_supply) * 100

        # Use actual count if available, otherwise use len(accounts) as MINIMUM
        holder_count = actual_holder_count if actual_holder_count else len(accounts)

        holder_summary = {
            "holder_count": holder_count,
            "top_holder_percentage": top_pct,
            "supply": effective_supply,
            "raw": {"accounts": accounts_raw, "supply": supply_raw},
            "holder_count_source": "rpc_program_accounts" if actual_holder_count else "top_accounts_only",
            "holder_count_is_estimate": actual_holder_count is None
        }
        return holder_summary

    async def _get_actual_holder_count(
        self, mint_address: str, session: aiohttp.ClientSession
    ) -> Optional[int]:
        """
        Get ACTUAL holder count using getProgramAccounts

        This queries the Token Program for all accounts holding this mint.
        WARNING: This can be expensive for tokens with many holders!
        """
        cached = self._cache_get("actual_holder_count", mint_address)
        if cached:
            return cached

        try:
            # Query the Token Program for all accounts with this mint
            data = await self._rpc_post(
                "getProgramAccounts",
                [
                    "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",  # SPL Token Program
                    {
                        "encoding": "jsonParsed",
                        "filters": [
                            {
                                "dataSize": 165  # Size of token account
                            },
                            {
                                "memcmp": {
                                    "offset": 0,
                                    "bytes": mint_address  # Filter by mint address
                                }
                            }
                        ]
                    }
                ],
                session
            )

            accounts = data.get("result", []) or []

            # Count only accounts with non-zero balance
            holder_count = 0
            for account in accounts:
                try:
                    parsed = account.get("account", {}).get("data", {}).get("parsed", {})
                    info = parsed.get("info", {})
                    token_amount = info.get("tokenAmount", {})
                    amount = self._safe_float(token_amount.get("uiAmount", 0))

                    if amount > 0:
                        holder_count += 1
                except:
                    continue

            if holder_count > 0:
                self._cache_set("actual_holder_count", mint_address, holder_count, ttl=60)
                return holder_count

            return None

        except Exception as exc:
            self.log.debug("getProgramAccounts failed for %s: %s", mint_address, exc)
            return None

    async def get_sol_price_async(self, session: aiohttp.ClientSession) -> Optional[float]:
        cached = self._cache_get("sol_price", "latest")
        if cached:
            return cached

        try:
            data = await self.http.get_json(
                "https://api.coingecko.com/api/v3/simple/price",
                session=session,
                params={"ids": "solana", "vs_currencies": "usd"},
                metrics_tag="coingecko:sol_price",
            )
        except HttpError as exc:
            if exc.status == 429:
                raise
            self.log.debug("Failed to refresh SOL price: %s", exc)
            return cached

        price = self._safe_float(data.get("solana", {}).get("usd"))
        if price:
            self._cache_set("sol_price", "latest", price, ttl=120)
            return price
        return cached

    async def _fetch_jupiter_price(
        self, mint_address: str, session: aiohttp.ClientSession
    ) -> Optional[Dict[str, Any]]:
        cached = self._cache_get("jupiter_price", mint_address)
        if cached:
            return cached

        try:
            data = await self.http.get_json(
                "https://price.jup.ag/v4/price",
                session=session,
                params={"ids": mint_address, "vsToken": "USDC"},
                metrics_tag="jupiter:price",
            )
        except HttpError as exc:
            if exc.status == 429:
                raise
            self.log.debug("Jupiter price fetch failed for %s: %s", mint_address, exc)
            return None

        entry = (data.get("data") or {}).get(mint_address)
        if not entry:
            return None

        result = {
            "price_usd": self._safe_float(entry.get("price") or entry.get("priceUsd")),
            "raw": self._trim_payload(entry),
        }
        self._cache_set("jupiter_price", mint_address, result, ttl=45)
        return result

    # ------------------------------------------------------------------ #
    # Aggregate collection
    # ------------------------------------------------------------------ #
    async def collect_full_data_async(
        self, mint_address: str, context: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        context = context or {}
        metadata_hint = context.get("metadata_hint") or {}
        discovery_sources: List[str] = []
        if context.get("source"):
            discovery_sources.append(str(context["source"]))

        self.log.debug("Collecting data for %s", mint_address)

        result: Dict[str, Any] = {
            "mint_address": mint_address,
            "first_seen": datetime.utcnow(),
            "token_metadata": {
                "context": self._trim_payload(context),
                "source_payloads": {},
            },
        }

        for key in ("name", "symbol", "decimals"):
            if metadata_hint.get(key):
                result[key] = metadata_hint[key]

        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            scheduled: List[Tuple[str, Awaitable[Any]]] = [
                ("helius_metadata", self._fetch_helius_metadata(mint_address, session)),
                ("gecko_metadata", self._fetch_gecko_metadata(mint_address, session)),
                ("dex_data", self._fetch_dex_data(mint_address, session)),
                ("mint_authority", self.check_mint_authority_async(mint_address, session)),
                ("holder_data", self._fetch_holder_data(mint_address, session)),
                ("sol_price", self.get_sol_price_async(session)),
            ]
            if self._birdeye_client:
                scheduled.append(
                    ("birdeye_market", self._birdeye_client.fetch_market_data(mint_address, session))
                )
                scheduled.append(
                    ("birdeye_holders", self._birdeye_client.fetch_holder_stats(mint_address, session))
                )
            scheduled.append(("jupiter_price", self._fetch_jupiter_price(mint_address, session)))

            names = [name for name, _ in scheduled]
            coroutines = [coro for _, coro in scheduled]
            raw_results = await asyncio.gather(*coroutines, return_exceptions=True)

        resolved = {
            name: self._resolve_task(name, value, mint_address)
            for name, value in zip(names, raw_results)
        }

        helius_metadata = resolved.get("helius_metadata")
        gecko_metadata = resolved.get("gecko_metadata")
        dex_data = resolved.get("dex_data")
        authority_info = resolved.get("mint_authority")
        holder_data = resolved.get("holder_data")
        sol_price = resolved.get("sol_price")
        birdeye_market = resolved.get("birdeye_market")
        birdeye_holders = resolved.get("birdeye_holders")
        jupiter_price = resolved.get("jupiter_price")

        source_payloads: Dict[str, Any] = result["token_metadata"].setdefault("source_payloads", {})

        if isinstance(helius_metadata, dict):
            for key in ("name", "symbol", "decimals", "supply"):
                value = helius_metadata.get(key)
                if value not in (None, "", "UNK", "Unknown"):
                    result[key] = value
            source_payloads["helius"] = helius_metadata.get("raw")

        if isinstance(gecko_metadata, dict):
            for key in ("name", "symbol", "decimals"):
                if not result.get(key) or str(result[key]).upper() in {"UNK", "UNKNOWN"}:
                    if gecko_metadata.get(key):
                        result[key] = gecko_metadata[key]
            if gecko_metadata.get("market_cap_usd"):
                result.setdefault("market_cap", gecko_metadata["market_cap_usd"])
            source_payloads["geckoterminal"] = gecko_metadata.get("raw")

        if isinstance(authority_info, dict):
            result["mint_authority"] = authority_info.get("mint_authority")
            result["freeze_authority"] = authority_info.get("freeze_authority")
            source_payloads["mint_authority"] = authority_info.get("raw")

        if isinstance(dex_data, dict):
            # Core metrics
            result.update({k: dex_data[k] for k in ("liquidity_usd", "price_usd", "volume_24h", "market_cap") if k in dex_data})
            result["initial_liquidity"] = dex_data.get("liquidity_usd", 0)
            result.setdefault("pool_address", dex_data.get("pool_address"))
            result.setdefault("dex_name", dex_data.get("dex_name"))

            # Trade data for ML - store in token_metadata.trades
            trades_data = {
                "buy_count": dex_data.get("buy_count_24h", 0),
                "sell_count": dex_data.get("sell_count_24h", 0),
                "buy_count_5m": dex_data.get("buy_count_5m", 0),
                "sell_count_5m": dex_data.get("sell_count_5m", 0),
                "total_trades": dex_data.get("total_trades_24h", 0),
                "buy_sell_ratio": dex_data.get("buy_sell_ratio_24h", 0),
                "volume_5m": dex_data.get("volume_5m", 0),
                "price_change_5m": dex_data.get("price_change_5m", 0),
            }
            result["token_metadata"]["trades"] = trades_data

            source_payloads["dexscreener"] = dex_data.get("raw")
        elif "dex_hint" in context:
            dex_hint = context.get("dex_hint") or {}
            result["liquidity_usd"] = self._safe_float(dex_hint.get("liquidity_usd"))
            result["price_usd"] = self._safe_float(
                dex_hint.get("price_usd") if dex_hint.get("price_usd") is not None else result.get("price_usd", 0)
            )
            result["volume_24h"] = self._safe_float(dex_hint.get("volume_24h"))
            result["market_cap"] = self._safe_float(dex_hint.get("fdv_usd"))
            result["initial_liquidity"] = self._safe_float(dex_hint.get("liquidity_usd"))
            result["pool_address"] = dex_hint.get("pool_address") or result.get("pool_address")
            result["dex_name"] = dex_hint.get("dex") or result.get("dex_name")
            source_payloads["dex_hint"] = self._trim_payload(dex_hint)
        else:
            result.setdefault("liquidity_usd", 0.0)
            result.setdefault("price_usd", 0.0)
            result.setdefault("volume_24h", 0.0)
            result.setdefault("market_cap", 0.0)
            result.setdefault("initial_liquidity", 0.0)

        if isinstance(birdeye_market, dict):
            price_override = self._safe_float(
                birdeye_market.get("price_usd") or birdeye_market.get("price")
            )
            liquidity_override = self._safe_float(
                birdeye_market.get("liquidity_usd") or birdeye_market.get("liquidity")
            )
            volume_override = self._safe_float(
                birdeye_market.get("volume_24h") or birdeye_market.get("volume")
            )
            fdv_override = self._safe_float(
                birdeye_market.get("fdv_usd") or birdeye_market.get("market_cap")
            )

            if price_override:
                result["price_usd"] = price_override
            if liquidity_override:
                result["liquidity_usd"] = liquidity_override
                if not result.get("initial_liquidity"):
                    result["initial_liquidity"] = liquidity_override
            if volume_override:
                result["volume_24h"] = volume_override
            if fdv_override:
                result["market_cap"] = fdv_override

            source_payloads["birdeye_market"] = self._trim_payload(
                birdeye_market.get("raw") if isinstance(birdeye_market.get("raw"), (dict, list)) else birdeye_market
            )

        if isinstance(jupiter_price, dict):
            j_price = self._safe_float(jupiter_price.get("price_usd"))
            if j_price and not result.get("price_usd"):
                result["price_usd"] = j_price
            if jupiter_price.get("raw"):
                source_payloads["jupiter"] = jupiter_price.get("raw")

        if isinstance(context.get("pump_portal"), dict):
            pump_data = context["pump_portal"]
            source_payloads["pump_portal"] = self._trim_payload(pump_data)

            liquidity_sol = pump_data.get("vSolInBondingCurve") or pump_data.get("initialBuy")
            if liquidity_sol and sol_price:
                try:
                    liquidity_value = float(liquidity_sol) * float(sol_price)
                    if liquidity_value > 0:
                        result["liquidity_usd"] = liquidity_value
                        result.setdefault("initial_liquidity", liquidity_value)
                except (TypeError, ValueError):
                    pass

            market_cap_sol = pump_data.get("marketCapSol")
            if market_cap_sol and sol_price:
                try:
                    result["market_cap"] = float(market_cap_sol) * float(sol_price)
                except (TypeError, ValueError):
                    pass

            if pump_data.get("initialBuy") and not result.get("initial_liquidity"):
                try:
                    result["initial_liquidity"] = float(pump_data["initialBuy"])
                except (TypeError, ValueError):
                    pass

        if isinstance(holder_data, dict):
            result["holder_count"] = holder_data.get("holder_count", 0)
            result["top_holder_percentage"] = holder_data.get("top_holder_percentage", 0.0)
            result["initial_holders"] = holder_data.get("holder_count", 0)
            source_payloads["holders"] = holder_data.get("raw")
            if holder_data.get("supply") and not result.get("supply"):
                result["supply"] = holder_data["supply"]
        else:
            result.setdefault("holder_count", 0)
            result.setdefault("top_holder_percentage", 0.0)
            result.setdefault("initial_holders", 0)

        if isinstance(birdeye_holders, dict):
            holder_count_override = birdeye_holders.get("holder_count")
            if holder_count_override is not None:
                count_value = int(self._safe_float(holder_count_override))
                result["holder_count"] = max(result.get("holder_count", 0), count_value)
                result["initial_holders"] = result["holder_count"]
            top_holder_override = birdeye_holders.get("top_holder_percentage")
            pct_value = self._safe_float(top_holder_override)
            if pct_value > 0:
                if result.get("top_holder_percentage"):
                    result["top_holder_percentage"] = min(
                        result["top_holder_percentage"], pct_value
                    )
                else:
                    result["top_holder_percentage"] = pct_value
            source_payloads["birdeye_holders"] = self._trim_payload(
                birdeye_holders.get("raw") if isinstance(birdeye_holders.get("raw"), (dict, list)) else birdeye_holders
            )

        if metadata_hint.get("discovery_sources"):
            discovery_sources.extend(metadata_hint["discovery_sources"])

        if discovery_sources:
            unique_sources = sorted({s for s in discovery_sources if s})
            result["token_metadata"]["discovery_sources"] = unique_sources

        result["token_metadata"]["authority_checked_at"] = datetime.utcnow().isoformat()
        authority_warnings: List[str] = result["token_metadata"].setdefault("warnings", [])
        if result.get("mint_authority"):
            authority_warnings.append("mint_authority_active")
        if result.get("freeze_authority"):
            authority_warnings.append("freeze_authority_active")
        if authority_warnings:
            result["token_metadata"]["warnings"] = sorted(set(authority_warnings))

        label = result.get("symbol") or result.get("name") or "Unknown"
        self.log.debug("Data collected for %s (%s)", label, mint_address)
        return result

    def collect_full_data(
        self, mint_address: str, context: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Synchronous wrapper for async collection.
        """
        try:
            return asyncio.run(self.collect_full_data_async(mint_address, context=context))
        except RuntimeError:
            # Fallback for environments with a running loop (e.g., notebooks)
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(
                    self.collect_full_data_async(mint_address, context=context)
                )
            finally:
                loop.close()
