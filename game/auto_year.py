from __future__ import annotations

import random

from .capture import calculate_capture_chance
from .character import Character
from .pokemon import PokemonSpecies


def automatic_encounter_chance(character: Character, location_has_encounters: bool) -> float:
    if not location_has_encounters or character.age < 10:
        return 0.0
    chance = 0.22
    if character.career == "Treinador":
        chance += 0.10
    elif character.career == "Criador":
        chance += 0.05
    chance += min(0.08, character.attributes.POK / 1000)
    chance += min(0.05, character.attributes.LUK / 1400)
    if character.flags.get("repel_years", 0):
        chance *= 0.35
    return max(0.02, min(0.55, chance))


def decide_auto_encounter_action(
    character: Character,
    species: PokemonSpecies,
    level: int,
    has_ball: bool,
) -> str:
    active = character.active_pokemon()
    if has_ball:
        chance = calculate_capture_chance(
            species.rarity,
            pokemon_health_percent=65,
            player_attributes=character.attributes,
            ball_bonus=0,
            pokemon_level=level,
            evolution_stage=species.evolution_stage,
        )
        capture_desire = chance + character.attributes.LUK * 0.08
        if len(character.team) < 6:
            capture_desire += 8
        if species.rarity in {"rare", "very_rare"}:
            capture_desire += 12
        if capture_desire >= 35:
            return "capture"
    if active and active.current_health > active.healthy * 0.35:
        battle_desire = 35 + character.attributes.PHY * 0.12 + character.attributes.POK * 0.10
        if character.career == "Treinador":
            battle_desire += 12
        if level <= active.level + 5 and random.random() < battle_desire / 100:
            return "battle"
    return "observe"

