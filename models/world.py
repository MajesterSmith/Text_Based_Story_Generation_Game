from __future__ import annotations
from .base import Stats, LocationType, ServiceType, NPCDisposition, LocationNode, District, NPC
from pydantic import BaseModel, Field
from typing import Dict, List, Optional

class GlobalEvent(BaseModel):
    id: str
    title: str
    description: str
    turn_triggered: int
    affected_factions: List[str] = Field(default_factory=list)  # plain strings
    heat_delta: Dict[str, int]   = Field(default_factory=dict)
    is_resolved: bool = False


class WorldState(BaseModel):
    city_name: str = "Neon City"
    theme: str = "cyberpunk"
    tone: str  = "gritty and morally ambiguous"
    lore_intro: str = ""
    turn_count: int = 0
    factions: List[str] = Field(default_factory=list)   # ordered faction name strings
    locations: Dict[str, LocationNode] = Field(default_factory=dict)
    districts: Dict[str, District]     = Field(default_factory=dict)
    npcs: Dict[str, NPC]               = Field(default_factory=dict)
    global_events: List[GlobalEvent]   = Field(default_factory=list)

    def get_location(self, loc_id: str) -> Optional[LocationNode]:
        return self.locations.get(loc_id)

    def get_npc(self, npc_id: str) -> Optional[NPC]:
        return self.npcs.get(npc_id)

    def npcs_at(self, loc_id: str) -> List[NPC]:
        return [n for n in self.npcs.values() if n.location_id == loc_id]

    def active_events(self) -> List[GlobalEvent]:
        return [e for e in self.global_events if not e.is_resolved]

    def to_llm_context(self, loc_id: str) -> Dict:
        loc      = self.get_location(loc_id)
        district = self.districts.get(loc.district) if loc else None
        return {
            "city":  self.city_name,
            "theme": self.theme,
            "tone":  self.tone,
            "turn":  self.turn_count,
            "factions": self.factions,
            "location": {
                "name":         loc.name if loc else "Unknown",
                "type":         loc.type if loc else None,
                "faction_owner": loc.faction_owner if loc else None,
                "danger_level": loc.danger_level if loc else 0,
                "hint":         loc.description_hint if loc else "",
            },
            "district": {
                "name":       district.name if district else "Unknown",
                "atmosphere": district.atmosphere if district else "",
            },
            "npcs": [
                {"name": n.name, "faction": n.faction, "disposition": n.disposition}
                for n in self.npcs_at(loc_id)
            ],
            "events": [
                {"title": e.title, "description": e.description}
                for e in self.active_events()
            ],
        }