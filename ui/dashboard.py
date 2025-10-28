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
        """Create a table showing top tokens with extended metrics including ML insights."""
        table = Table(title="TOP ACTIVE TOKENS - ML ENHANCED", show_header=True, header_style="bold magenta")

        table.add_column("#", style="dim", width=3)
        table.add_column("Symbol", style="cyan", no_wrap=True, width=8)
        table.add_column("Score", justify="right", style="bold cyan", width=6)
        table.add_column("MCap", justify="right", style="green", width=10)
        table.add_column("Liq", justify="right", style="blue", width=10)
        table.add_column("Holders", justify="right", style="yellow", width=8)
        table.add_column("B/S Ratio", justify="center", style="white", width=9)
        table.add_column("Quick Profit", justify="center", style="bold yellow", width=12)
        table.add_column("Rug Risk", justify="center", style="bold red", width=9)
        table.add_column("Status", style="white", width=10)

        for i, token in enumerate(tokens[:20], 1):
            metadata = token.token_metadata or {}
            performance = metadata.get("performance") or {}
            score = performance.get("score")
            score_text = f"{score:.0f}" if isinstance(score, (int, float)) else "-"

            trades = metadata.get("trades") or {}
            buy_count = trades.get("buy_count", 0)
            sell_count = trades.get('sell_count', 0)
            buy_sell_ratio = trades.get('buy_sell_ratio', 0)

            # Format buy/sell ratio
            if buy_sell_ratio > 2:
                ratio_text = f"{buy_sell_ratio:.1f}x"
                ratio_style = "bold green"
            elif buy_sell_ratio > 1:
                ratio_text = f"{buy_sell_ratio:.1f}x"
                ratio_style = "green"
            elif buy_sell_ratio > 0.5:
                ratio_text = f"{buy_sell_ratio:.1f}x"
                ratio_style = "yellow"
            else:
                ratio_text = f"{buy_sell_ratio:.1f}x"
                ratio_style = "red"

            # Check for quick profit opportunity
            # (This would be populated by the filter's detect_quick_profit_rug method)
            quick_profit_data = metadata.get("quick_profit", {})
            if quick_profit_data.get("is_quick_profit_opportunity"):
                expected_profit = quick_profit_data.get("expected_max_profit_pct", 0)
                profit_window = quick_profit_data.get("profit_window_minutes", 0)
                quick_profit_text = f"+{expected_profit:.0f}% ({profit_window:.0f}m)"
                quick_profit_style = "bold yellow"
            else:
                quick_profit_text = "-"
                quick_profit_style = "dim"

            # Rug risk indicator
            top_holder_pct = token.top_holder_percentage or 0
            mint_auth_active = metadata.get("warnings", [])
            rug_indicators = len([w for w in mint_auth_active if 'authority' in w.lower()])
            if top_holder_pct > 40:
                rug_indicators += 1

            if rug_indicators >= 2:
                rug_risk_text = "HIGH"
                rug_risk_style = "bold red"
            elif rug_indicators == 1:
                rug_risk_text = "MED"
                rug_risk_style = "yellow"
            else:
                rug_risk_text = "LOW"
                rug_risk_style = "green"

            # Status with better indicators
            if token.is_graduated:
                status = "🎓 GRAD"
                row_style = "bright_green"
            elif token.is_safe:
                if quick_profit_data.get("is_quick_profit_opportunity"):
                    status = "⚡ QUICK$"
                    row_style = "bold yellow"
                else:
                    status = "✓ SAFE"
                    row_style = "green"
            else:
                status = "⚠ RISKY"
                row_style = "red"

            table.add_row(
                str(i),
                token.symbol or "UNK",
                score_text,
                self.format_number(token.market_cap, '$'),
                self.format_number(token.liquidity_usd, '$'),
                str(token.holder_count or 0),
                Text(ratio_text, style=ratio_style),
                Text(quick_profit_text, style=quick_profit_style),
                Text(rug_risk_text, style=rug_risk_style),
                status,
                style=row_style
            )

        return table

    def create_recent_mints_table(self, tokens: List[Token]) -> Table:
        """Create a table showing recently discovered tokens with ML analysis."""
        table = Table(title="⚡ RECENT MINTS - QUICK PROFIT SCANNER", show_header=True, header_style="bold cyan")

        table.add_column("Time", style="dim", width=8)
        table.add_column("Symbol", style="cyan", no_wrap=True, width=8)
        table.add_column("Score", justify="right", style="bold cyan", width=6)
        table.add_column("Liq", justify="right", style="blue", width=10)
        table.add_column("Holders", justify="right", style="yellow", width=8)
        table.add_column("B/S", justify="center", style="white", width=7)
        table.add_column("Quick $", justify="center", style="bold yellow", width=12)
        table.add_column("Action", style="white", width=12)

        for token in tokens[:10]:
            time_str = token.first_seen.strftime('%H:%M:%S') if token.first_seen else '-'
            metadata = token.token_metadata or {}
            performance = metadata.get("performance") or {}
            score = performance.get("score")
            score_text = f"{score:.0f}" if isinstance(score, (int, float)) else "-"

            trades = metadata.get("trades") or {}
            buy_sell_ratio = trades.get('buy_sell_ratio', 0)
            ratio_text = f"{buy_sell_ratio:.1f}x" if buy_sell_ratio > 0 else "-"

            # Quick profit opportunity
            quick_profit_data = metadata.get("quick_profit", {})
            if quick_profit_data.get("is_quick_profit_opportunity"):
                expected_profit = quick_profit_data.get("expected_max_profit_pct", 0)
                profit_window = quick_profit_data.get("profit_window_minutes", 0)
                quick_profit_text = f"+{expected_profit:.0f}%/{profit_window:.0f}m"
                quick_profit_style = "bold yellow"

                # Show strategy
                strategy = quick_profit_data.get("strategy", {})
                action = strategy.get("action", "WATCH")
                action_style = "bold yellow"
            else:
                quick_profit_text = "-"
                quick_profit_style = "dim"

                if token.is_safe:
                    action = "✓ SAFE"
                    action_style = "green"
                else:
                    # Show first risk flag
                    risk_flags = token.risk_flags or []
                    if risk_flags:
                        action = f"⚠ {risk_flags[0][:10]}"
                    else:
                        action = "⚠ RISKY"
                    action_style = "red"

            # Determine row style
            if quick_profit_data.get("is_quick_profit_opportunity"):
                row_style = "bold yellow"
            elif token.is_safe:
                row_style = "green"
            else:
                row_style = "dim"

            table.add_row(
                time_str,
                token.symbol or "UNK",
                score_text,
                self.format_number(token.liquidity_usd, '$'),
                str(token.holder_count or 0),
                ratio_text,
                Text(quick_profit_text, style=quick_profit_style),
                Text(action, style=action_style),
                style=row_style
            )

        return table

    def create_stats_panel(self) -> Panel:
        """
        Create a panel with overall statistics including ML insights

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

        # Count quick profit opportunities
        quick_profit_count = 0
        for token in all_tokens:
            metadata = token.token_metadata or {}
            if metadata.get("quick_profit", {}).get("is_quick_profit_opportunity"):
                quick_profit_count += 1

        stats_text = f"""
        📈 SCANNER STATUS
        Total Tokens: {len(all_tokens)} | Safe: {len(safe_tokens)} ({safe_pct:.1f}%) | Risky: {len(all_tokens) - len(safe_tokens)}
        Graduated: {len(graduated)} | Whitelisted: {whitelist_count} | Blacklisted: {blacklist_count}

        ⚡ QUICK PROFIT SCANNER
        Opportunities Detected: {quick_profit_count}

        🤖 ML STATUS
        Data Collection: ✓ ACCURATE (Fixed holder counts & trade data)
        Quick-Rug Detection: ✓ ACTIVE
        ML Agent: {"✓ READY" if os.getenv('OPENAI_API_KEY') else "⚠ NO API KEY"}

        🕐 Last Updated: {datetime.now().strftime('%H:%M:%S')}
        """

        return Panel(stats_text, title="🚀 MEME-B ML SCANNER", border_style="bold green")
    
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
