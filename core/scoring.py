"""
Token scoring utilities.

Calculates a composite performance score for tokens based on liquidity,
market cap, holder distribution, trade activity, and migration state.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Dict, Tuple


def _normalize(value: float, max_value: float) -> float:
    if max_value <= 0:
        return 0.0
    return max(0.0, min(1.0, value / max_value))


def _penalize_top_holder(top_holder_pct: float) -> float:
    if top_holder_pct is None:
        return 0.0
    if top_holder_pct <= 20:
        return 0.0
    if top_holder_pct >= 80:
        return -1.0
    # linear penalty between 20% and 80%
    return -((top_holder_pct - 20) / 60)


def calculate_score(token_data: Dict, context: Dict | None = None) -> Tuple[float, Dict]:
    """
    Compute a 0-100 score for a token, returning the score and breakdown.
    """
    context = context or {}
    metadata = token_data.get("token_metadata", {}) or {}
    trades = metadata.get("trades", {})

    liquidity = float(token_data.get("liquidity_usd") or 0)
    market_cap = float(token_data.get("market_cap") or 0)
    volume_24h = float(token_data.get("volume_24h") or 0)
    holder_count = float(token_data.get("holder_count") or 0)
    top_holder_pct = float(token_data.get("top_holder_percentage") or 0)

    buy_count = float(trades.get("buy_count", 0))
    sell_count = float(trades.get("sell_count", 0))
    trade_volume = float(trades.get("sol_volume", 0))

    first_seen = token_data.get("first_seen")
    age_minutes = 0.0
    if isinstance(first_seen, datetime):
        age_seconds = (datetime.utcnow() - first_seen).total_seconds()
        age_minutes = max(0.0, age_seconds / 60.0)

    migration_state = metadata.get("migration", {}).get("status")

    mc_to_liquidity = market_cap / max(liquidity, 1)

    components = {
        "liquidity": _normalize(liquidity, 150_000) * 25,
        "market_cap": _normalize(market_cap, 250_000) * 10,
        "volume": _normalize(volume_24h, 150_000) * 10,
        "holders": _normalize(holder_count, 1500) * 10,
        "trades": _normalize(buy_count + sell_count, 200) * 10 + _normalize(trade_volume, 500) * 5,
        "freshness": (1 - min(1.0, age_minutes / 240)) * 5,
        "top_holder_penalty": _penalize_top_holder(top_holder_pct) * 10,
    }

    if liquidity < 10_000:
        components["liquidity_penalty"] = -min(20, (10_000 - liquidity) / 10_000 * 20)
    else:
        components["liquidity_penalty"] = 0

    if mc_to_liquidity > 500:
        penalty = math.log10(mc_to_liquidity / 500 + 1) * 25
        components["mc_liquidity_penalty"] = -min(40, penalty)
    else:
        components["mc_liquidity_penalty"] = 0

    if holder_count < 50:
        components["holder_penalty"] = -max(5, (50 - holder_count) / 50 * 15)
    else:
        components["holder_penalty"] = 0

    if migration_state == "migrated":
        components["migration_bonus"] = 5
    else:
        components["migration_bonus"] = 0

    score = sum(components.values())
    score = max(0.0, min(100.0, score))
    components["score"] = score

    return score, components
