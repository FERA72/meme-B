"""
Main orchestrator for meme-beta.5.

Initialises all subsystems (database, collectors, filters, webhook server,
dashboard) and wires together real-time feeds from PumpPortal + GeckoTerminal.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from threading import Thread
from typing import Dict, Optional

from dotenv import load_dotenv


def _bool_env(value: Optional[str], default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}

from core.audit import perform_audit
from core.data_collector import DataCollector
from core.filters import TokenFilter
from core.graduation import GraduationWatcher
from core.pump_portal_stream import PumpPortalStream
from core.rpc_scanner_improved import RPCScanner as GeckoScanner
from core.scanner import TokenScanner
from core.token_refresher import TokenRefresher
from core.direct_scrapers import DirectScraperOrchestrator
from db.database import init_database, Database
from ui.dashboard import Dashboard
from webhook_server import init_webhook_server, run_webhook_server_async


# --------------------------------------------------------------------------- #
# Configuration helpers
# --------------------------------------------------------------------------- #
def load_config() -> Dict:
    """Load configuration from environment variables / .env file."""
    load_dotenv()

    return {
        "database_url": os.getenv(
            "DATABASE_URL", "postgresql://REPLACE_ME:REPLACE_ME@localhost:5432/memebeta"
        ),
        "helius_api_key": os.getenv("HELIUS_API_KEY", "REPLACE_ME"),
        "webhook_host": os.getenv("WEBHOOK_HOST", "0.0.0.0"),
        "webhook_port": int(os.getenv("WEBHOOK_PORT", 5000)),
        "min_liquidity_usd": float(os.getenv("MIN_LIQUIDITY_USD", 20000)),
        "max_top_holder_pct": float(os.getenv("MAX_TOP_HOLDER_PCT", 40)),
        "min_holder_count": int(os.getenv("MIN_HOLDER_COUNT", 10)),
        "min_liquidity_growth": float(os.getenv("MIN_LIQUIDITY_GROWTH", 2.0)),
        "min_market_cap": float(os.getenv("MIN_MARKET_CAP", 100000)),
        "min_holder_growth": float(os.getenv("MIN_HOLDER_GROWTH", 1.5)),
        "min_volume_24h": float(os.getenv("MIN_VOLUME_24H", 10000)),
        "graduation_check_interval": int(os.getenv("GRADUATION_CHECK_INTERVAL", 60)),
        "refresh_interval_seconds": int(os.getenv("REFRESH_INTERVAL_SECONDS", 120)),
        "enable_gpt_scoring": _bool_env(os.getenv("ENABLE_GPT_SCORING"), False),
        "gpt_model": os.getenv("GPT_MODEL", "gpt-4o-mini"),
        "birdeye_api_key": os.getenv("BIRDEYE_API_KEY"),
    }


def validate_config(config: Dict):
    """Ensure mandatory configuration values are set."""
    missing = []
    if "REPLACE_ME" in config["database_url"]:
        missing.append("DATABASE_URL not configured in .env")
    if config["helius_api_key"] == "REPLACE_ME":
        missing.append("HELIUS_API_KEY not configured in .env")

    if missing:
        print("\n" + "=" * 70)
        print("Configuration errors detected:")
        for item in missing:
            print(f" - {item}")
        print("\nUpdate your .env file before running meme-beta.5")
        print("=" * 70 + "\n")
        sys.exit(1)


# --------------------------------------------------------------------------- #
# System bootstrap
# --------------------------------------------------------------------------- #
def initialize_system(config: Dict):
    """Initialise database, data collector, filters, scanner, watcher, dashboard."""
    print("\n" + "=" * 70)
    print("Initialising MEME-BETA.5")
    print("=" * 70)

    print("[Init] Connecting database...")
    db = init_database(config["database_url"])
    print("[Init] Database ready")
    pruned = db.prune_placeholder_tokens()
    if pruned:
        print(f"[Init] Removed {pruned} placeholder tokens from previous runs")

    print("[Init] Setting up data collector...")
    collector = DataCollector(
        config["helius_api_key"],
        birdeye_api_key=config.get("birdeye_api_key"),
    )
    print("[Init] Data collector ready")

    print("[Init] Configuring safety filters...")
    filter_config = {
        "min_liquidity_usd": config["min_liquidity_usd"],
        "max_top_holder_pct": config["max_top_holder_pct"],
        "min_holder_count": config["min_holder_count"],
    }
    token_filter = TokenFilter(filter_config)
    print(f"[Init] Filters loaded: {filter_config}")

    gpt_scorer = None
    if config.get("enable_gpt_scoring"):
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            try:
                from core.gpt_agent import GPTScorer

                gpt_scorer = GPTScorer(api_key, model=config.get("gpt_model", "gpt-4o-mini"))
                print(f"[Init] GPT scoring enabled ({config.get('gpt_model', 'gpt-4o-mini')})")
            except Exception as exc:
                print(f"[Init] GPT scoring disabled: {exc}")
        else:
            print("[Init] GPT scoring disabled: OPENAI_API_KEY not set")

    print("[Init] Spinning up scanner...")
    scanner = TokenScanner(db, collector, token_filter, gpt_scorer=gpt_scorer)
    print("[Init] Scanner ready")

    print("[Init] Preparing graduation watcher...")
    graduation_config = {
        "min_liquidity_growth": config["min_liquidity_growth"],
        "min_market_cap": config["min_market_cap"],
        "min_holder_growth": config["min_holder_growth"],
        "min_volume_24h": config["min_volume_24h"],
        "check_interval_seconds": config["graduation_check_interval"],
    }
    watcher = GraduationWatcher(db, collector, graduation_config)
    print(f"[Init] Graduation watcher configured: {graduation_config}")

    print("[Init] Preparing webhook server...")
    init_webhook_server(scanner)
    print("[Init] Webhook server initialised")

    dashboard = Dashboard(db)
    print("[Init] Dashboard ready")

    print("=" * 70)
    print("All systems initialised\n")

    return db, scanner, watcher, dashboard, collector, config


# --------------------------------------------------------------------------- #
# Feed management
# --------------------------------------------------------------------------- #
def start_external_feeds(
    db: Database,
    collector: DataCollector,
    scanner: TokenScanner,
    config: Dict,
    *,
    gecko_background: bool = True,
    gecko_interval: int = 30,
) -> Dict[str, Optional[object]]:
    """
    Start PumpPortal websocket and optionally GeckoTerminal poller.
    """
    feeds: Dict[str, Optional[object]] = {}

    pump_stream = PumpPortalStream(scanner)
    pump_stream.start()
    feeds["pump_stream"] = pump_stream

    whitelist_entries = db.get_watchlist("whitelist")
    initial_tokens = [entry.mint_address for entry in whitelist_entries[:50]]
    if not initial_tokens:
        safe_tokens = db.get_safe_tokens(limit=20)
        initial_tokens = [token.mint_address for token in safe_tokens]
    pump_stream.add_tracked_tokens(initial_tokens)

    gecko_scanner = GeckoScanner(config["helius_api_key"])
    feeds["gecko_scanner"] = gecko_scanner

    if gecko_background:
        gecko_thread = Thread(
            target=gecko_scanner.start_polling,
            args=(scanner, gecko_interval),
            daemon=True,
            name="GeckoScanner",
        )
        gecko_thread.start()
        feeds["gecko_thread"] = gecko_thread

    # DIRECT SCRAPER - Custom scrapers that go straight to the source
    print("[Feeds] Starting DIRECT scrapers (Pump.fun + On-chain DEX monitoring)...")
    rpc_url = f"https://mainnet.helius-rpc.com/?api-key={config['helius_api_key']}"
    direct_scraper = DirectScraperOrchestrator(rpc_url=rpc_url)

    async def handle_discovered_tokens(tokens):
        """Callback for newly discovered tokens from direct scrapers"""
        loop = asyncio.get_event_loop()

        for token_info in tokens:
            mint_address = token_info["mint_address"]
            source = token_info.get("source", "unknown")
            symbol = token_info.get("symbol", "UNKNOWN")
            name = token_info.get("name", "Unknown")

            pumpfun_url = f"https://pump.fun/coin/{mint_address}"
            dexscreener_url = f"https://dexscreener.com/solana/{mint_address}"

            print(f"[Discovery] 🚀 NEW TOKEN from {source}: {symbol} ({name})")
            print(f"           Mint: {mint_address}")
            print(f"           Pump.fun: {pumpfun_url}")
            print(f"           DexScreener: {dexscreener_url}")

            # Check if duplicate
            if scanner.is_duplicate(mint_address):
                print(f"           ⚠️  Already processed, skipping")
                continue

            # Run sync scanner in thread executor to avoid event loop conflicts
            try:
                result = await loop.run_in_executor(
                    None,
                    scanner.process_mint_event,
                    mint_address,
                    token_info
                )
                if result:
                    print(f"           ✅ Processed successfully! Added to dashboard")
                else:
                    print(f"           ❌ Processing failed (check logs)")
            except Exception as e:
                print(f"           ❌ Error: {e}")

    # Start direct scraper in background (runs every 30 seconds)
    def run_scraper_loop():
        """Run the scraper in a background thread"""
        async def discovery_loop():
            await direct_scraper.run_continuous_discovery(
                callback=handle_discovered_tokens,
                interval=30  # Every 30 seconds
            )
        asyncio.run(discovery_loop())

    scraper_thread = Thread(target=run_scraper_loop, daemon=True, name="DirectScraperThread")
    scraper_thread.start()
    feeds["direct_scraper"] = direct_scraper
    feeds["scraper_thread"] = scraper_thread
    print("[Feeds] Direct scrapers online - scanning Pump.fun every 30s!")

    refresher = TokenRefresher(
        database=db,
        collector=collector,
        interval=config.get("refresh_interval_seconds", 120),
        gpt_scorer=getattr(scanner, "gpt_scorer", None),
    )
    refresher.start()
    feeds["refresher"] = refresher

    print("[Feeds] PumpPortal + GeckoTerminal + Refresher online")
    return feeds


def stop_external_feeds(feeds: Dict[str, Optional[object]]):
    """Stop background feeds gracefully."""
    if not feeds:
        return

    pump_stream = feeds.get("pump_stream")
    if pump_stream:
        pump_stream.stop()

    gecko_scanner = feeds.get("gecko_scanner")
    if gecko_scanner:
        gecko_scanner.stop()

    gecko_thread = feeds.get("gecko_thread")
    if gecko_thread and gecko_thread.is_alive():
        gecko_thread.join(timeout=2)

    refresher = feeds.get("refresher")
    if refresher:
        refresher.stop()


# --------------------------------------------------------------------------- #
# Execution modes
# --------------------------------------------------------------------------- #
def run_dashboard_mode(db, config):
    print("[Launcher] Dashboard mode")
    print("Use this to review existing data only. Press Ctrl+C to exit.\n")
    dashboard = Dashboard(db)
    dashboard.run()


def run_audit_mode(config: Dict, mint_address: str):
    print(f"[Audit] Gathering data for {mint_address}")
    db = init_database(config["database_url"])
    collector = DataCollector(
        config["helius_api_key"],
        birdeye_api_key=config.get("birdeye_api_key"),
    )
    report = perform_audit(mint_address, db, collector)
    print(json.dumps(report, indent=2, default=str))
    print("[Audit] Complete")

def run_scanner_mode(db, scanner, watcher, collector, config):
    print("[Launcher] Scanner mode starting")
    print(" - Webhook server forwarding Helius events")
    print(" - PumpPortal websocket + GeckoTerminal polling enabled")
    print("Press Ctrl+C to stop\n")

    watcher_thread = Thread(target=watcher.start, daemon=True, name="GraduationWatcher")
    watcher_thread.start()
    print("[Launcher] Graduation watcher running")

    feeds = start_external_feeds(db, collector, scanner, config)

    run_webhook_server_async(
        host=config["webhook_host"],
        port=config["webhook_port"],
    )
    print(
        f"[Launcher] Webhook listening at http://{config['webhook_host']}:{config['webhook_port']}/webhook/mint"
    )

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[Launcher] Stopping scanner mode...")
    finally:
        watcher.stop()
        stop_external_feeds(feeds)
        scanner.shutdown()


def run_rpc_mode(db, scanner, watcher, collector, config):
    print("[Launcher] RPC polling mode")
    print("Use when webhooks are unavailable. Press Ctrl+C to stop.\n")

    watcher_thread = Thread(target=watcher.start, daemon=True, name="GraduationWatcher")
    watcher_thread.start()
    print("[Launcher] Graduation watcher running")

    feeds = start_external_feeds(db, collector, scanner, config, gecko_background=False)

    gecko_scanner: GeckoScanner = feeds["gecko_scanner"]  # type: ignore
    try:
        gecko_scanner.start_polling(scanner, interval=30)
    except KeyboardInterrupt:
        print("\n[Launcher] RPC polling interrupted")
    finally:
        watcher.stop()
        stop_external_feeds(feeds)
        scanner.shutdown()


def run_full_mode(db, scanner, watcher, collector, config):
    print("[Launcher] Full mode: dashboard + realtime feeds")
    print("Press Ctrl+C to stop dashboard; other services will continue to run.\n")

    watcher_thread = Thread(target=watcher.start, daemon=True, name="GraduationWatcher")
    watcher_thread.start()
    print("[Launcher] Graduation watcher running")

    feeds = start_external_feeds(db, collector, scanner, config)

    run_webhook_server_async(
        host=config["webhook_host"],
        port=config["webhook_port"],
    )
    print(
        f"[Launcher] Webhook listening at http://{config['webhook_host']}:{config['webhook_port']}/webhook/mint"
    )

    time.sleep(2)  # give servers a moment to start

    dashboard = Dashboard(db)
    try:
        dashboard.run()
    finally:
        watcher.stop()
        stop_external_feeds(feeds)
        scanner.shutdown()


# --------------------------------------------------------------------------- #
# Entrypoint
# --------------------------------------------------------------------------- #
def main():
    config = load_config()
    validate_config(config)

    if len(sys.argv) > 1:
        mode = sys.argv[1]
        if mode == "--reset":
            db = init_database(config["database_url"])
            db.reset_data()
            print("[Reset] Database cleared. Restart the desired mode.")
            return
        if mode == "--dashboard":
            db = init_database(config["database_url"])
            run_dashboard_mode(db, config)
            return
        if mode == "--scanner":
            db, scanner, watcher, _, collector, config = initialize_system(config)
            run_scanner_mode(db, scanner, watcher, collector, config)
            return
        if mode == "--rpc":
            db, scanner, watcher, _, collector, config = initialize_system(config)
            run_rpc_mode(db, scanner, watcher, collector, config)
            return
        if mode == "--audit":
            if len(sys.argv) < 3:
                print("Usage: python main.py --audit <mint_address>")
                return
            mint = sys.argv[2]
            run_audit_mode(config, mint)
            return
        if mode == "--help":
            print(
                """
Usage: python main.py [mode]

Modes:
  --dashboard    Run dashboard only
  --scanner      Run scanner (webhooks + feeds) without dashboard
  --rpc          Run RPC polling mode
  --audit <mint> Run collector audit for a specific mint address
  --help         Show this help message

Default (no args) runs the full system: dashboard + feeds + webhooks.
"""
            )
            return

    db, scanner, watcher, _, collector, config = initialize_system(config)
    run_full_mode(db, scanner, watcher, collector, config)


if __name__ == "__main__":
    main()
