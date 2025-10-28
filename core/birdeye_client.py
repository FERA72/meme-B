"""
Thin wrapper around Birdeye's public API endpoints.
"""

from __future__ import annotations

from typing import Any, Dict

import aiohttp

from core.http_client import HttpClient, HttpError


class BirdeyeClient:
    BASE_URL = "https://public-api.birdeye.so/public"

    def __init__(self, api_key: str, http_client: HttpClient):
        if not api_key:
            raise ValueError("Birdeye API key is required")
        self.api_key = api_key
        self.http = http_client

    def _headers(self) -> Dict[str, str]:
        return {
            "X-API-KEY": self.api_key,
            "accept": "application/json",
        }

    async def fetch_market_data(
        self, mint_address: str, session: aiohttp.ClientSession
    ) -> Dict[str, Any]:
        """
        Retrieve market snapshot (price, liquidity, volume, fdv).
        """
        url = f"{self.BASE_URL}/token/market-data"
        params = {"address": mint_address}
        data = await self.http.get_json(
            url,
            session=session,
            params=params,
            headers=self._headers(),
            metrics_tag="birdeye:market_data",
        )
        payload = data.get("data") or data
        return {
            "price_usd": payload.get("priceUsd")
            or payload.get("price_usd")
            or payload.get("value")
            or payload.get("price"),
            "liquidity_usd": payload.get("liquidity")
            or payload.get("liquidityUsd")
            or payload.get("liquidity_usd"),
            "volume_24h": payload.get("volume24h")
            or payload.get("volume24hUsd")
            or payload.get("volume_usd")
            or payload.get("volume24hUsdValue"),
            "fdv_usd": payload.get("fdv")
            or payload.get("fdvUsd")
            or payload.get("marketCap")
            or payload.get("market_cap"),
            "raw": payload,
        }

    async def fetch_holder_stats(
        self, mint_address: str, session: aiohttp.ClientSession
    ) -> Dict[str, Any]:
        """
        Retrieve holder statistics (total holders, top holder weight) if available.
        """
        url = f"{self.BASE_URL}/token/holders"
        params = {"address": mint_address}
        try:
            data = await self.http.get_json(
                url,
                session=session,
                params=params,
                headers=self._headers(),
                metrics_tag="birdeye:holders",
            )
        except HttpError as exc:
            # Some tokens may not have holder analytics yet; surface as empty dict.
            if exc.status in {400, 404, 422}:
                return {}
            raise

        payload = data.get("data") or data
        holder_count = (
            payload.get("holders")
            or payload.get("holder")
            or payload.get("address_count")
            or payload.get("holder_count")
        )
        top_holder_pct = (
            payload.get("topHolderPercent")
            or payload.get("top_holder_percent")
            or payload.get("largestHolderPercent")
        )
        return {
            "holder_count": holder_count,
            "top_holder_percentage": top_holder_pct,
            "raw": payload,
        }
