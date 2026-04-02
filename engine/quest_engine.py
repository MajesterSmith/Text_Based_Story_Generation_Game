"""engine/quest_engine.py — faction references are plain strings."""
from __future__ import annotations
import json
import uuid
from typing import Optional, Tuple, Dict
from models import PlayerState, WorldState, QuestState, GeneratedQuestData, BeatChoice, QuestStatus
from engine.llm import generate_quest

QUEST_REGISTRY: Dict[str, QuestState] = {}


def request_quest(player: PlayerState, world: WorldState,
                  npc_id: str) -> Tuple[Optional[QuestState], str]:
    npc = world.get_npc(npc_id)
    if not npc:
        return None, "NPC not found."

    raw_json = generate_quest(
        player, world,
        giver_npc_name=npc.name,
        giver_faction=npc.faction,   # already a plain str or None
    )

    cleaned = raw_json.strip()
    cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"```$",          "", cleaned, flags=re.MULTILINE).strip()

    try:
        data       = json.loads(cleaned)
        quest_data = GeneratedQuestData(**data)
    except Exception as e:
        return None, f"Quest generation failed: {e}\nRaw: {raw_json[:300]}"

    quest_id = f"q_{uuid.uuid4().hex[:8]}"
    quest    = quest_data.to_quest_state(quest_id)
    quest    = quest.model_copy(update={"giver_npc_id": npc_id})
    QUEST_REGISTRY[quest_id] = quest
    return quest, "Quest generated."


def accept_quest(quest_id: str, player: PlayerState,
                 turn: int) -> Tuple[PlayerState, QuestState, str]:
    quest = QUEST_REGISTRY.get(quest_id)
    if not quest:
        return player, None, "Quest not found."
    quest      = quest.accept(turn)
    QUEST_REGISTRY[quest_id] = quest
    new_player = player.model_copy(
        update={"active_quest_ids": player.active_quest_ids + [quest_id]}
    )
    return new_player, quest, f"Quest accepted: {quest.title}"


def resolve_choice(player: PlayerState, quest: QuestState,
                   choice: BeatChoice, turn: int) -> Tuple[PlayerState, QuestState, str]:
    new_player = player

    # Stat check
    success = True
    if choice.required_stat and choice.required_stat_value > 0:
        success = new_player.effective_stat(choice.required_stat) >= choice.required_stat_value

    if choice.health_delta:
        new_player = new_player.with_health(
            choice.health_delta if success else choice.health_delta * 2
        )
    if choice.creds_delta:
        new_player = new_player.with_creds(choice.creds_delta if success else 0)

    for faction_str, delta in (choice.rep_delta if success else {}).items():
        new_player = new_player.with_rep_change(faction_str, delta)
    for faction_str, delta in choice.heat_delta.items():
        new_player = new_player.with_heat_raise(faction_str, delta)

    narration = choice.success_narration if success else choice.failure_narration

    next_id = choice.next_beat_id
    if next_id and next_id in quest.beats:
        quest = quest.advance_to(next_id, turn)
    else:
        terminal_beat = list(quest.beats.values())[-1]
        terminal_beat = terminal_beat.model_copy(
            update={"is_terminal": True, "terminal_status": QuestStatus.COMPLETED}
        )
        quest = quest.model_copy(update={"beats": {**quest.beats, terminal_beat.id: terminal_beat}})
        quest = quest.advance_to(terminal_beat.id, turn)

    QUEST_REGISTRY[quest.id] = quest

    if quest.status.value in ("completed", "failed"):
        new_player = new_player.model_copy(update={
            "active_quest_ids":    [q for q in new_player.active_quest_ids if q != quest.id],
            "completed_quest_ids": new_player.completed_quest_ids + [quest.id],
        })
        new_player = new_player.with_creds(quest.reward_creds)
        for faction_str, delta in quest.reward_rep.items():
            new_player = new_player.with_rep_change(faction_str, delta)

    return new_player, quest, narration


def get_active_quests(player: PlayerState) -> list[QuestState]:
    return [QUEST_REGISTRY[qid] for qid in player.active_quest_ids if qid in QUEST_REGISTRY]


# lazy import to avoid circular at module level
import re