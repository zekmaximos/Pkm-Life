from __future__ import annotations

import json
import time
from pathlib import Path
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
API = "https://pokeapi.co/api/v2"

STARTERS = {"Bulbasaur", "Charmander", "Squirtle"}
MYTHIC = {"Mew"}

LEGENDARY_LOCATIONS = {
    "Articuno": ["Seafoam Islands"],
    "Zapdos": ["Power Plant"],
    "Moltres": ["Victory Road"],
    "Mewtwo": ["Cerulean Cave"],
    "Mew": ["Mythic Event"],
}

SPECIFIC_LOCATIONS = {
    "Bulbasaur": [],
    "Ivysaur": [],
    "Venusaur": [],
    "Charmander": [],
    "Charmeleon": [],
    "Charizard": [],
    "Squirtle": [],
    "Wartortle": [],
    "Blastoise": [],
    "Caterpie": ["Viridian Forest", "Route 2", "Route 24"],
    "Metapod": ["Viridian Forest", "Route 2"],
    "Butterfree": ["Viridian Forest", "Route 24"],
    "Weedle": ["Viridian Forest", "Route 2", "Route 25"],
    "Kakuna": ["Viridian Forest", "Route 2"],
    "Beedrill": ["Viridian Forest", "Route 25"],
    "Pidgey": ["Pallet Town", "Route 1", "Route 2", "Route 5", "Route 6"],
    "Pidgeotto": ["Route 14", "Route 15", "Route 21"],
    "Pidgeot": ["Route 21"],
    "Rattata": ["Pallet Town", "Route 1", "Route 2", "Route 4", "Route 9"],
    "Raticate": ["Route 16", "Route 17", "Route 18", "Pokemon Mansion"],
    "Spearow": ["Route 3", "Route 4", "Route 9", "Route 10"],
    "Fearow": ["Route 17", "Route 18", "Victory Road"],
    "Ekans": ["Route 4", "Route 8", "Route 9", "Route 10"],
    "Arbok": ["Route 23", "Victory Road"],
    "Pikachu": ["Viridian Forest", "Power Plant"],
    "Raichu": ["Power Plant"],
    "Sandshrew": ["Route 4", "Route 8", "Route 9", "Route 10"],
    "Sandslash": ["Route 23", "Victory Road"],
    "Nidoran-F": ["Route 22", "Safari Zone"],
    "Nidorina": ["Safari Zone", "Route 23"],
    "Nidoqueen": ["Safari Zone"],
    "Nidoran-M": ["Route 22", "Safari Zone"],
    "Nidorino": ["Safari Zone", "Route 23"],
    "Nidoking": ["Safari Zone"],
    "Clefairy": ["Mt. Moon"],
    "Clefable": ["Mt. Moon"],
    "Vulpix": ["Route 7", "Route 8", "Pokemon Mansion"],
    "Ninetales": ["Pokemon Mansion"],
    "Jigglypuff": ["Route 3"],
    "Wigglytuff": ["Route 3"],
    "Zubat": ["Mt. Moon", "Rock Tunnel", "Seafoam Islands", "Victory Road"],
    "Golbat": ["Seafoam Islands", "Victory Road", "Cerulean Cave"],
    "Oddish": ["Route 5", "Route 6", "Route 7", "Route 12"],
    "Gloom": ["Route 12", "Route 13", "Route 14", "Route 15"],
    "Vileplume": ["Route 15"],
    "Paras": ["Mt. Moon", "Safari Zone"],
    "Parasect": ["Safari Zone", "Cerulean Cave"],
    "Venonat": ["Route 12", "Route 13", "Route 14", "Safari Zone"],
    "Venomoth": ["Safari Zone", "Victory Road"],
    "Diglett": ["Diglett's Cave"],
    "Dugtrio": ["Diglett's Cave"],
    "Meowth": ["Route 5", "Route 6", "Route 7", "Route 8"],
    "Persian": ["Route 7", "Route 8"],
    "Psyduck": ["Route 24", "Route 25", "Seafoam Islands", "Safari Zone"],
    "Golduck": ["Seafoam Islands", "Cerulean Cave"],
    "Mankey": ["Route 3", "Route 4", "Route 22", "Route 23"],
    "Primeape": ["Route 23", "Victory Road"],
    "Growlithe": ["Route 7", "Route 8", "Pokemon Mansion"],
    "Arcanine": ["Pokemon Mansion"],
    "Poliwag": ["Pallet Town", "Viridian City", "Route 22", "Cerulean City"],
    "Poliwhirl": ["Route 22", "Cerulean City", "Safari Zone"],
    "Poliwrath": ["Cerulean Cave"],
    "Abra": ["Route 24", "Route 25"],
    "Kadabra": ["Cerulean Cave"],
    "Alakazam": ["Cerulean Cave"],
    "Machop": ["Rock Tunnel", "Victory Road"],
    "Machoke": ["Victory Road", "Cerulean Cave"],
    "Machamp": ["Victory Road"],
    "Bellsprout": ["Route 5", "Route 6", "Route 7", "Route 12"],
    "Weepinbell": ["Route 12", "Route 13", "Route 14", "Route 15"],
    "Victreebel": ["Route 15"],
    "Tentacool": ["Route 19", "Route 20", "Route 21", "Cinnabar Island", "Seafoam Islands"],
    "Tentacruel": ["Route 20", "Route 21", "Seafoam Islands"],
    "Geodude": ["Mt. Moon", "Rock Tunnel", "Victory Road"],
    "Graveler": ["Rock Tunnel", "Victory Road", "Cerulean Cave"],
    "Golem": ["Victory Road"],
    "Ponyta": ["Pokemon Mansion", "Cinnabar Island"],
    "Rapidash": ["Pokemon Mansion"],
    "Slowpoke": ["Route 10", "Seafoam Islands", "Cerulean Cave"],
    "Slowbro": ["Seafoam Islands", "Cerulean Cave"],
    "Magnemite": ["Power Plant"],
    "Magneton": ["Power Plant", "Cerulean Cave"],
    "Farfetchd": ["Vermilion City"],
    "Doduo": ["Route 16", "Route 17", "Route 18", "Safari Zone"],
    "Dodrio": ["Route 17", "Route 18", "Safari Zone"],
    "Seel": ["Seafoam Islands", "Cinnabar Island"],
    "Dewgong": ["Seafoam Islands"],
    "Grimer": ["Pokemon Mansion", "Celadon City"],
    "Muk": ["Pokemon Mansion"],
    "Shellder": ["Vermilion City", "Cinnabar Island", "Seafoam Islands"],
    "Cloyster": ["Seafoam Islands"],
    "Gastly": ["Pokemon Tower", "Lavender Town"],
    "Haunter": ["Pokemon Tower", "Lavender Town"],
    "Gengar": ["Pokemon Tower"],
    "Onix": ["Rock Tunnel", "Victory Road"],
    "Drowzee": ["Route 11"],
    "Hypno": ["Route 11", "Cerulean Cave"],
    "Krabby": ["Route 6", "Route 11", "Vermilion City", "Seafoam Islands"],
    "Kingler": ["Route 23", "Seafoam Islands"],
    "Voltorb": ["Power Plant", "Route 10"],
    "Electrode": ["Power Plant", "Cerulean Cave"],
    "Exeggcute": ["Safari Zone"],
    "Exeggutor": ["Safari Zone"],
    "Cubone": ["Pokemon Tower", "Rock Tunnel"],
    "Marowak": ["Pokemon Tower", "Victory Road"],
    "Hitmonlee": ["Saffron City"],
    "Hitmonchan": ["Saffron City"],
    "Lickitung": ["Route 18"],
    "Koffing": ["Pokemon Mansion", "Celadon City"],
    "Weezing": ["Pokemon Mansion"],
    "Rhyhorn": ["Safari Zone", "Victory Road"],
    "Rhydon": ["Victory Road", "Cerulean Cave"],
    "Chansey": ["Safari Zone", "Cerulean Cave"],
    "Tangela": ["Route 21", "Pallet Town"],
    "Kangaskhan": ["Safari Zone"],
    "Horsea": ["Route 19", "Route 20", "Cinnabar Island"],
    "Seadra": ["Route 20", "Cinnabar Island", "Seafoam Islands"],
    "Goldeen": ["Route 6", "Route 22", "Route 23", "Cerulean City"],
    "Seaking": ["Route 23", "Cerulean Cave"],
    "Staryu": ["Pallet Town", "Cinnabar Island", "Seafoam Islands"],
    "Starmie": ["Seafoam Islands"],
    "Mr-Mime": ["Route 2"],
    "Scyther": ["Safari Zone"],
    "Jynx": ["Cerulean City"],
    "Electabuzz": ["Power Plant"],
    "Magmar": ["Pokemon Mansion"],
    "Pinsir": ["Safari Zone"],
    "Tauros": ["Safari Zone"],
    "Magikarp": ["Pallet Town", "Viridian City", "Route 4", "Route 10", "Route 22"],
    "Gyarados": ["Route 20", "Seafoam Islands", "Cerulean Cave"],
    "Lapras": ["Silph Co.", "Seafoam Islands"],
    "Ditto": ["Route 13", "Route 14", "Route 15", "Pokemon Mansion"],
    "Eevee": ["Celadon City"],
    "Vaporeon": ["Celadon City"],
    "Jolteon": ["Celadon City"],
    "Flareon": ["Celadon City"],
    "Porygon": ["Celadon City"],
    "Omanyte": ["Cinnabar Island"],
    "Omastar": ["Cinnabar Island"],
    "Kabuto": ["Cinnabar Island"],
    "Kabutops": ["Cinnabar Island"],
    "Aerodactyl": ["Cinnabar Island"],
    "Snorlax": ["Route 12", "Route 16"],
    "Dratini": ["Safari Zone"],
    "Dragonair": ["Safari Zone", "Cerulean Cave"],
    "Dragonite": ["Cerulean Cave"],
}

LOCATION_META = {
    "Pallet Town": ("city", 2, 5),
    "Viridian City": ("city", 3, 7),
    "Pewter City": ("city", 5, 9),
    "Cerulean City": ("city", 8, 16),
    "Vermilion City": ("city", 10, 18),
    "Lavender Town": ("city", 14, 24),
    "Celadon City": ("city", 16, 30),
    "Fuchsia City": ("city", 22, 35),
    "Saffron City": ("city", 24, 38),
    "Cinnabar Island": ("city", 30, 45),
    "Indigo Plateau": ("city", 45, 60),
    "Viridian Forest": ("forest", 3, 8),
    "Mt. Moon": ("cave", 7, 14),
    "Rock Tunnel": ("cave", 15, 25),
    "Diglett's Cave": ("cave", 14, 30),
    "Pokemon Tower": ("tower", 18, 32),
    "Power Plant": ("dungeon", 25, 42),
    "Pokemon Mansion": ("dungeon", 28, 45),
    "Safari Zone": ("wild_area", 20, 35),
    "Seafoam Islands": ("cave", 30, 50),
    "Victory Road": ("cave", 38, 58),
    "Cerulean Cave": ("cave", 50, 70),
    "Silph Co.": ("gift", 15, 25),
    "Mythic Event": ("special", 50, 70),
}

for route_num in range(1, 26):
    base = max(2, min(45, route_num * 2))
    LOCATION_META[f"Route {route_num}"] = ("route", base, base + 7)


def fetch(path: str) -> dict:
    request = Request(f"{API}{path}", headers={"User-Agent": "PokeLifeDataBuilder/1.0"})
    with urlopen(request, timeout=30) as response:
        time.sleep(0.04)
        return json.loads(response.read().decode("utf-8"))


def title_name(name: str) -> str:
    custom = {
        "mr-mime": "Mr-Mime",
        "nidoran-f": "Nidoran-F",
        "nidoran-m": "Nidoran-M",
        "farfetchd": "Farfetchd",
    }
    if name in custom:
        return custom[name]
    return "-".join(part.capitalize() for part in name.split("-"))


def clamp(value: float, minimum: int = 1, maximum: int = 100) -> int:
    return int(max(minimum, min(maximum, round(value))))


def stat_map(pokemon: dict) -> dict[str, int]:
    return {item["stat"]["name"]: item["base_stat"] for item in pokemon["stats"]}


def game_stats(stats: dict[str, int], types: list[str], legendary: bool, mythical: bool) -> dict[str, int]:
    combat = stats["attack"] * 0.32 + stats["special-attack"] * 0.32 + stats["speed"] * 0.18 + stats["defense"] * 0.08 + stats["special-defense"] * 0.10
    healthy = stats["hp"] * 0.45 + stats["defense"] * 0.28 + stats["special-defense"] * 0.27
    beauty = stats["speed"] * 0.34 + stats["special-attack"] * 0.24 + stats["special-defense"] * 0.12 + stats["hp"] * 0.10 + 18
    occult = stats["special-attack"] * 0.28 + stats["special-defense"] * 0.24 + stats["speed"] * 0.10
    if any(t in {"Psychic", "Ghost", "Dragon"} for t in types):
        occult += 24
    if any(t in {"Electric", "Ice", "Fire"} for t in types):
        occult += 10
    if legendary:
        occult += 28
    if mythical:
        occult += 35
    if any(t in {"Water", "Ice", "Psychic", "Dragon", "Flying"} for t in types):
        beauty += 10
    return {
        "base_combat": clamp(combat),
        "base_beauty": clamp(beauty),
        "base_healthy": clamp(healthy),
        "base_occult": clamp(occult),
    }


def parse_chain(node: dict, mapping: dict[str, list[dict]]) -> None:
    source = title_name(node["species"]["name"])
    for child in node["evolves_to"]:
        target = title_name(child["species"]["name"])
        detail = child["evolution_details"][0] if child["evolution_details"] else {}
        trigger = detail.get("trigger", {}).get("name") if detail.get("trigger") else "unknown"
        item = detail.get("item", {}).get("name") if detail.get("item") else None
        mapping.setdefault(source, []).append(
            {
                "species": target,
                "method": trigger or "unknown",
                "level": detail.get("min_level"),
                "item": item,
                "min_happiness": detail.get("min_happiness"),
            }
        )
        parse_chain(child, mapping)


def rarity_for(name: str, stats: dict[str, int], types: list[str], legendary: bool, mythical: bool, stage_hint: int) -> str:
    total = sum(stats.values())
    if mythical:
        return "mythic"
    if legendary:
        return "legendary"
    if name in STARTERS:
        return "rare"
    if stage_hint >= 3 or total >= 500:
        return "very_rare"
    if total >= 420:
        return "rare"
    if total >= 330 or any(t in {"Dragon", "Psychic", "Ghost", "Ice"} for t in types):
        return "uncommon"
    return "common"


def initial_stage_hints(evolutions: dict[str, list[dict]]) -> dict[str, int]:
    stages: dict[str, int] = {}
    for source in evolutions:
        stages.setdefault(source, 1)
    changed = True
    while changed:
        changed = False
        for source, targets in evolutions.items():
            source_stage = stages.get(source, 1)
            for target in targets:
                target_name = target["species"]
                next_stage = min(3, source_stage + 1)
                if stages.get(target_name, 1) < next_stage:
                    stages[target_name] = next_stage
                    changed = True
    return stages


def encounter_weight(rarity: str, stage: int, legendary: bool) -> int:
    if legendary:
        return 1
    base = {"common": 55, "uncommon": 30, "rare": 14, "very_rare": 6, "legendary": 1, "mythic": 1}.get(rarity, 12)
    return max(1, base - ((stage - 1) * 8))


def build() -> None:
    evolution_map: dict[str, list[dict]] = {}
    species_payloads: dict[int, dict] = {}
    pokemon_payloads: dict[int, dict] = {}

    for pokedex_id in range(1, 152):
        pokemon = fetch(f"/pokemon/{pokedex_id}")
        species = fetch(f"/pokemon-species/{pokedex_id}")
        pokemon_payloads[pokedex_id] = pokemon
        species_payloads[pokedex_id] = species
        chain_id = species["evolution_chain"]["url"].rstrip("/").split("/")[-1]
        if chain_id:
            chain = fetch(f"/evolution-chain/{chain_id}")
            parse_chain(chain["chain"], evolution_map)

    stage_hints = initial_stage_hints(evolution_map)
    pokemon_rows = []
    encounters_by_location: dict[str, list[dict]] = {}

    for pokedex_id in range(1, 152):
        pokemon = pokemon_payloads[pokedex_id]
        species = species_payloads[pokedex_id]
        name = title_name(pokemon["name"])
        types = [title_name(t["type"]["name"]) for t in pokemon["types"]]
        stats = stat_map(pokemon)
        legendary = bool(species["is_legendary"])
        mythical = bool(species["is_mythical"]) or name in MYTHIC
        stage = stage_hints.get(name, 1)
        rarity = rarity_for(name, stats, types, legendary, mythical, stage)
        locations = LEGENDARY_LOCATIONS.get(name, SPECIFIC_LOCATIONS.get(name, []))
        can_be_wild = bool(locations) and name not in STARTERS and not mythical
        evolutions = evolution_map.get(name, [])
        level_evolutions = [evo for evo in evolutions if evo.get("level")]
        first_evolution = level_evolutions[0] if level_evolutions else (evolutions[0] if len(evolutions) == 1 else None)
        ability = title_name(pokemon["abilities"][0]["ability"]["name"]) if pokemon["abilities"] else "None"
        row = {
            "pokedex_id": pokedex_id,
            "name": name,
            "types": types,
            "ability": ability,
            "rarity": rarity,
            "habitats": locations,
            "evolution": first_evolution["species"] if first_evolution else None,
            "evolution_level": first_evolution.get("level") if first_evolution else None,
            "evolutions": evolutions,
            "evolution_stage": stage,
            "base_stats": {
                "hp": stats["hp"],
                "attack": stats["attack"],
                "defense": stats["defense"],
                "special_attack": stats["special-attack"],
                "special_defense": stats["special-defense"],
                "speed": stats["speed"],
            },
            **game_stats(stats, types, legendary, mythical),
            "can_be_wild": can_be_wild,
            "is_legendary": legendary,
            "is_mythic": mythical,
            "is_starter": name in STARTERS,
            "availability": {
                "wild": can_be_wild,
                "gift": name in STARTERS or name in {"Eevee", "Lapras", "Hitmonlee", "Hitmonchan", "Porygon", "Omanyte", "Kabuto", "Aerodactyl"},
                "event": legendary or mythical or name in {"Snorlax"},
                "evolution": stage > 1,
            },
        }
        pokemon_rows.append(row)

        for location in locations:
            kind, min_level, max_level = LOCATION_META.get(location, ("area", 8, 18))
            level_min = min(100, min_level + max(0, stage - 1) * 6)
            level_max = min(100, max_level + max(0, stage - 1) * 8)
            encounters_by_location.setdefault(location, []).append(
                {
                    "species": name,
                    "min_level": level_min,
                    "max_level": max(level_min, level_max),
                    "weight": encounter_weight(rarity, stage, legendary),
                }
            )

    locations_rows = []
    for location in sorted(encounters_by_location):
        kind, min_level, max_level = LOCATION_META.get(location, ("area", 8, 18))
        locations_rows.append(
            {
                "id": location.lower().replace(" ", "_").replace(".", "").replace("'", ""),
                "name": location,
                "kind": kind,
                "region": "Kanto",
                "level_range": [min_level, max_level],
                "encounters": sorted(encounters_by_location[location], key=lambda item: (item["min_level"], item["species"])),
            }
        )

    (DATA_DIR / "pokemon_kanto.json").write_text(json.dumps(pokemon_rows, indent=2, ensure_ascii=False), encoding="utf-8")
    (DATA_DIR / "encounters_kanto.json").write_text(json.dumps(locations_rows, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(pokemon_rows)} Pokemon and {len(locations_rows)} encounter locations.")


if __name__ == "__main__":
    build()
