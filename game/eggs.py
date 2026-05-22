from __future__ import annotations

from dataclasses import dataclass
import random
from uuid import uuid4

from .pokemon import PokemonSpecies, create_owned_pokemon


EGG_TYPE_COLORS = {
    "Normal": "creme com pintas marrons",
    "Fire": "vermelho alaranjado",
    "Water": "azul com ondas claras",
    "Electric": "amarelo com marcas em zigue-zague",
    "Grass": "verde com manchas de folhas",
    "Ice": "azul palido cristalino",
    "Fighting": "vermelho escuro com faixas",
    "Poison": "roxo com pontos escuros",
    "Ground": "ocre com rachaduras",
    "Flying": "branco com plumas azuis",
    "Psychic": "rosa com brilho suave",
    "Bug": "verde claro com casca segmentada",
    "Rock": "cinza pedregoso",
    "Ghost": "lilas nebuloso",
    "Dragon": "azul profundo com escamas",
}

EGG_TIER_LABELS = {
    "C": "Comum",
    "I": "Incomum",
    "R": "Raro",
    "RR": "Rarissimo",
    "SR": "Super raro",
}

EGG_TIER_RARITIES = {
    "C": {"common"},
    "I": {"uncommon"},
    "R": {"rare"},
    "RR": {"very_rare"},
    "SR": {"rare", "very_rare"},
}

EGG_HATCH_YEARS = {"C": 1, "I": 1, "R": 1, "RR": 1, "SR": 1}


@dataclass
class PokeEgg:
    egg_id: str
    species: str
    primary_type: str
    color: str
    rarity_tier: str
    years_to_hatch: int
    progress: int = 0
    origin: str = "desconhecida"

    @classmethod
    def from_dict(cls, data: dict) -> "PokeEgg":
        return cls(
            egg_id=data["egg_id"],
            species=data["species"],
            primary_type=data["primary_type"],
            color=data["color"],
            rarity_tier=data["rarity_tier"],
            years_to_hatch=int(data["years_to_hatch"]),
            progress=int(data.get("progress", 0)),
            origin=data.get("origin", "desconhecida"),
        )

    def to_dict(self) -> dict:
        return {
            "egg_id": self.egg_id,
            "species": self.species,
            "primary_type": self.primary_type,
            "color": self.color,
            "rarity_tier": self.rarity_tier,
            "years_to_hatch": self.years_to_hatch,
            "progress": self.progress,
            "origin": self.origin,
        }

    @property
    def rarity_label(self) -> str:
        return EGG_TIER_LABELS.get(self.rarity_tier, self.rarity_tier)


def create_random_egg(
    pokemon_by_name: dict[str, PokemonSpecies],
    tier: str,
    origin: str,
    type_hint: str | None = None,
) -> PokeEgg:
    candidates = [
        species for species in pokemon_by_name.values()
        if _egg_candidate(species, tier, type_hint)
    ]
    if not candidates:
        candidates = [
            species for species in pokemon_by_name.values()
            if not species.is_legendary and not species.is_mythic and species.evolution_stage == 1
        ]
    species = random.choice(candidates)
    primary_type = type_hint if type_hint in species.types else species.types[0]
    return PokeEgg(
        egg_id=uuid4().hex,
        species=species.name,
        primary_type=primary_type,
        color=EGG_TYPE_COLORS.get(primary_type, "claro com marcas misteriosas"),
        rarity_tier=tier,
        years_to_hatch=EGG_HATCH_YEARS.get(tier, 3),
        origin=origin,
    )


def choose_egg_tier(weights: dict[str, int] | None = None) -> str:
    weights = weights or {"C": 60, "I": 25, "R": 10, "RR": 4, "SR": 1}
    tiers = list(weights)
    return random.choices(tiers, weights=[weights[tier] for tier in tiers], k=1)[0]


def progress_eggs(character, pokemon_by_name: dict[str, PokemonSpecies]) -> list[str]:
    notes: list[str] = []
    remaining: list[PokeEgg] = []
    hatch_report = list(getattr(character, "flags", {}).get("last_hatched_eggs", []))
    for egg in character.eggs:
        egg.progress += 1
        if egg.progress >= egg.years_to_hatch:
            species = pokemon_by_name.get(egg.species)
            if species:
                pokemon = create_owned_pokemon(species, level=1, origin=f"chocado de ovo: {egg.origin}")
                destination = character.add_pokemon(pokemon)
                location = "equipe" if destination == "team" else "Box"
                if hasattr(character, "register_caught"):
                    character.register_caught(species.name)
                notes.append(f"Um ovo {egg.color} chocou e revelou {pokemon.species}.")
                hatch_report.append({
                    "action": "hatched",
                    "species": pokemon.species,
                    "destination": location,
                    "source": egg.origin,
                    "tier": egg.rarity_tier,
                })
        else:
            remaining.append(egg)
    character.eggs = remaining
    if hatch_report and hasattr(character, "flags"):
        character.flags["last_hatched_eggs"] = hatch_report
    return notes


def _egg_candidate(species: PokemonSpecies, tier: str, type_hint: str | None) -> bool:
    if species.is_legendary or species.is_mythic:
        return False
    if species.evolution_stage != 1:
        return False
    if type_hint and type_hint not in species.types:
        return False
    rarities = EGG_TIER_RARITIES.get(tier, {"common", "uncommon"})
    if tier == "SR":
        return species.rarity in rarities or "Dragon" in species.types or species.is_starter
    return species.rarity in rarities
