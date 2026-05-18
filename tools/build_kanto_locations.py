from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"


CITY_DESCRIPTIONS = {
    "Pallet Town": "Cidade pequena e tranquila, ponto de partida de muitas historias Pokemon.",
    "Viridian City": "Cidade verde entre Pallet, a floresta e o caminho para a Liga Pokemon.",
    "Pewter City": "Cidade de pedra, museus e do ginasio de Brock.",
    "Cerulean City": "Cidade aquatica marcada por pontes, rios e pelo ginasio de Misty.",
    "Vermilion City": "Cidade portuaria movimentada, ligada ao mar e ao comercio.",
    "Lavender Town": "Cidade silenciosa, conhecida por memoria, misterio e Pokemon espirituais.",
    "Celadon City": "Grande centro urbano com lojas, jardins e raridades.",
    "Fuchsia City": "Cidade ligada a areas selvagens, safaris e criadores experientes.",
    "Saffron City": "Metropole central de Kanto, forte em tecnologia e fenomenos psiquicos.",
    "Cinnabar Island": "Ilha vulcanica com laboratorio e especies raras.",
    "Indigo Plateau": "Sede da Liga Pokemon e destino de treinadores de elite.",
}

SPECIAL_DESCRIPTIONS = {
    "Viridian Forest": "Floresta inicial com muitos insetos e alguns Pokemon eletricos raros.",
    "Mt. Moon": "Caverna lunar conhecida por fosseis, Zubat e Pokemon de pedra.",
    "Rock Tunnel": "Tunel escuro entre montanhas, habitado por rochosos e lutadores.",
    "Diglett's Cave": "Caverna estreita dominada por Diglett e Dugtrio.",
    "Pokemon Tower": "Torre de Lavender Town associada a Pokemon fantasma.",
    "Power Plant": "Usina abandonada tomada por Pokemon eletricos.",
    "Pokemon Mansion": "Mansao em ruinas de Cinnabar, quente e perigosa.",
    "Safari Zone": "Grande area selvagem de Fuchsia com especies raras.",
    "Seafoam Islands": "Ilhas geladas e cavernosas entre rotas maritimas.",
    "Victory Road": "Caverna final antes da Liga Pokemon.",
    "Cerulean Cave": "Caverna de alto risco com Pokemon muito fortes.",
    "Silph Co.": "Predio corporativo de Saffron ligado a presentes e eventos.",
    "Mythic Event": "Local narrativo reservado para eventos miticos.",
}

CITY_ORDER = [
    "Pallet Town",
    "Viridian City",
    "Pewter City",
    "Cerulean City",
    "Vermilion City",
    "Lavender Town",
    "Celadon City",
    "Fuchsia City",
    "Saffron City",
    "Cinnabar Island",
    "Indigo Plateau",
]


def slug(name: str) -> str:
    return name.lower().replace(" ", "_").replace(".", "").replace("'", "").replace("-", "_")


def route_description(route_name: str) -> str:
    number = route_name.split(" ")[1]
    return f"Rota {number} de Kanto, usada para encontros selvagens e captura de Pokemon."


def build() -> None:
    encounters = json.loads((DATA_DIR / "encounters_kanto.json").read_text(encoding="utf-8"))
    encounters_by_name = {entry["name"]: entry for entry in encounters}
    locations = []

    for city in CITY_ORDER:
        encounter = encounters_by_name.get(city)
        locations.append(
            {
                "id": slug(city),
                "name": city,
                "kind": "city",
                "region": "Kanto",
                "description": CITY_DESCRIPTIONS[city],
                "level_range": encounter.get("level_range", [1, 5]) if encounter else [1, 5],
                "encounter_enabled": bool(encounter),
                "capture_enabled": bool(encounter),
            }
        )

    for route_number in range(1, 26):
        name = f"Route {route_number}"
        encounter = encounters_by_name.get(name)
        locations.append(
            {
                "id": slug(name),
                "name": name,
                "kind": "route",
                "region": "Kanto",
                "description": route_description(name),
                "level_range": encounter.get("level_range", [max(2, route_number), max(5, route_number + 6)]) if encounter else [max(2, route_number), max(5, route_number + 6)],
                "encounter_enabled": bool(encounter),
                "capture_enabled": bool(encounter),
            }
        )

    known = {location["name"] for location in locations}
    for encounter in encounters:
        if encounter["name"] in known:
            continue
        name = encounter["name"]
        locations.append(
            {
                "id": slug(name),
                "name": name,
                "kind": encounter.get("kind", "area"),
                "region": "Kanto",
                "description": SPECIAL_DESCRIPTIONS.get(name, f"Area especial de Kanto: {name}."),
                "level_range": encounter.get("level_range", [1, 5]),
                "encounter_enabled": True,
                "capture_enabled": True,
            }
        )

    locations_by_id = {location["id"]: location for location in locations}
    for encounter in encounters:
        encounter["location_id"] = slug(encounter["name"])
        if encounter["location_id"] in locations_by_id:
            encounter["kind"] = locations_by_id[encounter["location_id"]]["kind"]

    (DATA_DIR / "locations_kanto.json").write_text(json.dumps(locations, indent=2, ensure_ascii=False), encoding="utf-8")
    (DATA_DIR / "encounters_kanto.json").write_text(json.dumps(encounters, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(locations)} locations and updated {len(encounters)} encounter tables.")


if __name__ == "__main__":
    build()

