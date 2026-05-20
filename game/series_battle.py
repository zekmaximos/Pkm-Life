from __future__ import annotations

from dataclasses import dataclass, field
from copy import deepcopy

from .battle import calculate_trainer_bonus, get_type_factor, simulate_simple_battle
from .character import Character
from .pokemon import OwnedPokemon, PokemonSpecies, create_owned_pokemon
from .utils import clamp


@dataclass
class SeriesOpponent:
    trainer_name: str
    species: str
    level: int


@dataclass
class SeriesBattleResult:
    won: bool
    wins: int
    losses: int
    total: int
    log: list[str] = field(default_factory=list)


def estimate_matchup_chance(
    character: Character,
    pokemon: OwnedPokemon,
    opponent_species: PokemonSpecies,
    opponent_level: int,
    species_by_name: dict[str, PokemonSpecies],
) -> float:
    species = species_by_name.get(pokemon.species)
    if not species:
        return 0.05
    type_factor = get_type_factor(pokemon.types or species.types, opponent_species.types)
    health_factor = pokemon.health_percent(species)
    trainer_bonus = calculate_trainer_bonus(character.attributes)
    player_power = (
        pokemon.level * 2.2
        + pokemon.combat * 0.75
        + pokemon.healthy * 0.35
        + pokemon.occult * 0.18
        + trainer_bonus * 0.22
        + type_factor * 18
    ) * clamp(0.65 + health_factor * 0.45, 0.45, 1.15)
    enemy_power = opponent_level * 2.4 + opponent_species.base_combat * 0.75 + opponent_species.base_healthy * 0.35 + 45 * 0.22
    chance = 0.50 + (player_power - enemy_power) / 260
    chance += (character.attributes.LUK - 50) / 650
    return float(clamp(chance, 0.05, 0.95))


def estimate_series_chance(
    character: Character,
    opponents: list[SeriesOpponent],
    species_by_name: dict[str, PokemonSpecies],
    wins_required: int | None = None,
) -> dict:
    if not character.team or not opponents:
        return {"series_chance": 0, "average_match_chance": 0, "match_chances": [], "wins_required": wins_required or len(opponents)}
    wins_required = wins_required or len(opponents)
    available = [pokemon for pokemon in character.team if pokemon.current_health > 0]
    match_chances: list[float] = []
    for opponent in opponents:
        opponent_species = species_by_name.get(opponent.species)
        if not opponent_species:
            continue
        best = max(
            available,
            key=lambda pokemon: estimate_matchup_chance(character, pokemon, opponent_species, opponent.level, species_by_name),
        )
        match_chances.append(estimate_matchup_chance(character, best, opponent_species, opponent.level, species_by_name))
    if not match_chances:
        return {"series_chance": 0, "average_match_chance": 0, "match_chances": [], "wins_required": wins_required}
    # Conservative estimate: team series is harder than the average individual fight.
    average_match = sum(match_chances) / len(match_chances)
    pressure = wins_required / max(1, len(match_chances))
    series = average_match ** (0.65 + pressure * 0.85)
    if wins_required < len(match_chances):
        series += (1 - pressure) * 0.18
    return {
        "series_chance": int(clamp(round(series * 100), 5, 95)),
        "average_match_chance": int(clamp(round(average_match * 100), 5, 95)),
        "match_chances": [int(round(chance * 100)) for chance in match_chances],
        "wins_required": wins_required,
    }


def run_team_series(
    character: Character,
    opponents: list[SeriesOpponent],
    species_by_name: dict[str, PokemonSpecies],
    wins_required: int | None = None,
    important: bool = True,
    title: str = "Serie de batalhas",
) -> SeriesBattleResult:
    wins_required = wins_required or len(opponents)
    losses_allowed = max(0, len(opponents) - wins_required)
    wins = 0
    losses = 0
    log = [title]
    for index, opponent in enumerate(opponents, start=1):
        if wins >= wins_required:
            break
        if losses > losses_allowed:
            break
        opponent_species = species_by_name.get(opponent.species)
        if not opponent_species:
            continue
        active = _best_team_member_for_opponent(character, opponent_species, opponent.level, species_by_name)
        if active is None:
            log.append("Sua equipe nao tem Pokemon saudaveis para continuar.")
            losses = losses_allowed + 1
            break
        character.set_active_pokemon(character.team.index(active))
        log.append(f"Batalha {index}: {active.display_name()} enfrenta {opponent.trainer_name} - {opponent.species} Lv.{opponent.level}.")
        won, battle_log = simulate_simple_battle(
            character,
            active,
            species_by_name[active.species],
            f"{opponent.trainer_name} - {opponent.species}",
            opponent_species,
            opponent.level,
            important=important,
            species_by_name=species_by_name,
        )
        result_line = next((line for line in battle_log if "venceu" in line or "perdeu" in line), battle_log[-1])
        log.append(f"  {result_line}")
        if won:
            wins += 1
        else:
            losses += 1
            active.current_health = 0
            active.status = "badly_injured"
            log.append(f"  {active.display_name()} caiu.")
    series_won = wins >= wins_required
    log.append(f"Placar da serie: {wins} vitoria(s), {losses} derrota(s).")
    return SeriesBattleResult(series_won, wins, losses, len(opponents), log)


def preview_series_without_damage(
    character: Character,
    opponents: list[SeriesOpponent],
    species_by_name: dict[str, PokemonSpecies],
    wins_required: int | None = None,
) -> dict:
    clone = deepcopy(character)
    return estimate_series_chance(clone, opponents, species_by_name, wins_required)


def _best_team_member_for_opponent(
    character: Character,
    opponent_species: PokemonSpecies,
    opponent_level: int,
    species_by_name: dict[str, PokemonSpecies],
) -> OwnedPokemon | None:
    best = None
    best_chance = -1.0
    for pokemon in character.team:
        species = species_by_name.get(pokemon.species)
        if not species or pokemon.current_health <= 0 or pokemon.status == "badly_injured":
            continue
        if not pokemon.types:
            pokemon.types = list(species.types)
        chance = estimate_matchup_chance(character, pokemon, opponent_species, opponent_level, species_by_name)
        if chance > best_chance:
            best = pokemon
            best_chance = chance
    return best
