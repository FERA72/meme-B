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
            async with aiohttp.ClientSession() as session:
                url = f"{self.api_url}/coins"
                params = {
                    "sort": "created_timestamp",
                    "order": "desc",
                    "limit": limit,
                    "offset": 0
                }

                timeout = aiohttp.ClientTimeout(total=5)
                async with session.get(url, params=params, timeout=timeout) as resp:
                    if resp.status != 200:
                        print(f"[ERROR] API returned {resp.status}")
                        return []

                    data = await resp.json()

                    # Filter for NEW tokens only
                    new_tokens = []
                    for coin in data:
                        mint = coin.get("mint")
                        if not mint or mint in self.seen_tokens:
                            continue

                        self.seen_tokens.add(mint)
                        new_tokens.append(coin)

                    return new_tokens

        except asyncio.TimeoutError:
            print("[ERROR] API timeout")
            return []
        except Exception as e:
            print(f"[ERROR] Scanner failed: {e}")
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

        while True:
            check_count += 1
            start_time = time.time()

            try:
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
