"""
Optional GPT-based scoring helper.

Requires the `openai` package and a valid API key. Designed to be best-effort: if the
API is unavailable or returns an unexpected payload we simply skip the GPT score.
"""

from __future__ import annotations

import json
import os
import threading
from typing import Dict, Optional

from core.logger import get_logger

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - optional dependency
    OpenAI = None


class GPTScorer:
    def __init__(self, api_key: str, model: str = "gpt-4o-mini", cache_size: int = 128):
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required for GPT scoring")
        if OpenAI is None:
            raise RuntimeError("openai package is not installed. Run `pip install openai`." )

        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.cache_size = cache_size
        self.cache: Dict[str, Dict] = {}
        self.lock = threading.Lock()
        self.log = get_logger("gpt_scorer")

    def evaluate(self, token_data: Dict) -> Optional[Dict]:
        mint = token_data.get("mint_address")
        if not mint:
            return None

        with self.lock:
            cached = self.cache.get(mint)
            if cached:
                return cached

        prompt = self._build_prompt(token_data)

        try:
            response = self.client.responses.create(
                model=self.model,
                input=prompt,
                temperature=0.2,
            )
            text = response.output[0].content[0].text  # type: ignore[index]
            result = json.loads(text)
        except Exception as exc:  # pragma: no cover - external API
            self.log.warning("GPT evaluation failed for %s: %s", mint, exc)
            return None

        score = result.get("score")
        if not isinstance(score, (int, float)):
            self.log.debug("GPT response missing numeric score for %s", mint)
            return None

        verdict = {
            "score": float(score),
            "verdict": result.get("verdict", ""),
            "risk_flags": result.get("risk_flags", []),
            "raw": result,
        }

        with self.lock:
            if len(self.cache) >= self.cache_size:
                self.cache.pop(next(iter(self.cache)))
            self.cache[mint] = verdict

        return verdict

    def _build_prompt(self, token_data: Dict) -> str:
        metadata = token_data.get("token_metadata", {}) or {}
        trades = metadata.get("trades") or {}
        migration = metadata.get("migration") or {}

        return (
            "You are an expert crypto risk analyst. Review the following token data and "
            "return a JSON object with keys: score (0-100 float), verdict (short string), "
            "risk_flags (list of brief strings). Penalize unrealistic market caps, low liquidity, "
            "missing burns, or other red flags.\n" +
            json.dumps(
                {
                    "mint": token_data.get("mint_address"),
                    "symbol": token_data.get("symbol"),
                    "name": token_data.get("name"),
                    "liquidity_usd": token_data.get("liquidity_usd"),
                    "market_cap": token_data.get("market_cap"),
                    "volume_24h": token_data.get("volume_24h"),
                    "holder_count": token_data.get("holder_count"),
                    "top_holder_percentage": token_data.get("top_holder_percentage"),
                    "trades": trades,
                    "migration": migration,
                },
                indent=2,
            )
        )
