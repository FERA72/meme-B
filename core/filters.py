"""
Safety filters to detect potential rug pulls and scams
Analyzes token data and flags suspicious characteristics
Enhanced with ML-ready quick-profit rug detection
"""

from typing import Dict, List, Tuple, Optional
from datetime import datetime
import math


class TokenFilter:
    """
    Applies safety checks to detect potentially dangerous tokens
    Each filter returns (passed, reason) tuple
    """
    
    def __init__(self, config: Dict = None):
        """
        Initialize filter with configurable thresholds
        
        Args:
            config: Dictionary with filter thresholds
        """
        # Default configuration - ADJUST THESE VALUES AS NEEDED
        self.config = config or {
            'min_liquidity_usd': 20000,  # Minimum $20k liquidity (REPLACE ME with your threshold)
            'max_top_holder_pct': 40,    # Max 40% held by single wallet (REPLACE ME)
            'min_holder_count': 10,       # At least 10 holders (REPLACE ME)
            'max_mint_authority': False,  # Must be None (revoked)
            'max_freeze_authority': False, # Must be None (revoked)
        }
    
    def check_liquidity(self, token_data: Dict) -> Tuple[bool, str]:
        """
        Check if token has sufficient liquidity
        Low liquidity = easy to manipulate price = DANGEROUS
        
        Args:
            token_data: Dictionary with token information
        
        Returns:
            (passed, reason) tuple
        """
        liquidity = token_data.get('liquidity_usd', 0)
        min_liquidity = self.config['min_liquidity_usd']
        
        if liquidity < min_liquidity:
            return False, f"Liquidity too low: ${liquidity:.2f} < ${min_liquidity}"
        
        return True, f"Liquidity OK: ${liquidity:.2f}"
    
    def check_mint_authority(self, token_data: Dict) -> Tuple[bool, str]:
        """
        Check if mint authority is revoked
        If NOT revoked, creator can print unlimited tokens = RUG PULL RISK
        
        Args:
            token_data: Dictionary with token information
        
        Returns:
            (passed, reason) tuple
        """
        mint_auth = token_data.get('mint_authority')
        
        # None means revoked (GOOD)
        if mint_auth is not None:
            return False, f"Mint authority NOT revoked: {mint_auth}"
        
        return True, "Mint authority revoked (SAFE)"
    
    def check_freeze_authority(self, token_data: Dict) -> Tuple[bool, str]:
        """
        Check if freeze authority is revoked
        If NOT revoked, creator can freeze your wallet = DANGER
        
        Args:
            token_data: Dictionary with token information
        
        Returns:
            (passed, reason) tuple
        """
        freeze_auth = token_data.get('freeze_authority')
        
        # None means revoked (GOOD)
        if freeze_auth is not None:
            return False, f"Freeze authority NOT revoked: {freeze_auth}"
        
        return True, "Freeze authority revoked (SAFE)"
    
    def check_holder_concentration(self, token_data: Dict) -> Tuple[bool, str]:
        """
        Check if supply is too concentrated in one wallet
        High concentration = creator can dump = RUG PULL RISK
        
        Args:
            token_data: Dictionary with token information
        
        Returns:
            (passed, reason) tuple
        """
        top_holder_pct = token_data.get('top_holder_percentage', 0)
        max_pct = self.config['max_top_holder_pct']
        
        if top_holder_pct > max_pct:
            return False, f"Top holder owns {top_holder_pct:.1f}% (max allowed: {max_pct}%)"
        
        return True, f"Holder concentration OK: {top_holder_pct:.1f}%"
    
    def check_holder_count(self, token_data: Dict) -> Tuple[bool, str]:
        """
        Check if token has enough holders
        Very few holders = no real community = SUSPICIOUS
        
        Args:
            token_data: Dictionary with token information
        
        Returns:
            (passed, reason) tuple
        """
        holder_count = token_data.get('holder_count', 0)
        min_holders = self.config['min_holder_count']
        
        if holder_count < min_holders:
            return False, f"Too few holders: {holder_count} < {min_holders}"
        
        return True, f"Holder count OK: {holder_count}"
    
    def check_lp_lock(self, token_data: Dict) -> Tuple[bool, str]:
        """
        Check if liquidity pool is locked
        Unlocked LP = creator can remove all liquidity = RUG PULL
        
        Args:
            token_data: Dictionary with token information
        
        Returns:
            (passed, reason) tuple
        """
        lp_locked = token_data.get('lp_locked', False)
        lp_burn_pct = token_data.get('lp_burn_percentage', 0)
        
        # Consider it "locked" if LP tokens are burned (even better than locked)
        if lp_locked or lp_burn_pct > 90:
            return True, "LP is locked or burned (SAFE)"
        
        # For new tokens, we might be lenient here
        # Some legit projects lock LP after launch
        return False, "LP not locked (RISKY)"
    
    def check_price_available(self, token_data: Dict) -> Tuple[bool, str]:
        """
        Check if token has price data (means it's trading)
        No price = not yet trading or no liquidity
        
        Args:
            token_data: Dictionary with token information
        
        Returns:
            (passed, reason) tuple
        """
        price = token_data.get('price_usd', 0)
        
        if price <= 0:
            return False, "No price data available (not trading yet?)"
        
        return True, f"Trading at ${price:.10f}"
    
    def apply_all_filters(self, token_data: Dict) -> Dict:
        """
        Run ALL filters on a token and return comprehensive results
        This is the main method to use
        
        Args:
            token_data: Dictionary with token information
        
        Returns:
            Dictionary with filter results:
            {
                'passed': bool,           # Did it pass ALL filters?
                'safe_score': int,        # How many filters it passed (0-7)
                'failed_filters': list,   # Names of failed filters
                'results': dict          # Detailed results from each filter
            }
        """
        # List of all filter functions to run
        filters = [
            ('liquidity', self.check_liquidity),
            ('mint_authority', self.check_mint_authority),
            ('freeze_authority', self.check_freeze_authority),
            ('holder_concentration', self.check_holder_concentration),
            ('holder_count', self.check_holder_count),
            ('lp_lock', self.check_lp_lock),
            ('price_available', self.check_price_available)
        ]
        
        results = {}
        failed_filters = []
        passed_count = 0
        
        # Run each filter
        for filter_name, filter_func in filters:
            passed, reason = filter_func(token_data)
            
            results[filter_name] = {
                'passed': passed,
                'reason': reason
            }
            
            if passed:
                passed_count += 1
            else:
                failed_filters.append(filter_name)
        
        # Token is "safe" if it passes ALL critical filters
        # LP lock is optional for very new tokens
        critical_filters = [
            'liquidity', 'mint_authority', 'freeze_authority', 
            'holder_concentration', 'price_available'
        ]
        
        all_critical_passed = all(
            results[f]['passed'] for f in critical_filters if f in results
        )
        
        return {
            'passed': all_critical_passed,
            'safe_score': passed_count,
            'total_filters': len(filters),
            'failed_filters': failed_filters,
            'results': results,
            'risk_level': self._calculate_risk_level(passed_count, len(filters))
        }
    
    def _calculate_risk_level(self, passed: int, total: int) -> str:
        """
        Calculate risk level based on how many filters passed

        Args:
            passed: Number of filters passed
            total: Total number of filters

        Returns:
            Risk level string
        """
        percentage = (passed / total) * 100

        if percentage >= 90:
            return "LOW"
        elif percentage >= 70:
            return "MEDIUM"
        elif percentage >= 50:
            return "HIGH"
        else:
            return "CRITICAL"

    def detect_quick_profit_rug(self, token_data: Dict) -> Dict:
        """
        ADVANCED: Detect if token might rug BUT could be profitable in first minutes

        This analyzes tokens that have rug indicators but show strong early momentum.
        Goal: Identify tokens where you can profit before the rug happens.

        Args:
            token_data: Dictionary with token information

        Returns:
            Dictionary with quick profit analysis:
            {
                'is_quick_profit_opportunity': bool,
                'profit_window_minutes': float,
                'expected_max_profit_pct': float,
                'rug_probability': float (0-1),
                'signals': list of detected signals,
                'strategy': recommended entry/exit strategy
            }
        """
        signals = []
        warnings = []
        rug_indicators = 0
        profit_indicators = 0

        # Get token metrics
        liquidity = token_data.get('liquidity_usd', 0)
        holder_count = token_data.get('holder_count', 0)
        top_holder_pct = token_data.get('top_holder_percentage', 0)
        volume_24h = token_data.get('volume_24h', 0)
        price = token_data.get('price_usd', 0)
        market_cap = token_data.get('market_cap', 0)

        # Check for trades data
        metadata = token_data.get('token_metadata', {}) or {}
        trades = metadata.get('trades', {})
        buy_count = trades.get('buy_count', 0)
        sell_count = trades.get('sell_count', 0)

        # === RUG INDICATORS ===

        # High concentration = potential rug
        if top_holder_pct > 30:
            rug_indicators += 1
            warnings.append(f"High concentration: {top_holder_pct:.1f}%")

        # Authorities not revoked = can rug anytime
        if token_data.get('mint_authority') is not None:
            rug_indicators += 2  # This is serious
            warnings.append("Mint authority NOT revoked")

        if token_data.get('freeze_authority') is not None:
            rug_indicators += 1
            warnings.append("Freeze authority NOT revoked")

        # No LP lock = liquidity can be pulled
        if not token_data.get('lp_locked', False) and token_data.get('lp_burn_percentage', 0) < 90:
            rug_indicators += 2
            warnings.append("LP not locked or burned")

        # === PROFIT INDICATORS ===

        # Strong buying pressure
        if buy_count > 0 and sell_count > 0:
            buy_sell_ratio = buy_count / max(sell_count, 1)
            if buy_sell_ratio > 2.0:
                profit_indicators += 2
                signals.append(f"Strong buy pressure: {buy_sell_ratio:.1f}x more buys")

        # High volume relative to liquidity = active trading
        if liquidity > 0:
            volume_to_liquidity = volume_24h / liquidity
            if volume_to_liquidity > 0.5:
                profit_indicators += 1
                signals.append(f"High trading activity: {volume_to_liquidity:.1f}x volume/liquidity")

        # Decent liquidity = easier to enter/exit
        if 10000 <= liquidity < 50000:
            profit_indicators += 1
            signals.append(f"Good liquidity for quick trades: ${liquidity:,.0f}")

        # Growing holder count = interest building
        if holder_count > 20:
            profit_indicators += 1
            signals.append(f"Decent holder base: {holder_count}")

        # Reasonable market cap = room to grow
        if market_cap > 0 and 50000 < market_cap < 500000:
            profit_indicators += 1
            signals.append(f"Room for growth: ${market_cap:,.0f} mcap")

        # === CALCULATE OPPORTUNITY SCORE ===

        # Is it a quick profit opportunity?
        is_opportunity = (
            rug_indicators >= 2 and  # Has rug risk
            profit_indicators >= 3 and  # BUT has profit signals
            liquidity >= 10000 and  # Enough liquidity to trade
            price > 0  # Actually trading
        )

        # Estimate profit window (shorter if more rug indicators)
        profit_window_minutes = max(3, 15 - (rug_indicators * 2))

        # Estimate max profit based on momentum
        expected_profit_pct = min(200, profit_indicators * 20)

        # Calculate rug probability
        rug_probability = min(0.95, rug_indicators * 0.2)

        # === STRATEGY ===
        strategy = {}
        if is_opportunity:
            strategy = {
                'action': 'QUICK_SCALP',
                'max_hold_minutes': profit_window_minutes,
                'entry_advice': 'Enter on first dip, exit on momentum peak',
                'exit_trigger': f'Exit after {expected_profit_pct/2:.0f}% gain or {profit_window_minutes} minutes',
                'stop_loss': '-15%',
                'position_size': 'SMALL (1-2% of portfolio)',
                'warnings': warnings
            }

        return {
            'is_quick_profit_opportunity': is_opportunity,
            'profit_window_minutes': profit_window_minutes,
            'expected_max_profit_pct': expected_profit_pct,
            'rug_probability': rug_probability,
            'rug_indicators': rug_indicators,
            'profit_indicators': profit_indicators,
            'signals': signals,
            'warnings': warnings,
            'strategy': strategy,
            'opportunity_score': profit_indicators * 10 if is_opportunity else 0
        }

    def calculate_ml_features(self, token_data: Dict) -> Dict:
        """
        Extract and calculate ALL features needed for ML training

        This creates a standardized feature set that ML models can learn from.
        Features are normalized and calculated to be ML-ready.

        Args:
            token_data: Raw token data

        Returns:
            Dictionary of ML features with consistent naming and normalization
        """
        metadata = token_data.get('token_metadata', {}) or {}
        trades = metadata.get('trades', {})

        # Basic metrics
        liquidity = float(token_data.get('liquidity_usd', 0))
        market_cap = float(token_data.get('market_cap', 0))
        price = float(token_data.get('price_usd', 0))
        volume_24h = float(token_data.get('volume_24h', 0))
        holder_count = int(token_data.get('holder_count', 0))
        top_holder_pct = float(token_data.get('top_holder_percentage', 0))

        # Trading metrics
        buy_count = int(trades.get('buy_count', 0))
        sell_count = int(trades.get('sell_count', 0))
        total_trades = buy_count + sell_count
        buy_sell_ratio = buy_count / max(sell_count, 1) if sell_count > 0 else buy_count

        # Authority flags
        mint_authority_revoked = token_data.get('mint_authority') is None
        freeze_authority_revoked = token_data.get('freeze_authority') is None
        lp_locked = token_data.get('lp_locked', False)
        lp_burn_pct = float(token_data.get('lp_burn_percentage', 0))

        # Calculated ratios
        volume_to_liquidity = volume_24h / max(liquidity, 1)
        mcap_to_liquidity = market_cap / max(liquidity, 1)
        volume_per_holder = volume_24h / max(holder_count, 1)

        # Concentration risk
        holder_concentration_risk = top_holder_pct / 100.0

        # Social presence
        has_website = bool(metadata.get('website'))
        has_twitter = bool(metadata.get('twitter'))
        has_telegram = bool(metadata.get('telegram'))
        description_length = len(metadata.get('description', ''))

        # Risk scores (0-1)
        authority_risk = (not mint_authority_revoked) * 0.5 + (not freeze_authority_revoked) * 0.3
        lp_risk = (not lp_locked and lp_burn_pct < 90) * 0.4
        concentration_risk = min(1.0, top_holder_pct / 50.0)

        overall_risk_score = (authority_risk + lp_risk + concentration_risk) / 3.0

        return {
            # Core metrics
            'liquidity_usd': liquidity,
            'market_cap': market_cap,
            'price_usd': price,
            'volume_24h': volume_24h,
            'holder_count': holder_count,
            'top_holder_pct': top_holder_pct,

            # Trading metrics
            'buy_count': buy_count,
            'sell_count': sell_count,
            'total_trades': total_trades,
            'buy_sell_ratio': buy_sell_ratio,

            # Boolean flags
            'mint_authority_revoked': mint_authority_revoked,
            'freeze_authority_revoked': freeze_authority_revoked,
            'lp_locked': lp_locked,
            'lp_burn_pct': lp_burn_pct,

            # Calculated ratios
            'volume_to_liquidity_ratio': volume_to_liquidity,
            'mcap_to_liquidity_ratio': mcap_to_liquidity,
            'volume_per_holder': volume_per_holder,

            # Risk metrics (0-1 normalized)
            'holder_concentration_risk': holder_concentration_risk,
            'authority_risk': authority_risk,
            'lp_risk': lp_risk,
            'overall_risk_score': overall_risk_score,

            # Social indicators
            'has_website': has_website,
            'has_twitter': has_twitter,
            'has_telegram': has_telegram,
            'description_length': description_length,

            # Derived features
            'trading_active': total_trades > 10,
            'high_concentration': top_holder_pct > 40,
            'dangerous_authorities': not (mint_authority_revoked and freeze_authority_revoked),
            'no_lp_protection': not lp_locked and lp_burn_pct < 90,
        }

    def update_config(self, new_config: Dict):
        """
        Update filter configuration on the fly

        Args:
            new_config: Dictionary with new threshold values
        """
        self.config.update(new_config)
        print(f"Filter config updated: {self.config}")


# Example usage:
# filter = TokenFilter()
# result = filter.apply_all_filters(token_data)
# if result['passed']:
#     print("Token is safe!")
# else:
#     print(f"Token failed: {result['failed_filters']}")
