from __future__ import annotations

from dataclasses import dataclass
import random

from .utils import clamp


ATTRIBUTE_KEYS = ("PHY", "MEN", "POK", "LUK")


@dataclass
class PlayerAttributes:
    PHY: int
    MEN: int
    POK: int
    LUK: int

    def __post_init__(self) -> None:
        self.PHY = int(clamp(self.PHY, 0, 100))
        self.MEN = int(clamp(self.MEN, 0, 100))
        self.POK = int(clamp(self.POK, 0, 100))
        self.LUK = int(clamp(self.LUK, 0, 100))

    @classmethod
    def generate(cls) -> "PlayerAttributes":
        return cls(
            PHY=_generate_initial_attribute(),
            MEN=_generate_initial_attribute(),
            POK=_generate_initial_attribute(),
            LUK=_generate_initial_attribute(),
        )

    @classmethod
    def from_dict(cls, data: dict) -> "PlayerAttributes":
        if all(key in data for key in ATTRIBUTE_KEYS):
            return cls(PHY=data["PHY"], MEN=data["MEN"], POK=data["POK"], LUK=data["LUK"])

        # Compatibility with early prototype saves/events.
        return cls(
            PHY=max(data.get("coragem", 0), data.get("disciplina", 0)) * 10,
            MEN=max(data.get("inteligencia", 0), data.get("disciplina", 0)) * 10,
            POK=data.get("conhecimento_pokemon", 0) * 10,
            LUK=max(35, data.get("carisma", 0) * 10),
        )

    def to_dict(self) -> dict[str, int]:
        return {"PHY": self.PHY, "MEN": self.MEN, "POK": self.POK, "LUK": self.LUK}

    def as_items(self) -> list[tuple[str, int]]:
        return list(self.to_dict().items())

    def get(self, key: str, default: int = 0) -> int:
        return getattr(self, key, default)

    def modify(self, changes: dict[str, int]) -> None:
        for key, amount in changes.items():
            if key not in ATTRIBUTE_KEYS:
                continue
            setattr(self, key, int(clamp(getattr(self, key) + amount, 0, 100)))


def _generate_initial_attribute() -> int:
    base = random.randint(20, 80)
    modifier = random.randint(-10, 10)
    return int(clamp(base + modifier, 0, 100))


def generate_initial_attributes() -> PlayerAttributes:
    return PlayerAttributes.generate()


def modify_attributes(attributes: PlayerAttributes, changes: dict[str, int]) -> PlayerAttributes:
    attributes.modify(changes)
    return attributes

