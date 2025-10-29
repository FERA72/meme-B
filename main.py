"""
REAL-TIME PUMP.FUN MONITOR - Main Runner

Monitors Pump.fun for new tokens EVERY SECOND.
Collects ALL available data for each token.
Displays everything in real-time PowerShell dashboard.

Features:
✅ Real-time scanning (checks every 1-2 seconds)
✅ Comprehensive data collection (market, holders, transactions)
✅ Live updating dashboard with full token table
✅ Links panel with Pump.fun and DexScreener URLs
✅ Instant alerts when new tokens appear
"""

import asyncio
from realtime_scanner import RealtimePumpScanner
from data_collector import DataCollector
from realtime_dashboard import RealtimeDashboard


async def main():
    """Main entry point"""
    print("\n" + "=" * 70)
    print("🔥 REAL-TIME PUMP.FUN MONITOR")
    print("=" * 70)
    print("\nMonitoring Pump.fun for new token launches...")
    print("Collecting ALL data: MCap, Volume, Liquidity, B/S, Holders, etc.")
    print("Dashboard updates LIVE every second.\n")
    print("Press Ctrl+C to stop\n")

    # Initialize components
    scanner = RealtimePumpScanner()
    collector = DataCollector()
    dashboard = RealtimeDashboard(max_tokens=50)

    # Callback for new tokens
    async def handle_new_tokens(tokens: list):
        """Process newly discovered tokens"""
        for token in tokens:
            # Print alert above dashboard
            dashboard.print_new_token_alert(token)

            # Collect comprehensive data (in background to not slow down feed)
            asyncio.create_task(enrich_and_add_token(token))

    async def enrich_and_add_token(token):
        """Enrich token with full data and add to dashboard"""
        try:
            # Collect all data
            complete_data = await collector.collect_all_data(token)

            # Add to dashboard
            dashboard.add_token(complete_data)

        except Exception as e:
            print(f"[ERROR] Failed to enrich token {token.get('symbol')}: {e}")
            # Add anyway with basic data
            dashboard.add_token(token)

    # Start scanner in background
    scan_task = asyncio.create_task(
        scanner.monitor_realtime(handle_new_tokens, interval=1.5)  # Check every 1.5 seconds
    )

    # Give scanner a moment to start
    await asyncio.sleep(2)

    # Run dashboard (blocks until Ctrl+C)
    try:
        await dashboard.run_live()

    except KeyboardInterrupt:
        print("\n\n[STOPPED] Monitor stopped by user")
        scan_task.cancel()

    print("\nShutting down...")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBye!")
