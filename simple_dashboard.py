"""
SIMPLE DASHBOARD - Show new tokens + buy signals

Clean, real-time display of Pump.fun opportunities.
"""

import os
from datetime import datetime
from typing import List, Dict
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from rich.text import Text


class SimpleDashboard:
    """
    Minimal dashboard showing:
    1. Recent new tokens
    2. Buy signals
    3. Stats
    """

    def __init__(self):
        self.console = Console()
        self.tokens = []  # All tokens we've seen
        self.buy_opportunities = []  # Tokens with buy signals
        self.stats = {
            "total_scanned": 0,
            "buy_signals": 0,
            "started_at": datetime.now(),
        }

    def add_token(self, token: Dict, analysis: Dict):
        """Add a token and its analysis"""
        # Add to all tokens list (keep last 20)
        self.tokens.insert(0, {"token": token, "analysis": analysis})
        if len(self.tokens) > 20:
            self.tokens.pop()

        # Update stats
        self.stats["total_scanned"] += 1

        # If it's a buy signal, add to opportunities
        if analysis.get("should_buy"):
            self.buy_opportunities.insert(0, {"token": token, "analysis": analysis})
            if len(self.buy_opportunities) > 10:
                self.buy_opportunities.pop()
            self.stats["buy_signals"] += 1

    def create_stats_panel(self) -> Panel:
        """Create stats panel"""
        runtime = datetime.now() - self.stats["started_at"]
        runtime_minutes = runtime.total_seconds() / 60

        stats_text = Text()
        stats_text.append("📊 STATS\n\n", style="bold cyan")
        stats_text.append(f"Runtime: {runtime_minutes:.1f} minutes\n")
        stats_text.append(f"Tokens Scanned: {self.stats['total_scanned']}\n")
        stats_text.append(f"Buy Signals: {self.stats['buy_signals']}\n", style="bold green")
        stats_text.append(f"Hit Rate: {(self.stats['buy_signals'] / max(1, self.stats['total_scanned']) * 100):.1f}%\n")

        return Panel(stats_text, title="Scanner Status", border_style="cyan")

    def create_buy_signals_table(self) -> Table:
        """Create table of buy opportunities"""
        table = Table(title="🎯 BUY SIGNALS", show_header=True, header_style="bold green")

        table.add_column("#", width=3)
        table.add_column("Symbol", width=10)
        table.add_column("Name", width=20)
        table.add_column("Confidence", justify="center", width=10)
        table.add_column("MCap", justify="right", width=12)
        table.add_column("Age", justify="center", width=8)
        table.add_column("Links", width=30)

        if not self.buy_opportunities:
            table.add_row("", "", "No buy signals yet...", "", "", "", "")
            return table

        for i, item in enumerate(self.buy_opportunities[:10], 1):
            token = item["token"]
            analysis = item["analysis"]

            # Format data
            symbol = token.get("symbol", "???")[:10]
            name = token.get("name", "Unknown")[:20]
            confidence = analysis.get("confidence", 0)
            mcap = token.get("market_cap_usd", 0)
            age = token.get("age_minutes", 0)
            mint = token.get("mint", "")

            # Confidence color
            if confidence >= 70:
                conf_style = "bold green"
            elif confidence >= 50:
                conf_style = "yellow"
            else:
                conf_style = "white"

            # Links
            pump_url = f"pump.fun/coin/{mint[:8]}..."
            dex_url = f"dexscreener.com/solana/{mint[:8]}..."

            table.add_row(
                str(i),
                symbol,
                name,
                f"[{conf_style}]{confidence}%[/{conf_style}]",
                f"${mcap:,.0f}",
                f"{age:.0f}m",
                f"{pump_url}\n{dex_url}",
            )

        return table

    def create_recent_tokens_table(self) -> Table:
        """Create table of all recent tokens"""
        table = Table(title="📋 RECENT TOKENS (Last 20)", show_header=True, header_style="bold white")

        table.add_column("#", width=3)
        table.add_column("Symbol", width=10)
        table.add_column("Name", width=25)
        table.add_column("MCap", justify="right", width=12)
        table.add_column("Age", justify="center", width=8)
        table.add_column("Signal", justify="center", width=10)

        if not self.tokens:
            table.add_row("", "", "Waiting for tokens...", "", "", "")
            return table

        for i, item in enumerate(self.tokens[:20], 1):
            token = item["token"]
            analysis = item["analysis"]

            symbol = token.get("symbol", "???")[:10]
            name = token.get("name", "Unknown")[:25]
            mcap = token.get("market_cap_usd", 0)
            age = token.get("age_minutes", 0)
            should_buy = analysis.get("should_buy", False)

            signal = "✅ BUY" if should_buy else "⏭️ SKIP"
            signal_style = "bold green" if should_buy else "dim"

            table.add_row(
                str(i),
                symbol,
                name,
                f"${mcap:,.0f}",
                f"{age:.0f}m",
                f"[{signal_style}]{signal}[/{signal_style}]",
            )

        return table

    def generate_layout(self) -> Layout:
        """Generate the dashboard layout"""
        layout = Layout()

        # Split into top (stats) and bottom (tables)
        layout.split_column(
            Layout(name="stats", size=8),
            Layout(name="tables"),
        )

        # Stats panel
        layout["stats"].update(self.create_stats_panel())

        # Split tables into buy signals and recent
        layout["tables"].split_column(
            Layout(name="buy_signals", ratio=1),
            Layout(name="recent", ratio=1),
        )

        layout["buy_signals"].update(self.create_buy_signals_table())
        layout["recent"].update(self.create_recent_tokens_table())

        return layout

    def print_token_alert(self, token: Dict, analysis: Dict):
        """Print alert for new token (above dashboard)"""
        symbol = token.get("symbol", "???")
        name = token.get("name", "Unknown")
        mint = token.get("mint", "")
        should_buy = analysis.get("should_buy", False)

        if should_buy:
            self.console.print(f"\n[bold green]🚨 BUY SIGNAL: {symbol} - {name}[/bold green]")
            self.console.print(f"[green]   Pump.fun: https://pump.fun/coin/{mint}[/green]")
            self.console.print(f"[green]   DexScreener: https://dexscreener.com/solana/{mint}[/green]")
            self.console.print(f"[green]   Confidence: {analysis.get('confidence')}%[/green]")
        else:
            self.console.print(f"\n[dim]⏭️  SKIP: {symbol} - {name} (Confidence: {analysis.get('confidence')}%)[/dim]")

    def run(self):
        """Run the dashboard with live updates"""
        self.console.clear()
        self.console.print("\n[bold cyan]🚀 PUMP.FUN PROFIT SCANNER[/bold cyan]")
        self.console.print("[cyan]Starting...[/cyan]\n")

        with Live(self.generate_layout(), refresh_per_second=1, screen=True) as live:
            # Dashboard will update automatically when tokens are added
            # The live display refreshes every second
            try:
                while True:
                    live.update(self.generate_layout())
            except KeyboardInterrupt:
                self.console.print("\n[yellow]Dashboard stopped[/yellow]")


# Test function
def test():
    import time

    dashboard = SimpleDashboard()

    # Simulate some tokens
    test_tokens = [
        {
            "token": {
                "mint": "ABC123",
                "symbol": "TEST1",
                "name": "Test Token 1",
                "market_cap_usd": 15000,
                "age_minutes": 5,
            },
            "analysis": {
                "should_buy": True,
                "confidence": 75,
            }
        },
        {
            "token": {
                "mint": "XYZ789",
                "symbol": "TEST2",
                "name": "Test Token 2",
                "market_cap_usd": 3000,
                "age_minutes": 45,
            },
            "analysis": {
                "should_buy": False,
                "confidence": 25,
            }
        },
    ]

    # Add tokens
    for item in test_tokens:
        dashboard.add_token(item["token"], item["analysis"])
        dashboard.print_token_alert(item["token"], item["analysis"])
        time.sleep(1)

    # Show dashboard
    print("\n\nDashboard preview:")
    dashboard.console.print(dashboard.generate_layout())


if __name__ == "__main__":
    test()
