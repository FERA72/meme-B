"""
PROFIT ANALYZER - Determine if a token is worth buying

Simple rules-based system to identify profitable opportunities.
Focus: Get in early, get out fast.
"""

from typing import Dict


class ProfitAnalyzer:
    """
    Analyzes tokens for profit potential.

    Strategy: Find tokens with early momentum indicators.
    """

    def __init__(self):
        # Thresholds
        self.MIN_MARKET_CAP = 5000  # At least $5k (has some interest)
        self.MAX_MARKET_CAP = 50000  # Under $50k (still early)
        self.MAX_AGE_MINUTES = 30  # Under 30 minutes old (very fresh)
        self.MIN_ACTIVITY = 3  # At least 3 replies (some engagement)

    def analyze(self, token: Dict) -> Dict:
        """
        Analyze a token and return profit signals.

        Returns:
        {
            "should_buy": bool,
            "confidence": float (0-100),
            "signals": [list of positive signals],
            "warnings": [list of concerns],
            "strategy": "description of play"
        }
        """
        signals = []
        warnings = []
        score = 0

        # Extract data
        mcap = token.get("market_cap_usd", 0)
        age_minutes = token.get("age_minutes", 999)
        activity = token.get("reply_count", 0)
        has_socials = bool(token.get("twitter") or token.get("telegram") or token.get("website"))
        symbol = token.get("symbol", "???")
        name = token.get("name", "")

        # === AGE CHECK ===
        if age_minutes < 5:
            signals.append("🔥 SUPER FRESH (<5 min)")
            score += 30
        elif age_minutes < 15:
            signals.append("🚀 Very fresh (<15 min)")
            score += 20
        elif age_minutes < 30:
            signals.append("✅ Fresh (<30 min)")
            score += 10
        else:
            warnings.append(f"⏰ Already {age_minutes:.0f} min old")
            score -= 20

        # === MARKET CAP CHECK ===
        if mcap < self.MIN_MARKET_CAP:
            warnings.append(f"💤 Low interest (${mcap:.0f} mcap)")
            score -= 10
        elif mcap > self.MAX_MARKET_CAP:
            warnings.append(f"📈 Already pumped (${mcap:.0f} mcap)")
            score -= 15
        else:
            signals.append(f"💰 Good mcap range (${mcap:.0f})")
            score += 15

        # === ACTIVITY CHECK ===
        if activity >= 10:
            signals.append(f"🔥 HIGH activity ({activity} replies)")
            score += 25
        elif activity >= self.MIN_ACTIVITY:
            signals.append(f"👥 Some activity ({activity} replies)")
            score += 10
        else:
            warnings.append(f"😴 Low activity ({activity} replies)")
            score -= 5

        # === SOCIAL PRESENCE ===
        if has_socials:
            signals.append("🌐 Has social links")
            score += 10
        else:
            warnings.append("❌ No social links")
            score -= 5

        # === NAME/SYMBOL CHECK ===
        # Look for obvious scam patterns
        scam_words = ["elon", "trump", "biden", "test", "rug", "scam"]
        name_lower = name.lower()
        symbol_lower = symbol.lower()

        if any(word in name_lower or word in symbol_lower for word in scam_words):
            warnings.append("⚠️ Suspicious name/symbol")
            score -= 20

        # === CALCULATE CONFIDENCE ===
        confidence = max(0, min(100, score))

        # === DECISION ===
        should_buy = (
            confidence >= 50 and
            age_minutes <= self.MAX_AGE_MINUTES and
            mcap >= self.MIN_MARKET_CAP and
            mcap <= self.MAX_MARKET_CAP
        )

        # === STRATEGY ===
        if should_buy:
            if confidence >= 70:
                strategy = "🎯 STRONG BUY - High confidence, enter with larger position"
            else:
                strategy = "✅ BUY - Good opportunity, enter with normal position"
        else:
            strategy = "❌ SKIP - Not enough positive signals"

        return {
            "should_buy": should_buy,
            "confidence": confidence,
            "signals": signals,
            "warnings": warnings,
            "strategy": strategy,
            "score": score,
        }

    def get_entry_target(self, token: Dict, analysis: Dict) -> Dict:
        """
        Calculate entry price and target exits.

        Returns suggested entry, take profit, and stop loss.
        """
        mcap = token.get("market_cap_usd", 0)
        confidence = analysis.get("confidence", 0)

        # Target multipliers based on confidence
        if confidence >= 70:
            take_profit_multiplier = 3.0  # 3x
            stop_loss_multiplier = 0.7  # -30%
        else:
            take_profit_multiplier = 2.0  # 2x
            stop_loss_multiplier = 0.8  # -20%

        return {
            "entry_mcap": mcap,
            "take_profit_mcap": mcap * take_profit_multiplier,
            "stop_loss_mcap": mcap * stop_loss_multiplier,
            "take_profit_multiplier": take_profit_multiplier,
            "stop_loss_pct": (1 - stop_loss_multiplier) * 100,
        }


# Test function
def test():
    analyzer = ProfitAnalyzer()

    # Test token examples
    test_tokens = [
        {
            "symbol": "BONK",
            "name": "Bonk Inu",
            "market_cap_usd": 15000,
            "age_minutes": 8,
            "reply_count": 15,
            "twitter": "https://x.com/bonk",
        },
        {
            "symbol": "SCAM",
            "name": "Elon Trump Coin",
            "market_cap_usd": 3000,
            "age_minutes": 45,
            "reply_count": 1,
            "twitter": None,
        },
        {
            "symbol": "MOON",
            "name": "To The Moon",
            "market_cap_usd": 75000,
            "age_minutes": 120,
            "reply_count": 50,
            "twitter": "https://x.com/moon",
        },
    ]

    print("Testing Profit Analyzer")
    print("=" * 60)

    for token in test_tokens:
        print(f"\n{token['symbol']} - {token['name']}")
        print(f"MCap: ${token['market_cap_usd']:,} | Age: {token['age_minutes']:.0f}m | Activity: {token['reply_count']}")

        analysis = analyzer.analyze(token)

        print(f"\n{analysis['strategy']}")
        print(f"Confidence: {analysis['confidence']}%")

        if analysis['signals']:
            print(f"\n✅ SIGNALS:")
            for signal in analysis['signals']:
                print(f"   {signal}")

        if analysis['warnings']:
            print(f"\n⚠️  WARNINGS:")
            for warning in analysis['warnings']:
                print(f"   {warning}")

        if analysis['should_buy']:
            targets = analyzer.get_entry_target(token, analysis)
            print(f"\n🎯 TARGETS:")
            print(f"   Entry: ${targets['entry_mcap']:,.0f}")
            print(f"   Take Profit: ${targets['take_profit_mcap']:,.0f} ({targets['take_profit_multiplier']}x)")
            print(f"   Stop Loss: ${targets['stop_loss_mcap']:,.0f} (-{targets['stop_loss_pct']:.0f}%)")

        print("-" * 60)


if __name__ == "__main__":
    test()
