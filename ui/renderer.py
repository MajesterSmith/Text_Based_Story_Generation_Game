"""
ui/renderer.py
────────────────────────────────────────────────────────────────────────────
All rendering is now fully dynamic: faction tables iterate over whatever
factions exist in the world, and role selection displays whatever roles
are in ROLE_REGISTRY.
"""
from __future__ import annotations
from typing import List, Tuple
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box
from rich.align import Align
from models import PlayerState, WorldState, LocationNode, QuestState, ROLE_REGISTRY

console = Console()


def clear():
    console.clear()


def print_title():
    console.print(Panel.fit(
        "[bold red]T E X T   A D V E N T U R E[/bold red]\n"
        "[dim]A Neuro-Symbolic Story Engine[/dim]",
        border_style="red", padding=(1, 4),
    ))


def print_location(loc: LocationNode, narration: str):
    danger_bar = "█" * loc.danger_level + "░" * (5 - loc.danger_level)
    header = f"[bold cyan]{loc.name}[/bold cyan]  [dim]Danger:[/dim] [red]{danger_bar}[/red]"
    if loc.faction_owner:
        header += f"  [dim]|[/dim]  [yellow]{loc.faction_owner}[/yellow]"
    body = header
    if narration:
        body += f"\n\n[italic]{narration}[/italic]"
    console.print(Panel(body, border_style="cyan", padding=(1, 2)))


def print_player_bar(player: PlayerState):
    """Render a detailed player status bar with HP and stats."""
    s = player.stats
    stats_str = (
        f"[bold red]STR {s.strength}[/bold red]  "
        f"[bold green]AGI {s.agility}[/bold green]  "
        f"[bold blue]VIT {s.vitality}[/bold blue]  "
        f"[bold yellow]STE {s.stealth}[/bold yellow]  "
        f"[bold magenta]PER {s.persuasion}[/bold magenta]  "
        f"[bold cyan]INT {s.intelligence}[/bold cyan]"
    )
    
    # ── Health Bar ────────────────────────────────────────────────────────
    hp_pct = (player.health / player.max_health) * 100
    color = "green" if hp_pct > 60 else "yellow" if hp_pct > 25 else "red"
    filled = int(hp_pct / 5)
    hp_bar = f"[{color}]" + ("█" * filled) + ("░" * (20 - filled)) + "[/]"
    
    status_table = Table(show_header=False, box=None, padding=(0, 1))
    status_table.add_column("Left", justify="left")
    status_table.add_column("Right", justify="right")
    
    status_table.add_row(
        f"[bold magenta]ID:[/bold magenta] {player.name}  [dim]({player.role})[/dim]",
        f"[bold yellow]CREDITS:[/bold yellow] {player.creds}¢"
    )
    status_table.add_row(
        f"HP: {hp_bar} [bold {color}]{player.health}/{player.max_health}[/]",
        f"Turn: {player.turn_count}"
    )

    console.print(Panel(status_table, title="[bold cyan]S T A T U S[/bold cyan]", border_style="cyan"))
    console.print(Align.center(stats_str))
    print()


def print_faction_table(player: PlayerState, world: WorldState):
    """Print reputation and heat for all factions in this world."""
    if not world.factions:
        console.print("[dim]No factions in this world.[/dim]")
        return

    table = Table(
        title="Faction Status", box=box.SIMPLE,
        show_header=True, header_style="bold magenta",
    )
    table.add_column("Faction",  style="cyan")
    table.add_column("Rep",      justify="right")
    table.add_column("Standing")
    table.add_column("Heat",     justify="right")
    table.add_column("Threat")

    for faction in world.factions:
        rep    = player.faction_rep.get(faction)
        heat   = player.heat.get(faction)
        stand  = player.faction_rep.standing_label(faction)
        threat = player.heat.threat_label(faction)
        color  = player.heat.threat_color(faction)
        table.add_row(faction, str(rep), stand, str(heat), f"[{color}]{threat}[/{color}]")

    console.print(table)


def print_menu(options: List[Tuple[int, str]], title: str = "What do you do?"):
    console.print(f"\n[bold yellow]{title}[/bold yellow]")
    for idx, label in options:
        console.print(f"  [bold cyan]{idx}.[/bold cyan] {label}")
    console.print()


def print_npcs(npcs: list):
    if not npcs:
        return
    names = ", ".join(f"[bold]{n.name}[/bold]" for n in npcs)
    console.print(f"[dim]People here:[/dim] {names}")


def get_quest_status_hint(counter: int, threshold: int) -> str:
    """Translates the hidden counter into a vague narrative hint."""
    if counter <= 5:
        return "[bold red]Critical: The mission is nearly a total loss.[/bold red]"
    if counter < threshold * 0.4:
        return "[red]Unstable: Serious mistakes have been made.[/red]"
    if counter < threshold * 0.7:
        return "[yellow]Tenuous: You're making progress, but it's risky.[/yellow]"
    if counter < threshold:
        return "[cyan]Solid: The plan is coming together.[/cyan]"
    return "[bold green]Excellent: You have exceeded all expectations.[/bold green]"


def print_quest_panel(player: PlayerState):
    from engine.quest_engine import get_active_quests
    quests = get_active_quests(player)
    if not quests:
        return

    for q in quests:
        beat = q.current_beat()
        status_hint = get_quest_status_hint(q.hidden_counter, q.win_threshold)
        
        # ── Prepend Transition Narration if exists ──────────────────
        narration_text = ""
        if q.last_transitional_narration:
            narration_text = f"[italic]{q.last_transitional_narration}[/italic]\n\n"
        
        content = (
            f"[bold cyan]{q.title}[/bold cyan]\n"
            f"[dim]{q.description}[/dim]\n\n"
            f"{narration_text}"
            f"[yellow]Objective:[/yellow] {beat.objective if beat else 'None'}\n"
            f"[magenta]Status:[/magenta] {status_hint}"
        )
        console.print(Panel(content, title="Active Quest", border_style="cyan"))


def print_beat_narration(narration: str):
    console.print(Panel(f"[italic]{narration}[/italic]",
                        border_style="yellow", padding=(1, 2)))


def print_message(msg: str = "", style: str = ""):
    console.print(f"[{style}]{msg}[/{style}]" if style else msg)


def prompt_input(prompt_text: str = "> ") -> str:
    return console.input(f"[bold green]{prompt_text}[/bold green]").strip()


def print_role_select(world_name: str = ""):
    """Dynamically render role selection from ROLE_REGISTRY."""
    if not ROLE_REGISTRY:
        console.print("[red]No roles available.[/red]")
        return

    lines = []
    for i, (rid, rdef) in enumerate(ROLE_REGISTRY.items(), start=1):
        s = rdef.stats
        stat_bar = (
            f"STR {s.strength} · AGI {s.agility} · VIT {s.vitality} · "
            f"STE {s.stealth} · PER {s.persuasion} · INT {s.intelligence}"
        )
        start_creds = rdef.start_creds
        lines.append(
            f"[cyan]{i}.[/cyan] [bold]{rdef.name}[/bold]\n"
            f"   {rdef.description}\n"
            f"   [dim]{stat_bar} | {start_creds}¢[/dim]"
        )

    header = f"[red]{'— ' + world_name + ' — ' if world_name else ''}Character Select[/red]"
    console.print(Panel(
        "[bold]Choose your role:[/bold]\n\n" + "\n\n".join(lines),
        title=header, border_style="red", padding=(1, 3),
    ))


def print_lore_intro(world: WorldState):
    console.print(Panel(
        f"[italic]{world.lore_intro}[/italic]",
        title=f"[bold cyan]{world.city_name}[/bold cyan]",
        border_style="cyan", padding=(1, 2),
    ))