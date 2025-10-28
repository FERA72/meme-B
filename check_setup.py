"""
Setup verification script
Run this to check if everything is configured correctly
"""

import os
import sys
from dotenv import load_dotenv

def check_python_version():
    """Check if Python version is 3.9+"""
    print("\n[1/6] Checking Python version...")
    version = sys.version_info
    if version.major == 3 and version.minor >= 9:
        print(f"  ✓ Python {version.major}.{version.minor}.{version.micro} (OK)")
        return True
    else:
        print(f"  ✗ Python {version.major}.{version.minor}.{version.micro} (Need 3.9+)")
        return False

def check_env_file():
    """Check if .env file exists and has required values"""
    print("\n[2/6] Checking .env file...")
    
    if not os.path.exists('.env'):
        print("  ✗ .env file not found!")
        print("  → Copy .env.example to .env and configure it")
        return False
    
    print("  ✓ .env file exists")
    
    # Load and check values
    load_dotenv()
    
    errors = []
    
    database_url = os.getenv('DATABASE_URL', '')
    if 'REPLACE_ME' in database_url or not database_url:
        errors.append("DATABASE_URL not configured")
    
    helius_key = os.getenv('HELIUS_API_KEY', '')
    if helius_key == 'REPLACE_ME' or not helius_key:
        errors.append("HELIUS_API_KEY not configured")
    
    if errors:
        print("  ✗ Configuration errors:")
        for error in errors:
            print(f"    - {error}")
        return False
    
    print("  ✓ Configuration looks good")
    return True

def check_dependencies():
    """Check if all required packages are installed"""
    print("\n[3/6] Checking Python packages...")
    
    required = [
        'flask',
        'sqlalchemy',
        'psycopg2',
        'requests',
        'aiohttp',
        'rich',
        'dotenv'  # Package is python-dotenv but imports as dotenv
    ]
    
    missing = []
    for package in required:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)
    
    if missing:
        print("  ✗ Missing packages:")
        for pkg in missing:
            print(f"    - {pkg}")
        print("\n  → Run: pip install -r requirements.txt")
        return False
    
    print("  ✓ All packages installed")
    return True

def check_database():
    """Check if PostgreSQL is accessible"""
    print("\n[4/6] Checking PostgreSQL connection...")
    
    try:
        import psycopg2
        from dotenv import load_dotenv
        load_dotenv()
        
        database_url = os.getenv('DATABASE_URL')
        
        # Try to connect
        conn = psycopg2.connect(database_url)
        conn.close()
        
        print("  ✓ PostgreSQL connection successful")
        return True
        
    except Exception as e:
        print(f"  ✗ Database connection failed: {e}")
        print("\n  Troubleshooting:")
        print("    1. Is PostgreSQL running?")
        print("    2. Is the password in .env correct?")
        print("    3. Does the 'memebeta' database exist?")
        print("\n  Create database with: psql -U postgres -c 'CREATE DATABASE memebeta;'")
        return False

def check_helius():
    """Check if Helius API key works"""
    print("\n[5/6] Checking Helius API...")
    
    try:
        import requests
        from dotenv import load_dotenv
        load_dotenv()
        
        api_key = os.getenv('HELIUS_API_KEY')
        
        # Test API call
        url = f"https://api.helius.xyz/v0/addresses/So11111111111111111111111111111111111111112/balances?api-key={api_key}"
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            print("  ✓ Helius API key is valid")
            return True
        elif response.status_code == 429:
            print(f"  ⚠ Helius API rate limit reached (429)")
            print("  → This is normal on free tier - your key works!")
            print("  → System will work fine, just slower during rate limits")
            return True  # Key is valid, just rate limited
        else:
            print(f"  ✗ Helius API returned status {response.status_code}")
            print("  → Check your API key at helius.dev")
            return False
            
    except Exception as e:
        print(f"  ✗ Helius API check failed: {e}")
        print("  → Get FREE API key from helius.dev")
        return False

def check_database_tables():
    """Check if database tables are created"""
    print("\n[6/6] Checking database tables...")
    
    try:
        from db.database import init_database
        from dotenv import load_dotenv
        load_dotenv()
        
        database_url = os.getenv('DATABASE_URL')
        db = init_database(database_url)
        
        # Try to query
        tokens = db.get_all_tokens(limit=1)
        
        print("  ✓ Database tables exist and are accessible")
        return True
        
    except Exception as e:
        print(f"  ✗ Table check failed: {e}")
        print("\n  Tables will be created automatically on first run")
        return False

def main():
    """Run all checks"""
    print("="*80)
    print("MEME-BETA.5 SETUP VERIFICATION")
    print("="*80)
    
    checks = [
        check_python_version(),
        check_env_file(),
        check_dependencies(),
        check_database(),
        check_helius(),
        check_database_tables()
    ]
    
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    
    passed = sum(checks)
    total = len(checks)
    
    print(f"\nPassed: {passed}/{total} checks")
    
    if passed == total:
        print("\n✓ ALL CHECKS PASSED! You're ready to run:")
        print("  python main.py")
    elif passed >= 4:
        print("\n⚠ MOSTLY READY - Some optional checks failed")
        print("  You can try running: python main.py")
        print("  But some features might not work")
    else:
        print("\n✗ SETUP INCOMPLETE - Fix the errors above")
        print("  Read README.md for detailed setup instructions")
    
    print("\n" + "="*80 + "\n")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nSetup check cancelled by user")
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
