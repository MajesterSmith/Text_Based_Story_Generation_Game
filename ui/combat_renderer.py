from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import BarColumn, Progress, TextColumn
from rich.columns import Columns
from rich.align import Align
from rich.text import Text
from engine.combat import CombatManager, Combatant

console = Console()

class CombatRenderer:
    @staticmethod
    def render(manager: CombatManager):
        # 1. Initiative Table
        init_table = Table(title="Turn Order", border_style="cyan", show_header=True)
        init_table.add_column("Initiative", justify="right")
        init_table.add_column("Combatant", justify="left")
        init_table.add_column("Status", justify="center")

        for c in manager.turn_order:
            style = "bold magenta" if c.is_player else "red"
            status = "[yellow]DEFENDING[/yellow]" if c.defending else "Ready"
            if c.health <= 0:
                status = "[dim]DEFEATED[/dim]"
            
            init_table.add_row(
                str(c.initiative),
                f"[{style}]{c.name}[/{style}]",
                status
            )

        # 2. Vitality Display (Health Bars)
        player_bar = CombatRenderer._create_health_bar(manager.player)
        enemy_bars = [CombatRenderer._create_health_bar(e) for e in manager.enemies if e.health > 0]
        
        # 3. Overall Layout
        combat_panel = Panel(
            Align.center(
                Columns([
                    Panel(player_bar, title="[bold magenta]PLAYER[/bold magenta]", border_style="magenta", expand=False),
                    Panel(Columns(enemy_bars), title="[bold red]ENEMIES[/bold red]", border_style="red", expand=False)
                ], align="center")
            ),
            title="[bold yellow]COMBAT ENCOUNTER[/bold yellow]",
            subtitle=f"[dim]{manager.log[-1] if manager.log else ''}[/dim]",
            border_style="yellow",
            padding=(1, 2)
        )

        console.clear()
        console.print(init_table)
        console.print(combat_panel)

    @staticmethod
    def _create_health_bar(c: Combatant):
        pct = (c.health / c.max_health) * 100
        color = "green" if pct > 60 else "yellow" if pct > 25 else "red"
        
        # Simple string-based bar since Progress is for async/long tasks
        filled = int(pct / 10)
        bar_str = "█" * filled + "░" * (10 - filled)
        
        return f"{c.name}\n[bold {color}]{c.health}/{c.max_health}[/bold {color}]\n[{color}]{bar_str}[/{color}]"

    @staticmethod
    def show_actions(manager: CombatManager):
        choices = "[1] Attack   [2] Defend   [3] Flee"
        console.print(Panel(Align.center(choices), title="Choose Action", border_style="green"))
        
        if len(manager.enemies) > 1:
            console.print("\nTarget:")
            for i, e in enumerate(manager.enemies):
                console.print(f"  [{i+1}] {e.name} ({e.health}/{e.max_health} HP)")
