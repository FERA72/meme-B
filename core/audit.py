"""
Audit helpers for inspecting token state and fresh data collection.
"""

from __future__ import annotations

import datetime as _dt
from typing import Any, Dict, Optional

from core.data_collector import DataCollector
from core.http_client import HttpError
from core.metrics import METRICS
from db.database import Database
from db.models import Token


def _token_to_dict(token: Token) -> Dict[str, Any]:
    return {
        "mint_address": token.mint_address,
        "symbol": token.symbol,
        "name": token.name,
        "is_safe": token.is_safe,
        "is_graduated": token.is_graduated,
        "liquidity_usd": token.liquidity_usd,
        "market_cap": token.market_cap,
        "price_usd": token.price_usd,
        "volume_24h": token.volume_24h,
        "holder_count": token.holder_count,
        "top_holder_percentage": token.top_holder_percentage,
        "mint_authority": token.mint_authority,
        "freeze_authority": token.freeze_authority,
        "initial_liquidity": token.initial_liquidity,
        "initial_holders": token.initial_holders,
        "growth_rate": token.growth_rate,
        "last_updated": token.last_updated.isoformat() if isinstance(token.last_updated, _dt.datetime) else None,
        "first_seen": token.first_seen.isoformat() if isinstance(token.first_seen, _dt.datetime) else None,
        "token_metadata": token.token_metadata,
    }


def perform_audit(mint_address: str, db: Database, collector: DataCollector) -> Dict[str, Any]:
    """
    Gather current database snapshot, fresh collector data, and metrics.
    """
    report: Dict[str, Any] = {"mint_address": mint_address}

    existing = db.get_token(mint_address)
    if existing:
        report["database_record"] = _token_to_dict(existing)
    else:
        report["database_record"] = None

    try:
        fresh_data = collector.collect_full_data(mint_address, context={"source": "audit"})
        report["fresh_data"] = fresh_data
        report["error"] = None
    except HttpError as exc:
        report["fresh_data"] = None
        report["error"] = {
            "type": "HttpError",
            "status": exc.status,
            "message": str(exc),
        }
    except Exception as exc:  # pragma: no cover - defensive diagnostic
        report["fresh_data"] = None
        report["error"] = {
            "type": exc.__class__.__name__,
            "message": str(exc),
        }

    report["metrics"] = METRICS.snapshot()
    report["telemetry"] = {
        "uptime_seconds": METRICS.uptime_seconds(),
    }
    return report

