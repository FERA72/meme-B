"""
REAL-TIME DASHBOARD
Shows every new token as it's created with ALL data in a table.

Displays:
- Token table with: Symbol, Name, MCap, Volume, Liq, B/S, Holders, Age
- Links section below with Pump.fun and DexScreener URLs
"""

from datetime import datetime
from typing import List, Dict
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from rich.text import Text
import time


class RealtimeDashboard:
    """
    Real-time dashboard that shows tokens as they're discovered.

    Updates live every second.
    Shows comprehensive data for each token.
    """

    def __init__(self, max_tokens: int = 50):
        self.console = Console()
        self.tokens: List[Dict] = []
        self.max_tokens = max_tokens
        self.started_at = datetime.now()
        self.total_discovered = 0

    def add_token(self, token: Dict):
        """Add a new token to the dashboard"""
        # Add to beginning (newest first)
        self.tokens.insert(0, token)

        # Keep only max_tokens
        if len(self.tokens) > self.max_tokens:
            self.tokens = self.tokens[:self.max_tokens]

        self.total_discovered += 1

    def create_stats_panel(self) -> Panel:
        """Create stats panel"""
        runtime = datetime.now() - self.started_at
        runtime_seconds = runtime.total_seconds()
        runtime_minutes = runtime_seconds / 60

        stats_text = Text()
        stats_text.append("🔥 REAL-TIME PUMP.FUN MONITOR\n\n", style="bold cyan")
        stats_text.append(f"Runtime: {runtime_minutes:.1f} minutes ({runtime_seconds:.0f}s)\n")
        stats_text.append(f"Tokens Discovered: {self.total_discovered}\n", style="bold green")

        if runtime_seconds > 0:
            rate = (self.total_discovered / runtime_seconds) * 60
            stats_text.append(f"Discovery Rate: {rate:.1f} tokens/minute\n")

        return Panel(stats_text, title="Scanner Status", border_style="cyan")

    def create_tokens_table(self) -> Table:
        """Create comprehensive tokens table"""
        table = Table(title="📊 NEW TOKENS (Live Feed)", show_header=True, header_style="bold cyan")

        # Columns with all the data
        table.add_column("#", width=4, justify="right")
        table.add_column("Symbol", width=10)
        table.add_column("Name", width=20)
        table.add_column("MCap", width=10, justify="right")
        table.add_column("Liq", width=10, justify="right")
        table.add_column("Vol 1h", width=10, justify="right")
        table.add_column("B/S 5m", width=8, justify="center")
        table.add_column("Holders", width=8, justify="right")
        table.add_column("Age", width=8, justify="center")
        table.add_column("Creator", width=12)

        if not self.tokens:
            table.add_row("", "", "Waiting for tokens...", "", "", "", "", "", "", "")
            return table

        for i, token in enumerate(self.tokens, 1):
            # Extract data with defaults
            symbol = token.get("symbol", "???")[:10]
            name = token.get("name", "Unknown")[:20]

            # Market data
            mcap = token.get("market_cap_usd", 0) or token.get("market_cap", 0)
            liq = token.get("liquidity_usd", 0)
            vol_1h = token.get("volume_1h", 0)

            # Buy/Sell ratio
            bs_ratio = token.get("buy_sell_ratio_5m", 0)
            buys = token.get("buys_5m", 0)
            sells = token.get("sells_5m", 0)

            # Holders
            holders = token.get("holder_count", 0)

            # Age
            age_minutes = token.get("age_minutes", 0)

            # Creator
            creator = token.get("creator", "")[:8] + "..." if token.get("creator") else "N/A"

            # Format values
            mcap_str = f"${mcap/1000:.1f}k" if mcap >= 1000 else f"${mcap:.0f}"
            liq_str = f"${liq/1000:.1f}k" if liq >= 1000 else f"${liq:.0f}"
            vol_str = f"${vol_1h/1000:.1f}k" if vol_1h >= 1000 else f"${vol_1h:.0f}"

            # B/S display
            if bs_ratio > 0:
                bs_str = f"{buys}/{sells}"
                if bs_ratio >= 2.0:
                    bs_style = "bold green"
                elif bs_ratio >= 1.0:
                    bs_style = "green"
                elif bs_ratio >= 0.5:
                    bs_style = "yellow"
                else:
                    bs_style = "red"
            else:
                bs_str = "0/0"
                bs_style = "dim"

            # Age display
            if age_minutes < 5:
                age_str = f"{age_minutes:.1f}m"
                age_style = "bold green"
            elif age_minutes < 15:
                age_str = f"{age_minutes:.0f}m"
                age_style = "green"
            elif age_minutes < 60:
                age_str = f"{age_minutes:.0f}m"
                age_style = "yellow"
            else:
                hours = age_minutes / 60
                age_str = f"{hours:.1f}h"
                age_style = "red"

            # Row style based on freshness
            if age_minutes < 2:
                row_style = "bold"
            else:
                row_style = ""

            table.add_row(
                str(i),
                f"[{row_style}]{symbol}[/{row_style}]",
                f"[{row_style}]{name}[/{row_style}]",
                mcap_str,
                liq_str,
                vol_str,
                f"[{bs_style}]{bs_str}[/{bs_style}]",
                str(holders) if holders > 0 else "-",
                f"[{age_style}]{age_str}[/{age_style}]",
                creator,
            )

        return table

    def create_links_panel(self) -> Panel:
        """Create panel with links for latest tokens"""
        if not self.tokens:
            return Panel(Text("No tokens yet...", style="dim"), title="🔗 Links", border_style="cyan")

        links_text = Text()

        # Show links for the 5 most recent tokens
        for i, token in enumerate(self.tokens[:5], 1):
            mint = token.get("mint", "")
            symbol = token.get("symbol", "???")
            name = token.get("name", "Unknown")

            links_text.append(f"\n{i}. {symbol} - {name}\n", style="bold white")
            links_text.append(f"   Mint: {mint}\n", style="dim")
            links_text.append(f"   Pump.fun: https://pump.fun/coin/{mint}\n", style="cyan")
            links_text.append(f"   DexScreener: https://dexscreener.com/solana/{mint}\n", style="cyan")

        return Panel(links_text, title="🔗 Latest Token Links (Copy & Paste)", border_style="cyan")

    def generate_layout(self) -> Layout:
        """Generate the dashboard layout"""
        layout = Layout()

        # Split into: stats (top) | table (middle) | links (bottom)
        layout.split_column(
            Layout(name="stats", size=6),
            Layout(name="table", ratio=2),
            Layout(name="links", size=15),
        )

        layout["stats"].update(self.create_stats_panel())
        layout["table"].update(self.create_tokens_table())
        layout["links"].update(self.create_links_panel())

        return layout

    def print_new_token_alert(self, token: Dict):
        """Print alert when a new token is discovered (above dashboard)"""
        symbol = token.get("symbol", "???")
        name = token.get("name", "Unknown")
        mint = token.get("mint", "")
        mcap = token.get("market_cap_usd", 0) or token.get("market_cap", 0)
        age_minutes = token.get("age_minutes", 0)

        self.console.print(
            f"\n[bold green]🚨 NEW TOKEN: {symbol} - {name}[/bold green] "
            f"[dim]| MCap: ${mcap:,.0f} | Age: {age_minutes:.1f}m[/dim]"
        )

    async def run_live(self):
        """Run the dashboard with live updates"""
        self.console.clear()
        self.console.print("\n[bold cyan]🚀 STARTING REAL-TIME PUMP.FUN MONITOR[/bold cyan]")
        self.console.print("[cyan]Scanning for new tokens every second...[/cyan]\n")

        with Live(self.generate_layout(), refresh_per_second=1, screen=True) as live:
            try:
                while True:
                    live.update(self.generate_layout())
                    await asyncio.sleep(0.1)  # Small delay to prevent busy loop

            except KeyboardInterrupt:
                self.console.print("\n[yellow]Dashboard stopped[/yellow]")


# For async support in dashboard
import asyncio


# Test function
async def test():
    dashboard = RealtimeDashboard()

    # Simulate some tokens
    test_tokens = [
        {
            "mint": "ABC123XYZ",
            "symbol": "TEST1",
            "name": "Test Token 1",
            "market_cap_usd": 15000,
            "market_cap": 15000,
            "liquidity_usd": 5000,
            "volume_1h": 2000,
            "buys_5m": 10,
            "sells_5m": 3,
            "buy_sell_ratio_5m": 3.33,
            "holder_count": 45,
            "age_minutes": 2.5,
            "creator": "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
        },
        {
            "mint": "DEF456ABC",
            "symbol": "TEST2",
            "name": "Test Token 2",
            "market_cap_usd": 8000,
            "market_cap": 8000,
            "liquidity_usd": 3000,
            "volume_1h": 500,
            "buys_5m": 5,
            "sells_5m": 8,
            "buy_sell_ratio_5m": 0.625,
            "holder_count": 23,
            "age_minutes": 15.0,
            "creator": "9yKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
        },
    ]

    for token in test_tokens:
        dashboard.add_token(token)
        dashboard.print_new_token_alert(token)
        await asyncio.sleep(1)

    # Show final layout
    dashboard.console.print("\n\n")
    dashboard.console.print(dashboard.generate_layout())


if __name__ == "__main__":
    asyncio.run(test())
