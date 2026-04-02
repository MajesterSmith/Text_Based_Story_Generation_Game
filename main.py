"""main.py — entry point."""
from __future__ import annotations
import sys
from rich.console import Console
from rich.panel import Panel

from models import PlayerState, ROLE_REGISTRY
from data.seed import build_world as build_neon_city
from data.seed_generator import generate_world_from_prompt
from engine.navigation import available_moves, locked_moves, move_player
from engine.quest_engine import request_quest, accept_quest, resolve_choice, get_active_quests
from engine.llm import narrate_location, narrate_travel, narrate_npc_dialogue
from engine.combat import CombatManager
from ui.renderer import (
    console, clear, print_title, print_location, print_player_bar,
    print_faction_table, print_menu, print_npcs, print_quest_panel,
    print_beat_narration, print_message, prompt_input,
    print_role_select, print_lore_intro,
)


# ── Helpers ────────────────────────────────────────────────────────────────

def pick_int(prompt: str, lo: int, hi: int) -> int:
    while True:
        raw = prompt_input(prompt)
        if raw.isdigit() and lo <= int(raw) <= hi:
            return int(raw)
        print_message(f"Enter a number between {lo} and {hi}.", "red")


# ── World Selection ────────────────────────────────────────────────────────

def world_selection():
    """
    Ask the player which world to load.
    Returns (world, G, seed_quests).
    ROLE_REGISTRY is populated as a side-effect of whichever path is taken.
    """
    clear()
    print_title()
    print_message("\n[bold yellow]Choose your world:[/bold yellow]")
    print_message(
        "  [bold cyan]1.[/bold cyan] [bold]Neon City[/bold] — "
        "The classic cyberpunk world  [dim](instant start)[/dim]"
    )
    print_message(
        "  [bold cyan]2.[/bold cyan] [bold]Generate New World[/bold] — "
        "Build a custom world from your idea  [dim](~30–90 s)[/dim]"
    )
    print_message()

    choice = pick_int("Select (1-2): ", 1, 2)

    if choice == 1:
        world, G = build_neon_city()
        return world, G, []

    world, G, seed_quests = generate_world_from_prompt()
    return world, G, seed_quests


# ── Character Creation ─────────────────────────────────────────────────────

def character_creation(world) -> PlayerState:
    """Dynamic character creation using whatever roles are in ROLE_REGISTRY."""
    clear()
    print_title()

    name = prompt_input("Enter your name: ")
    if not name:
        name = "Stranger"

    roles = list(ROLE_REGISTRY.keys())
    if not roles:
        print_message("[red]No roles available — using default.[/red]")
        return PlayerState(name=name, role="wanderer", current_location=next(iter(world.locations), ""))

    print_role_select(world_name=world.city_name)
    role_idx = pick_int(f"Choose role (1-{len(roles)}): ", 1, len(roles))
    chosen_role_id = roles[role_idx - 1]
    role_def = ROLE_REGISTRY[chosen_role_id]

    # PlayerState.apply_role_defaults will set stats/rep/heat/location from ROLE_REGISTRY
    player = PlayerState(name=name, role=chosen_role_id)

    # Safety: if start_location is empty or invalid, use first available
    if player.current_location not in world.locations and world.locations:
        player = player.model_copy(update={"current_location": next(iter(world.locations))})

    print_message(f"\nWelcome to {world.city_name}, [bold]{player.name}[/bold].", "green")
    print_message(f"[dim]{role_def.name} archetype loaded.[/dim]")
    prompt_input("Press Enter to begin...")
    return player


# ── Location Menu ──────────────────────────────────────────────────────────

def location_menu(player: PlayerState, world, G) -> PlayerState:
    loc       = world.get_location(player.current_location)
    npcs_here = world.npcs_at(player.current_location)
    moves     = available_moves(player, world, G)
    locked    = locked_moves(player, world, G)
    active_quests = get_active_quests(player)

    options = []
    idx = 1

    # Movement
    move_map = {}
    for loc_id, loc_node, edge in moves:
        label = f"Travel to {loc_node.name} [dim](danger {edge.get('danger', 1)}/5)[/dim]"
        options.append((idx, label))
        move_map[idx] = (loc_id, loc_node, edge)
        idx += 1

    # ── Group NPCs ────────────────────────────────────────────────────────
    hostile_npcs    = [n for n in npcs_here if n.disposition == "hostile"]
    neutral_npcs    = [n for n in npcs_here if n.disposition != "hostile"]

    # ── Combat options if hostile NPCs present ────────────────────────────
    combat_idx = -1
    if hostile_npcs:
        combat_idx = idx
        options.append((idx, f"[bold red]ENGAGE HOSTILE ENFORCERS ({len(hostile_npcs)})[/bold red]"))
        idx += 1

    # ── Interact with neutral NPCs ────────────────────────────────────────
    npc_map   = {}
    quest_map = {}
    for n in neutral_npcs:
        rep = player.faction_rep.get(n.faction) if n.faction else 0
        if n.can_talk(rep):
            options.append((idx, f"Talk to {n.name}"))
            npc_map[idx] = n
            idx += 1
            
            if n.disposition == "quest_giver":
                options.append((idx, f"Ask {n.name} for a job"))
                quest_map[idx] = n
                idx += 1

    # Active quest beat choices
    beat_choice_map = {}
    for quest in active_quests:
        beat = quest.current_beat()
        if beat and beat.choices:
            for choice in beat.choices:
                stat_req = ""
                if choice.required_stat:
                    effective = player.effective_stat(choice.required_stat)
                    color = "green" if effective >= choice.required_stat_value else "red"
                    stat_req = (
                        f" [dim]([{color}]{choice.required_stat} "
                        f"{effective}/{choice.required_stat_value}[/{color}])[/dim]"
                    )
                options.append((idx, f"[Quest] {choice.label}{stat_req}"))
                beat_choice_map[idx] = (quest, choice)
                idx += 1

    options.append((idx, "Check faction status")); status_idx = idx; idx += 1
    options.append((idx, "Quit"));                 quit_idx   = idx

    # ── Display ────────────────────────────────────────────────────────────
    clear()
    print_player_bar(player)
    if active_quests:
        print_quest_panel(active_quests[0])
    print_location(loc, "")
    print_npcs(npcs_here)
    if locked:
        for _, locked_loc, reason in locked:
            print_message(f"[dim]✖ {locked_loc.name} — {reason}[/dim]")
    print_menu(options)

    choice_num = pick_int("> ", 1, quit_idx)

    # ── Handle choice ──────────────────────────────────────────────────────

    if choice_num == quit_idx:
        print_message("Until next time.", "dim")
        sys.exit(0)

    if choice_num == status_idx:
        print_faction_table(player, world)
        prompt_input("Press Enter to continue...")
        return player

    if choice_num in move_map:
        target_id, target_loc, edge = move_map[choice_num]
        print_message("\n[dim]Moving…[/dim]")
        narration = narrate_travel(
            player,
            player.current_location, target_id,
            loc.name, target_loc.name,
            edge.get("danger", 1),
            world=world,
        )
        print_message(f"\n[italic]{narration}[/italic]")
        prompt_input("Press Enter to arrive...")

        new_player, denial = move_player(player, world, G, target_id)
        if denial:
            print_message(f"Blocked: {denial}", "red")
            prompt_input("Press Enter...")
            return player

        new_loc       = world.get_location(target_id)
        loc_narration = narrate_location(new_player, world)
        clear()
        print_player_bar(new_player)
        print_location(new_loc, loc_narration)
        prompt_input("Press Enter to continue...")
        return new_player

    if choice_num == combat_idx:
        manager = CombatManager(player, hostile_npcs)
        new_player = manager.run_combat()
        if not new_player:
            print_message("\n[bold red]FATAL SYSTEM ERROR: PLAYER DERESOLVED[/bold red]", "red")
            print_message("Game Over.", "dim")
            sys.exit(0)
        return new_player

    if choice_num in npc_map:
        npc = npc_map[choice_num]
        rep = player.faction_rep.get(npc.faction) if npc.faction else 0
        dialogue = narrate_npc_dialogue(
            player, npc.name, npc.background_hint, npc.faction, rep, world=world
        )
        print_message(f"\n[bold]{npc.name}:[/bold] [italic]{dialogue}[/italic]")
        prompt_input("Press Enter...")
        return player

    if choice_num in quest_map:
        npc = quest_map[choice_num]
        print_message("\n[dim]Generating quest…[/dim]")
        quest, msg = request_quest(player, world, npc.id)
        if not quest:
            print_message(f"[red]{msg}[/red]")
            prompt_input("Press Enter...")
            return player

        print_message(f"\n[bold magenta]{quest.title}[/bold magenta]")
        print_message(f"[dim]{quest.description}[/dim]")
        print_message(f"[green]Reward: {quest.reward_creds}¢[/green]")
        ans = prompt_input("Accept? (y/n): ")
        if ans.lower() == "y":
            new_player, quest, accept_msg = accept_quest(quest.id, player, player.turn_count)
            print_message(f"[green]{accept_msg}[/green]")
            prompt_input("Press Enter...")
            return new_player
        return player

    if choice_num in beat_choice_map:
        quest, choice = beat_choice_map[choice_num]
        new_player, updated_quest, narration = resolve_choice(
            player, quest, choice, player.turn_count
        )
        if narration:
            print_beat_narration(narration)
        if updated_quest.status.value == "completed":
            print_message(f"\n[bold green]✔ Quest Complete: {updated_quest.title}[/bold green]")
            print_message(f"[green]+{updated_quest.reward_creds}¢[/green]")
        elif updated_quest.status.value == "failed":
            print_message(f"\n[bold red]✖ Quest Failed: {updated_quest.title}[/bold red]")
        prompt_input("Press Enter...")
        return new_player

    return player


# ── Entry Point ────────────────────────────────────────────────────────────

def main():
    world, G, seed_quests = world_selection()
    player = character_creation(world)

    # Lore intro
    clear()
    print_player_bar(player)
    print_lore_intro(world)
    if seed_quests:
        print_message(
            f"[dim]{len(seed_quests)} job(s) are already circulating. "
            "Find a quest-giver to hear them.[/dim]"
        )
    prompt_input("Press Enter to begin your story...")

    # First location narration
    loc       = world.get_location(player.current_location)
    narration = narrate_location(player, world)
    clear()
    print_player_bar(player)
    print_location(loc, narration)
    prompt_input("Press Enter to continue...")

    while player.is_alive:
        player = location_menu(player, world, G)


if __name__ == "__main__":
    main()