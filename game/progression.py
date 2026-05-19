from __future__ import annotations

import random

from .careers import career_progress, default_career_for_age
from .character import Character
from .eggs import progress_eggs
from .pokemon import OwnedPokemon, PokemonSpecies, can_evolve, evolve_pokemon
from .utils import clamp


XP_PER_LEVEL = 100


def progress_year(character: Character, species_by_name: dict[str, PokemonSpecies] | None = None) -> list[str]:
    notes: list[str] = []
    if character.career is None:
        default_career = default_career_for_age(character.age)
        if default_career:
            character.career = default_career
            notes.append(f"Voce entrou na rotina de {default_career}.")

    career = career_progress(character.career, character.attributes, character.age, character.career_rank())
    character.attributes.modify(career.attribute_changes)
    if career.money_gain:
        character.money = max(0, character.money + career.money_gain)
        notes.append(f"Voce ganhou {career.money_gain} Pokedollar.")
    if career.reputation_change:
        character.reputation += career.reputation_change
    if career.note and (career.attribute_changes or career.money_gain or character.team):
        notes.append(career.note)

    for pokemon in character.team:
        notes.extend(_progress_pokemon(pokemon, character, career.pokemon_xp_bonus))
        notes.extend(check_evolution(pokemon, species_by_name or {}))
        pokemon.happiness = int(clamp(pokemon.happiness + career.pokemon_happiness_bonus + random.choice([0, 1]), 0, 100))
        pokemon.healthy = int(clamp(pokemon.healthy + career.pokemon_health_bonus + random.choice([-1, 0, 1]), 1, 100))
        pokemon.beauty = int(clamp(pokemon.beauty + career.pokemon_beauty_bonus, 1, 100))
        max_hp = pokemon.max_health(species_by_name.get(pokemon.species) if species_by_name else None)
        pokemon.current_health = int(clamp(pokemon.current_health + career.pokemon_health_bonus + 2, 0, max_hp))
        _update_condition(pokemon)

    if character.team and random.random() < _team_incident_chance(character):
        pokemon = random.choice(character.team)
        pokemon.status = random.choice(["tired", "injured", "sick"])
        pokemon.current_health = int(clamp(pokemon.current_health - random.randint(5, 16), 0, pokemon.max_health(species_by_name.get(pokemon.species) if species_by_name else None)))
        notes.append(f"{pokemon.display_name()} teve um problema de saude e agora esta {pokemon.status}.")

    notes.extend(progress_eggs(character, species_by_name or {}))

    return notes


def _progress_pokemon(pokemon: OwnedPokemon, character: Character, career_xp_bonus: int) -> list[str]:
    notes: list[str] = []
    if pokemon.level >= 100:
        return notes
    yearly_xp = career_xp_bonus + 18 + max(0, character.attributes.POK // 6) + random.randint(4, 18)
    if character.career == "Treinador":
        yearly_xp += 12 + character.attributes.PHY // 8
    elif character.career == "Criador":
        yearly_xp += 6 + character.attributes.MEN // 12
    elif character.career == "Coordenador":
        yearly_xp += 8 + character.attributes.LUK // 12
    if pokemon.status in {"injured", "badly_injured", "sick"}:
        yearly_xp = max(0, yearly_xp // 2)
    notes.extend(grant_pokemon_xp(pokemon, yearly_xp))
    return notes


def grant_pokemon_xp(
    pokemon: OwnedPokemon,
    amount: int,
    species_by_name: dict[str, PokemonSpecies] | None = None,
) -> list[str]:
    notes: list[str] = []
    if amount <= 0 or pokemon.level >= 100:
        return notes
    pokemon.experience += amount
    while pokemon.experience >= XP_PER_LEVEL and pokemon.level < 100:
        pokemon.experience -= XP_PER_LEVEL
        pokemon.level += 1
        pokemon.combat = int(clamp(pokemon.combat + random.randint(1, 3), 1, 100))
        pokemon.healthy = int(clamp(pokemon.healthy + random.randint(0, 2), 1, 100))
        pokemon.heal_full(species_by_name.get(pokemon.species) if species_by_name else None)
        notes.append(f"{pokemon.display_name()} subiu para o nivel {pokemon.level}.")
    notes.extend(check_evolution(pokemon, species_by_name or {}))
    return notes


def check_evolution(pokemon: OwnedPokemon, species_by_name: dict[str, PokemonSpecies]) -> list[str]:
    species = species_by_name.get(pokemon.species)
    if not species or not can_evolve(pokemon, species):
        return []
    target = species_by_name.get(species.evolution or "")
    if not target:
        return []
    return [evolve_pokemon(pokemon, target)]


def _update_condition(pokemon: OwnedPokemon) -> None:
    max_hp = pokemon.max_health()
    if pokemon.current_health <= 0:
        pokemon.status = "badly_injured"
    elif pokemon.current_health < max_hp * 0.35:
        pokemon.status = "injured"
    elif pokemon.status in {"tired", "injured", "sick"} and pokemon.current_health >= max_hp * 0.75:
        pokemon.status = "healthy"


def _team_incident_chance(character: Character) -> float:
    care = (character.attributes.POK + character.attributes.MEN) / 2
    return float(clamp(0.18 - care / 1000, 0.04, 0.18))
