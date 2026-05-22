from __future__ import annotations

from dataclasses import dataclass, field
import random

from .character import Character
from .pokemon import OwnedPokemon, PokemonSpecies
from .utils import clamp


RARITY_STYLE_BONUS = {
    "common": 0,
    "uncommon": 4,
    "rare": 9,
    "very_rare": 15,
    "legendary": 20,
    "mythic": 24,
}

CONTEST_TYPE_BONUS = {
    "Normal": 2,
    "Fire": 4,
    "Water": 6,
    "Electric": 5,
    "Grass": 5,
    "Ice": 8,
    "Psychic": 8,
    "Dragon": 9,
    "Flying": 5,
    "Ghost": 7,
}


@dataclass
class ContestResult:
    category: str
    rank: int
    participants: int
    score: float
    prize_money: int
    rep_gained: int
    log: list[str] = field(default_factory=list)


CONTEST_CATEGORIES = {
    "beauty": {"label": "Beauty", "main": "beauty", "secondary": "happiness", "types": {"Water", "Ice", "Psychic", "Fire"}},
    "cute": {"label": "Cute", "main": "happiness", "secondary": "beauty", "types": {"Normal", "Fairy", "Grass", "Water"}},
    "cool": {"label": "Cool", "main": "combat", "secondary": "beauty", "types": {"Fire", "Electric", "Dragon", "Flying"}},
    "smart": {"label": "Smart", "main": "bond", "secondary": "occult", "types": {"Psychic", "Electric", "Poison", "Normal"}},
    "mysterious": {"label": "Mysterious", "main": "occult", "secondary": "beauty", "types": {"Ghost", "Psychic", "Dragon", "Poison"}},
}

CONTEST_ITEM_BONUSES = {
    "Contest Outfit": 5,
    "Silk Ribbon": 4,
    "Stage Cologne": 3,
    "Mystic Veil": 5,
    "Cool Jacket": 4,
}


def contest_score(character: Character, pokemon: OwnedPokemon, species: PokemonSpecies, category: str = "beauty") -> float:
    category_data = CONTEST_CATEGORIES.get(category, CONTEST_CATEGORIES["beauty"])
    type_bonus = max(CONTEST_TYPE_BONUS.get(type_name, 0) for type_name in species.types)
    if set(species.types).intersection(category_data["types"]):
        type_bonus += 6
    rarity_bonus = RARITY_STYLE_BONUS.get(species.rarity, 4)
    coordinator_bonus = 10 + character.career_rank("Coordenador") * 2 if character.career == "Coordenador" else 0
    item_bonus = sum(
        bonus for item_name, bonus in CONTEST_ITEM_BONUSES.items()
        if character.inventory.get(item_name, 0) > 0
    )
    main_value = getattr(pokemon, str(category_data["main"]), pokemon.beauty)
    secondary_value = getattr(pokemon, str(category_data["secondary"]), pokemon.happiness)
    trainer_bonus = (
        main_value * 0.46
        + secondary_value * 0.18
        + pokemon.beauty * 0.08
        + pokemon.happiness * 0.08
        + pokemon.bond * 0.08
        + pokemon.occult * 0.06
        + character.attributes.POK * 0.08
        + character.attributes.LUK * 0.07
        + character.reputation * 0.05
        + type_bonus
        + rarity_bonus
        + coordinator_bonus
        + item_bonus
    )
    condition = {
        "healthy": 1.00,
        "inspired": 1.10,
        "tired": 0.92,
        "injured": 0.78,
        "badly_injured": 0.55,
        "sick": 0.72,
    }.get(pokemon.status, 1.0)
    return trainer_bonus * condition * random.uniform(0.90, 1.12)


def run_contest(character: Character, pokemon: OwnedPokemon, species: PokemonSpecies, difficulty: str = "local", category: str = "beauty") -> ContestResult:
    participants = {"local": 8, "city": 12, "regional": 16}.get(difficulty, 8)
    baseline = {"local": 50, "city": 66, "regional": 84}.get(difficulty, 50)
    spread = {"local": 15, "city": 17, "regional": 18}.get(difficulty, 15)
    score = contest_score(character, pokemon, species, category)
    npc_scores = [random.uniform(baseline - spread, baseline + spread) for _ in range(participants - 1)]
    ranking = sorted(npc_scores + [score], reverse=True)
    rank = ranking.index(score) + 1
    if rank == 1:
        prize = {"local": 350, "city": 750, "regional": 1800}.get(difficulty, 350)
        rep = {"local": 3, "city": 6, "regional": 12}.get(difficulty, 3)
    elif rank <= 3:
        prize = {"local": 150, "city": 350, "regional": 800}.get(difficulty, 150)
        rep = {"local": 1, "city": 3, "regional": 6}.get(difficulty, 1)
    else:
        prize = 0
        rep = 0
    pokemon.beauty = int(clamp(pokemon.beauty + (2 if rank <= 3 else 1), 1, 100))
    pokemon.happiness = int(clamp(pokemon.happiness + 1, 0, 100))
    if category == "mysterious" and rank <= 3:
        pokemon.occult = int(clamp(pokemon.occult + 1, 1, 100))
    if category == "cool" and rank <= 3:
        pokemon.combat = int(clamp(pokemon.combat + 1, 1, 100))
    return ContestResult(
        category=category,
        rank=rank,
        participants=participants,
        score=score,
        prize_money=prize,
        rep_gained=rep,
        log=[
            f"{pokemon.display_name()} apresentou uma rotina {difficulty} na categoria {CONTEST_CATEGORIES.get(category, CONTEST_CATEGORIES['beauty'])['label']}.",
            f"Score final: {score:.1f}. Colocacao: {rank}/{participants}.",
            f"Premio: {prize}P. Reputacao: +{rep}.",
        ],
    )
