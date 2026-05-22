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

    def total(self) -> int:
        return sum(self.to_dict().values())

    def as_items(self) -> list[tuple[str, int]]:
        return list(self.to_dict().items())

    def get(self, key: str, default: int = 0) -> int:
        return getattr(self, key, default)

    def modify(self, changes: dict[str, int], soft_caps: dict[str, int] | None = None) -> None:
        """Aplica mudancas com soft cap por atributo.

        Acima do soft cap cada ponto tem chance decrescente de aplicar:
          <= cap       -> 100 %
          cap+1..+10   -> 65 %
          cap+11..+20  -> 35 %
          cap+21..+30  -> 15 %
          > cap+30     -> 5 % (hard squeeze, nunca bloqueia totalmente)
        Cap maximo absoluto: 95.
        """
        for key, amount in changes.items():
            if key not in ATTRIBUTE_KEYS:
                continue
            current = getattr(self, key)
            cap = (soft_caps or {}).get(key, 95)
            cap = min(cap, 95)
            if amount <= 0:
                # Negative changes always apply fully (no soft cap resistance)
                setattr(self, key, int(clamp(current + amount, 0, 95)))
                continue
            # Apply each point with decreasing probability above cap
            new_val = current
            for _ in range(amount):
                over = new_val - cap
                if over <= 0:
                    prob = 1.0
                elif over <= 10:
                    prob = 0.65
                elif over <= 20:
                    prob = 0.35
                elif over <= 30:
                    prob = 0.15
                else:
                    prob = 0.05
                if random.random() < prob:
                    new_val += 1
            setattr(self, key, int(clamp(new_val, 0, 95)))


def _generate_initial_attribute() -> int:
    base = random.randint(20, 80)
    modifier = random.randint(-10, 10)
    return int(clamp(base + modifier, 0, 100))


def generate_initial_attributes() -> PlayerAttributes:
    return PlayerAttributes.generate()


def modify_attributes(attributes: PlayerAttributes, changes: dict[str, int]) -> PlayerAttributes:
    attributes.modify(changes)
    return attributes
