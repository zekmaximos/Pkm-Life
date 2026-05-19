from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CityServices:
    city: str
    services: list[str]
    shop_inventory: list[str]
    careers: list[str]
    gym: str | None = None
    event_focus: list[str] | None = None
    encounter_sources: list[str] | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "CityServices":
        return cls(
            city=data["city"],
            services=data.get("services", []),
            shop_inventory=data.get("shop_inventory", []),
            careers=data.get("careers", []),
            gym=data.get("gym"),
            event_focus=data.get("event_focus", []),
            encounter_sources=data.get("encounter_sources", []),
        )

    def has_service(self, service: str) -> bool:
        return service in self.services
