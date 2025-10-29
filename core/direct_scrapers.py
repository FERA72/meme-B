"""
Direct scrapers that go straight to the source - NO third-party APIs.

This module contains:
1. PumpFunScraper - Scrapes Pump.fun directly for new tokens
2. OnChainDEXMonitor - Monitors DEX programs on-chain for new pools
3. DirectRPCCollector - Gets all token data directly from Solana RPC
4. TransactionParser - Parses DEX transactions for buy/sell ratios
"""

import asyncio
import time
from typing import Dict, List, Optional, Set
from datetime import datetime
import aiohttp
from solders.pubkey import Pubkey
from solders.rpc.responses import GetProgramAccountsResp
import logging

from core.http_client import HttpClient
from core.logging_config import get_logger


class PumpFunScraper:
    """
    Scrapes Pump.fun directly for new tokens.

    Pump.fun is the primary memecoin launchpad on Solana. This scraper:
    - Monitors their API/website for new token creations
    - Gets trending tokens
    - Extracts all metadata (symbol, name, creator, etc.)
    """

    def __init__(self, rpc_url: str):
        self.rpc_url = rpc_url
        self.http = HttpClient("pumpfun_scraper")
        self.log = get_logger("pumpfun_scraper")
        self.seen_tokens: Set[str] = set()

        # Pump.fun program ID
        self.PUMP_PROGRAM_ID = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"

        # Pump.fun API endpoints (they have a public API)
        self.PUMPFUN_API = "https://frontend-api.pump.fun"

    async def get_new_tokens(self, session: aiohttp.ClientSession, limit: int = 50) -> List[Dict]:
        """
        Get newest tokens from Pump.fun.

        Returns list of token data:
        - mint_address
        - symbol, name
        - creator
        - creation_time
        - market_cap, liquidity
        - etc.
        """
        tokens = []

        try:
            # Pump.fun has a /coins endpoint that returns new tokens
            url = f"{self.PUMPFUN_API}/coins"
            params = {
                "sort": "created_timestamp",
                "order": "desc",
                "limit": limit,
                "offset": 0
            }

            data = await self.http.get_json(url, session=session, params=params, metrics_tag="pumpfun:new_tokens")

            if not data:
                self.log.warning("No data from Pump.fun API")
                return tokens

            # Parse tokens
            for coin in data:
                mint = coin.get("mint")
                if not mint or mint in self.seen_tokens:
                    continue

                self.seen_tokens.add(mint)

                # Extract all relevant data
                tokens.append({
                    "mint_address": mint,
                    "source": "pumpfun_direct",
                    "symbol": coin.get("symbol"),
                    "name": coin.get("name"),
                    "description": coin.get("description"),
                    "image_uri": coin.get("image_uri"),
                    "creator": coin.get("creator"),
                    "created_timestamp": coin.get("created_timestamp"),
                    "market_cap": coin.get("usd_market_cap", 0),
                    "reply_count": coin.get("reply_count", 0),
                    "twitter": coin.get("twitter"),
                    "telegram": coin.get("telegram"),
                    "website": coin.get("website"),
                    "show_name": coin.get("show_name", False),
                    "king_of_the_hill_timestamp": coin.get("king_of_the_hill_timestamp"),
                    "metadata": {
                        "complete": coin.get("complete", False),
                        "total_supply": coin.get("total_supply"),
                        "decimals": coin.get("decimals", 6),
                    }
                })

            self.log.info(f"Found {len(tokens)} new tokens from Pump.fun")

        except Exception as e:
            self.log.error(f"Error fetching from Pump.fun: {e}")

        return tokens

    async def get_trending_tokens(self, session: aiohttp.ClientSession, limit: int = 30) -> List[Dict]:
        """Get trending tokens from Pump.fun"""
        tokens = []

        try:
            # Pump.fun has different endpoints for trending/graduating tokens
            url = f"{self.PUMPFUN_API}/coins"
            params = {
                "sort": "last_reply",  # Most active
                "order": "desc",
                "limit": limit,
                "offset": 0
            }

            data = await self.http.get_json(url, session=session, params=params, metrics_tag="pumpfun:trending")

            if not data:
                return tokens

            for coin in data:
                mint = coin.get("mint")
                if not mint:
                    continue

                tokens.append({
                    "mint_address": mint,
                    "source": "pumpfun_trending",
                    "symbol": coin.get("symbol"),
                    "name": coin.get("name"),
                    "market_cap": coin.get("usd_market_cap", 0),
                    "reply_count": coin.get("reply_count", 0),
                    "created_timestamp": coin.get("created_timestamp"),
                })

            self.log.info(f"Found {len(tokens)} trending tokens from Pump.fun")

        except Exception as e:
            self.log.error(f"Error fetching trending from Pump.fun: {e}")

        return tokens

    async def get_graduating_tokens(self, session: aiohttp.ClientSession) -> List[Dict]:
        """Get tokens about to graduate (reach bonding curve completion)"""
        tokens = []

        try:
            url = f"{self.PUMPFUN_API}/coins"
            params = {
                "sort": "usd_market_cap",
                "order": "desc",
                "limit": 50,
                "offset": 0,
            }

            data = await self.http.get_json(url, session=session, params=params, metrics_tag="pumpfun:graduating")

            if not data:
                return tokens

            for coin in data:
                mint = coin.get("mint")
                # Filter for high market cap (close to graduation)
                market_cap = coin.get("usd_market_cap", 0)

                if not mint or market_cap < 50000:  # Close to $69k graduation
                    continue

                tokens.append({
                    "mint_address": mint,
                    "source": "pumpfun_graduating",
                    "symbol": coin.get("symbol"),
                    "name": coin.get("name"),
                    "market_cap": market_cap,
                    "complete": coin.get("complete", False),
                })

            self.log.info(f"Found {len(tokens)} graduating tokens")

        except Exception as e:
            self.log.error(f"Error fetching graduating tokens: {e}")

        return tokens


class OnChainDEXMonitor:
    """
    Monitors DEX programs on-chain for new liquidity pool creations.

    This watches:
    - Raydium (most popular)
    - Orca
    - Meteora
    - Phoenix

    When a new pool is created, we extract the token addresses and pool data.
    """

    def __init__(self, rpc_url: str):
        self.rpc_url = rpc_url
        self.log = get_logger("dex_monitor")
        self.seen_pools: Set[str] = set()

        # DEX program IDs
        self.RAYDIUM_AMM = "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8"
        self.RAYDIUM_CLMM = "CAMMCzo5YL8w4VFF8KVHrK22GGUsp5VTaW7grrKgrWqK"
        self.ORCA_WHIRLPOOL = "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc"
        self.METEORA = "LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo"

    async def scan_raydium_pools(self, session: aiohttp.ClientSession) -> List[Dict]:
        """
        Scan Raydium for new liquidity pools.

        We do this by querying the Raydium program accounts and looking for
        new pool creation transactions in recent slots.
        """
        new_pools = []

        try:
            # Get recent Raydium pool creations via RPC
            # We'll look at recent confirmed transactions for the Raydium program
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getSignaturesForAddress",
                "params": [
                    self.RAYDIUM_AMM,
                    {"limit": 100}
                ]
            }

            async with session.post(self.rpc_url, json=payload) as resp:
                data = await resp.json()

                if "result" not in data:
                    return new_pools

                signatures = data["result"]

                # For each signature, we'd need to parse the transaction
                # This is complex - let's use a simpler approach for now
                self.log.info(f"Found {len(signatures)} recent Raydium transactions")

        except Exception as e:
            self.log.error(f"Error scanning Raydium: {e}")

        return new_pools

    async def monitor_new_pools(self, callback) -> None:
        """
        Continuously monitor for new pool creations.

        This runs forever, checking every 10 seconds for new pools.
        When found, calls the callback with pool data.
        """
        while True:
            try:
                async with aiohttp.ClientSession() as session:
                    pools = await self.scan_raydium_pools(session)
                    if pools:
                        await callback(pools)

                await asyncio.sleep(10)

            except Exception as e:
                self.log.error(f"Error in pool monitoring: {e}")
                await asyncio.sleep(30)


class DirectRPCCollector:
    """
    Collects ALL token data directly from Solana RPC.

    This replaces third-party APIs - we get everything on-chain:
    - Token metadata (Metaplex)
    - Holder count (Token Program accounts)
    - Liquidity (DEX pool balances)
    - Supply info
    - Authority status
    """

    def __init__(self, rpc_url: str):
        self.rpc_url = rpc_url
        self.log = get_logger("direct_rpc")

        # Token program
        self.TOKEN_PROGRAM = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
        self.METADATA_PROGRAM = "metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s"

    async def get_token_data(self, mint_address: str, session: aiohttp.ClientSession) -> Optional[Dict]:
        """
        Collect ALL data for a token directly from RPC.

        Returns comprehensive token data including:
        - metadata (name, symbol, uri)
        - supply info
        - holder count
        - authority status
        - liquidity (from known DEX pools)
        """
        try:
            # Get token supply and authority info
            supply_data = await self._get_token_supply(mint_address, session)

            # Get metadata
            metadata = await self._get_token_metadata(mint_address, session)

            # Get holder count
            holder_count = await self._get_holder_count(mint_address, session)

            # Get liquidity from DEX pools
            liquidity = await self._get_liquidity(mint_address, session)

            return {
                "mint_address": mint_address,
                "symbol": metadata.get("symbol", "UNKNOWN"),
                "name": metadata.get("name", "Unknown"),
                "uri": metadata.get("uri"),
                "supply": supply_data.get("supply", 0),
                "decimals": supply_data.get("decimals", 9),
                "holder_count": holder_count,
                "liquidity_usd": liquidity,
                "mint_authority": supply_data.get("mint_authority"),
                "freeze_authority": supply_data.get("freeze_authority"),
                "collected_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            self.log.error(f"Error collecting data for {mint_address}: {e}")
            return None

    async def _get_token_supply(self, mint: str, session: aiohttp.ClientSession) -> Dict:
        """Get token supply and authority info"""
        try:
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getAccountInfo",
                "params": [mint, {"encoding": "jsonParsed"}]
            }

            async with session.post(self.rpc_url, json=payload) as resp:
                data = await resp.json()

                if "result" not in data or not data["result"]["value"]:
                    return {}

                parsed = data["result"]["value"]["data"]["parsed"]["info"]

                return {
                    "supply": int(parsed.get("supply", 0)),
                    "decimals": parsed.get("decimals", 9),
                    "mint_authority": parsed.get("mintAuthority"),
                    "freeze_authority": parsed.get("freezeAuthority"),
                }

        except Exception as e:
            self.log.error(f"Error getting supply for {mint}: {e}")
            return {}

    async def _get_token_metadata(self, mint: str, session: aiohttp.ClientSession) -> Dict:
        """Get token metadata from Metaplex"""
        try:
            # Derive metadata PDA
            mint_pubkey = Pubkey.from_string(mint)
            metadata_program = Pubkey.from_string(self.METADATA_PROGRAM)

            # Find PDA: ["metadata", metadata_program, mint]
            seeds = [b"metadata", bytes(metadata_program), bytes(mint_pubkey)]
            metadata_pda, _ = Pubkey.find_program_address(seeds, metadata_program)

            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getAccountInfo",
                "params": [str(metadata_pda), {"encoding": "jsonParsed"}]
            }

            async with session.post(self.rpc_url, json=payload) as resp:
                data = await resp.json()

                if "result" not in data or not data["result"]["value"]:
                    return {}

                # Parse metadata (this is complex - simplified for now)
                # We'd need to deserialize the Metaplex metadata structure
                return {
                    "symbol": "UNKNOWN",
                    "name": "Unknown",
                    "uri": None
                }

        except Exception as e:
            self.log.error(f"Error getting metadata for {mint}: {e}")
            return {}

    async def _get_holder_count(self, mint: str, session: aiohttp.ClientSession) -> int:
        """Get actual holder count using getProgramAccounts"""
        try:
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getProgramAccounts",
                "params": [
                    self.TOKEN_PROGRAM,
                    {
                        "encoding": "jsonParsed",
                        "filters": [
                            {"dataSize": 165},
                            {"memcmp": {"offset": 0, "bytes": mint}}
                        ]
                    }
                ]
            }

            async with session.post(self.rpc_url, json=payload) as resp:
                data = await resp.json()

                if "result" not in data:
                    return 0

                # Count non-zero balances
                accounts = data["result"]
                holders = 0

                for account in accounts:
                    try:
                        balance = int(account["account"]["data"]["parsed"]["info"]["tokenAmount"]["amount"])
                        if balance > 0:
                            holders += 1
                    except:
                        continue

                return holders

        except Exception as e:
            self.log.error(f"Error getting holders for {mint}: {e}")
            return 0

    async def _get_liquidity(self, mint: str, session: aiohttp.ClientSession) -> float:
        """
        Get liquidity by checking DEX pools.

        This is complex - we'd need to:
        1. Find all pools containing this token
        2. Get pool balances
        3. Calculate USD value

        For now, return 0 (implement later)
        """
        return 0.0


class TransactionParser:
    """
    Parses DEX transactions to calculate buy/sell ratios.

    This analyzes recent swap transactions for a token to determine:
    - Buy count (swaps TO the token)
    - Sell count (swaps FROM the token)
    - Buy/sell ratio
    - Trade volume
    """

    def __init__(self, rpc_url: str):
        self.rpc_url = rpc_url
        self.log = get_logger("tx_parser")

    async def get_trade_stats(self, mint: str, session: aiohttp.ClientSession, hours: int = 24) -> Dict:
        """
        Get buy/sell statistics for a token.

        Returns:
        - buy_count
        - sell_count
        - buy_sell_ratio
        - volume_24h
        """
        try:
            # This requires:
            # 1. Get all token account addresses for this mint
            # 2. Get recent transactions for those accounts
            # 3. Parse transaction logs to identify swaps
            # 4. Classify as buy or sell
            # 5. Aggregate stats

            # This is complex - placeholder for now
            return {
                "buy_count": 0,
                "sell_count": 0,
                "buy_sell_ratio": 0,
                "volume_24h": 0,
            }

        except Exception as e:
            self.log.error(f"Error parsing trades for {mint}: {e}")
            return {}


class DirectScraperOrchestrator:
    """
    Orchestrates all direct scrapers to provide real-time token discovery.

    This replaces the multi-source discovery system with our own scrapers.
    """

    def __init__(self, rpc_url: str):
        self.rpc_url = rpc_url
        self.log = get_logger("direct_scraper")

        # Initialize all scrapers
        self.pumpfun = PumpFunScraper(rpc_url)
        self.dex_monitor = OnChainDEXMonitor(rpc_url)
        self.rpc_collector = DirectRPCCollector(rpc_url)
        self.tx_parser = TransactionParser(rpc_url)

        self.discovered_tokens: Set[str] = set()

    async def discover_new_tokens(self, session: aiohttp.ClientSession) -> List[Dict]:
        """
        Run all discovery methods and return new tokens.

        This combines:
        - Pump.fun new tokens
        - Pump.fun trending
        - DEX pool creations
        """
        all_tokens = []

        # Get from Pump.fun
        pumpfun_new = await self.pumpfun.get_new_tokens(session, limit=50)
        pumpfun_trending = await self.pumpfun.get_trending_tokens(session, limit=30)

        all_tokens.extend(pumpfun_new)
        all_tokens.extend(pumpfun_trending)

        # Filter out already discovered
        new_tokens = []
        for token in all_tokens:
            mint = token["mint_address"]
            if mint not in self.discovered_tokens:
                self.discovered_tokens.add(mint)
                new_tokens.append(token)

        self.log.info(f"Discovered {len(new_tokens)} new tokens ({len(pumpfun_new)} new, {len(pumpfun_trending)} trending)")

        return new_tokens

    async def enrich_token_data(self, token: Dict, session: aiohttp.ClientSession) -> Dict:
        """
        Enrich token data with on-chain information.

        Takes basic token info and adds:
        - Full on-chain data
        - Trade statistics
        - Holder count
        - Liquidity
        """
        mint = token["mint_address"]

        # Get on-chain data
        on_chain_data = await self.rpc_collector.get_token_data(mint, session)

        # Get trade stats
        trade_stats = await self.tx_parser.get_trade_stats(mint, session)

        # Merge all data
        enriched = {
            **token,
            **on_chain_data,
            **trade_stats,
        }

        return enriched

    async def run_continuous_discovery(self, callback, interval: int = 30):
        """
        Run discovery continuously.

        Every `interval` seconds:
        1. Discover new tokens
        2. Enrich with on-chain data
        3. Call callback with enriched tokens
        """
        self.log.info(f"Starting continuous discovery (every {interval}s)")

        while True:
            try:
                async with aiohttp.ClientSession() as session:
                    # Discover
                    tokens = await self.discover_new_tokens(session)

                    if tokens:
                        self.log.info(f"Found {len(tokens)} new tokens, enriching data...")

                        # Enrich each token
                        enriched_tokens = []
                        for token in tokens:
                            enriched = await self.enrich_token_data(token, session)
                            enriched_tokens.append(enriched)

                        # Call callback
                        await callback(enriched_tokens)

                await asyncio.sleep(interval)

            except Exception as e:
                self.log.error(f"Error in continuous discovery: {e}")
                await asyncio.sleep(60)
