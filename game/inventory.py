from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Item:
    item_id: str
    name: str
    item_type: str
    capture_bonus: float = 0
    preferred_rarities: tuple[str, ...] = ()
    preferred_types: tuple[str, ...] = ()
    max_evolution_stage: int | None = None
    healing: int = 0
    price: int = 0
    effect: str | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "Item":
        return cls(
            item_id=data["id"],
            name=data["name"],
            item_type=data["type"],
            capture_bonus=float(data.get("capture_bonus", data.get("modifier", 0))),
            preferred_rarities=tuple(data.get("preferred_rarities", [])),
            preferred_types=tuple(data.get("preferred_types", [])),
            max_evolution_stage=data.get("max_evolution_stage"),
            healing=int(data.get("healing", 0)),
            price=int(data.get("price", 0)),
            effect=data.get("effect"),
        )

    def capture_bonus_for(self, rarity: str, types: list[str], evolution_stage: int) -> float:
        if self.item_type != "capture":
            return 0
        bonus = self.capture_bonus
        if self.preferred_rarities and rarity in self.preferred_rarities:
            bonus += 6
        if self.preferred_types and any(pokemon_type in self.preferred_types for pokemon_type in types):
            bonus += 8
        if self.max_evolution_stage is not None and evolution_stage <= self.max_evolution_stage:
            bonus += 5
        return bonus


def add_item(inventory: dict[str, int], item: str, amount: int = 1) -> None:
    inventory[item] = inventory.get(item, 0) + amount


def consume_item(inventory: dict[str, int], item: str, amount: int = 1) -> bool:
    if inventory.get(item, 0) < amount:
        return False
    inventory[item] -= amount
    if inventory[item] <= 0:
        del inventory[item]
    return True
