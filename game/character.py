from __future__ import annotations

from dataclasses import dataclass, field

from .attributes import PlayerAttributes, generate_initial_attributes
from .eggs import PokeEgg
from .history import HistoryEntry
from .pokemon import OwnedPokemon


def life_phase(age: int) -> str:
    if age <= 4:
        return "primeira infancia"
    if age <= 9:
        return "infancia"
    if age <= 15:
        return "inicio da jornada"
    if age <= 24:
        return "juventude"
    if age <= 59:
        return "vida adulta"
    return "maturidade/legado"


@dataclass
class Character:
    name: str
    age: int = 0
    region: str = "Kanto"
    hometown: str = "Pallet Town"
    current_city: str = "Pallet Town"
    money: int = 0
    health: int = 100
    reputation: int = 0
    attributes: PlayerAttributes = field(default_factory=generate_initial_attributes)
    history: list[HistoryEntry] = field(default_factory=list)
    team: list[OwnedPokemon] = field(default_factory=list)
    box: list[OwnedPokemon] = field(default_factory=list)
    active_pokemon_index: int = 0
    eggs: list[PokeEgg] = field(default_factory=list)
    badges: list[str] = field(default_factory=list)
    inventory: dict[str, int] = field(default_factory=lambda: {"Poke Ball": 5, "Potion": 1})
    flags: dict[str, bool | str | int | list[str] | dict] = field(default_factory=dict)
    career: str | None = None
    generated_gyms: dict[str, dict] = field(default_factory=dict)
    career_ranks: dict[str, int] = field(default_factory=dict)
    career_xp: dict[str, int] = field(default_factory=dict)
    pokedex_seen: list[str] = field(default_factory=list)
    pokedex_caught: list[str] = field(default_factory=list)
    assets: dict[str, int] = field(default_factory=dict)

    @property
    def phase(self) -> str:
        return life_phase(self.age)

    def add_history(self, text: str, tags: list[str] | None = None) -> None:
        self.history.append(HistoryEntry(age=self.age, text=text, tags=tags or []))

    def add_pokemon(self, pokemon: OwnedPokemon) -> str:
        if len(self.team) < 6:
            pokemon.active = not self.team
            self.team.append(pokemon)
            self._sync_active_flags()
            return "team"
        pokemon.active = False
        self.box.append(pokemon)
        return "box"

    def active_pokemon(self) -> OwnedPokemon | None:
        if not self.team:
            return None
        self.active_pokemon_index = max(0, min(self.active_pokemon_index, len(self.team) - 1))
        return self.team[self.active_pokemon_index]

    def set_active_pokemon(self, index: int) -> bool:
        if index < 0 or index >= len(self.team):
            return False
        self.active_pokemon_index = index
        self._sync_active_flags()
        return True

    def _sync_active_flags(self) -> None:
        if not self.team:
            self.active_pokemon_index = 0
            return
        self.active_pokemon_index = max(0, min(self.active_pokemon_index, len(self.team) - 1))
        for index, pokemon in enumerate(self.team):
            pokemon.active = index == self.active_pokemon_index

    def attr_soft_caps(self) -> dict[str, int]:
        """Retorna os soft caps por atributo (initial + 35, max 90).
        Compatível com saves antigos: se não existir, deriva dos atributos atuais como fallback."""
        caps = self.flags.get("attr_soft_caps")
        if isinstance(caps, dict):
            return caps
        # Fallback para saves sem caps registrados: usa atributo atual como base
        return {k: min(90, v + 35) for k, v in self.attributes.to_dict().items()}

    def set_attr_soft_caps(self) -> None:
        """Registra os soft caps a partir dos atributos atuais do nascimento.
        Deve ser chamado apenas uma vez na criação do personagem."""
        if "attr_soft_caps" not in self.flags:
            self.flags["attr_soft_caps"] = {k: min(90, v + 35) for k, v in self.attributes.to_dict().items()}

    def modify_attributes(self, changes: dict[str, int]) -> None:
        """Wrapper de modify que passa os soft caps automaticamente."""
        self.attributes.modify(changes, self.attr_soft_caps())

    def career_rank(self, career: str | None = None) -> int:
        key = career or self.career or ""
        return int(self.career_ranks.get(key, 0))

    def register_seen(self, species_name: str) -> None:
        if species_name not in self.pokedex_seen:
            self.pokedex_seen.append(species_name)

    def register_caught(self, species_name: str) -> None:
        self.register_seen(species_name)
        if species_name not in self.pokedex_caught:
            self.pokedex_caught.append(species_name)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "age": self.age,
            "region": self.region,
            "hometown": self.hometown,
            "current_city": self.current_city,
            "money": self.money,
            "health": self.health,
            "reputation": self.reputation,
            "attributes": self.attributes.to_dict(),
            "history": [entry.to_dict() for entry in self.history],
            "team": [pokemon.to_dict() for pokemon in self.team],
            "box": [pokemon.to_dict() for pokemon in self.box],
            "reserve": [pokemon.to_dict() for pokemon in self.box],
            "active_pokemon_index": self.active_pokemon_index,
            "eggs": [egg.to_dict() for egg in self.eggs],
            "badges": self.badges,
            "inventory": self.inventory,
            "flags": self.flags,
            "career": self.career,
            "generated_gyms": self.generated_gyms,
            "career_ranks": self.career_ranks,
            "career_xp": self.career_xp,
            "pokedex_seen": self.pokedex_seen,
            "pokedex_caught": self.pokedex_caught,
            "assets": self.assets,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Character":
        character = cls(name=data["name"])
        character.age = data.get("age", 0)
        character.region = data.get("region", "Kanto")
        character.hometown = data.get("hometown", "Pallet Town")
        character.current_city = data.get("current_city", character.hometown)
        character.money = data.get("money", 0)
        character.health = data.get("health", 100)
        character.reputation = data.get("reputation", 0)
        character.attributes = PlayerAttributes.from_dict(data.get("attributes", {}))
        character.history = [HistoryEntry.from_dict(entry) for entry in data.get("history", [])]
        character.team = [OwnedPokemon.from_dict(pokemon) for pokemon in data.get("team", [])]
        box_data = data.get("box", data.get("reserve", []))
        character.box = [OwnedPokemon.from_dict(pokemon) for pokemon in box_data]
        character.active_pokemon_index = data.get("active_pokemon_index", 0)
        character._sync_active_flags()
        character.eggs = [PokeEgg.from_dict(egg) for egg in data.get("eggs", [])]
        character.badges = data.get("badges", [])
        character.inventory = data.get("inventory", {"Poke Ball": 5, "Potion": 1})
        character.flags = data.get("flags", {})
        character.career = data.get("career")
        character.generated_gyms = data.get("generated_gyms", {})
        character.career_ranks = data.get("career_ranks", {})
        character.career_xp = data.get("career_xp", {})
        character.pokedex_seen = data.get("pokedex_seen", [])
        character.pokedex_caught = data.get("pokedex_caught", [])
        character.assets = data.get("assets", {})
        return character
