from __future__ import annotations

from dataclasses import dataclass, field
import random

from .utils import clamp


@dataclass
class PokemonSpecies:
    pokedex_id: int
    name: str
    types: list[str]
    rarity: str
    habitats: list[str]
    evolution: str | None
    evolution_level: int | None
    base_combat: int
    base_beauty: int
    base_healthy: int
    base_occult: int
    can_be_wild: bool
    is_legendary: bool
    is_starter: bool
    is_mythic: bool = False
    ability: str = "None"
    evolution_stage: int = 1
    evolutions: list[dict] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "PokemonSpecies":
        base_stats = data.get("base_stats", {"hp": 20, "attack": 10, "defense": 10, "speed": 10})
        return cls(
            pokedex_id=data["pokedex_id"],
            name=data["name"],
            types=data["types"],
            rarity=data["rarity"],
            habitats=data.get("habitats", []),
            evolution=data.get("evolution"),
            evolution_level=data.get("evolution_level"),
            base_combat=data.get("base_combat", _derive_combat(base_stats)),
            base_beauty=data.get("base_beauty", _derive_beauty(base_stats, data["types"])),
            base_healthy=data.get("base_healthy", _derive_healthy(base_stats)),
            base_occult=data.get("base_occult", _derive_occult(data["types"], data.get("is_legendary", False))),
            can_be_wild=data.get("can_be_wild", True),
            is_legendary=data.get("is_legendary", False),
            is_mythic=data.get("is_mythic", False),
            is_starter=data.get("is_starter", False),
            ability=data.get("ability", "None"),
            evolution_stage=data.get("evolution_stage", 1),
            evolutions=data.get("evolutions", []),
        )

    @property
    def base_stats(self) -> dict[str, int]:
        return {
            "hp": self.base_healthy,
            "attack": self.base_combat,
            "defense": self.base_healthy,
            "speed": max(1, (self.base_combat + self.base_beauty) // 2),
        }


@dataclass
class OwnedPokemon:
    species: str
    nickname: str | None = None
    level: int = 5
    experience: int = 0
    current_health: int = 20
    combat: int = 50
    beauty: int = 50
    healthy: int = 50
    occult: int = 1
    types: list[str] = field(default_factory=list)
    ability: str = "None"
    evolution_stage: int = 1
    happiness: int = 50
    bond: int = 30
    personality: str = "curioso"
    origin: str = "desconhecida"
    status: str = "healthy"
    active: bool = True
    battle_level: int = 0

    def display_name(self) -> str:
        return self.nickname or self.species

    def max_health(self, species_data: PokemonSpecies | None = None) -> int:
        base_hp = species_data.base_stats["hp"] if species_data else self.healthy
        return calculate_max_health(self.healthy, self.level, base_hp)

    def health_percent(self, species_data: PokemonSpecies | None = None) -> float:
        return self.current_health / max(1, self.max_health(species_data))

    def heal(self, amount: int, species_data: PokemonSpecies | None = None) -> None:
        self.current_health = int(clamp(self.current_health + amount, 0, self.max_health(species_data)))

    def heal_full(self, species_data: PokemonSpecies | None = None) -> None:
        self.current_health = self.max_health(species_data)

    def to_dict(self) -> dict:
        return {
            "species": self.species,
            "nickname": self.nickname,
            "level": self.level,
            "experience": self.experience,
            "current_health": self.current_health,
            "combat": self.combat,
            "beauty": self.beauty,
            "healthy": self.healthy,
            "occult": self.occult,
            "types": self.types,
            "ability": self.ability,
            "evolution_stage": self.evolution_stage,
            "happiness": self.happiness,
            "bond": self.bond,
            "personality": self.personality,
            "origin": self.origin,
            "status": self.status,
            "active": self.active,
            "battle_level": self.battle_level,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "OwnedPokemon":
        data = dict(data)
        data.setdefault("combat", 50)
        data.setdefault("beauty", 50)
        data.setdefault("healthy", max(1, min(100, data.get("current_health", 50))))
        data.setdefault("occult", 1)
        data.setdefault("battle_level", 0)
        data.setdefault("types", [])
        data.setdefault("ability", "None")
        data.setdefault("evolution_stage", 1)
        data["status"] = _normalize_condition(data.get("status", "healthy"))
        return cls(**data)


def minimum_level_for_species(
    species: PokemonSpecies,
    species_by_name: dict[str, PokemonSpecies] | None = None,
) -> int:
    if not species_by_name:
        return {1: 1, 2: 16, 3: 32}.get(species.evolution_stage, 1)
    incoming_levels: list[int] = []
    for candidate in species_by_name.values():
        if candidate.evolution == species.name and candidate.evolution_level:
            incoming_levels.append(int(candidate.evolution_level))
        for evolution in candidate.evolutions:
            if evolution.get("species") == species.name and evolution.get("method") == "level-up" and evolution.get("level"):
                incoming_levels.append(int(evolution["level"]))
    if incoming_levels:
        return max(1, min(incoming_levels))
    return {1: 1, 2: 16, 3: 32}.get(species.evolution_stage, 1)


def coherent_pokemon_level(
    species: PokemonSpecies,
    level: int,
    species_by_name: dict[str, PokemonSpecies] | None = None,
) -> int:
    minimum = minimum_level_for_species(species, species_by_name)
    return int(clamp(max(level, minimum), 1, 100))


def create_owned_pokemon(
    species: PokemonSpecies,
    level: int = 5,
    origin: str = "Kanto",
    species_by_name: dict[str, PokemonSpecies] | None = None,
) -> OwnedPokemon:
    personalities = ["corajoso", "calmo", "brincalhao", "teimoso", "gentil", "alerta"]
    coherent_level = coherent_pokemon_level(species, level, species_by_name)
    pokemon = OwnedPokemon(
        species=species.name,
        level=coherent_level,
        current_health=species.base_healthy,
        combat=_individual_stat(species.base_combat),
        beauty=_individual_stat(species.base_beauty),
        healthy=_individual_stat(species.base_healthy),
        occult=_individual_stat(species.base_occult),
        types=list(species.types),
        ability=species.ability,
        evolution_stage=species.evolution_stage,
        personality=random.choice(personalities),
        origin=origin,
    )
    pokemon.heal_full(species)
    return pokemon


def assign_evolution_stages(species_by_name: dict[str, PokemonSpecies]) -> None:
    for species in species_by_name.values():
        species.evolution_stage = max(1, species.evolution_stage)
    changed = True
    while changed:
        changed = False
        for species in species_by_name.values():
            if species.evolution and species.evolution in species_by_name:
                evolved = species_by_name[species.evolution]
                next_stage = max(1, min(3, species.evolution_stage + 1))
                if evolved.evolution_stage < next_stage:
                    evolved.evolution_stage = next_stage
                    changed = True
            for evolution in species.evolutions:
                target_name = evolution.get("species")
                if target_name and target_name in species_by_name:
                    evolved = species_by_name[target_name]
                    next_stage = max(1, min(3, species.evolution_stage + 1))
                    if evolved.evolution_stage < next_stage:
                        evolved.evolution_stage = next_stage
                        changed = True


def evolve_pokemon(pokemon: OwnedPokemon, target_species: PokemonSpecies) -> str:
    old_name = pokemon.species
    pokemon.species = target_species.name
    pokemon.types = list(target_species.types)
    pokemon.ability = target_species.ability
    pokemon.evolution_stage = target_species.evolution_stage
    pokemon.combat = _evolved_stat(pokemon.combat, target_species.base_combat)
    pokemon.beauty = _evolved_stat(pokemon.beauty, target_species.base_beauty)
    pokemon.healthy = _evolved_stat(pokemon.healthy, target_species.base_healthy)
    pokemon.occult = _evolved_stat(pokemon.occult, target_species.base_occult)
    pokemon.heal_full(target_species)
    return f"{old_name} evoluiu para {target_species.name}!"


def calculate_max_health(healthy: int, level: int, species_base_hp: int | None = None) -> int:
    base = species_base_hp if species_base_hp is not None else healthy
    value = 18 + level * 1.55 + healthy * 0.40 + base * 0.16
    return int(clamp(round(value), 20, 220))


def can_evolve(pokemon: OwnedPokemon, species: PokemonSpecies) -> bool:
    return bool(species.evolution and species.evolution_level and pokemon.level >= species.evolution_level)


def _evolved_stat(current: int, target_base: int) -> int:
    gain = random.randint(4, 9)
    return max(1, min(100, max(current + gain, target_base + random.randint(-5, 8))))


def _individual_stat(base: int) -> int:
    return max(1, min(100, base + random.randint(-10, 10)))


def _derive_combat(base_stats: dict[str, int]) -> int:
    return max(1, min(100, int(base_stats.get("attack", 10) * 0.7 + base_stats.get("speed", 10) * 0.3)))


def _derive_beauty(base_stats: dict[str, int], types: list[str]) -> int:
    type_bonus = 12 if any(t in {"Water", "Ice", "Psychic", "Dragon", "Flying"} for t in types) else 0
    return max(1, min(100, int(base_stats.get("speed", 10) * 0.45 + base_stats.get("hp", 10) * 0.25 + 20 + type_bonus)))


def _derive_healthy(base_stats: dict[str, int]) -> int:
    return max(1, min(100, int(base_stats.get("hp", 10) * 0.65 + base_stats.get("defense", 10) * 0.35)))


def _derive_occult(types: list[str], legendary: bool) -> int:
    if legendary:
        return 90
    if any(t in {"Psychic", "Ghost", "Dragon"} for t in types):
        return 65
    if any(t in {"Electric", "Ice", "Fire"} for t in types):
        return 35
    return 15
def _normalize_condition(status: str) -> str:
    if status == "saudavel":
        return "healthy"
    return status
