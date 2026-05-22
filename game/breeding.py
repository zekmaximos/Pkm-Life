from __future__ import annotations

import random

from .character import Character
from .eggs import PokeEgg, choose_egg_tier, create_random_egg
from .pokemon import OwnedPokemon, PokemonSpecies
from .utils import clamp


def compatible_for_breeding(first: OwnedPokemon, second: OwnedPokemon) -> bool:
    if first.species == second.species:
        return True
    return bool(set(first.types).intersection(second.types))


def breed_success_chance(character: Character, first: OwnedPokemon, second: OwnedPokemon) -> float:
    base = 0.18
    if character.career == "Criador":
        base += 0.18
    base += character.attributes.POK * 0.002
    base += character.attributes.MEN * 0.001
    base += ((first.happiness + second.happiness) / 2) * 0.002
    if compatible_for_breeding(first, second):
        base += 0.12
    rank = character.career_rank("Criador") if hasattr(character, "career_rank") else 0
    base += rank * 0.025
    return float(clamp(base, 0.05, 0.78))


def create_bred_egg(
    character: Character,
    first: OwnedPokemon,
    second: OwnedPokemon,
    species_by_name: dict[str, PokemonSpecies],
) -> tuple[bool, PokeEgg | None, str]:
    chance = breed_success_chance(character, first, second)
    if random.random() > chance:
        first.happiness = int(clamp(first.happiness - 1, 0, 100))
        second.happiness = int(clamp(second.happiness - 1, 0, 100))
        return False, None, f"A tentativa de criacao nao gerou ovo. Chance era {chance * 100:.1f}%."

    parent_species = random.choice([first.species, second.species])
    parent = species_by_name.get(parent_species)
    type_hint = random.choice(parent.types) if parent else None
    tier_weights = {"C": 70, "I": 22, "R": 7, "RR": 1}
    if character.career == "Criador":
        tier_weights = {"C": 55, "I": 30, "R": 12, "RR": 3}
    tier = choose_egg_tier(tier_weights)
    egg = create_random_egg(species_by_name, tier=tier, origin="criacao Pokemon", type_hint=type_hint)
    first.happiness = int(clamp(first.happiness + 1, 0, 100))
    second.happiness = int(clamp(second.happiness + 1, 0, 100))
    return True, egg, f"A criacao deu certo: um ovo {egg.color} ({egg.rarity_label}) foi gerado."
