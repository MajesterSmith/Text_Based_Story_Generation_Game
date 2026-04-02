"""engine/navigation.py — all faction references are plain strings."""
from __future__ import annotations
from typing import List, Optional, Tuple
import networkx as nx
from models import PlayerState, WorldState, LocationNode
from graphs.city import get_neighbors, get_edge_data


def available_moves(player: PlayerState, world: WorldState,
                    G: nx.DiGraph) -> List[Tuple[str, LocationNode, dict]]:
    results = []
    for neighbor_id in get_neighbors(G, player.current_location):
        loc = world.get_location(neighbor_id)
        if not loc:
            continue
        edge = get_edge_data(G, player.current_location, neighbor_id)

        if loc.faction_owner:
            p_heat = player.heat.get(loc.faction_owner)
            p_rep  = player.faction_rep.get(loc.faction_owner)
        else:
            p_heat, p_rep = 0, 0

        if loc.is_accessible(p_heat, p_rep):
            results.append((neighbor_id, loc, edge))
    return results


def locked_moves(player: PlayerState, world: WorldState,
                 G: nx.DiGraph) -> List[Tuple[str, LocationNode, str]]:
    results = []
    for neighbor_id in get_neighbors(G, player.current_location):
        loc = world.get_location(neighbor_id)
        if not loc:
            continue
        if loc.faction_owner:
            p_heat = player.heat.get(loc.faction_owner)
            p_rep  = player.faction_rep.get(loc.faction_owner)
            reason = loc.denial_reason(p_heat, p_rep)
            if reason:
                results.append((neighbor_id, loc, reason))
    return results


def move_player(player: PlayerState, world: WorldState,
                G: nx.DiGraph, target_id: str) -> Tuple[PlayerState, Optional[str]]:
    loc = world.get_location(target_id)
    if not loc:
        return player, "That location doesn't exist."

    if loc.faction_owner:
        p_heat = player.heat.get(loc.faction_owner)
        p_rep  = player.faction_rep.get(loc.faction_owner)
        reason = loc.denial_reason(p_heat, p_rep)
        if reason:
            return player, reason

    new_player = player
    for faction_name, delta in loc.heat_modifier.items():
        new_player = new_player.with_heat_raise(faction_name, delta)

    new_player = new_player.with_location(target_id).next_turn()
    return new_player, None