"""
REAL-TIME PUMP.FUN SCANNER
Monitors Pump.fun for new tokens EVERY SECOND and collects ALL data.
"""

import asyncio
import time
from typing import Dict, List, Optional, Set
from datetime import datetime
import aiohttp


class RealtimePumpScanner:
    """
    Ultra-fast real-time scanner for Pump.fun.

    Checks for new tokens every 1-2 seconds.
    Tracks every single new token the moment it's created.
    """

    def __init__(self):
        self.api_url = "https://frontend-api.pump.fun"
        self.seen_tokens: Set[str] = set()
        self.last_check = 0

    async def get_latest_tokens(self, limit: int = 100) -> List[Dict]:
        """
        Get the absolute latest tokens from Pump.fun.

        Fetches more tokens (100) to ensure we catch everything.
        """
        try:
            # Headers to bypass Cloudflare
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Origin': 'https://pump.fun',
                'Referer': 'https://pump.fun/',
                'Connection': 'keep-alive',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-site',
            }

            async with aiohttp.ClientSession(headers=headers) as session:
                url = f"{self.api_url}/coins"
                params = {
                    "limit": limit,
                    "offset": 0,
                    "sort": "created_timestamp",
                    "order": "DESC",
                    "includeNsfw": "true"
                }

                timeout = aiohttp.ClientTimeout(total=10)

                try:
                    async with session.get(url, params=params, timeout=timeout) as resp:
                        print(f"[DEBUG] API Status: {resp.status}")

                        if resp.status != 200:
                            text = await resp.text()
                            print(f"[ERROR] API returned {resp.status}: {text[:200]}")
                            return []

                        data = await resp.json()
                        print(f"[DEBUG] Got data type: {type(data)}, Length: {len(data) if isinstance(data, list) else 'N/A'}")

                        # Handle response (should be a list)
                        if not isinstance(data, list):
                            print(f"[ERROR] Unexpected data format: {data}")
                            return []

                        # Filter for NEW tokens only
                        new_tokens = []
                        for coin in data:
                            mint = coin.get("mint")
                            if not mint:
                                continue

                            if mint in self.seen_tokens:
                                continue

                            self.seen_tokens.add(mint)
                            new_tokens.append(coin)

                            # Debug first token
                            if len(new_tokens) == 1:
                                print(f"[DEBUG] First token: {coin.get('symbol')} - {coin.get('name')} (mint: {mint[:8]}...)")

                        return new_tokens

                except aiohttp.ClientError as e:
                    print(f"[ERROR] Client error: {e}")
                    return []

        except asyncio.TimeoutError:
            print("[ERROR] API timeout")
            return []
        except Exception as e:
            print(f"[ERROR] Scanner failed: {e}")
            import traceback
            traceback.print_exc()
            return []

    async def get_token_details(self, mint: str) -> Optional[Dict]:
        """Get detailed data for a specific token"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.api_url}/coins/{mint}"

                timeout = aiohttp.ClientTimeout(total=3)
                async with session.get(url, timeout=timeout) as resp:
                    if resp.status != 200:
                        return None

                    return await resp.json()

        except Exception as e:
            print(f"[ERROR] Failed to get details for {mint}: {e}")
            return None

    def parse_token_data(self, coin: Dict) -> Dict:
        """
        Extract ALL available data from Pump.fun coin object.
        """
        mint = coin.get("mint", "")

        # Calculate age
        created_ts = coin.get("created_timestamp", 0)
        age_seconds = time.time() - (created_ts / 1000) if created_ts else 0
        age_minutes = age_seconds / 60

        # Parse all available fields
        return {
            # Basic info
            "mint": mint,
            "symbol": coin.get("symbol", "???"),
            "name": coin.get("name", "Unknown"),
            "description": coin.get("description", "")[:100],  # First 100 chars

            # Financial data
            "market_cap_usd": coin.get("usd_market_cap", 0),
            "virtual_sol_reserves": coin.get("virtual_sol_reserves", 0),
            "virtual_token_reserves": coin.get("virtual_token_reserves", 0),
            "total_supply": coin.get("total_supply", 0),

            # Creator & ownership
            "creator": coin.get("creator", ""),
            "creator_name": coin.get("creator_name", ""),
            "creator_username": coin.get("creator_username", ""),

            # Metadata
            "image_uri": coin.get("image_uri", ""),
            "metadata_uri": coin.get("metadata_uri", ""),
            "twitter": coin.get("twitter"),
            "telegram": coin.get("telegram"),
            "website": coin.get("website"),

            # Activity metrics
            "reply_count": coin.get("reply_count", 0),
            "last_reply": coin.get("last_reply"),
            "is_currently_live": coin.get("is_currently_live", True),

            # Bonding curve status
            "complete": coin.get("complete", False),  # Has it graduated?
            "nsfw": coin.get("nsfw", False),
            "show_name": coin.get("show_name", False),

            # Timestamps
            "created_timestamp": created_ts,
            "age_seconds": age_seconds,
            "age_minutes": age_minutes,
            "raydium_pool": coin.get("raydium_pool"),  # If graduated to Raydium

            # King of the hill (trending indicator)
            "king_of_the_hill_timestamp": coin.get("king_of_the_hill_timestamp"),
            "market_cap_rank": coin.get("market_cap_rank"),

            # Internal tracking
            "discovered_at": datetime.utcnow().isoformat(),
        }

    async def monitor_realtime(self, callback, interval: float = 1.5):
        """
        Monitor Pump.fun in real-time.

        Args:
            callback: Function to call with new tokens
            interval: Seconds between checks (default 1.5s for fast updates)
        """
        print(f"[REALTIME] Starting real-time monitor (checking every {interval}s)")
        print(f"[REALTIME] Will detect new tokens the INSTANT they appear on Pump.fun\n")

        check_count = 0
        total_found = 0
        last_cache_clear = time.time()

        while True:
            check_count += 1
            start_time = time.time()

            try:
                # Clear cache every 5 minutes to allow re-discovery
                if time.time() - last_cache_clear > 300:
                    cache_size = len(self.seen_tokens)
                    self.seen_tokens.clear()
                    print(f"[REALTIME] Cleared cache ({cache_size} tokens) - will re-discover trending tokens")
                    last_cache_clear = time.time()

                # Get latest tokens
                new_tokens = await self.get_latest_tokens(limit=100)

                if new_tokens:
                    total_found += len(new_tokens)
                    print(f"[REALTIME] Check #{check_count}: Found {len(new_tokens)} NEW tokens! (Total: {total_found})")

                    # Parse all data
                    parsed_tokens = []
                    for coin in new_tokens:
                        parsed = self.parse_token_data(coin)
                        parsed_tokens.append(parsed)

                    # Send to callback
                    await callback(parsed_tokens)
                else:
                    # Still show we're checking
                    if check_count % 10 == 0:  # Every 10 checks
                        print(f"[REALTIME] Check #{check_count}: No new tokens (monitoring...)")

                # Calculate how long to wait
                elapsed = time.time() - start_time
                wait_time = max(0, interval - elapsed)

                await asyncio.sleep(wait_time)

            except Exception as e:
                print(f"[ERROR] Monitor loop error: {e}")
                import traceback
                traceback.print_exc()
                await asyncio.sleep(5)  # Wait longer on error


# Test function
async def test():
    scanner = RealtimePumpScanner()

    print("Testing Real-Time Pump.fun Scanner")
    print("=" * 60)
    print("Fetching latest tokens...\n")

    tokens = await scanner.get_latest_tokens(limit=5)

    if tokens:
        print(f"Found {len(tokens)} tokens:\n")

        for i, coin in enumerate(tokens, 1):
            parsed = scanner.parse_token_data(coin)

            print(f"{i}. {parsed['symbol']} - {parsed['name']}")
            print(f"   Mint: {parsed['mint']}")
            print(f"   Age: {parsed['age_minutes']:.1f} minutes")
            print(f"   MCap: ${parsed['market_cap_usd']:,.0f}")
            print(f"   Creator: {parsed['creator'][:8]}...")
            print(f"   Activity: {parsed['reply_count']} replies")
            print()
    else:
        print("No tokens found")


if __name__ == "__main__":
    asyncio.run(test())
