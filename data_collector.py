"""
COMPREHENSIVE DATA COLLECTOR
Collects ALL available data for tokens - on-chain and off-chain.

Gets:
- Market data (price, volume, liquidity)
- Holder data (top holders, distribution)
- Transaction data (buys, sells, volume)
- Ownership data (creator, insiders)
"""

import asyncio
from typing import Dict, List, Optional
import aiohttp


class DataCollector:
    """
    Collects comprehensive data for tokens.

    Sources:
    1. Pump.fun API - Basic token info, creator, socials
    2. DexScreener - Market data, volume, liquidity, buys/sells
    3. Solana RPC - Holder count, transactions (if needed)
    """

    def __init__(self, rpc_url: str = "https://api.mainnet-beta.solana.com"):
        self.rpc_url = rpc_url
        self.dexscreener_api = "https://api.dexscreener.com/latest/dex"

    async def get_dexscreener_data(self, mint: str) -> Dict:
        """
        Get market data from DexScreener.

        Returns: price, volume, liquidity, buys, sells, etc.
        """
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.dexscreener_api}/tokens/{mint}"

                timeout = aiohttp.ClientTimeout(total=5)
                async with session.get(url, timeout=timeout) as resp:
                    if resp.status != 200:
                        return {}

                    data = await resp.json()
                    pairs = data.get("pairs", [])

                    if not pairs:
                        return {}

                    # Get the first/main pair (usually Pump.fun bonding curve or Raydium)
                    pair = pairs[0]

                    # Extract ALL available data
                    return {
                        "price_usd": float(pair.get("priceUsd", 0)),
                        "price_native": float(pair.get("priceNative", 0)),

                        # Volume
                        "volume_5m": float(pair.get("volume", {}).get("m5", 0)),
                        "volume_1h": float(pair.get("volume", {}).get("h1", 0)),
                        "volume_6h": float(pair.get("volume", {}).get("h6", 0)),
                        "volume_24h": float(pair.get("volume", {}).get("h24", 0)),

                        # Liquidity
                        "liquidity_usd": float(pair.get("liquidity", {}).get("usd", 0)),
                        "liquidity_base": float(pair.get("liquidity", {}).get("base", 0)),
                        "liquidity_quote": float(pair.get("liquidity", {}).get("quote", 0)),

                        # Price changes
                        "price_change_5m": float(pair.get("priceChange", {}).get("m5", 0)),
                        "price_change_1h": float(pair.get("priceChange", {}).get("h1", 0)),
                        "price_change_6h": float(pair.get("priceChange", {}).get("h6", 0)),
                        "price_change_24h": float(pair.get("priceChange", {}).get("h24", 0)),

                        # Buy/Sell data
                        "buys_5m": pair.get("txns", {}).get("m5", {}).get("buys", 0),
                        "sells_5m": pair.get("txns", {}).get("m5", {}).get("sells", 0),
                        "buys_1h": pair.get("txns", {}).get("h1", {}).get("buys", 0),
                        "sells_1h": pair.get("txns", {}).get("h1", {}).get("sells", 0),
                        "buys_6h": pair.get("txns", {}).get("h6", {}).get("buys", 0),
                        "sells_6h": pair.get("txns", {}).get("h6", {}).get("sells", 0),
                        "buys_24h": pair.get("txns", {}).get("h24", {}).get("buys", 0),
                        "sells_24h": pair.get("txns", {}).get("h24", {}).get("sells", 0),

                        # Market info
                        "fdv": float(pair.get("fdv", 0)),
                        "market_cap": float(pair.get("marketCap", 0)),

                        # Pair info
                        "pair_address": pair.get("pairAddress"),
                        "pair_created_at": pair.get("pairCreatedAt"),
                        "dex_id": pair.get("dexId", ""),
                        "chain_id": pair.get("chainId", "solana"),

                        # URLs
                        "url": pair.get("url"),
                    }

        except Exception as e:
            print(f"[ERROR] DexScreener data fetch failed for {mint}: {e}")
            return {}

    async def get_holder_data(self, mint: str) -> Dict:
        """
        Get holder data from Solana RPC.

        Returns: holder count, top holders (if available)
        """
        try:
            async with aiohttp.ClientSession() as session:
                # Get token accounts for this mint
                payload = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "getProgramAccounts",
                    "params": [
                        "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
                        {
                            "encoding": "jsonParsed",
                            "filters": [
                                {"dataSize": 165},
                                {"memcmp": {"offset": 0, "bytes": mint}}
                            ]
                        }
                    ]
                }

                timeout = aiohttp.ClientTimeout(total=10)
                async with session.post(self.rpc_url, json=payload, timeout=timeout) as resp:
                    if resp.status != 200:
                        return {"holder_count": 0}

                    data = await resp.json()

                    if "result" not in data:
                        return {"holder_count": 0}

                    accounts = data["result"]

                    # Count non-zero balances
                    holders = []
                    for account in accounts:
                        try:
                            info = account["account"]["data"]["parsed"]["info"]
                            balance = int(info["tokenAmount"]["amount"])
                            decimals = info["tokenAmount"]["decimals"]
                            owner = info["owner"]

                            if balance > 0:
                                holders.append({
                                    "owner": owner,
                                    "balance": balance,
                                    "balance_ui": balance / (10 ** decimals)
                                })
                        except:
                            continue

                    # Sort by balance
                    holders.sort(key=lambda x: x["balance"], reverse=True)

                    # Calculate total supply held
                    total_held = sum(h["balance"] for h in holders)

                    # Get top 10 holders with percentages
                    top_holders = []
                    for holder in holders[:10]:
                        pct = (holder["balance"] / total_held * 100) if total_held > 0 else 0
                        top_holders.append({
                            "address": holder["owner"],
                            "balance_ui": holder["balance_ui"],
                            "percentage": pct,
                        })

                    return {
                        "holder_count": len(holders),
                        "top_holders": top_holders,
                        "top_holder_pct": top_holders[0]["percentage"] if top_holders else 0,
                    }

        except Exception as e:
            print(f"[ERROR] Holder data fetch failed for {mint}: {e}")
            return {"holder_count": 0}

    async def collect_all_data(self, token: Dict) -> Dict:
        """
        Collect ALL data for a token.

        Takes basic token data from Pump.fun and enriches it with:
        - DexScreener market data
        - On-chain holder data
        """
        mint = token.get("mint")

        print(f"[DATA] Collecting data for {token.get('symbol', '???')} ({mint[:8]}...)")

        # Fetch data in parallel
        dex_task = self.get_dexscreener_data(mint)
        holder_task = self.get_holder_data(mint)

        dex_data, holder_data = await asyncio.gather(dex_task, holder_task)

        # Merge all data
        complete_data = {
            **token,  # Original Pump.fun data
            **dex_data,  # DexScreener market data
            **holder_data,  # On-chain holder data
        }

        # Calculate buy/sell ratio
        buys_5m = complete_data.get("buys_5m", 0)
        sells_5m = complete_data.get("sells_5m", 0)
        if sells_5m > 0:
            complete_data["buy_sell_ratio_5m"] = buys_5m / sells_5m
        else:
            complete_data["buy_sell_ratio_5m"] = buys_5m if buys_5m > 0 else 0

        return complete_data


# Test function
async def test():
    import sys
    sys.path.append(".")
    from realtime_scanner import RealtimePumpScanner

    print("Testing Data Collector")
    print("=" * 60)

    # Get a recent token
    scanner = RealtimePumpScanner()
    tokens = await scanner.get_latest_tokens(limit=1)

    if not tokens:
        print("No tokens found")
        return

    token = scanner.parse_token_data(tokens[0])

    print(f"\nCollecting data for: {token['symbol']} - {token['name']}")
    print(f"Mint: {token['mint']}\n")

    # Collect all data
    collector = DataCollector()
    complete_data = await collector.collect_all_data(token)

    print(f"\n{'='*60}")
    print("COMPLETE DATA:")
    print(f"{'='*60}\n")

    # Market data
    print("MARKET DATA:")
    print(f"  Price: ${complete_data.get('price_usd', 0):.8f}")
    print(f"  Market Cap: ${complete_data.get('market_cap', 0):,.0f}")
    print(f"  Liquidity: ${complete_data.get('liquidity_usd', 0):,.0f}")
    print(f"  Volume 1h: ${complete_data.get('volume_1h', 0):,.0f}")
    print(f"  Volume 24h: ${complete_data.get('volume_24h', 0):,.0f}")

    # Buy/Sell data
    print(f"\nBUY/SELL DATA (5 min):")
    print(f"  Buys: {complete_data.get('buys_5m', 0)}")
    print(f"  Sells: {complete_data.get('sells_5m', 0)}")
    print(f"  Ratio: {complete_data.get('buy_sell_ratio_5m', 0):.2f}")

    # Holder data
    print(f"\nHOLDER DATA:")
    print(f"  Total Holders: {complete_data.get('holder_count', 0)}")
    print(f"  Top Holder: {complete_data.get('top_holder_pct', 0):.2f}%")

    # Creator
    print(f"\nCREATOR:")
    print(f"  Address: {complete_data.get('creator', 'N/A')}")


if __name__ == "__main__":
    asyncio.run(test())
