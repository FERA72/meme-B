"""
PUMP.FUN SCANNER - Get new tokens as they're created
Simple, fast, focused on making money.
"""

import asyncio
import time
from typing import Dict, List, Optional
from datetime import datetime
import aiohttp


class PumpFunScanner:
    """
    Scrapes Pump.fun for new token launches.

    Pump.fun is THE memecoin launchpad. Every new token starts here.
    We scrape their public API to get tokens the moment they're created.
    """

    def __init__(self):
        self.api_url = "https://frontend-api.pump.fun"
        self.seen_tokens = set()

    async def get_new_tokens(self, limit: int = 50) -> List[Dict]:
        """
        Get newest tokens from Pump.fun.

        Returns list of tokens sorted by creation time (newest first).
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

                async with session.get(url, params=params) as resp:
                    if resp.status != 200:
                        print(f"[ERROR] Pump.fun API returned {resp.status}")
                        return []

                    data = await resp.json()

                    tokens = []
                    for coin in data:
                        mint = coin.get("mint")
                        if not mint or mint in self.seen_tokens:
                            continue

                        self.seen_tokens.add(mint)

                        # Calculate age
                        created_ts = coin.get("created_timestamp", 0)
                        age_seconds = time.time() - (created_ts / 1000) if created_ts else 999999
                        age_minutes = age_seconds / 60

                        tokens.append({
                            "mint": mint,
                            "symbol": coin.get("symbol", "???"),
                            "name": coin.get("name", "Unknown"),
                            "description": coin.get("description", ""),
                            "creator": coin.get("creator"),
                            "market_cap_usd": coin.get("usd_market_cap", 0),
                            "created_timestamp": created_ts,
                            "age_minutes": age_minutes,
                            "twitter": coin.get("twitter"),
                            "telegram": coin.get("telegram"),
                            "website": coin.get("website"),
                            "image_uri": coin.get("image_uri"),
                            "reply_count": coin.get("reply_count", 0),  # Activity indicator
                        })

                    return tokens

        except Exception as e:
            print(f"[ERROR] Failed to fetch from Pump.fun: {e}")
            return []

    async def get_token_details(self, mint: str) -> Optional[Dict]:
        """
        Get detailed info for a specific token.
        """
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.api_url}/coins/{mint}"

                async with session.get(url) as resp:
                    if resp.status != 200:
                        return None

                    data = await resp.json()
                    return data

        except Exception as e:
            print(f"[ERROR] Failed to get token details: {e}")
            return None

    async def monitor_new_tokens(self, callback, interval: int = 10):
        """
        Continuously monitor for new tokens.

        Checks Pump.fun every `interval` seconds and calls callback with new tokens.
        """
        print(f"[Scanner] Monitoring Pump.fun for new tokens (every {interval}s)...")

        while True:
            try:
                tokens = await self.get_new_tokens(limit=50)

                if tokens:
                    print(f"[Scanner] Found {len(tokens)} new tokens!")
                    await callback(tokens)
                else:
                    print(f"[Scanner] No new tokens found")

                await asyncio.sleep(interval)

            except Exception as e:
                print(f"[ERROR] Monitor loop error: {e}")
                await asyncio.sleep(30)


# Test function
async def test():
    scanner = PumpFunScanner()

    print("Testing Pump.fun scanner...")
    print("=" * 60)

    tokens = await scanner.get_new_tokens(limit=10)

    print(f"\nFound {len(tokens)} tokens:\n")

    for i, token in enumerate(tokens, 1):
        print(f"{i}. {token['symbol']} - {token['name']}")
        print(f"   Mint: {token['mint']}")
        print(f"   Age: {token['age_minutes']:.1f} minutes")
        print(f"   MCap: ${token['market_cap_usd']:,.0f}")
        print(f"   Activity: {token['reply_count']} replies")
        print()


if __name__ == "__main__":
    asyncio.run(test())
