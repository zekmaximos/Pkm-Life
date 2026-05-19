from __future__ import annotations

from dataclasses import dataclass
import random

from .names import NameDatabase
from .pokemon import PokemonSpecies


@dataclass
class GymTemplate:
    gym_id: str
    city: str
    main_type: str
    difficulty: int
    badge: str
    recommended_level: int
    official: bool

    @classmethod
    def from_dict(cls, data: dict) -> "GymTemplate":
        return cls(
            gym_id=data["id"],
            city=data["city"],
            main_type=data["main_type"],
            difficulty=int(data["difficulty"]),
            badge=data["badge"],
            recommended_level=int(data["recommended_level"]),
            official=bool(data.get("official", True)),
        )


def generate_gyms(
    templates: list[GymTemplate],
    pokemon_by_name: dict[str, PokemonSpecies],
    names: NameDatabase,
) -> dict[str, dict]:
    used_names: set[str] = set()
    generated: dict[str, dict] = {}
    for template in templates:
        leader = names.random_full_name(used_names)
        used_names.add(leader)
        base_level = max(12, min(38, template.recommended_level + random.randint(-1, 1)))
        generated[template.gym_id] = {
            "id": template.gym_id,
            "city": template.city,
            "leader": leader,
            "main_type": template.main_type,
            "difficulty": template.difficulty,
            "badge": template.badge,
            "recommended_level": base_level,
            "level_range": [base_level, base_level + 3],
            "official": template.official,
            "team": generate_gym_team(template, pokemon_by_name, base_level),
        }
    return generated


def generate_gym_team(template: GymTemplate, pokemon_by_name: dict[str, PokemonSpecies], base_level: int) -> list[dict]:
    all_candidates = [
        species for species in pokemon_by_name.values()
        if template.main_type in species.types and not species.is_legendary and not species.is_mythic
    ]
    candidates = _sandbox_candidates(template, all_candidates)
    if len(candidates) < 3:
        candidates = all_candidates
    if len(candidates) < 3:
        raise ValueError(f"Not enough Pokemon for {template.main_type} gym.")

    team_size = random.randint(3, min(6, max(3, len(candidates))))
    team_species = _pick_varied_team(candidates, team_size)
    team_species.sort(key=lambda species: (species.evolution_stage, species.rarity, species.pokedex_id))

    team = []
    for index, species in enumerate(team_species):
        level = random.randint(base_level, base_level + 3)
        team.append({"species": species.name, "level": max(12, min(41, level))})
    return team


def _sandbox_candidates(template: GymTemplate, candidates: list[PokemonSpecies]) -> list[PokemonSpecies]:
    max_stage = _max_stage_for(template)
    filtered = [
        species for species in candidates
        if species.evolution_stage <= max_stage
        and (template.difficulty > 2 or species.rarity not in {"very_rare", "legendary", "mythic"})
    ]
    return filtered if len(filtered) >= 3 else candidates


def _pick_varied_team(candidates: list[PokemonSpecies], team_size: int) -> list[PokemonSpecies]:
    shuffled = candidates[:]
    random.shuffle(shuffled)
    picked: list[PokemonSpecies] = []
    rarity_counts: dict[str, int] = {}
    stage_counts: dict[int, int] = {}
    for species in sorted(shuffled, key=lambda item: (_rarity_rank(item.rarity), item.evolution_stage, random.random())):
        if species.rarity in {"very_rare", "legendary"} and rarity_counts.get(species.rarity, 0) >= 1:
            continue
        if species.rarity == "rare" and rarity_counts.get("rare", 0) >= 2:
            continue
        if species.evolution_stage == 3 and stage_counts.get(3, 0) >= 1:
            continue
        picked.append(species)
        rarity_counts[species.rarity] = rarity_counts.get(species.rarity, 0) + 1
        stage_counts[species.evolution_stage] = stage_counts.get(species.evolution_stage, 0) + 1
        if len(picked) == team_size:
            return picked
    if len(picked) >= 3:
        return picked
    for species in shuffled:
        if species not in picked:
            picked.append(species)
        if len(picked) == team_size:
            break
    return picked


def _max_stage_for(template: GymTemplate) -> int:
    if template.difficulty <= 2:
        return 1
    if template.difficulty <= 5:
        return 2
    return 3


def _rarity_rank(rarity: str) -> int:
    return {
        "common": 0,
        "uncommon": 1,
        "rare": 2,
        "very_rare": 3,
        "legendary": 4,
        "mythic": 5,
    }.get(rarity, 2)
