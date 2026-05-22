from __future__ import annotations

from dataclasses import dataclass
import random

from .attributes import PlayerAttributes
from .character import Character
from .pokemon import OwnedPokemon, PokemonSpecies, create_owned_pokemon
from .progression import grant_pokemon_xp
from .utils import clamp


TYPE_RELATIONS: dict[str, dict[str, float]] = {
    "Fire": {"Grass": 1.35, "Bug": 1.35, "Ice": 1.35, "Water": 0.65, "Rock": 0.65},
    "Water": {"Fire": 1.35, "Rock": 1.35, "Ground": 1.35, "Grass": 0.65, "Dragon": 0.85},
    "Grass": {"Water": 1.35, "Rock": 1.35, "Ground": 1.35, "Fire": 0.65, "Poison": 0.85},
    "Electric": {"Water": 1.35, "Flying": 1.35, "Ground": 0.40, "Grass": 0.85},
    "Rock": {"Fire": 1.35, "Flying": 1.35, "Bug": 1.35, "Water": 0.85, "Grass": 0.85},
    "Ground": {"Electric": 1.35, "Poison": 1.35, "Rock": 1.35, "Fire": 1.15, "Flying": 0.40},
    "Psychic": {"Fighting": 1.35, "Poison": 1.35, "Psychic": 0.85},
    "Ghost": {"Psychic": 1.35, "Normal": 0.40},
    "Ice": {"Dragon": 1.35, "Flying": 1.35, "Grass": 1.35, "Ground": 1.35, "Fire": 0.65},
    "Fighting": {"Normal": 1.35, "Rock": 1.35, "Ghost": 0.40, "Psychic": 0.65},
    "Poison": {"Grass": 1.35, "Ground": 0.85, "Psychic": 0.65},
    "Dragon": {"Dragon": 1.35, "Ice": 0.85},
}

CONDITION_FACTORS = {
    "healthy": 1.00,
    "tired": 0.90,
    "injured": 0.75,
    "badly_injured": 0.55,
    "sick": 0.70,
    "inspired": 1.10,
}


@dataclass
class BattleResult:
    winner: str
    loser: str
    player_score: float
    enemy_score: float
    win_chance: float
    result_text: str
    xp_gain: int
    health_loss: int

    def to_dict(self) -> dict:
        return {
            "winner": self.winner,
            "loser": self.loser,
            "player_score": round(self.player_score, 2),
            "enemy_score": round(self.enemy_score, 2),
            "win_chance": round(self.win_chance, 4),
            "result_text": self.result_text,
            "xp_gain": self.xp_gain,
            "health_loss": self.health_loss,
        }


def calculate_trainer_bonus(attributes: PlayerAttributes) -> float:
    return attributes.MEN * 0.35 + attributes.POK * 0.45 + attributes.LUK * 0.20


def calculate_base_power(pokemon: OwnedPokemon, trainer_bonus: float) -> float:
    # battle_level: experiência acumulada em combate — influente mas não dominante.
    # +0.10 por ponto (cap +7). Dois Pokémon idênticos: o maior battle_level vence.
    battle_exp = min(getattr(pokemon, "battle_level", 0) * 0.10, 7.0)
    return (
        pokemon.combat * 0.50
        + pokemon.healthy * 0.25
        + pokemon.occult * 0.15
        + pokemon.beauty * 0.05
        + trainer_bonus * 0.05
        + battle_exp
    )


def get_type_factor(attacker_types: list[str], defender_types: list[str]) -> float:
    best = 1.0
    worst = 1.0
    for attacker_type in attacker_types:
        relations = TYPE_RELATIONS.get(attacker_type, {})
        for defender_type in defender_types:
            factor = relations.get(defender_type, 1.0)
            best = max(best, factor)
            worst = min(worst, factor)
    if best >= 1.35:
        return 1.35
    if best >= 1.15:
        return 1.15
    if worst <= 0.40:
        return 0.40
    if worst <= 0.65:
        return 0.65
    if worst <= 0.85:
        return 0.85
    return 1.0


def get_ability_factor(pokemon: OwnedPokemon, opponent: OwnedPokemon) -> float:
    return 1.0


def get_condition_factor(pokemon: OwnedPokemon) -> float:
    return CONDITION_FACTORS.get(pokemon.status, 1.0)


def calculate_battle_score(
    pokemon: OwnedPokemon,
    opponent: OwnedPokemon,
    trainer_bonus: float,
    trainer_luck: int = 50,
) -> float:
    base_power = calculate_base_power(pokemon, trainer_bonus)
    # level_factor: peso maior para o nível — diferença de 18 níveis ≈ +55% de score
    level_factor = 1 + (pokemon.level / 20)
    type_factor = get_type_factor(pokemon.types, opponent.types)
    ability_factor = get_ability_factor(pokemon, opponent)
    condition_factor = get_condition_factor(pokemon)
    luck_bonus = (trainer_luck - 50) / 1000
    random_factor = random.uniform(0.92 + luck_bonus, 1.08 + luck_bonus)
    return base_power * level_factor * type_factor * ability_factor * condition_factor * random_factor


def resolve_auto_battle(
    player_pokemon: OwnedPokemon,
    enemy_pokemon: OwnedPokemon,
    player_attributes: PlayerAttributes,
    enemy_trainer_bonus: float = 45.0,
    enemy_luck: int = 50,
) -> BattleResult:
    player_bonus = calculate_trainer_bonus(player_attributes)
    player_score = calculate_battle_score(player_pokemon, enemy_pokemon, player_bonus, player_attributes.LUK)
    enemy_score = calculate_battle_score(enemy_pokemon, player_pokemon, enemy_trainer_bonus, enemy_luck)
    win_chance = player_score / max(0.01, player_score + enemy_score)
    win_chance = clamp(win_chance, 0.05, 0.95)
    player_won = random.random() <= win_chance
    xp_gain = _suggest_xp_gain(enemy_pokemon.level, player_won)
    health_loss = _suggest_health_loss(player_won, win_chance, enemy_score, player_score)

    if player_won:
        winner = player_pokemon.display_name()
        loser = enemy_pokemon.display_name()
        text = f"{winner} venceu {loser} com {win_chance * 100:.1f}% de chance estimada."
    else:
        winner = enemy_pokemon.display_name()
        loser = player_pokemon.display_name()
        text = f"{loser} perdeu para {winner}. A chance estimada era {win_chance * 100:.1f}%."

    return BattleResult(
        winner=winner,
        loser=loser,
        player_score=player_score,
        enemy_score=enemy_score,
        win_chance=win_chance,
        result_text=text,
        xp_gain=xp_gain,
        health_loss=health_loss,
    )


def simulate_simple_battle(
    character: Character,
    player_pokemon: OwnedPokemon,
    player_species: PokemonSpecies,
    opponent_name: str,
    opponent_species: PokemonSpecies,
    opponent_level: int,
    important: bool = False,
    species_by_name: dict[str, PokemonSpecies] | None = None,
) -> tuple[bool, list[str]]:
    if not player_pokemon.types:
        player_pokemon.types = list(player_species.types)
    enemy = create_owned_pokemon(opponent_species, level=opponent_level, origin="encontro selvagem")
    enemy.nickname = opponent_name
    result = resolve_auto_battle(player_pokemon, enemy, character.attributes)
    if important:
        result.xp_gain = int(result.xp_gain * 1.25)
    player_won = result.winner == player_pokemon.display_name()
    player_pokemon.current_health = max(0, player_pokemon.current_health - result.health_loss)
    level_notes = grant_pokemon_xp(player_pokemon, result.xp_gain, species_by_name or {player_species.name: player_species})
    if player_won:
        player_pokemon.bond = int(clamp(player_pokemon.bond + 2, 0, 100))
        if important:
            character.add_history(f"Voce venceu uma batalha importante contra {opponent_name}.")
    else:
        character.health = int(clamp(character.health - 3, 0, 100))
        if important:
            character.add_history(f"Voce perdeu uma batalha importante contra {opponent_name}.")

    log = [
        f"BATALHA|{player_pokemon.display_name()}|{opponent_name}|{result.win_chance * 100:.0f}|{'win' if player_won else 'loss'}|{result.player_score:.1f}|{result.enemy_score:.1f}|{result.xp_gain}|{result.health_loss}",
    ]
    log.extend(level_notes)
    return player_won, log


def _suggest_health_loss(player_won: bool, win_chance: float, enemy_score: float, player_score: float) -> int:
    pressure = enemy_score / max(1.0, player_score + enemy_score)
    if player_won:
        return int(clamp(5 + pressure * 25, 1, 35))
    return int(clamp(18 + (1 - win_chance) * 35, 10, 60))


def _suggest_xp_gain(enemy_level: int, player_won: bool) -> int:
    if player_won:
        return max(18, 12 + enemy_level * 5)
    return max(6, 4 + enemy_level * 2)
