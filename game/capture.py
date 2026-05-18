from __future__ import annotations

from dataclasses import dataclass
import random

from .attributes import PlayerAttributes
from .character import Character
from .inventory import consume_item
from .inventory import Item
from .pokemon import OwnedPokemon, PokemonSpecies, create_owned_pokemon
from .utils import clamp


RARITY_BASE_CHANCE = {
    "common": 45,
    "uncommon": 30,
    "rare": 18,
    "very_rare": 10,
    "legendary": 3,
    "mythic": 1,
}

LEGACY_BALL_BONUS = {"Poke Ball": 0, "Great Ball": 12, "Ultra Ball": 25, "Master Ball": 100}


@dataclass
class CaptureResult:
    success: bool
    chance: float
    text: str

    def to_dict(self) -> dict:
        return {"success": self.success, "chance": round(self.chance, 2), "text": self.text}


def calculate_capture_chance(
    rarity: str,
    pokemon_health_percent: float,
    player_attributes: PlayerAttributes,
    ball_bonus: float = 0,
    status_bonus: float = 0,
    pokemon_level: int = 1,
    evolution_stage: int = 1,
) -> float:
    if ball_bonus >= 100:
        return 100.0
    rarity_base = RARITY_BASE_CHANCE.get(rarity, 18)
    level_penalty = max(0, pokemon_level - 1) * 0.22
    stage_penalty = max(0, evolution_stage - 1) * 12
    chance = (
        rarity_base
        + (player_attributes.POK * 0.12)
        + (player_attributes.LUK * 0.08)
        + ball_bonus
        + ((100 - pokemon_health_percent) * 0.25)
        + status_bonus
        - level_penalty
        - stage_penalty
    )
    return float(clamp(chance, 1, 95))


def attempt_capture(
    rarity: str,
    pokemon_name: str,
    pokemon_health_percent: float,
    player_attributes: PlayerAttributes,
    ball_bonus: float = 0,
    status_bonus: float = 0,
    pokemon_level: int = 1,
    evolution_stage: int = 1,
) -> CaptureResult:
    chance = calculate_capture_chance(
        rarity=rarity,
        pokemon_health_percent=pokemon_health_percent,
        player_attributes=player_attributes,
        ball_bonus=ball_bonus,
        status_bonus=status_bonus,
        pokemon_level=pokemon_level,
        evolution_stage=evolution_stage,
    )
    success = random.random() <= chance / 100
    if success:
        text = f"Captura bem-sucedida! Chance calculada: {chance:.1f}%."
    else:
        text = f"{pokemon_name} escapou. Chance calculada: {chance:.1f}%."
    return CaptureResult(success=success, chance=chance, text=text)


def try_capture(
    character: Character,
    species: PokemonSpecies,
    wild_level: int,
    ball: str = "Poke Ball",
    current_health_ratio: float = 0.5,
    item: Item | None = None,
) -> tuple[bool, str, OwnedPokemon | None]:
    if not consume_item(character.inventory, ball):
        return False, f"Voce nao tem {ball}.", None

    health_percent = clamp(current_health_ratio * 100, 1, 100)
    ball_bonus = item.capture_bonus_for(species.rarity, species.types, species.evolution_stage) if item else LEGACY_BALL_BONUS.get(ball, 0)
    result = attempt_capture(
        rarity=species.rarity,
        pokemon_name=species.name,
        pokemon_health_percent=health_percent,
        player_attributes=character.attributes,
        ball_bonus=ball_bonus,
        pokemon_level=wild_level,
        evolution_stage=species.evolution_stage,
    )
    if result.success:
        pokemon = create_owned_pokemon(species, level=wild_level, origin=f"capturado em {character.current_city}")
        destination = character.add_pokemon(pokemon)
        location = "equipe ativa" if destination == "team" else "Box"
        character.add_history(f"Voce capturou um {species.name} em {character.current_city}.")
        return True, f"{species.name} foi capturado e enviado para a {location}. {result.text}", pokemon
    return False, result.text, None
