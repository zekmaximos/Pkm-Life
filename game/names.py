from __future__ import annotations

from dataclasses import dataclass
import random


@dataclass(frozen=True)
class NameDatabase:
    first_names: list[str]
    last_names: list[str]

    @classmethod
    def from_dict(cls, data: dict) -> "NameDatabase":
        return cls(first_names=data.get("first_names", []), last_names=data.get("last_names", []))

    def random_full_name(self, used_names: set[str] | None = None) -> str:
        used_names = used_names or set()
        for _ in range(100):
            name = f"{random.choice(self.first_names)} {random.choice(self.last_names)}"
            if name not in used_names:
                return name
        return f"{random.choice(self.first_names)} {random.choice(self.last_names)}"

