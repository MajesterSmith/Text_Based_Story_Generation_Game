from __future__ import annotations
from enum import Enum
import random
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

# ── Enums ─────────────────────────────────────────────────────────────

class ItemType(str, Enum):
    WEAPON     = "weapon"
    CYBERNETIC = "cybernetic"
    TOOL       = "tool"
    CONSUMABLE = "consumable"
    KEY_ITEM   = "key_item"


class LocationType(str, Enum):
    DISTRICT    = "district"
    BAR         = "bar"
    MARKET      = "market"
    HIDEOUT     = "hideout"
    CORP_OFFICE = "corp_office"
    PRECINCT    = "precinct"
    PORT        = "port"
    RUINS       = "ruins"
    DATA_NEXUS  = "data_nexus"


class ServiceType(str, Enum):
    WEAPON_DEALER = "weapon_dealer"
    MEDIC         = "medic"
    CYBERDOC      = "cyberdoc"
    INFO_BROKER   = "info_broker"
    FENCE         = "fence"
    QUEST_GIVER   = "quest_giver"
    TRANSIT       = "transit"
    SAFE_HOUSE    = "safe_house"


class NPCDisposition(str, Enum):
    FRIENDLY    = "friendly"
    NEUTRAL     = "neutral"
    HOSTILE     = "hostile"
    INFORMANT   = "informant"
    VENDOR      = "vendor"
    QUEST_GIVER = "quest_giver"


class QuestStatus(str, Enum):
    AVAILABLE = "available"
    ACTIVE    = "active"
    COMPLETED = "completed"
    FAILED    = "failed"


class BeatType(str, Enum):
    INVESTIGATION = "investigation"
    CHOICE        = "choice"
    COMBAT        = "combat"
    INFILTRATION  = "infiltration"
    DIALOGUE      = "dialogue"
    DELIVERY      = "delivery"
    FINALE        = "finale"


# ── Shared Data Structures ─────────────────────────────────────────────

class Stats(BaseModel):
    """
    Core attributes for the combat and skill systems.
    Attribute values range from 1 to 10.
    """
    strength:     int = Field(default_factory=lambda: random.randint(2, 4), ge=1, le=10)
    agility:      int = Field(default_factory=lambda: random.randint(2, 4), ge=1, le=10)
    vitality:     int = Field(default_factory=lambda: random.randint(2, 4), ge=1, le=10)
    stealth:      int = Field(default_factory=lambda: random.randint(2, 4), ge=1, le=10)
    persuasion:   int = Field(default_factory=lambda: random.randint(2, 4), ge=1, le=10)
    intelligence: int = Field(default_factory=lambda: random.randint(2, 4), ge=1, le=10)

    def effective(self, stat: str, bonuses: Dict[str, int]) -> int:
        return min(10, getattr(self, stat, 1) + bonuses.get(stat, 0))


class FactionRep(BaseModel):
    """Reputation per faction, keyed by faction name string."""
    scores: Dict[str, int] = Field(default_factory=dict)

    def get(self, faction: str) -> int:
        return self.scores.get(faction, 0)

    def adjust(self, faction: str, delta: int) -> "FactionRep":
        updated = dict(self.scores)
        updated[faction] = max(-100, min(100, updated.get(faction, 0) + delta))
        return FactionRep(scores=updated)

    def standing_label(self, faction: str) -> str:
        rep = self.get(faction)
        if rep >= 60:  return "Trusted Ally"
        if rep >= 20:  return "Friendly"
        if rep >= -20: return "Neutral"
        if rep >= -60: return "Hostile"
        return "Kill on Sight"

    @classmethod
    def from_dict(cls, d: Dict[str, int]) -> "FactionRep":
        return cls(scores=dict(d))


class HeatLevel(BaseModel):
    """Heat (wanted level) per faction, keyed by faction name string."""
    scores: Dict[str, int] = Field(default_factory=dict)

    def get(self, faction: str) -> int:
        return self.scores.get(faction, 0)

    def raise_heat(self, faction: str, amount: int) -> "HeatLevel":
        updated = dict(self.scores)
        updated[faction] = max(0, min(100, updated.get(faction, 0) + amount))
        return HeatLevel(scores=updated)

    def decay(self, amount: int = 2) -> "HeatLevel":
        return HeatLevel(scores={k: max(0, v - amount) for k, v in self.scores.items()})

    def threat_label(self, faction: str) -> str:
        h = self.get(faction)
        if h <= 20: return "Clean"
        if h <= 50: return "Suspicious"
        if h <= 75: return "Wanted"
        return "Shoot on Sight"

    def threat_color(self, faction: str) -> str:
        h = self.get(faction)
        if h <= 20: return "green"
        if h <= 50: return "yellow"
        if h <= 75: return "dark_orange"
        return "red"

    @classmethod
    def from_dict(cls, d: Dict[str, int]) -> "HeatLevel":
        return cls(scores=dict(d))


class Item(BaseModel):
    model_config = {"frozen": True}
    id: str
    name: str
    type: ItemType
    description: str
    value: int = Field(default=0, ge=0)
    stat_bonus: Dict[str, int] = Field(default_factory=dict)
    quest_id: Optional[str] = None


class RoleDef(BaseModel):
    """A playable role generated for the current world."""
    id: str                        # snake_case key, e.g. "witch"
    name: str                      # Display name, e.g. "Witch"
    description: str
    stats: Stats
    faction_rep: FactionRep = Field(default_factory=FactionRep)
    heat: HeatLevel          = Field(default_factory=HeatLevel)
    start_location: str      = ""
    start_creds: int         = Field(default=500, ge=0)


# ── Entity Models ─────────────────────────────────────────────────────────────

class LocationNode(BaseModel):
    id: str
    name: str
    district: str
    type: LocationType
    faction_owner: Optional[str] = None
    description_hint: str = ""
    danger_level: int = Field(default=1, ge=1, le=5)
    heat_modifier: Dict[str, int] = Field(default_factory=dict)
    heat_lock_threshold: int = Field(default=100, ge=0, le=100)
    rep_lock_threshold: int  = Field(default=-100, ge=-100, le=100)
    services: List[ServiceType] = Field(default_factory=list)
    resident_npc_ids: List[str] = Field(default_factory=list)

    def is_accessible(self, player_heat: int, player_rep: int) -> bool:
        return player_heat < self.heat_lock_threshold and player_rep >= self.rep_lock_threshold

    def denial_reason(self, player_heat: int, player_rep: int) -> Optional[str]:
        if player_heat >= self.heat_lock_threshold:
            return f"Heat too high ({player_heat}/{self.heat_lock_threshold})"
        if player_rep < self.rep_lock_threshold:
            return f"Reputation too low ({player_rep}/{self.rep_lock_threshold})"
        return None


class District(BaseModel):
    id: str
    name: str
    faction_owner: Optional[str] = None
    atmosphere: str = ""
    sub_location_ids: List[str] = Field(default_factory=list)


class NPC(BaseModel):
    id: str
    name: str
    faction: Optional[str] = None
    disposition: NPCDisposition = NPCDisposition.NEUTRAL
    location_id: str
    background_hint: str = ""
    min_rep_to_talk: int = Field(default=-100, ge=-100, le=100)
    quest_ids: List[str] = Field(default_factory=list)
    combat_stats: Optional[Stats] = None

    def can_talk(self, player_rep: int) -> bool:
        """Simple reputation check to see if the NPC is willing to speak."""
        return player_rep >= self.min_rep_to_talk
