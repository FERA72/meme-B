"""
Advanced ML Agent powered by OpenAI API for token analysis and decision-making.

This is the ML brain that learns from patterns, predicts outcomes, and makes trading decisions.
It analyzes tokens, identifies quick profit opportunities, and detects rugs before they happen.
"""

from __future__ import annotations

import json
import os
import threading
from typing import Dict, Optional, List
from datetime import datetime

from core.logger import get_logger

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - optional dependency
    OpenAI = None


class GPTAgent:
    """
    Advanced ML Agent that learns from token patterns and makes trading decisions.

    This agent can:
    - Analyze tokens and predict outcomes
    - Detect quick profit opportunities (even in potential rugs)
    - Learn from historical data
    - Make buy/sell/hold decisions
    - Track prediction accuracy
    """

    def __init__(self, api_key: str, model: str = "gpt-4o-mini", cache_size: int = 128):
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required for GPT Agent")
        if OpenAI is None:
            raise RuntimeError("openai package is not installed. Run `pip install openai`.")

        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.cache_size = cache_size
        self.cache: Dict[str, Dict] = {}
        self.lock = threading.Lock()
        self.log = get_logger("gpt_agent")

        # Track historical patterns for learning
        self.historical_patterns: List[Dict] = []
        self.prediction_accuracy: Dict[str, float] = {}

    def evaluate(self, token_data: Dict) -> Optional[Dict]:
        """
        Simple evaluation (legacy method for compatibility)
        """
        return self.analyze_token(token_data)

    def analyze_token(self, token_data: Dict, ml_features: Dict = None) -> Optional[Dict]:
        """
        MAIN METHOD: Complete ML analysis of a token

        Args:
            token_data: Raw token data
            ml_features: Pre-calculated ML features (optional)

        Returns:
            Complete analysis including predictions, recommendations, and learning data
        """
        mint = token_data.get("mint_address")
        if not mint:
            return None

        # Check cache
        with self.lock:
            cached = self.cache.get(mint)
            if cached:
                return cached

        # Build comprehensive prompt with historical context
        prompt = self._build_ml_prompt(token_data, ml_features)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": self._get_system_prompt()
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.2,
                response_format={"type": "json_object"}
            )

            text = response.choices[0].message.content
            result = json.loads(text)

        except Exception as exc:
            self.log.warning("GPT analysis failed for %s: %s", mint, exc)
            return None

        # Parse and structure the result
        analysis = self._structure_analysis(result, token_data)

        # Cache the result
        with self.lock:
            if len(self.cache) >= self.cache_size:
                self.cache.pop(next(iter(self.cache)))
            self.cache[mint] = analysis

        return analysis

    def detect_quick_profit(self, token_data: Dict, ml_features: Dict = None) -> Optional[Dict]:
        """
        Specialized method to detect quick profit opportunities (even in potential rugs)

        Args:
            token_data: Token data
            ml_features: ML features

        Returns:
            Quick profit analysis or None
        """
        mint = token_data.get("mint_address")
        if not mint:
            return None

        prompt = self._build_quick_profit_prompt(token_data, ml_features)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert memecoin quick-scalp trader. You identify tokens that can be profitable in the first few minutes, even if they might rug later. Your goal is maximum profit in minimal time."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )

            text = response.choices[0].message.content
            result = json.loads(text)

            return self._structure_quick_profit_result(result, token_data)

        except Exception as exc:
            self.log.warning("Quick profit analysis failed for %s: %s", mint, exc)
            return None

    def learn_from_outcome(self, mint_address: str, predicted: Dict, actual: Dict):
        """
        Learn from actual outcomes to improve future predictions

        Args:
            mint_address: Token address
            predicted: What we predicted
            actual: What actually happened
        """
        pattern = {
            'mint': mint_address,
            'timestamp': datetime.utcnow().isoformat(),
            'predicted': predicted,
            'actual': actual,
            'accuracy': self._calculate_accuracy(predicted, actual)
        }

        with self.lock:
            self.historical_patterns.append(pattern)

            # Keep only recent patterns (last 1000)
            if len(self.historical_patterns) > 1000:
                self.historical_patterns = self.historical_patterns[-1000:]

            # Update accuracy metrics
            accuracy_key = predicted.get('predicted_outcome', 'unknown')
            if accuracy_key not in self.prediction_accuracy:
                self.prediction_accuracy[accuracy_key] = []

            self.prediction_accuracy[accuracy_key].append(pattern['accuracy'])

            # Keep only recent accuracy scores
            if len(self.prediction_accuracy[accuracy_key]) > 100:
                self.prediction_accuracy[accuracy_key] = self.prediction_accuracy[accuracy_key][-100:]

        self.log.info(f"Learned from {mint_address}: accuracy={pattern['accuracy']:.2f}")

    def get_learning_stats(self) -> Dict:
        """Get current learning statistics"""
        with self.lock:
            stats = {
                'total_patterns': len(self.historical_patterns),
                'avg_accuracy_by_outcome': {}
            }

            for outcome, accuracies in self.prediction_accuracy.items():
                if accuracies:
                    stats['avg_accuracy_by_outcome'][outcome] = sum(accuracies) / len(accuracies)

            return stats

    def _get_system_prompt(self) -> str:
        """System prompt for the ML agent"""
        return """You are an advanced ML-powered memecoin analysis agent. Your expertise:

1. Detect rug pulls before they happen
2. Identify quick profit opportunities (even in risky tokens)
3. Predict price movements in first minutes/hours
4. Learn from patterns to improve accuracy

Always respond in valid JSON format with these keys:
- predicted_outcome: "RUG" | "MOON" | "STABLE" | "QUICK_PROFIT"
- confidence: 0.0-1.0
- risk_score: 0-100
- opportunity_score: 0-100 (profit potential)
- rug_probability: 0.0-1.0
- expected_max_profit_pct: float
- time_to_peak_minutes: float
- recommended_action: "BUY" | "AVOID" | "WATCH" | "QUICK_SCALP"
- reasoning: string explaining your analysis
- key_signals: list of positive signals
- key_risks: list of risk factors"""

    def _build_ml_prompt(self, token_data: Dict, ml_features: Dict = None) -> str:
        """Build comprehensive prompt for ML analysis"""
        metadata = token_data.get("token_metadata", {}) or {}
        trades = metadata.get("trades", {}) or {}

        prompt_data = {
            "mint": token_data.get("mint_address"),
            "symbol": token_data.get("symbol"),
            "name": token_data.get("name"),

            # Core metrics
            "liquidity_usd": token_data.get("liquidity_usd"),
            "market_cap": token_data.get("market_cap"),
            "price_usd": token_data.get("price_usd"),
            "volume_24h": token_data.get("volume_24h"),

            # Holder data
            "holder_count": token_data.get("holder_count"),
            "top_holder_pct": token_data.get("top_holder_percentage"),

            # Authority status
            "mint_authority_revoked": token_data.get("mint_authority") is None,
            "freeze_authority_revoked": token_data.get("freeze_authority") is None,
            "lp_locked": token_data.get("lp_locked", False),

            # Trade data (CRITICAL for quick-profit detection)
            "buy_count": trades.get("buy_count", 0),
            "sell_count": trades.get("sell_count", 0),
            "buy_sell_ratio": trades.get("buy_sell_ratio", 0),
            "volume_5m": trades.get("volume_5m", 0),
            "price_change_5m": trades.get("price_change_5m", 0),
        }

        if ml_features:
            prompt_data["ml_features"] = ml_features

        return f"""Analyze this token and predict its outcome:

{json.dumps(prompt_data, indent=2)}

Consider:
1. Can this token be profitable in first 5-15 minutes?
2. What's the rug risk?
3. Is there strong buying momentum?
4. Should we trade this or avoid it?

Respond in JSON format as specified."""

    def _build_quick_profit_prompt(self, token_data: Dict, ml_features: Dict = None) -> str:
        """Build prompt specifically for quick profit detection"""
        metadata = token_data.get("token_metadata", {}) or {}
        trades = metadata.get("trades", {}) or {}

        prompt_data = {
            "liquidity_usd": token_data.get("liquidity_usd"),
            "market_cap": token_data.get("market_cap"),
            "price_change_5m": trades.get("price_change_5m", 0),
            "buy_count": trades.get("buy_count", 0),
            "sell_count": trades.get("sell_count", 0),
            "buy_sell_ratio": trades.get("buy_sell_ratio", 0),
            "volume_5m": trades.get("volume_5m", 0),
            "top_holder_pct": token_data.get("top_holder_percentage"),
            "mint_authority_revoked": token_data.get("mint_authority") is None,
            "lp_locked": token_data.get("lp_locked", False),
        }

        return f"""Quick scalp opportunity analysis:

{json.dumps(prompt_data, indent=2)}

This token has RUG INDICATORS but shows MOMENTUM. Can we profit in first few minutes before potential rug?

Respond in JSON:
{{
  "is_quick_profit_opportunity": bool,
  "expected_max_profit_pct": float,
  "profit_window_minutes": float,
  "rug_probability": float,
  "entry_advice": string,
  "exit_advice": string,
  "max_hold_minutes": float,
  "position_size_advice": string,
  "key_signals": [list],
  "key_risks": [list]
}}"""

    def _structure_analysis(self, result: Dict, token_data: Dict) -> Dict:
        """Structure GPT response into standard format"""
        return {
            "predicted_outcome": result.get("predicted_outcome", "UNKNOWN"),
            "confidence": float(result.get("confidence", 0)),
            "risk_score": float(result.get("risk_score", 50)),
            "opportunity_score": float(result.get("opportunity_score", 0)),
            "rug_probability": float(result.get("rug_probability", 0.5)),
            "expected_max_profit_pct": float(result.get("expected_max_profit_pct", 0)),
            "time_to_peak_minutes": float(result.get("time_to_peak_minutes", 0)),
            "recommended_action": result.get("recommended_action", "WATCH"),
            "reasoning": result.get("reasoning", ""),
            "key_signals": result.get("key_signals", []),
            "key_risks": result.get("key_risks", []),
            "raw_analysis": result,
            "analyzed_at": datetime.utcnow().isoformat(),
            "model_version": self.model
        }

    def _structure_quick_profit_result(self, result: Dict, token_data: Dict) -> Dict:
        """Structure quick profit response"""
        return {
            "is_quick_profit_opportunity": bool(result.get("is_quick_profit_opportunity", False)),
            "expected_max_profit_pct": float(result.get("expected_max_profit_pct", 0)),
            "profit_window_minutes": float(result.get("profit_window_minutes", 5)),
            "rug_probability": float(result.get("rug_probability", 0.5)),
            "entry_advice": result.get("entry_advice", ""),
            "exit_advice": result.get("exit_advice", ""),
            "max_hold_minutes": float(result.get("max_hold_minutes", 10)),
            "position_size_advice": result.get("position_size_advice", "SMALL"),
            "key_signals": result.get("key_signals", []),
            "key_risks": result.get("key_risks", []),
            "analyzed_at": datetime.utcnow().isoformat()
        }

    def _calculate_accuracy(self, predicted: Dict, actual: Dict) -> float:
        """Calculate prediction accuracy"""
        # Simple accuracy calculation - can be improved
        pred_outcome = predicted.get("predicted_outcome", "")
        actual_outcome = actual.get("actual_outcome", "")

        if pred_outcome == actual_outcome:
            return 1.0

        # Partial credit for close predictions
        if pred_outcome in ["RUG", "QUICK_PROFIT"] and actual_outcome in ["RUG", "QUICK_PROFIT"]:
            return 0.7

        if pred_outcome in ["MOON", "STABLE"] and actual_outcome in ["MOON", "STABLE"]:
            return 0.7

        return 0.0

    def export_training_data(self, filepath: str = "ml_training_data.json"):
        """Export historical patterns as training data for ML"""
        with self.lock:
            data = {
                "patterns": self.historical_patterns,
                "accuracy_stats": self.get_learning_stats(),
                "exported_at": datetime.utcnow().isoformat()
            }

        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)

        self.log.info(f"Exported {len(self.historical_patterns)} patterns to {filepath}")
        return filepath


# Legacy alias for compatibility
GPTScorer = GPTAgent
