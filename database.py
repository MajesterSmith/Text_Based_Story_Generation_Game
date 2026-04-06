import sqlite3
import json
import os
import uuid
from typing import Optional, List, Dict, Tuple
from dotenv import load_dotenv

# Import our models
from models import (
    WorldState, LocationNode, LocationType, ServiceType,
    District, NPC, NPCDisposition,
    PlayerState, Stats, FactionRep, HeatLevel,
    QuestState, QuestStatus, QuestBeat, BeatType, BeatChoice, Item
)

load_dotenv()

class DatabaseManager:
    def __init__(self, db_url: Optional[str] = None):
        self.db_url = db_url or os.getenv("DATABASE_URL", "game.sqlite")
        self._init_db()

    def _get_connection(self):
        return sqlite3.connect(self.db_url)

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # --- Worlds Table ---
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS worlds (
                    id TEXT PRIMARY KEY,
                    city_name TEXT,
                    theme TEXT,
                    tone TEXT,
                    lore_intro TEXT,
                    turn_count INTEGER,
                    is_generated BOOLEAN
                )
            ''')
            
            # --- Factions Table ---
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS factions (
                    world_id TEXT,
                    name TEXT,
                    FOREIGN KEY(world_id) REFERENCES worlds(id) ON DELETE CASCADE
                )
            ''')
            
            # --- Districts Table ---
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS districts (
                    id TEXT,
                    world_id TEXT,
                    name TEXT,
                    faction_owner TEXT,
                    atmosphere TEXT,
                    PRIMARY KEY(id, world_id),
                    FOREIGN KEY(world_id) REFERENCES worlds(id) ON DELETE CASCADE
                )
            ''')
            
            # --- Locations Table ---
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS locations (
                    id TEXT,
                    world_id TEXT,
                    name TEXT,
                    district_id TEXT,
                    type TEXT,
                    faction_owner TEXT,
                    description_hint TEXT,
                    danger_level INTEGER,
                    heat_lock_threshold INTEGER,
                    rep_lock_threshold INTEGER,
                    services_json TEXT,
                    PRIMARY KEY(id, world_id),
                    FOREIGN KEY(world_id) REFERENCES worlds(id) ON DELETE CASCADE
                )
            ''')
            
            # --- NPCs Table ---
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS npcs (
                    id TEXT,
                    world_id TEXT,
                    name TEXT,
                    faction TEXT,
                    disposition TEXT,
                    location_id TEXT,
                    background_hint TEXT,
                    min_rep_to_talk INTEGER,
                    is_quest_giver BOOLEAN,
                    PRIMARY KEY(id, world_id),
                    FOREIGN KEY(world_id) REFERENCES worlds(id) ON DELETE CASCADE
                )
            ''')
            
            # --- Player state Table ---
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS player_state (
                    world_id TEXT PRIMARY KEY,
                    name TEXT,
                    role TEXT,
                    current_location TEXT,
                    creds INTEGER,
                    health INTEGER,
                    max_health INTEGER,
                    stats_json TEXT,
                    faction_rep_json TEXT,
                    heat_json TEXT,
                    turn_count INTEGER,
                    is_alive BOOLEAN,
                    FOREIGN KEY(world_id) REFERENCES worlds(id) ON DELETE CASCADE
                )
            ''')
            
            # --- Quests Table ---
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS quests (
                    id TEXT,
                    world_id TEXT,
                    title TEXT,
                    description TEXT,
                    status TEXT,
                    giver_npc_id TEXT,
                    reward_creds INTEGER,
                    reward_rep_json TEXT,
                    reward_heat_json TEXT,
                    initial_value INTEGER,
                    hidden_counter INTEGER,
                    win_threshold INTEGER,
                    current_beat_id TEXT,
                    history_json TEXT,
                    tags_json TEXT,
                    turn_accepted INTEGER,
                    turn_completed INTEGER,
                    PRIMARY KEY(id, world_id),
                    FOREIGN KEY(world_id) REFERENCES worlds(id) ON DELETE CASCADE
                )
            ''')
            
            # --- Quest Beats Table ---
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS quest_beats (
                    id TEXT,
                    quest_id TEXT,
                    world_id TEXT,
                    title TEXT,
                    type TEXT,
                    narration TEXT,
                    objective TEXT,
                    is_terminal BOOLEAN,
                    terminal_status TEXT,
                    choices_json TEXT,
                    on_enter_heat_delta_json TEXT,
                    on_enter_rep_delta_json TEXT,
                    PRIMARY KEY(id, quest_id, world_id),
                    FOREIGN KEY(quest_id, world_id) REFERENCES quests(id, world_id) ON DELETE CASCADE
                )
            ''')
            
            conn.commit()

    def save_world(self, world: WorldState, is_generated: bool):
        # We always overwrite worlds with the same city_name or use a unique ID for generated ones
        # Actually Neon City can just be "neon_city" as id
        world_id = "neon_city" if not is_generated else world.city_name.lower().replace(" ", "_")
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Wipe previous data for this world_id
            cursor.execute("DELETE FROM worlds WHERE id = ?", (world_id,))
            
            # Save world metadata
            cursor.execute('''
                INSERT INTO worlds (id, city_name, theme, tone, lore_intro, turn_count, is_generated)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (world_id, world.city_name, world.theme, world.tone, world.lore_intro, world.turn_count, is_generated))
            
            # Save factions
            for faction_name in world.factions:
                cursor.execute("INSERT INTO factions (world_id, name) VALUES (?, ?)", (world_id, faction_name))
            
            # Save districts
            for district in world.districts.values():
                cursor.execute('''
                    INSERT INTO districts (id, world_id, name, faction_owner, atmosphere)
                    VALUES (?, ?, ?, ?, ?)
                ''', (district.id, world_id, district.name, district.faction_owner, district.atmosphere))
            
            # Save locations
            for loc in world.locations.values():
                cursor.execute('''
                    INSERT INTO locations (id, world_id, name, district_id, type, faction_owner, description_hint, danger_level, heat_lock_threshold, rep_lock_threshold, services_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (loc.id, world_id, loc.name, loc.district, loc.type.value, loc.faction_owner, loc.description_hint, loc.danger_level, loc.heat_lock_threshold, loc.rep_lock_threshold, json.dumps([s.value for s in loc.services])))
            
            # Save NPCs
            for npc in world.npcs.values():
                cursor.execute('''
                    INSERT INTO npcs (id, world_id, name, faction, disposition, location_id, background_hint, min_rep_to_talk, is_quest_giver)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (npc.id, world_id, npc.name, npc.faction, npc.disposition.value, npc.location_id, npc.background_hint, npc.min_rep_to_talk, npc.disposition == NPCDisposition.QUEST_GIVER))
            
            conn.commit()
            return world_id

    def save_player(self, world_id: str, player: PlayerState):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM player_state WHERE world_id = ?", (world_id,))
            cursor.execute('''
                INSERT INTO player_state (world_id, name, role, current_location, creds, health, max_health, stats_json, faction_rep_json, heat_json, turn_count, is_alive)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (world_id, player.name, player.role, player.current_location, player.creds, player.health, player.max_health, player.stats.model_dump_json(), player.faction_rep.model_dump_json(), player.heat.model_dump_json(), player.turn_count, player.is_alive))
            conn.commit()

    def save_quest(self, world_id: str, quest: QuestState):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM quest_beats WHERE quest_id = ? AND world_id = ?", (quest.id, world_id))
            cursor.execute("DELETE FROM quests WHERE id = ? AND world_id = ?", (quest.id, world_id))
            
            cursor.execute('''
                INSERT INTO quests (id, world_id, title, description, status, giver_npc_id, reward_creds, reward_rep_json, reward_heat_json, initial_value, hidden_counter, win_threshold, current_beat_id, history_json, tags_json, turn_accepted, turn_completed)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (quest.id, world_id, quest.title, quest.description, quest.status.value, quest.giver_npc_id, quest.reward_creds, json.dumps(quest.reward_rep), json.dumps(quest.reward_heat), quest.initial_value, quest.hidden_counter, quest.win_threshold, quest.current_beat_id, json.dumps(quest.history), json.dumps(quest.tags), quest.turn_accepted, quest.turn_completed))
            
            for beat in quest.beats.values():
                cursor.execute('''
                    INSERT INTO quest_beats (id, quest_id, world_id, title, type, narration, objective, is_terminal, terminal_status, choices_json, on_enter_heat_delta_json, on_enter_rep_delta_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (beat.id, quest.id, world_id, beat.title, beat.type.value, beat.narration, beat.objective, beat.is_terminal, beat.terminal_status.value if beat.terminal_status else None, json.dumps([c.model_dump() for c in beat.choices]), json.dumps(beat.on_enter_heat_delta), json.dumps(beat.on_enter_rep_delta)))
            
            conn.commit()

    def delete_world_data(self, world_id: str):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM worlds WHERE id = ?", (world_id,))
            conn.commit()

    def get_all_world_ids(self) -> List[Tuple[str, bool]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, is_generated FROM worlds")
            return cursor.fetchall()
