"""
Real-time terminal dashboard for displaying token data
Updates continuously in PowerShell/terminal
"""

import os
import time
from datetime import datetime
from typing import List
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from rich.text import Text
from db.database import Database
from db.models import Token


class Dashboard:
    """
    Terminal-based dashboard that updates in real-time
    Shows top tokens and recent mints
    """
    
    def __init__(self, database: Database):
        """
        Initialize dashboard
        
        Args:
            database: Database instance
        """
        self.db = database
        self.console = Console()
        self.running = False
        
        # Dashboard refresh rate (seconds)
        self.refresh_rate = 2  # Update every 2 seconds (REPLACE ME with desired rate)
    
    def format_number(self, num: float, prefix: str = '') -> str:
        """
        Format numbers for display (e.g., $1,234.56)

        Args:
            num: Number to format
            prefix: Prefix to add (e.g., '$')

        Returns:
            Formatted string
        """
        if not isinstance(num, (int, float)):
            try:
                num = float(num or 0)
            except (TypeError, ValueError):
                num = 0
        if num >= 1_000_000:
            return f"{prefix}{num/1_000_000:.2f}M"
        elif num >= 1_000:
            return f"{prefix}{num/1_000:.2f}K"
        else:
            return f"{prefix}{num:.2f}"
    
    def create_top_tokens_table(self, tokens: List[Token]) -> Table:
        """Create a table showing top tokens with extended metrics."""
        table = Table(title="TOP ACTIVE TOKENS", show_header=True, header_style="bold magenta")

        table.add_column("#", style="dim", width=3)
        table.add_column("Symbol", style="cyan", no_wrap=True)
        table.add_column("Address", style="dim", min_width=44, overflow="fold")
        table.add_column("Name", style="white")
        table.add_column("Score", justify="right", style="bold cyan", width=8)
        table.add_column("Market Cap", justify="right", style="green", width=12)
        table.add_column("Liquidity", justify="right", style="blue", width=12)
        table.add_column("24h Vol", justify="right", style="magenta", width=12)
        table.add_column("Holders", justify="right", style="yellow", width=8)
        table.add_column("Trades (B/S)", justify="center", style="white", width=12)
        table.add_column("Migration", style="white", width=12)
        table.add_column("Status", style="white", width=8)

        for i, token in enumerate(tokens[:20], 1):
            metadata = token.token_metadata or {}
            performance = metadata.get("performance") or {}
            score = performance.get("score")
            score_text = f"{score:.1f}" if isinstance(score, (int, float)) else "-"

            trades = metadata.get("trades") or {}
            trades_text = f"{trades.get('buy_count', 0)}/{trades.get('sell_count', 0)}"

            migration_status = (metadata.get("migration") or {}).get("status") or "-"

            if token.is_graduated:
                status = "GRAD"
                row_style = "bright_green"
            elif token.is_safe:
                status = "SAFE"
                row_style = "green"
            else:
                status = "RISKY"
                row_style = "red"

            table.add_row(
                str(i),
                token.symbol or "UNK",
                token.mint_address or "-",
                token.name or "Unknown",
                score_text,
                self.format_number(token.market_cap, '$'),
                self.format_number(token.liquidity_usd, '$'),
                self.format_number(token.volume_24h, '$'),
                str(token.holder_count or 0),
                trades_text,
                migration_status,
                status,
                style=row_style
            )

        return table

    def create_recent_mints_table(self, tokens: List[Token]) -> Table:
        """Create a table showing recently discovered tokens with details."""
        table = Table(title="RECENT MINTS (Last 10 Minutes)", show_header=True, header_style="bold cyan")

        table.add_column("Time", style="dim", width=8)
        table.add_column("Symbol", style="cyan", no_wrap=True)
        table.add_column("Address", style="dim", min_width=44, overflow="fold")
        table.add_column("Score", justify="right", style="bold cyan", width=8)
        table.add_column("Liquidity", justify="right", style="blue", width=12)
        table.add_column("Holders", justify="right", style="yellow", width=8)
        table.add_column("Trades (B/S)", justify="center", style="white", width=12)
        table.add_column("Safety", style="white", width=14)

        for token in tokens[:10]:
            time_str = token.first_seen.strftime('%H:%M:%S') if token.first_seen else '-'
            metadata = token.token_metadata or {}
            performance = metadata.get("performance") or {}
            score = performance.get("score")
            score_text = f"{score:.1f}" if isinstance(score, (int, float)) else "-"

            trades = metadata.get("trades") or {}
            trades_text = f"{trades.get('buy_count', 0)}/{trades.get('sell_count', 0)}"

            if token.is_safe:
                safety = "SAFE"
                style = "green"
            else:
                safety = f"FAILED: {token.risk_flags[0]}" if token.risk_flags else "RISKY"
                style = "red"

            table.add_row(
                time_str,
                token.symbol or "UNK",
                token.mint_address or "-",
                score_text,
                self.format_number(token.liquidity_usd, '$'),
                str(token.holder_count or 0),
                trades_text,
                safety,
                style=style
            )

        return table

    def create_stats_panel(self) -> Panel:
        """
        Create a panel with overall statistics
        
        Returns:
            Rich Panel object
        """
        # Get stats
        all_tokens = self.db.get_all_tokens(include_blacklisted=True)
        safe_tokens = self.db.get_safe_tokens()
        graduated = self.db.get_graduated_tokens()
        watch_counts = self.db.get_watchlist_counts()
        whitelist_count = watch_counts.get("whitelist", 0)
        blacklist_count = watch_counts.get("blacklist", 0)
        
        # Calculate safe percentage
        safe_pct = (len(safe_tokens)/len(all_tokens)*100) if len(all_tokens) > 0 else 0
        
        stats_text = f"""
        Total Tokens Detected: {len(all_tokens)}
        Safe Tokens: {len(safe_tokens)} ({safe_pct:.1f}%)
        Graduated Tokens: {len(graduated)}
        Risky Tokens: {len(all_tokens) - len(safe_tokens)}
        Whitelisted: {whitelist_count}
        Blacklisted: {blacklist_count}
        
        Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        
        return Panel(stats_text, title="📊 Statistics", border_style="green")
    
    def generate_layout(self) -> Layout:
        """
        Generate the complete dashboard layout
        
        Returns:
            Rich Layout object
        """
        layout = Layout()
        
        # Get data
        top_tokens = self.db.get_top_tokens(limit=20)
        if not top_tokens:
            top_tokens = self.db.get_recent_tokens(limit=20)
        recent_mints = self.db.get_recent_mints(minutes=10)
        
        # Create components
        stats_panel = self.create_stats_panel()
        top_table = self.create_top_tokens_table(top_tokens)
        recent_table = self.create_recent_mints_table(recent_mints)
        
        # Split layout
        layout.split_column(
            Layout(name="header", size=8),
            Layout(name="body"),
            Layout(name="footer", size=15)
        )
        
        # Add components
        layout["header"].update(stats_panel)
        layout["body"].update(top_table)
        layout["footer"].update(recent_table)
        
        return layout
    
    def run(self):
        """
        Start the dashboard
        Runs continuously until stopped with Ctrl+C
        """
        self.running = True
        
        print("\n" + "="*80)
        print("🚀 MEME-BETA.5 DASHBOARD STARTING")
        print("="*80)
        print("Press Ctrl+C to stop")
        print("="*80 + "\n")
        
        time.sleep(2)  # Brief pause before starting
        
        try:
            # Use Rich Live for auto-updating display
            with Live(self.generate_layout(), refresh_per_second=1/self.refresh_rate, screen=True) as live:
                while self.running:
                    try:
                        # Update the layout
                        live.update(self.generate_layout())
                        time.sleep(self.refresh_rate)
                    except KeyboardInterrupt:
                        break
        except KeyboardInterrupt:
            pass
        
        print("\n" + "="*80)
        print("👋 Dashboard stopped")
        print("="*80 + "\n")
    
    def stop(self):
        """
        Stop the dashboard
        """
        self.running = False


# Example usage:
# dashboard = Dashboard(db)
# dashboard.run()  # Runs forever until Ctrl+C
