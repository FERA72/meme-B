"""
Safety filters to detect potential rug pulls and scams
Analyzes token data and flags suspicious characteristics
"""

from typing import Dict, List, Tuple


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
