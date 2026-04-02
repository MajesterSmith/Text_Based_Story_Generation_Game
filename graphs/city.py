from __future__ import annotations
import networkx as nx
from typing import List, Optional
from models import LocationNode, WorldState


def build_city_graph(world: WorldState) -> nx.DiGraph:
    G = nx.DiGraph()
    for loc_id, loc in world.locations.items():
        G.add_node(loc_id, data=loc)
    return G


def add_route(G: nx.DiGraph, src: str, dst: str,
              travel_time: int = 1,
              danger: int = 1,
              bidirectional: bool = True) -> None:
    G.add_edge(src, dst, travel_time=travel_time, danger=danger)
    if bidirectional:
        G.add_edge(dst, src, travel_time=travel_time, danger=danger)


def get_neighbors(G: nx.DiGraph, loc_id: str) -> List[str]:
    return list(G.successors(loc_id))


def get_edge_data(G: nx.DiGraph, src: str, dst: str) -> dict:
    return G.edges[src, dst] if G.has_edge(src, dst) else {}


def shortest_path(G: nx.DiGraph, src: str, dst: str) -> Optional[List[str]]:
    try:
        return nx.shortest_path(G, src, dst, weight="travel_time")
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None


def locations_by_faction(G: nx.DiGraph, faction: str) -> List[str]:
    """Return all location ids owned by the given faction string."""
    return [
        n for n, d in G.nodes(data=True)
        if d.get("data") and d["data"].faction_owner == faction
    ]