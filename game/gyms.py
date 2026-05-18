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
        base_level = random.randint(12, 38)
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
    candidates = [
        species for species in pokemon_by_name.values()
        if template.main_type in species.types and not species.is_legendary and not species.is_mythic
    ]
    if len(candidates) < 3:
        candidates = [
            species for species in pokemon_by_name.values()
            if template.main_type in species.types and not species.is_mythic
        ]
    if len(candidates) < 3:
        raise ValueError(f"Not enough Pokemon for {template.main_type} gym.")

    team_size = random.randint(3, min(6, max(3, len(candidates))))
    preferred = sorted(
        candidates,
        key=lambda species: (
            abs(_species_power_hint(species) - _target_power(template)),
            species.evolution_stage,
            species.pokedex_id,
        ),
    )
    pool_size = min(len(preferred), max(team_size + 4, 8))
    team_species = random.sample(preferred[:pool_size], team_size)
    team_species.sort(key=lambda species: (species.evolution_stage, _species_power_hint(species)))

    team = []
    for index, species in enumerate(team_species):
        level = random.randint(base_level, base_level + 3)
        team.append({"species": species.name, "level": max(12, min(41, level))})
    return team


def _species_power_hint(species: PokemonSpecies) -> int:
    return int((species.base_combat + species.base_healthy + species.base_occult) / 3)


def _target_power(template: GymTemplate) -> int:
    return min(100, 25 + template.difficulty * 8)
