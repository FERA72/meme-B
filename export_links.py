"""
Export all token DexScreener links to a file for easy access
Run this to get all links
"""

import os
from dotenv import load_dotenv
from db.database import init_database

load_dotenv()

def export_links():
    """Export all token links to text file"""
    database_url = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/memebeta")
    db = init_database(database_url)

    # Get all tokens
    tokens = db.get_all_tokens(include_blacklisted=True)

    print(f"\n📋 Found {len(tokens)} tokens in database\n")
    print("=" * 80)

    # Write to file
    with open("dexscreener_links.txt", "w") as f:
        f.write("DEXSCREENER LINKS - ALL TOKENS\n")
        f.write("=" * 80 + "\n\n")

        for i, token in enumerate(tokens, 1):
            link = f"https://dexscreener.com/solana/{token.mint_address}"
            status = "SAFE" if token.is_safe else "RISKY"
            line = f"{i}. {token.symbol or 'UNK'} ({status}): {link}\n"
            f.write(line)
            print(line.strip())

    print("\n" + "=" * 80)
    print(f"✅ Links saved to: dexscreener_links.txt")
    print("=" * 80 + "\n")

if __name__ == "__main__":
    export_links()
