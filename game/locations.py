from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Location:
    location_id: str
    name: str
    kind: str
    region: str
    description: str
    level_range: tuple[int, int]
    encounter_enabled: bool = True
    capture_enabled: bool = True

    @classmethod
    def from_dict(cls, data: dict) -> "Location":
        level_range = data.get("level_range", [1, 5])
        return cls(
            location_id=data["id"],
            name=data["name"],
            kind=data["kind"],
            region=data.get("region", "Kanto"),
            description=data.get("description", ""),
            level_range=(int(level_range[0]), int(level_range[1])),
            encounter_enabled=data.get("encounter_enabled", True),
            capture_enabled=data.get("capture_enabled", True),
        )

