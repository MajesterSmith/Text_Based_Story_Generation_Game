"""
data/seed_generator.py
────────────────────────────────────────────────────────────────────────────
Generates a complete game world from user inputs:
  • City name, theme, premise, tone
  • Dynamic factions (plain strings, no Enum)
  • Theme-specific roles replacing Ghost/Blade/Wire
  • Districts, locations, NPCs, routes
  • Starting global events
  • Seed quests pre-loaded into QUEST_REGISTRY

Public API
----------
    world, G, seed_quests = generate_world_from_prompt()
    # ROLE_REGISTRY is populated as a side-effect
"""
from __future__ import annotations

import json
import re
import uuid
from typing import Optional

import networkx as nx
from rich.console import Console
from rich.panel import Panel

from models import (
    WorldState, LocationNode, LocationType, ServiceType,
    District, NPC, NPCDisposition,
    RoleDef, ROLE_REGISTRY,
    Stats, FactionRep, HeatLevel,
    QuestState, GeneratedQuestData,
    GlobalEvent,
)
from graphs.city import build_city_graph, add_route
from engine.llm import _call_ollama
from engine.quest_engine import QUEST_REGISTRY

console = Console()

_LOC_TYPES    = [t.value for t in LocationType]
_SVC_TYPES    = [s.value for s in ServiceType]
_DISPOSITIONS = [d.value for d in NPCDisposition]
_BEAT_TYPES   = ["investigation", "choice", "combat",
                 "infiltration", "dialogue", "delivery", "finale"]
_STAT_NAMES   = ["strength", "agility", "vitality", "stealth", "persuasion", "intelligence"]


# ══════════════════════════════════════════════════════════════════════════════
#  STEP 1 – Collect inputs
# ══════════════════════════════════════════════════════════════════════════════

def _collect_inputs() -> dict:
    console.print(Panel.fit(
        "[bold magenta]W O R L D   G E N E R A T O R[/bold magenta]\n"
        "[dim]Answer a few questions and a new world will be built for you.[/dim]",
        border_style="magenta", padding=(1, 4),
    ))

    console.print("\n[bold cyan]1. Genre / Theme[/bold cyan]")
    console.print("[dim]e.g. cyberpunk · dark fantasy · post-apocalyptic · space opera · noir western · steampunk[/dim]")
    theme = console.input("[bold green]Theme → [/bold green]").strip() or "cyberpunk"

    console.print("\n[bold cyan]2. World Name[/bold cyan]")
    city_name = console.input("[bold green]World name → [/bold green]").strip() or "Unknown City"

    console.print("\n[bold cyan]3. Story Premise[/bold cyan]")
    console.print("[dim]One or two sentences: what is happening that the player steps into?[/dim]")
    premise = console.input("[bold green]Premise → [/bold green]").strip() or "A world on the edge. Power is shifting."

    console.print("\n[bold cyan]4. Factions (optional)[/bold cyan]")
    console.print("[dim]Name 2-4 rival groups separated by commas, or press Enter to let the AI decide.[/dim]")
    faction_raw = console.input("[bold green]Factions → [/bold green]").strip()
    factions = [f.strip() for f in faction_raw.split(",") if f.strip()] or []

    console.print("\n[bold cyan]5. Tone[/bold cyan]")
    console.print("[dim]e.g. gritty realism · high-action · horror · political intrigue · comedic · mythic[/dim]")
    tone = console.input("[bold green]Tone → [/bold green]").strip() or "gritty and morally ambiguous"

    console.print("\n[dim]Building your world — this takes ~30–90 s depending on your model…[/dim]\n")
    return dict(theme=theme, city_name=city_name, premise=premise,
                factions=factions, tone=tone)


# ══════════════════════════════════════════════════════════════════════════════
#  STEP 2 – LLM prompt
# ══════════════════════════════════════════════════════════════════════════════

_PROMPT = """\
You are a world-builder for a text-adventure game engine.

Theme   : {theme}
World   : {city_name}
Premise : {premise}
Factions: {factions_hint}
Tone    : {tone}

Generate the COMPLETE world as ONLY valid JSON — no markdown, no extra text.

Important constraints:
- stat names must come from: {stats} (used for skill checks)
- location types from: {loc_types}
- service types from:  {svc_types}
- NPC dispositions from: {dispositions}
- quest beat types from: {beat_types}
- All faction references everywhere must be EXACT matches to the names you define in "factions".

Schema:
{{
  "city_name": "string",
  "lore_intro": "string — 3 atmospheric sentences read aloud at game start",
  "factions": [
    {{
      "name": "string — unique faction name",
      "description": "string — 1 sentence"
    }}
  ],
  "roles": [
    {{
      "id": "snake_case",
      "name": "string — display name fitting the theme",
      "description": "string — 1 flavourful sentence",
      "stats": {{
        "strength": 1-10, "agility": 1-10, "vitality": 1-10,
        "stealth": 1-10, "persuasion": 1-10, "intelligence": 1-10
      }},
      "faction_rep": {{"faction_name": integer -100..100}},
      "heat":        {{"faction_name": integer 0..100}},
      "start_location": "location_id",
      "start_creds": 300-900
    }}
  ],
  "districts": [
    {{
      "id": "snake_case",
      "name": "string",
      "faction_owner": "faction name or null",
      "atmosphere": "string — 1-2 sentences"
    }}
  ],
  "locations": [
    {{
      "id": "snake_case",
      "name": "string",
      "district": "district id",
      "type": "one of {loc_types}",
      "faction_owner": "faction name or null",
      "description_hint": "string — 1 sentence",
      "danger_level": 1-5,
      "heat_lock_threshold": 0-100,
      "rep_lock_threshold": -100,
      "services": ["list from {svc_types}"]
    }}
  ],
  "npcs": [
    {{
      "id": "snake_case",
      "name": "string",
      "faction": "faction name or null",
      "disposition": "one of {dispositions}",
      "location_id": "location id",
      "background_hint": "string — 1 sentence",
      "min_rep_to_talk": -100,
      "is_quest_giver": true/false
    }}
  ],
  "routes": [
    {{
      "src": "location_id",
      "dst": "location_id",
      "travel_time": 1-4,
      "danger": 1-5,
      "bidirectional": true
    }}
  ],
  "events": [
    {{
      "id": "snake_case",
      "title": "string",
      "description": "string — 1 sentence",
      "affected_factions": ["faction name"]
    }}
  ],
  "seed_quests": [
    {{
      "title": "string",
      "description": "string — 2 sentences",
      "tags": ["string"],
      "giver_faction": "faction name or null",
      "giver_npc_id": "npc id or null",
      "reward_creds": 100-800,
      "reward_rep":  {{"faction_name": integer}},
      "reward_heat": {{"faction_name": integer}},
      "beats": [
        {{
          "id": "b1",
          "title": "string",
          "type": "one of {beat_types}",
          "narration": "string — 2-3 sentences",
          "objective": "string — 1 sentence",
          "is_terminal": false,
          "terminal_status": null,
          "choices": [
            {{
              "index": 1,
              "label": "string",
              "required_stat": "one of {stats} or null",
              "required_stat_value": 0,
              "next_beat_id": "b2",
              "heat_delta": {{}},
              "rep_delta":  {{}},
              "health_delta": 0,
              "creds_delta": 0,
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
  ]
}}

Produce:
- 2-4 factions
- 3 roles thematically fitting "{theme}" (NOT Ghost/Blade/Wire unless theme is cyberpunk)
- 3-5 districts
- 8-12 locations (at least 1 per district, each role's start_location must exist)
- 5-9 NPCs
- 7-12 routes (all location ids must be valid)
- 1-2 global events
- 2-3 seed quests

Return ONLY the JSON object.
"""


def _call_llm(inputs: dict) -> Optional[dict]:
    factions_hint = (
        ", ".join(inputs["factions"]) if inputs["factions"]
        else "invent 2-4 factions that fit the theme"
    )
    prompt = _PROMPT.format(
        theme=inputs["theme"],
        city_name=inputs["city_name"],
        premise=inputs["premise"],
        factions_hint=factions_hint,
        tone=inputs["tone"],
        stats=", ".join(_STAT_NAMES),
        loc_types=", ".join(_LOC_TYPES),
        svc_types=", ".join(_SVC_TYPES),
        dispositions=", ".join(_DISPOSITIONS),
        beat_types=", ".join(_BEAT_TYPES),
    )

    console.print("[dim]⚙  Calling LLM — generating full world…[/dim]")
    raw = _call_ollama(prompt, expect_json=True)

    if raw.startswith("[LLM UNAVAILABLE"):
        console.print(f"[red]{raw}[/red]")
        return None

    cleaned = re.sub(r"^```(?:json)?", "", raw.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r"```$", "", cleaned.strip(), flags=re.MULTILINE).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        console.print(f"[red]JSON parse error: {exc}[/red]")
        console.print(f"[dim]{cleaned[:500]}…[/dim]")
        return None


# ══════════════════════════════════════════════════════════════════════════════
#  STEP 3 – Assemble WorldState from LLM JSON
# ══════════════════════════════════════════════════════════════════════════════

def _safe_loc_type(t: str) -> LocationType:
    try:    return LocationType(t)
    except: return LocationType.DISTRICT

def _safe_service(s: str) -> Optional[ServiceType]:
    try:    return ServiceType(s)
    except: return None

def _safe_disposition(d: str) -> NPCDisposition:
    try:    return NPCDisposition(d)
    except: return NPCDisposition.NEUTRAL

def _clamp(v, lo, hi):
    return max(lo, min(hi, int(v)))


def _assemble(data: dict, inputs: dict) -> tuple[WorldState, nx.DiGraph, list[QuestState]]:
    city_name  = data.get("city_name", inputs["city_name"])
    lore_intro = data.get("lore_intro", "A world waits.")

    # ── Factions ───────────────────────────────────────────────────────────
    faction_names: list[str] = [f["name"] for f in data.get("factions", []) if f.get("name")]
    if not faction_names:
        faction_names = inputs["factions"] or ["The Order", "The Outlaws"]

    faction_set = set(faction_names)

    def valid_faction(name) -> Optional[str]:
        """Return name if it's a known faction, else None."""
        return name if name in faction_set else None

    # ── Roles → ROLE_REGISTRY ──────────────────────────────────────────────
    ROLE_REGISTRY.clear()
    raw_roles = data.get("roles", [])
    for r in raw_roles:
        rid = r.get("id", "").strip().lower().replace(" ", "_")
        if not rid:
            continue
        raw_stats = r.get("stats", {})
        role_stats = Stats(
            strength     = _clamp(raw_stats.get("strength",     1), 1, 10),
            agility      = _clamp(raw_stats.get("agility",      1), 1, 10),
            vitality     = _clamp(raw_stats.get("vitality",     1), 1, 10),
            stealth      = _clamp(raw_stats.get("stealth",      1), 1, 10),
            persuasion   = _clamp(raw_stats.get("persuasion",   1), 1, 10),
            intelligence = _clamp(raw_stats.get("intelligence", 1), 1, 10),
        )
        # Only keep rep/heat for factions we actually have
        rep_raw  = {k: v for k, v in r.get("faction_rep", {}).items() if k in faction_set}
        heat_raw = {k: v for k, v in r.get("heat", {}).items()        if k in faction_set}

        ROLE_REGISTRY[rid] = RoleDef(
            id=rid,
            name=r.get("name", rid.capitalize()),
            description=r.get("description", ""),
            stats=role_stats,
            faction_rep=FactionRep.from_dict(rep_raw),
            heat=HeatLevel.from_dict(heat_raw),
            start_location=r.get("start_location", ""),
            start_creds=_clamp(r.get("start_creds", 500), 0, 9999),
        )

    # Fallback role if LLM produced nothing valid
    if not ROLE_REGISTRY:
        ROLE_REGISTRY["wanderer"] = RoleDef(
            id="wanderer", name="Wanderer",
            description="You carry nothing but a name and a past.",
            stats=Stats(strength=2, agility=2, vitality=2, stealth=2, persuasion=2, intelligence=2),
            start_creds=500,
        )

    # ── Districts ──────────────────────────────────────────────────────────
    districts: dict[str, District] = {}
    for d in data.get("districts", []):
        did = d.get("id", "").strip()
        if not did:
            continue
        districts[did] = District(
            id=did,
            name=d.get("name", did),
            faction_owner=valid_faction(d.get("faction_owner")),
            atmosphere=d.get("atmosphere", ""),
            sub_location_ids=[],
        )

    # ── Locations ──────────────────────────────────────────────────────────
    locations: dict[str, LocationNode] = {}
    for loc in data.get("locations", []):
        lid = loc.get("id", "").strip()
        if not lid:
            continue
        district = loc.get("district", "")
        services = [sv for s in loc.get("services", [])
                    if (sv := _safe_service(s)) is not None]
        locations[lid] = LocationNode(
            id=lid,
            name=loc.get("name", lid),
            district=district,
            type=_safe_loc_type(loc.get("type", "district")),
            faction_owner=valid_faction(loc.get("faction_owner")),
            description_hint=loc.get("description_hint", ""),
            danger_level=_clamp(loc.get("danger_level", 2), 1, 5),
            heat_lock_threshold=_clamp(loc.get("heat_lock_threshold", 100), 0, 100),
            rep_lock_threshold=_clamp(loc.get("rep_lock_threshold", -100), -100, 100),
            services=services,
            resident_npc_ids=[],
        )
        if district in districts:
            prev = districts[district].sub_location_ids
            districts[district] = districts[district].model_copy(
                update={"sub_location_ids": prev + [lid]}
            )

    # Make sure every role has a valid start_location
    all_loc_ids = set(locations.keys())
    first_loc = next(iter(all_loc_ids), "")
    for rid, rdef in ROLE_REGISTRY.items():
        if rdef.start_location not in all_loc_ids:
            ROLE_REGISTRY[rid] = rdef.model_copy(update={"start_location": first_loc})

    # ── NPCs ───────────────────────────────────────────────────────────────
    npcs: dict[str, NPC] = {}
    for npc in data.get("npcs", []):
        nid = npc.get("id", "").strip()
        if not nid:
            continue
        loc_id = npc.get("location_id", "")
        if loc_id not in all_loc_ids:
            continue   # skip NPCs whose location doesn't exist

        disp = _safe_disposition(npc.get("disposition", "neutral"))
        if npc.get("is_quest_giver") and disp != NPCDisposition.QUEST_GIVER:
            disp = NPCDisposition.QUEST_GIVER

        npcs[nid] = NPC(
            id=nid,
            name=npc.get("name", nid),
            faction=valid_faction(npc.get("faction")),
            disposition=disp,
            location_id=loc_id,
            background_hint=npc.get("background_hint", ""),
            min_rep_to_talk=_clamp(npc.get("min_rep_to_talk", -100), -100, 100),
        )
        prev = locations[loc_id].resident_npc_ids
        locations[loc_id] = locations[loc_id].model_copy(
            update={"resident_npc_ids": prev + [nid]}
        )

    # ── Global events ──────────────────────────────────────────────────────
    events: list[GlobalEvent] = []
    for i, ev in enumerate(data.get("events", [])):
        events.append(GlobalEvent(
            id=ev.get("id", f"ev_{i}"),
            title=ev.get("title", "Unknown Event"),
            description=ev.get("description", ""),
            turn_triggered=0,
            affected_factions=[f for f in ev.get("affected_factions", []) if f in faction_set],
        ))

    # ── WorldState ─────────────────────────────────────────────────────────
    world = WorldState(
        city_name=city_name,
        theme=inputs["theme"],
        tone=inputs["tone"],
        lore_intro=lore_intro,
        factions=faction_names,
        locations=locations,
        districts=districts,
        npcs=npcs,
        global_events=events,
    )

    # ── City graph ─────────────────────────────────────────────────────────
    G = build_city_graph(world)
    seen_pairs: set[tuple[str, str]] = set()
    for route in data.get("routes", []):
        src = route.get("src", "")
        dst = route.get("dst", "")
        if src not in all_loc_ids or dst not in all_loc_ids or src == dst:
            continue
        pair = (min(src, dst), max(src, dst))
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)
        add_route(G, src, dst,
                  travel_time=_clamp(route.get("travel_time", 2), 1, 10),
                  danger=_clamp(route.get("danger", 2), 1, 5),
                  bidirectional=bool(route.get("bidirectional", True)))

    # ── Seed quests ────────────────────────────────────────────────────────
    seed_quests: list[QuestState] = []
    for qdata in data.get("seed_quests", []):
        try:
            gqd = GeneratedQuestData(**qdata)
            qid = f"sq_{uuid.uuid4().hex[:8]}"
            qs  = gqd.to_quest_state(qid)
            QUEST_REGISTRY[qid] = qs
            seed_quests.append(qs)
        except Exception as exc:
            console.print(f"[yellow]Skipped a seed quest: {exc}[/yellow]")

    return world, G, seed_quests


# ══════════════════════════════════════════════════════════════════════════════
#  STEP 4 – Fallback world
# ══════════════════════════════════════════════════════════════════════════════

def _fallback(inputs: dict) -> tuple[WorldState, nx.DiGraph, list[QuestState]]:
    console.print("[yellow]⚠  Using minimal fallback world.[/yellow]")
    ROLE_REGISTRY.clear()
    ROLE_REGISTRY["wanderer"] = RoleDef(
        id="wanderer", name="Wanderer",
        description="You carry nothing but a name and a past.",
        stats=Stats(hacking=2, combat=2, stealth=2, persuasion=2, street_cred=2),
        start_location="hub_inn",
        start_creds=500,
    )

    districts = {"hub": District(id="hub", name="The Hub",
                                 atmosphere="The last safe place in a dangerous world.",
                                 sub_location_ids=["hub_inn", "hub_market"])}
    locations = {
        "hub_inn": LocationNode(
            id="hub_inn", name="The Inn", district="hub",
            type=LocationType.HIDEOUT, danger_level=1,
            description_hint="Warm light and whispered deals.",
            services=[ServiceType.QUEST_GIVER, ServiceType.SAFE_HOUSE],
            resident_npc_ids=["npc_keeper"],
        ),
        "hub_market": LocationNode(
            id="hub_market", name="The Market", district="hub",
            type=LocationType.MARKET, danger_level=2,
            description_hint="Traders, rogues, and rumours.",
            services=[ServiceType.WEAPON_DEALER, ServiceType.FENCE],
        ),
    }
    npcs = {"npc_keeper": NPC(
        id="npc_keeper", name="The Keeper",
        disposition=NPCDisposition.QUEST_GIVER, location_id="hub_inn",
        background_hint="Knows everything. Trusts no one. Has work for the willing.",
    )}
    world = WorldState(
        city_name=inputs["city_name"], theme=inputs["theme"], tone=inputs["tone"],
        lore_intro=f"Welcome to {inputs['city_name']}. The {inputs['theme']} era has left scars on every stone.",
        factions=["The Order", "The Outlaws"],
        locations=locations, districts=districts, npcs=npcs,
    )
    G = build_city_graph(world)
    add_route(G, "hub_inn", "hub_market", travel_time=1, danger=1)
    return world, G, []


# ══════════════════════════════════════════════════════════════════════════════
#  PUBLIC ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def generate_world_from_prompt() -> tuple[WorldState, nx.DiGraph, list[QuestState]]:
    """
    Full pipeline: collect inputs → call LLM → assemble world.
    ROLE_REGISTRY is populated as a side-effect.
    Returns (world, G, seed_quests).
    """
    inputs = _collect_inputs()
    data   = _call_llm(inputs)

    if not data:
        return _fallback(inputs)

    try:
        world, G, seed_quests = _assemble(data, inputs)
    except Exception as exc:
        console.print(f"[red]Assembly error: {exc}[/red]")
        return _fallback(inputs)

    if not world.locations:
        console.print("[red]No locations generated — falling back.[/red]")
        return _fallback(inputs)

    console.print(
        f"[bold green]✔  '{world.city_name}' ready:[/bold green] "
        f"{len(world.factions)} factions · {len(ROLE_REGISTRY)} roles · "
        f"{len(world.locations)} locations · {len(world.npcs)} NPCs · "
        f"{len(seed_quests)} seed quests"
    )
    return world, G, seed_quests