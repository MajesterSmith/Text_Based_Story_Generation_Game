"""
engine/llm.py
────────────────────────────────────────────────────────────────────────────
All narration and quest-generation prompts now use the world's theme, tone
and faction list rather than hard-coded cyberpunk references.
"""
from __future__ import annotations
import json
import urllib.request
import urllib.error
from typing import Optional
from models import PlayerState, WorldState, QuestState

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL      = "qwen2.5:7b"


def _call_ollama(prompt: str, expect_json: bool = False) -> str:
    payload = json.dumps({
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.8, "num_predict": 3500},
    }).encode()

    req = urllib.request.Request(
        OLLAMA_URL, data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=360) as resp:
            data = json.loads(resp.read().decode())
            return data.get("response", "").strip()
    except urllib.error.URLError as e:
        return f"[LLM UNAVAILABLE: {e}]"


def narrate_location(player: PlayerState, world: WorldState) -> str:
    ctx = world.to_llm_context(player.current_location)
    prompt = f"""You are the narrator of a {ctx['tone']} {ctx['theme']} text adventure set in {ctx['city']}.

Location: {ctx['location']['name']} ({ctx['location']['type']})
District: {ctx['district']['name']} — {ctx['district']['atmosphere']}
Danger Level: {ctx['location']['danger_level']}/5
Faction Owner: {ctx['location']['faction_owner'] or 'None'}
Scene Hint: {ctx['location']['hint']}
NPCs Present: {', '.join(n['name'] for n in ctx['npcs']) or 'Nobody notable'}
Active Events: {', '.join(e['title'] for e in ctx['events']) or 'None'}

Player: {player.name} ({player.role}) | Health: {player.health} | Creds: {player.creds}
Turn: {ctx['turn']}

Write a vivid 2-3 sentence atmospheric description of arriving at this location.
Be specific and sensory, true to the {ctx['theme']} theme and {ctx['tone']} tone.
No dialogue. No choices. End with one short sentence hinting at tension or opportunity."""
    return _call_ollama(prompt)


def narrate_travel(player: PlayerState, from_loc: str, to_loc: str,
                   from_name: str, to_name: str, danger: int,
                   world: Optional[WorldState] = None) -> str:
    theme = world.theme if world else "unknown"
    tone  = world.tone  if world else "gritty"
    city  = world.city_name if world else "the city"
    prompt = f"""You are narrating a {tone} {theme} text adventure.

{player.name} travels from {from_name} to {to_name} through {city}.
Danger level of the route: {danger}/5.
Role: {player.role}

Write 1-2 sentences describing the journey. Be atmospheric, brief, and true to the {theme} setting."""
    return _call_ollama(prompt)


def narrate_npc_dialogue(player: PlayerState, npc_name: str,
                         npc_hint: str, npc_faction: Optional[str],
                         player_rep: int,
                         world: Optional[WorldState] = None) -> str:
    theme     = world.theme if world else "unknown"
    tone      = world.tone  if world else "gritty"
    rep_label = "hostile" if player_rep < -20 else "neutral" if player_rep < 20 else "friendly"
    prompt = f"""You are narrating a {tone} {theme} text adventure.

NPC: {npc_name} | Faction: {npc_faction or 'Independent'} | Background: {npc_hint}
Player: {player.name} ({player.role}) | Relationship: {rep_label} (rep: {player_rep})

Write 2-3 lines of sharp, in-character dialogue from {npc_name} to the player.
Stay true to the {theme} theme and {tone} tone. No narration, just dialogue."""
    return _call_ollama(prompt)


def generate_quest(player: PlayerState, world: WorldState,
                   giver_npc_name: str, giver_faction: Optional[str]) -> str:
    ctx        = world.to_llm_context(player.current_location)
    factions   = world.factions
    beat_types = ["investigation", "choice", "combat", "infiltration", "dialogue", "delivery", "finale"]

    prompt = f"""You are a quest designer for a {ctx['tone']} {ctx['theme']} text adventure set in {ctx['city']}.

Generate a quest given to {player.name} ({player.role}) by {giver_npc_name} ({giver_faction or 'Independent'}).
Current location: {ctx['location']['name']} in {ctx['district']['name']}.
Player health: {player.health} | Creds: {player.creds} | Turn: {ctx['turn']}
Known factions: {', '.join(factions)}

Return ONLY valid JSON — no markdown, no explanation — matching this exact schema:
{{
  "title": "string",
  "description": "string (2 sentences)",
  "tags": ["string"],
  "giver_faction": "one of {factions} or null",
  "giver_npc_id": null,
  "reward_creds": integer (100-800),
  "reward_rep":  {{"faction_name": integer_delta}},
  "reward_heat": {{"faction_name": integer_delta}},
  "initial_value": 15,
  "win_threshold": 40,
  "beats": [
    {{
      "id": "b1",
      "title": "string",
      "type": "one of {beat_types}",
      "narration": "string (2-3 sentences, {ctx['tone']} tone)",
      "objective": "string (1 sentence)",
      "is_terminal": false,
      "terminal_status": null,
      "choices": [
        {{
          "index": 1,
          "label": "string",
          "required_stat": "hacking|combat|stealth|persuasion|street_cred or null",
          "required_stat_value": integer,
          "next_beat_id": "b2",
          "heat_delta": {{}},
          "rep_delta":  {{}},
          "health_delta": 0,
          "creds_delta": 0,
          "counter_delta": integer (-15 to +15),
          "success_narration": "string",
          "failure_narration": "string"
        }}
      ],
      "on_enter_heat_delta": {{}},
      "on_enter_rep_delta": {{}}
    }},
    {{
      "id": "b2",
      "title": "Finale",
      "type": "finale",
      "narration": "string",
      "objective": "string",
      "is_terminal": true,
      "terminal_status": "completed",
      "choices": [],
      "on_enter_heat_delta": {{}},
      "on_enter_rep_delta": {{}}
    }}
  ]
}}

Make it thematically consistent with {ctx['theme']}, morally ambiguous, specific to {ctx['city']}.
Use only faction names from: {factions}
Minimum 2 beats.

### Threshold System Rules:
- The hidden counter starts at `initial_value`.
- Reaching `<= 0` fails the quest immediately.
- Reaching the finale with `< win_threshold` fails the quest.
- Assign higher `counter_delta` to "Correct/Smart" choices.
- Assign negative `counter_delta` to "Mistakes/Wrong" choices.
- A successful stat check adds +1 automatically (don't include this in delta).
- Balance the quest so it requires some smart choices to win.
"""
    return _call_ollama(prompt, expect_json=True)


def narrate_quest_beat(player: PlayerState, beat_narration: str,
                       quest_title: str, world: Optional[WorldState] = None) -> str:
    theme = world.theme if world else "unknown"
    tone  = world.tone  if world else "gritty"
    prompt = f"""You are narrating a {tone} {theme} text adventure.

Quest: {quest_title}
Scene: {beat_narration}
Player: {player.name} ({player.role}) | Health: {player.health}

Expand this scene into 2-3 vivid sentences. Stay atmospheric. End on tension."""
    return _call_ollama(prompt)


def narrate_quest_transition(player: PlayerState, world: WorldState,
                             quest: QuestState, latest_event_summary: str) -> str:
    ctx = world.to_llm_context(player.current_location)
    history_str = "\n".join(quest.history[-5:])  # Last 5 events for context

    # Foreshadowing hint logic
    ratio = quest.hidden_counter / max(1, quest.win_threshold)
    if ratio >= 0.8:
        foreshadow_hint = "The winds of fate favor them; success feels inevitable yet fragile."
    elif ratio >= 0.5:
        foreshadow_hint = "The path ahead is clear, but the shadows are beginning to lengthen."
    elif ratio >= 0.2:
        foreshadow_hint = "Each step feels heavier; the city is losing patience and the mission is in jeopardy."
    else:
        foreshadow_hint = "The situation is dire; survival is a whisper, and failure a deafening roar."

    prompt = f"""You are the Omniscient Narrator of a {ctx['tone']} {ctx['theme']} saga set in {ctx['city']}.
A pivotal moment has just passed for {player.name} ({player.role}) during the quest: '{quest.title}'.

Latest Event: {latest_event_summary}
Memory of Sins (Recent History): 
{history_str}

World Context: {ctx['location']['name']} — {ctx['location']['hint']}
Foreshadowing Note: {foreshadow_hint}

Write 2-3 sentences of immersive, detached third-person narration that bridges this latest outcome to the journey ahead.
- DO NOT use game mechanics (counter, threshold, success/failure).
- DO NOT use visual distinction (no italics, no special headers).
- Reference their "Sins" (past choices) if they weigh heavily on the moment.
- Weave in the poetic foreshadowing of their current momentum.
- Maintain the {ctx['tone']} tone.
"""
    return _call_ollama(prompt)