"""
PUMP.FUN PROFIT SCANNER - Main Entry Point

Simple system focused on making money from Pump.fun tokens.

How it works:
1. Scan Pump.fun for new tokens (every 10 seconds)
2. Analyze each token for profit potential
3. Show BUY signals on dashboard
4. You manually trade the best opportunities

Strategy:
- Get in early (tokens < 30 minutes old)
- Look for momentum indicators (activity, mcap growth)
- Set tight stop losses (-20% to -30%)
- Take profits at 2-3x
"""

import asyncio
from pumpfun_scanner import PumpFunScanner
from profit_analyzer import ProfitAnalyzer
from simple_dashboard import SimpleDashboard


async def main():
    """Main runner"""
    print("\n" + "=" * 70)
    print("🚀 PUMP.FUN PROFIT SCANNER")
    print("=" * 70)
    print("\nFocused. Simple. Profitable.")
    print("\nScanning Pump.fun for new token launches...")
    print("Looking for early momentum indicators...")
    print("BUY signals will appear in dashboard.\n")
    print("Press Ctrl+C to stop\n")

    # Initialize components
    scanner = PumpFunScanner()
    analyzer = ProfitAnalyzer()
    dashboard = SimpleDashboard()

    # Callback for new tokens
    async def handle_new_tokens(tokens):
        """Process newly discovered tokens"""
        for token in tokens:
            # Analyze
            analysis = analyzer.analyze(token)

            # Add to dashboard
            dashboard.add_token(token, analysis)

            # Print alert above dashboard
            dashboard.print_token_alert(token, analysis)

    # Start scanner in background
    scan_task = asyncio.create_task(
        scanner.monitor_new_tokens(handle_new_tokens, interval=10)
    )

    # Run dashboard (blocks until Ctrl+C)
    try:
        # Give scanner a moment to start
        await asyncio.sleep(2)

        # Show dashboard
        dashboard.run()

    except KeyboardInterrupt:
        print("\n\n[STOPPED] Scanner stopped by user")
        scan_task.cancel()

    print("\nShutting down...")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBye!")
