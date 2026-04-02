"""
models/quest.py
────────────────────────────────────────────────────────────────────────────
FactionName Enum removed.  giver_faction and all faction keys are plain str.
"""
from __future__ import annotations
from .base import QuestStatus, BeatType
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field



class BeatChoice(BaseModel):
    index: int
    label: str
    required_stat: Optional[str] = None
    required_stat_value: int = 0
    next_beat_id: Optional[str] = None
    heat_delta: Dict[str, int] = Field(default_factory=dict)
    rep_delta:  Dict[str, int] = Field(default_factory=dict)
    health_delta: int = 0
    creds_delta:  int = 0
    success_narration: str = ""
    failure_narration: str = ""


class QuestBeat(BaseModel):
    id: str
    title: str
    type: BeatType
    narration: str
    objective: str
    choices: List[BeatChoice] = Field(default_factory=list)
    is_terminal: bool = False
    terminal_status: Optional[QuestStatus] = None
    on_enter_heat_delta: Dict[str, int] = Field(default_factory=dict)
    on_enter_rep_delta:  Dict[str, int] = Field(default_factory=dict)


class QuestState(BaseModel):
    id: str
    title: str
    description: str
    giver_faction: Optional[str] = None      # plain string
    giver_npc_id:  Optional[str] = None
    status: QuestStatus = QuestStatus.AVAILABLE
    current_beat_id: Optional[str] = None
    completed_beat_ids: List[str] = Field(default_factory=list)
    beats: Dict[str, QuestBeat]   = Field(default_factory=dict)
    reward_creds: int = Field(default=0, ge=0)
    reward_rep:  Dict[str, int] = Field(default_factory=dict)
    reward_heat: Dict[str, int] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)
    turn_accepted:  Optional[int] = None
    turn_completed: Optional[int] = None

    def current_beat(self) -> Optional[QuestBeat]:
        return self.beats.get(self.current_beat_id) if self.current_beat_id else None

    def accept(self, turn: int) -> "QuestState":
        first = next(iter(self.beats), None)
        return self.model_copy(update={
            "status": QuestStatus.ACTIVE,
            "current_beat_id": first,
            "turn_accepted": turn,
        })

    def advance_to(self, beat_id: str, turn: int) -> "QuestState":
        done = list(set(
            self.completed_beat_ids +
            ([self.current_beat_id] if self.current_beat_id else [])
        ))
        beat = self.beats.get(beat_id)
        updates: Dict[str, Any] = {"current_beat_id": beat_id, "completed_beat_ids": done}
        if beat and beat.is_terminal:
            updates["status"] = beat.terminal_status or QuestStatus.COMPLETED
            updates["turn_completed"] = turn
        return self.model_copy(update=updates)

    def fail(self, turn: int) -> "QuestState":
        return self.model_copy(update={"status": QuestStatus.FAILED, "turn_completed": turn})

    def to_llm_context(self) -> Dict:
        beat = self.current_beat()
        return {
            "title":       self.title,
            "description": self.description,
            "tags":        self.tags,
            "current_beat": {
                "title":     beat.title,
                "type":      beat.type,
                "objective": beat.objective,
            } if beat else None,
        }


class GeneratedQuestData(BaseModel):
    """Raw schema the LLM must conform to — all faction fields are plain str."""
    title: str
    description: str
    tags: List[str] = Field(default_factory=list)
    giver_faction: Optional[str] = None
    giver_npc_id:  Optional[str] = None
    reward_creds: int = Field(default=200, ge=0)
    reward_rep:  Dict[str, int] = Field(default_factory=dict)
    reward_heat: Dict[str, int] = Field(default_factory=dict)
    beats: List[Dict] = Field(min_length=2)

    def to_quest_state(self, quest_id: str) -> QuestState:
        beats_dict: Dict[str, QuestBeat] = {}
        for b in self.beats:
            choices = [BeatChoice(**c) for c in b.get("choices", [])]
            beat = QuestBeat(
                id=b["id"],
                title=b["title"],
                type=BeatType(b["type"]),
                narration=b["narration"],
                objective=b["objective"],
                choices=choices,
                is_terminal=b.get("is_terminal", False),
                terminal_status=(
                    QuestStatus(b["terminal_status"]) if b.get("terminal_status") else None
                ),
                on_enter_heat_delta=b.get("on_enter_heat_delta", {}),
                on_enter_rep_delta=b.get("on_enter_rep_delta", {}),
            )
            beats_dict[b["id"]] = beat

        return QuestState(
            id=quest_id,
            title=self.title,
            description=self.description,
            tags=self.tags,
            giver_faction=self.giver_faction,   # already a plain str or None
            giver_npc_id=self.giver_npc_id,
            reward_creds=self.reward_creds,
            reward_rep=self.reward_rep,
            reward_heat=self.reward_heat,
            beats=beats_dict,
        )