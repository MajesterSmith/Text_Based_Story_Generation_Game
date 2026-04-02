"""
data/seed.py
────────────────────────────────────────────────────────────────────────────
Hard-coded Neon City world.  Now uses plain strings for faction names and
registers three RoleDefs (Ghost / Blade / Wire) into ROLE_REGISTRY.
"""
from __future__ import annotations
import networkx as nx

from models import (
    WorldState, LocationNode, LocationType, ServiceType,
    District, NPC, NPCDisposition,
    RoleDef, ROLE_REGISTRY,
    Stats, FactionRep, HeatLevel,
)
from graphs.city import build_city_graph, add_route

# ── Faction name constants (plain strings, no Enum needed) ─────────────────
NEXUS_CORP       = "Nexus Corporation"
IRON_VEIL        = "Iron Veil Gang"
PORT_AUTHORITY   = "Port Authority"
GHOST_COLLECTIVE = "Ghost Collective"
FIXERS_GUILD     = "Fixers Guild"

NEON_FACTIONS = [NEXUS_CORP, IRON_VEIL, PORT_AUTHORITY, GHOST_COLLECTIVE, FIXERS_GUILD]


def _register_neon_roles() -> None:
    """Populate ROLE_REGISTRY with the three classic Neon City archetypes."""
    ROLE_REGISTRY.clear()

    ROLE_REGISTRY["ghost"] = RoleDef(
        id="ghost", name="Ghost",
        description="A ghost in the machine. You live in the shadows of the net.",
        stats=Stats(hacking=4, combat=1, stealth=3, persuasion=2, street_cred=1),
        faction_rep=FactionRep.from_dict({GHOST_COLLECTIVE: 30, NEXUS_CORP: -20}),
        heat=HeatLevel.from_dict({NEXUS_CORP: 15}),
        start_location="glitch_data_den",
        start_creds=500,
    )

    ROLE_REGISTRY["blade"] = RoleDef(
        id="blade", name="Blade",
        description="Steel nerves, sharper blade. The streets know your name.",
        stats=Stats(hacking=1, combat=4, stealth=2, persuasion=1, street_cred=3),
        faction_rep=FactionRep.from_dict({IRON_VEIL: 20, PORT_AUTHORITY: -10}),
        heat=HeatLevel.from_dict({PORT_AUTHORITY: 10}),
        start_location="underbelly_rust_bar",
        start_creds=300,
    )

    ROLE_REGISTRY["wire"] = RoleDef(
        id="wire", name="Wire",
        description="Information is currency. You deal in both.",
        stats=Stats(hacking=2, combat=1, stealth=1, persuasion=4, street_cred=3),
        faction_rep=FactionRep.from_dict({FIXERS_GUILD: 40}),
        heat=HeatLevel(),
        start_location="midtown_fixers_den",
        start_creds=800,
    )


def build_world() -> tuple[WorldState, nx.DiGraph]:
    """Build the classic Neon City world and register its roles."""
    _register_neon_roles()

    # ── Districts ──────────────────────────────────────────────────────────
    districts = {
        "spire": District(
            id="spire", name="The Spire",
            faction_owner=NEXUS_CORP,
            atmosphere="Gleaming towers of chrome and glass. Corp enforcers patrol every corner.",
            sub_location_ids=["spire_nexus_hq", "spire_sky_lounge"],
        ),
        "midtown": District(
            id="midtown", name="Midtown Grid",
            atmosphere="Neon-soaked streets buzzing with fixers, merchants and neutral ground deals.",
            sub_location_ids=["midtown_fixers_den", "midtown_black_market"],
        ),
        "underbelly": District(
            id="underbelly", name="The Underbelly",
            faction_owner=IRON_VEIL,
            atmosphere="Corroded pipes, flickering lights, the smell of synth-smoke and old blood.",
            sub_location_ids=["underbelly_rust_bar", "underbelly_chop_shop"],
        ),
        "port_sigma": District(
            id="port_sigma", name="Port Sigma",
            faction_owner=PORT_AUTHORITY,
            atmosphere="Industrial docks, smuggler freight, the hum of off-world shuttles.",
            sub_location_ids=["port_docking_bay", "port_customs"],
        ),
        "glitch": District(
            id="glitch", name="The Glitch",
            faction_owner=GHOST_COLLECTIVE,
            atmosphere="Abandoned sector. Rogue AIs flicker through dead terminals. Silence is loud here.",
            sub_location_ids=["glitch_data_den", "glitch_ruins"],
        ),
    }

    # ── Locations ──────────────────────────────────────────────────────────
    locations = {
        "spire_nexus_hq": LocationNode(
            id="spire_nexus_hq", name="Nexus Corp HQ", district="spire",
            type=LocationType.CORP_OFFICE, faction_owner=NEXUS_CORP,
            description_hint="Sterile white corridors. Surveillance everywhere. Power radiates from every surface.",
            danger_level=4, heat_lock_threshold=30, rep_lock_threshold=20,
            services=[ServiceType.QUEST_GIVER],
            resident_npc_ids=["npc_director_vale"],
        ),
        "spire_sky_lounge": LocationNode(
            id="spire_sky_lounge", name="Sky Lounge 7", district="spire",
            type=LocationType.BAR, faction_owner=NEXUS_CORP,
            description_hint="High-altitude bar for corp elites. Perfect views, perfect lies.",
            danger_level=2, heat_lock_threshold=50,
            services=[ServiceType.INFO_BROKER, ServiceType.QUEST_GIVER],
            resident_npc_ids=["npc_rena_cross"],
        ),
        "midtown_fixers_den": LocationNode(
            id="midtown_fixers_den", name="The Fixers Den", district="midtown",
            type=LocationType.HIDEOUT,
            description_hint="Smoke-filled back room. Maps, contracts, and whispered deals.",
            danger_level=1,
            services=[ServiceType.QUEST_GIVER, ServiceType.INFO_BROKER, ServiceType.SAFE_HOUSE],
            resident_npc_ids=["npc_fixer_marek"],
        ),
        "midtown_black_market": LocationNode(
            id="midtown_black_market", name="The Black Market", district="midtown",
            type=LocationType.MARKET,
            description_hint="Stalls crammed with stolen tech, black-market implants and grey-market weapons.",
            danger_level=2,
            services=[ServiceType.WEAPON_DEALER, ServiceType.CYBERDOC, ServiceType.FENCE],
            resident_npc_ids=["npc_vendor_sike"],
        ),
        "underbelly_rust_bar": LocationNode(
            id="underbelly_rust_bar", name="The Rust Bar", district="underbelly",
            type=LocationType.BAR, faction_owner=IRON_VEIL,
            description_hint="Iron Veil territory. Every face is a scar. Every scar has a story.",
            danger_level=3, heat_lock_threshold=75,
            services=[ServiceType.QUEST_GIVER, ServiceType.MEDIC],
            resident_npc_ids=["npc_iron_vex"],
        ),
        "underbelly_chop_shop": LocationNode(
            id="underbelly_chop_shop", name="Chop Shop", district="underbelly",
            type=LocationType.MARKET, faction_owner=IRON_VEIL,
            description_hint="Strip a body, sell the parts. No questions asked.",
            danger_level=3, heat_lock_threshold=60,
            services=[ServiceType.CYBERDOC, ServiceType.FENCE],
        ),
        "port_docking_bay": LocationNode(
            id="port_docking_bay", name="Docking Bay 9", district="port_sigma",
            type=LocationType.PORT, faction_owner=PORT_AUTHORITY,
            description_hint="Cargo loaders and smugglers. The Port Authority turns a blind eye — for a price.",
            danger_level=2,
            services=[ServiceType.TRANSIT, ServiceType.QUEST_GIVER],
            resident_npc_ids=["npc_harbourmaster"],
        ),
        "port_customs": LocationNode(
            id="port_customs", name="Customs Office", district="port_sigma",
            type=LocationType.PRECINCT, faction_owner=PORT_AUTHORITY,
            description_hint="Officially, the law. Unofficially, the highest bidder.",
            danger_level=2, heat_lock_threshold=40,
            services=[ServiceType.INFO_BROKER],
        ),
        "glitch_data_den": LocationNode(
            id="glitch_data_den", name="The Data Den", district="glitch",
            type=LocationType.DATA_NEXUS, faction_owner=GHOST_COLLECTIVE,
            description_hint="Dead screens flicker with ghost signals. The Collective runs their ops from here.",
            danger_level=2,
            services=[ServiceType.INFO_BROKER, ServiceType.SAFE_HOUSE],
            resident_npc_ids=["npc_ghost_zero"],
        ),
        "glitch_ruins": LocationNode(
            id="glitch_ruins", name="The Ruins", district="glitch",
            type=LocationType.RUINS,
            description_hint="Collapsed towers. Rogue AI fragments haunt the dead network nodes.",
            danger_level=5,
            services=[],
        ),
    }

    # ── NPCs ───────────────────────────────────────────────────────────────
    npcs = {
        "npc_director_vale": NPC(
            id="npc_director_vale", name="Director Vale",
            faction=NEXUS_CORP, disposition=NPCDisposition.NEUTRAL,
            location_id="spire_nexus_hq",
            background_hint="Cold, calculating Nexus Corp director. Offers contracts that always cost more than they pay.",
            min_rep_to_talk=20,
        ),
        "npc_rena_cross": NPC(
            id="npc_rena_cross", name="Rena Cross",
            faction=NEXUS_CORP, disposition=NPCDisposition.INFORMANT,
            location_id="spire_sky_lounge",
            background_hint="Corp socialite who sells secrets with a smile. Her loyalty is to the highest bidder.",
        ),
        "npc_fixer_marek": NPC(
            id="npc_fixer_marek", name="Marek",
            faction=FIXERS_GUILD, disposition=NPCDisposition.QUEST_GIVER,
            location_id="midtown_fixers_den",
            background_hint="Veteran fixer. Seen everything twice. Respects results, despises excuses.",
        ),
        "npc_vendor_sike": NPC(
            id="npc_vendor_sike", name="Sike",
            disposition=NPCDisposition.VENDOR,
            location_id="midtown_black_market",
            background_hint="Wiry arms dealer with a nervous laugh and an inventory that shouldn't exist.",
        ),
        "npc_iron_vex": NPC(
            id="npc_iron_vex", name="Vex",
            faction=IRON_VEIL, disposition=NPCDisposition.QUEST_GIVER,
            location_id="underbelly_rust_bar",
            background_hint="Iron Veil enforcer. More augment than flesh. Tests everyone who walks in.",
            min_rep_to_talk=-40,
        ),
        "npc_harbourmaster": NPC(
            id="npc_harbourmaster", name="Harbourmaster Donn",
            faction=PORT_AUTHORITY, disposition=NPCDisposition.NEUTRAL,
            location_id="port_docking_bay",
            background_hint="Runs the docks with an iron ledger. Knows every ship, every cargo, every bribe.",
        ),
        "npc_ghost_zero": NPC(
            id="npc_ghost_zero", name="Zero",
            faction=GHOST_COLLECTIVE, disposition=NPCDisposition.FRIENDLY,
            location_id="glitch_data_den",
            background_hint="Ghost Collective's lead netrunner. Speaks in riddles, delivers in results.",
        ),
    }

    world = WorldState(
        city_name="Neon City",
        theme="cyberpunk",
        tone="gritty and morally ambiguous",
        lore_intro=(
            "Neon City never sleeps. Chrome towers scrape a sky choked with smog "
            "and satellite glare. Down in the grid, everyone's got an angle — "
            "and yours is just getting started."
        ),
        factions=NEON_FACTIONS,
        locations=locations,
        districts=districts,
        npcs=npcs,
    )

    G = build_city_graph(world)
    add_route(G, "midtown_fixers_den",  "midtown_black_market", travel_time=1, danger=1)
    add_route(G, "midtown_fixers_den",  "spire_sky_lounge",     travel_time=2, danger=2)
    add_route(G, "midtown_fixers_den",  "underbelly_rust_bar",  travel_time=2, danger=3)
    add_route(G, "midtown_fixers_den",  "port_docking_bay",     travel_time=2, danger=2)
    add_route(G, "midtown_fixers_den",  "glitch_data_den",      travel_time=3, danger=2)
    add_route(G, "spire_sky_lounge",    "spire_nexus_hq",       travel_time=1, danger=3)
    add_route(G, "underbelly_rust_bar", "underbelly_chop_shop", travel_time=1, danger=3)
    add_route(G, "port_docking_bay",    "port_customs",         travel_time=1, danger=2)
    add_route(G, "glitch_data_den",     "glitch_ruins",         travel_time=1, danger=5)

    return world, G