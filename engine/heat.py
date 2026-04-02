"""engine/heat.py — faction arguments are plain strings."""
from __future__ import annotations
from models import PlayerState

HEAT_THRESHOLDS = {
    "clean":          (0,  20),
    "suspicious":     (21, 50),
    "wanted":         (51, 75),
    "shoot_on_sight": (76, 100),
}


def apply_heat_event(player: PlayerState, faction: str,
                     amount: int, reason: str = "") -> tuple[PlayerState, str]:
    old = player.heat.get(faction)
    new_player = player.with_heat_raise(faction, amount)
    new = new_player.heat.get(faction)
    msg = f"[HEAT] {faction}: {old} → {new}"
    if reason:
        msg += f" ({reason})"
    return new_player, msg


def check_ambush(player: PlayerState, faction: str) -> bool:
    return player.heat.get(faction) > 75


def bribe_faction(player: PlayerState, faction: str,
                  creds_spent: int) -> tuple[PlayerState, str]:
    reduction = creds_spent // 10
    if player.creds < creds_spent:
        return player, "Not enough creds."
    new_player = player.with_creds(-creds_spent)
    old_heat   = new_player.heat.get(faction)
    new_heat_v = max(0, old_heat - reduction)
    delta      = new_heat_v - old_heat   # negative number
    new_player = new_player.model_copy(
        update={"heat": new_player.heat.raise_heat(faction, delta)}
    )
    return new_player, f"Paid {creds_spent} creds. {faction} heat: {old_heat} → {new_heat_v}"