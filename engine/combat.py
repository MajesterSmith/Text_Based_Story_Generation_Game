import random
from typing import List, Tuple, Optional
from models.player import PlayerState, Stats
from models.world import NPC

class Combatant:
    def __init__(self, name: str, stats: Stats, health: int, max_health: int, is_player: bool = False):
        self.name = name
        self.stats = stats
        self.health = health
        self.max_health = max_health
        self.is_player = is_player
        self.defending = False
        self.initiative = 0

    @classmethod
    def from_player(cls, player: PlayerState):
        return cls(
            name=player.name,
            stats=player.stats,
            health=player.health,
            max_health=player.max_health,
            is_player=True
        )

    @classmethod
    def from_npc(cls, npc: NPC, danger_level: int = 1):
        # If NPC doesn't have combat stats, generate them based on danger level
        stats = npc.combat_stats or cls.generate_enemy_stats(danger_level)
        max_hp = 50 + (stats.vitality * 8)
        return cls(
            name=npc.name,
            stats=stats,
            health=max_hp,
            max_health=max_hp,
            is_player=False
        )

    @staticmethod
    def generate_enemy_stats(danger_level: int) -> Stats:
        points = danger_level * 5
        base = random.randint(2, 4)
        # Distribute points randomly
        s = [base] * 6
        for _ in range(points):
            idx = random.randint(0, 5)
            if s[idx] < 10:
                s[idx] += 1
        
        return Stats(
            strength=s[0], agility=s[1], vitality=s[2],
            stealth=s[3], persuasion=s[4], intelligence=s[5]
        )

    def roll_initiative(self):
        self.initiative = self.stats.agility + random.randint(1, 10)
        return self.initiative

class CombatManager:
    def __init__(self, player: PlayerState, enemies: List[NPC], danger_level: int = 1):
        self.player_ref = player # Keep reference to update original object later
        self.player = Combatant.from_player(player)
        self.enemies = [Combatant.from_npc(e, danger_level) for e in enemies]
        self.turn_order: List[Combatant] = []
        self.log: List[str] = []
        self.active = True

    def start_combat(self):
        self.log.append(f"Combat started! {self.player.name} vs {', '.join([e.name for e in self.enemies])}")
        self.refresh_initiative()

    def refresh_initiative(self):
        all_combatants = [self.player] + self.enemies
        for c in all_combatants:
            c.roll_initiative()
        self.turn_order = sorted(all_combatants, key=lambda x: x.initiative, reverse=True)

    def get_current_turn(self) -> Combatant:
        return self.turn_order[0]

    def next_turn(self):
        # Rotate turn order
        last = self.turn_order.pop(0)
        self.turn_order.append(last)
        # Reset defense for the person starting their turn
        self.turn_order[0].defending = False

    def execute_attack(self, attacker: Combatant, target: Combatant) -> str:
        # Damage formula: (Str + 1d6) - (Target Vit / 2)
        base_dmg = attacker.stats.strength + random.randint(1, 6)
        mitigation = target.stats.vitality // 2
        
        if target.defending:
            mitigation *= 2
            
        damage = max(1, base_dmg - mitigation)
        target.health -= damage
        
        msg = f"{attacker.name} attacks {target.name} for {damage} damage!"
        if target.health <= 0:
            target.health = 0
            msg += f" {target.name} has been defeated!"
            if not target.is_player:
                self.enemies = [e for e in self.enemies if e.health > 0]
                self.turn_order = [c for c in self.turn_order if c.health > 0]
        
        self.log.append(msg)
        return msg

    def execute_player_action(self, action: str, target_idx: int = 0) -> str:
        if action == "attack":
            if target_idx < len(self.enemies):
                return self.execute_attack(self.player, self.enemies[target_idx])
        elif action == "defend":
            self.player.defending = True
            msg = f"{self.player.name} takes a defensive stance."
            self.log.append(msg)
            return msg
        return "Invalid action."

    def execute_enemy_turns(self) -> List[str]:
        """Runs turns for all enemies until it's the player's turn again."""
        responses = []
        while self.enemies and not self.get_current_turn().is_player and self.player.health > 0:
            enemy = self.get_current_turn()
            res = self.execute_attack(enemy, self.player)
            responses.append(res)
            self.next_turn()
        return responses

    def check_victory(self) -> Optional[str]:
        if self.player.health <= 0:
            self.active = False
            return "defeat"
        if not self.enemies:
            self.active = False
            return "victory"
        return None

    def finalize_player_state(self) -> PlayerState:
        """Updates the original player state and applies growth."""
        new_state = self.player_ref.model_copy(update={"health": self.player.health})
        
        # Automatic growth if victorious
        if not self.enemies:
            # Pick two random stats to grow
            possible_stats = ["strength", "agility", "vitality", "stealth", "persuasion", "intelligence"]
            grows = random.sample(possible_stats, 2)
            for s in grows:
                gain = random.randint(1, 3)
                new_state = new_state.add_xp(s, gain)
                self.log.append(f"Stat Increased: {s.capitalize()} +{gain}")
        
        return new_state

    def run_combat(self) -> Tuple[Optional[PlayerState], str]:
        """Runs the entire combat interaction loop."""
        from ui.renderer import console, clear, print_player_bar, print_message, prompt_input, pick_int
        from rich.table import Table
        
        self.start_combat()
        
        while self.active:
            clear()
            print_player_bar(self.player_ref)
            
            # Show battle status
            table = Table(title="Combat Status")
            table.add_column("Combatant", style="cyan")
            table.add_column("Health", style="red")
            table.add_column("Initiative", style="yellow")
            
            table.add_row(f"{self.player.name} (YOU)", f"{self.player.health}/{self.player.max_health}", str(self.player.initiative))
            for e in self.enemies:
                table.add_row(e.name, f"{e.health}/{e.max_health}", str(e.initiative))
            console.print(table)

            # Show logs
            for log_msg in self.log[-5:]:
                console.print(f"[dim]» {log_msg}[/dim]")

            current = self.get_current_turn()
            if current.is_player:
                console.print("\n[bold green]YOUR TURN[/bold green]")
                console.print(f"1. Attack")
                console.print(f"2. Defend")
                action_idx = pick_int("> ", 1, 2)
                
                if action_idx == 1:
                    # Choose target
                    for i, e in enumerate(self.enemies):
                        console.print(f"{i+1}. {e.name} ({e.health} HP)")
                    target_idx = pick_int("Target: ", 1, len(self.enemies)) - 1
                    self.execute_player_action("attack", target_idx)
                else:
                    self.execute_player_action("defend")
            else:
                console.print(f"\n[bold red]{current.name}'s TURN[/bold red]")
                res = self.execute_attack(current, self.player)
                console.print(f"[bold red]{res}[/bold red]")
                prompt_input("Press Enter to continue...")

            self.next_turn()
            
            result = self.check_victory()
            if result:
                new_p = self.finalize_player_state()
                if result == "victory":
                    print_message("\n[bold green]VICTORY![/bold green]")
                else:
                    print_message("\n[bold red]DEFEATED![/bold red]")
                    return None, "defeat"
                
                prompt_input("Press Enter to end combat...")
                return new_p, "victory"
        
        return self.finalize_player_state(), "none"
