"""
Alternative scanner using Helius RPC
Polls for new tokens instead of waiting for webhooks
"""

import time
import requests
from typing import List, Dict
from datetime import datetime


class RPCScanner:
    """
    Actively scans Solana for new token mints using RPC
    Use this if webhooks aren't working
    """
    
    def __init__(self, helius_api_key: str):
        """
        Initialize RPC scanner
        
        Args:
            helius_api_key: Your Helius API key
        """
        self.api_key = helius_api_key
        self.rpc_url = f"https://mainnet.helius-rpc.com/?api-key={helius_api_key}"
        self.last_signature = None
        
    def get_recent_token_mints(self, limit: int = 10) -> List[str]:
        """
        Get recently minted tokens from pump.fun
        
        Args:
            limit: Number of recent transactions to check
        
        Returns:
            List of mint addresses
        """
        # Pump.fun program address (where most memecoins mint)
        pump_program = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
        
        try:
            # Get recent signatures for pump.fun program
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getSignaturesForAddress",
                "params": [
                    pump_program,
                    {
                        "limit": limit,
                        "commitment": "confirmed"
                    }
                ]
            }
            
            response = requests.post(self.rpc_url, json=payload, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if 'result' in data:
                    signatures = data['result']
                    
                    # Get new signatures only
                    new_mints = []
                    for sig_info in signatures:
                        signature = sig_info['signature']
                        
                        # Stop if we've seen this before
                        if self.last_signature and signature == self.last_signature:
                            break
                        
                        # Parse transaction to find mint address
                        mint_address = self.parse_transaction(signature)
                        if mint_address:
                            new_mints.append(mint_address)
                    
                    # Update last signature
                    if signatures:
                        self.last_signature = signatures[0]['signature']
                    
                    return new_mints
        
        except Exception as e:
            print(f"Error getting recent mints: {e}")
        
        return []
    
    def parse_transaction(self, signature: str) -> str:
        """
        Parse a transaction to extract mint address
        
        Args:
            signature: Transaction signature
        
        Returns:
            Mint address or None
        """
        try:
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getTransaction",
                "params": [
                    signature,
                    {
                        "encoding": "jsonParsed",
                        "maxSupportedTransactionVersion": 0
                    }
                ]
            }
            
            response = requests.post(self.rpc_url, json=payload, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                if 'result' in data and data['result']:
                    # Look for new token accounts in the transaction
                    tx = data['result']
                    
                    # Check account keys for new mint accounts
                    if 'transaction' in tx and 'message' in tx['transaction']:
                        accounts = tx['transaction']['message'].get('accountKeys', [])
                        
                        # The mint address is usually in the accounts
                        # You'd need to parse instructions to find the exact one
                        # For now, return the first non-system account
                        for account in accounts:
                            if isinstance(account, dict):
                                pubkey = account.get('pubkey')
                            else:
                                pubkey = account
                            
                            # Skip system accounts
                            if pubkey and not pubkey.startswith('11111111'):
                                return pubkey
        
        except Exception as e:
            print(f"Error parsing transaction {signature}: {e}")
        
        return None
    
    def start_polling(self, scanner_instance, interval: int = 10):
        """
        Start polling for new mints
        
        Args:
            scanner_instance: Your TokenScanner instance
            interval: Seconds between polls (REPLACE ME - default 10)
        """
        print(f"🔍 Starting RPC polling every {interval} seconds...")
        print("Monitoring Pump.fun for new token mints...")
        
        while True:
            try:
                # Get recent mints
                new_mints = self.get_recent_token_mints(limit=20)
                
                if new_mints:
                    print(f"\n🆕 Found {len(new_mints)} new potential mints!")
                    
                    # Process each mint
                    for mint_address in new_mints:
                        print(f"Processing: {mint_address}")
                        scanner_instance.process_mint_event(mint_address)
                
                # Wait before next poll
                time.sleep(interval)
                
            except KeyboardInterrupt:
                print("\n👋 RPC polling stopped")
                break
            except Exception as e:
                print(f"Error in polling loop: {e}")
                time.sleep(interval)


# Example usage:
# rpc_scanner = RPCScanner(helius_api_key)
# rpc_scanner.start_polling(scanner_instance, interval=10)
