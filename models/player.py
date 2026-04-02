from __future__ import annotations
from .base import ItemType, Item, Stats, FactionRep, HeatLevel, RoleDef
from pydantic import BaseModel, Field, model_validator
from typing import Dict, List, Optional

# ── Global role registry (populated by seed / seed_generator) ─────────────

ROLE_REGISTRY: Dict[str, RoleDef] = {}   # id → RoleDef


# ── PlayerState ────────────────────────────────────────────────────────────

class PlayerState(BaseModel):
    name: str = Field(min_length=1, max_length=32)
    role: str                           # role id string, e.g. "witch"
    health: int = Field(default=100, ge=0)
    creds: int  = Field(default=500, ge=0)
    stats: Stats = Field(default_factory=Stats)
    faction_rep: FactionRep = Field(default_factory=FactionRep)
    heat: HeatLevel         = Field(default_factory=HeatLevel)
    inventory: List[Item]   = Field(default_factory=list)
    current_location: str   = ""
    visited_locations: List[str]    = Field(default_factory=list)
    active_quest_ids: List[str]     = Field(default_factory=list)
    completed_quest_ids: List[str]  = Field(default_factory=list)
    turn_count: int = Field(default=0, ge=0)

    @model_validator(mode="before")
    @classmethod
    def apply_role_defaults(cls, values):
        role_id = values.get("role", "")
        role_def = ROLE_REGISTRY.get(role_id)
        if role_def:
            if "stats" not in values:
                values["stats"] = role_def.stats
            if "faction_rep" not in values:
                values["faction_rep"] = role_def.faction_rep
            if "heat" not in values:
                values["heat"] = role_def.heat
            if not values.get("current_location"):
                values["current_location"] = role_def.start_location
            if "creds" not in values:
                values["creds"] = role_def.start_creds
        return values

    @property
    def max_health(self) -> int:
        """Dynamically calculated maximum HP based on Vitality."""
        return 70 + (self.stats.vitality * 10)

    @property
    def is_alive(self) -> bool:
        return self.health > 0

    @property
    def item_stat_bonuses(self) -> Dict[str, int]:
        bonuses: Dict[str, int] = {}
        for item in self.inventory:
            for stat, val in item.stat_bonus.items():
                bonuses[stat] = bonuses.get(stat, 0) + val
        return bonuses

    def effective_stat(self, stat: str) -> int:
        return self.stats.effective(stat, self.item_stat_bonuses)

    def health_label(self) -> str:
        if self.health >= 75: return "Healthy"
        if self.health >= 40: return "Wounded"
        if self.health >= 15: return "Critical"
        return "Near Death"

    def with_health(self, delta: int) -> "PlayerState":
        return self.model_copy(update={"health": max(0, min(self.max_health, self.health + delta))})

    def add_xp(self, stat_name: str, amount: int = 1) -> "PlayerState":
        """
        Increment a specific stat by 'amount' (post-battle growth).
        Clamped at 10.
        """
        if not hasattr(self.stats, stat_name):
            return self
        
        current_val = getattr(self.stats, stat_name)
        new_stats = self.stats.model_copy(update={stat_name: min(10, current_val + amount)})
        return self.model_copy(update={"stats": new_stats})

    def with_creds(self, delta: int) -> "PlayerState":
        return self.model_copy(update={"creds": max(0, self.creds + delta)})

    def with_location(self, loc_id: str) -> "PlayerState":
        visited = list(set(self.visited_locations + [loc_id]))
        return self.model_copy(update={"current_location": loc_id, "visited_locations": visited})

    def next_turn(self) -> "PlayerState":
        return self.model_copy(update={"heat": self.heat.decay(), "turn_count": self.turn_count + 1})

    def with_rep_change(self, faction: str, delta: int) -> "PlayerState":
        return self.model_copy(update={"faction_rep": self.faction_rep.adjust(faction, delta)})

    def with_heat_raise(self, faction: str, amount: int) -> "PlayerState":
        return self.model_copy(update={"heat": self.heat.raise_heat(faction, amount)})