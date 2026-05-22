from __future__ import annotations

from dataclasses import dataclass
import random

from .character import Character
from .attributes import ATTRIBUTE_KEYS


@dataclass
class EventChoice:
    text: str
    effects: dict
    history_entry: str
    chance: float | None = None
    failure_effects: dict | None = None
    failure_history_entry: str | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "EventChoice":
        return cls(
            text=data["text"],
            effects=data.get("effects", {}),
            history_entry=data.get("history_entry", ""),
            chance=data.get("chance"),
            failure_effects=data.get("failure_effects"),
            failure_history_entry=data.get("failure_history_entry"),
        )


@dataclass
class AppliedChoiceResult:
    history_entry: str
    effects: dict
    succeeded: bool


@dataclass
class LifeEvent:
    event_id: str
    title: str
    text: str
    min_age: int
    max_age: int
    phase: str | None
    region: str | None
    city: str | None
    choices: list[EventChoice]
    once: bool = False
    tags: list[str] | None = None
    base_weight: float = 1.0
    min_event_chance: float | None = None
    conditions: dict | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "LifeEvent":
        return cls(
            event_id=data["id"],
            title=data["title"],
            text=data["text"],
            min_age=data["min_age"],
            max_age=data["max_age"],
            phase=data.get("phase"),
            region=data.get("region"),
            city=data.get("city"),
            choices=[EventChoice.from_dict(choice) for choice in data.get("choices", [])],
            once=data.get("once", False),
            tags=data.get("tags", []),
            base_weight=float(data.get("base_weight", 1.0)),
            min_event_chance=data.get("min_event_chance"),
            conditions=data.get("conditions", {}),
        )


def valid_events(character: Character, events: list[LifeEvent]) -> list[LifeEvent]:
    seen_key = "seen_events"
    seen = set(character.flags.get(seen_key, []))
    valid = []
    for event in events:
        if event.once and event.event_id in seen:
            continue
        if not (event.min_age <= character.age <= event.max_age):
            continue
        if event.phase and event.phase != character.phase:
            continue
        if event.region and event.region != character.region:
            continue
        if event.city and event.city != character.current_city:
            continue
        if not _conditions_match(character, event.conditions or {}):
            continue
        valid.append(event)
    return valid


def choose_event(character: Character, events: list[LifeEvent]) -> LifeEvent | None:
    candidates = valid_events(character, events)
    if not candidates:
        return None
    return random.choices(candidates, weights=[max(0.05, event.base_weight) for event in candidates], k=1)[0]


def choose_weighted_event(
    character: Character,
    events: list[LifeEvent],
    city_focus: list[str] | None = None,
) -> LifeEvent | None:
    candidates = valid_events(character, events)
    if not candidates:
        return None
    recent: list[str] = list(character.flags.get("recent_event_ids", []))
    weights = []
    for event in candidates:
        w = event_weight(character, event, city_focus or [])
        # Penaliza eventos vistos recentemente (cooldown de 5 eventos)
        if event.event_id in recent:
            position = len(recent) - 1 - recent[::-1].index(event.event_id)
            penalty = max(0.05, 1.0 - (len(recent) - position) * 0.18)
            w *= penalty
        weights.append(w)
    chosen = random.choices(candidates, weights=weights, k=1)[0]
    # Atualiza cooldown (mantém fila de 5 mais recentes)
    if chosen.event_id in recent:
        recent.remove(chosen.event_id)
    recent.append(chosen.event_id)
    if len(recent) > 5:
        recent.pop(0)
    character.flags["recent_event_ids"] = recent
    return chosen


def event_occurrence_chance(character: Character, city_focus: list[str] | None = None) -> float:
    city_focus = city_focus or []
    chance = 0.30
    chance += (character.attributes.LUK - 50) * 0.002
    chance += (character.attributes.POK - 50) * 0.001
    chance += min(0.08, max(0, len(character.team)) * 0.015)
    chance += min(0.05, sum(character.inventory.values()) * 0.002)
    if character.career:
        chance += 0.05
    if city_focus:
        chance += 0.04
    if character.health < 35:
        chance += 0.08
    return max(0.08, min(0.85, chance))


def should_roll_life_event(
    character: Character,
    events: list[LifeEvent],
    city_focus: list[str] | None = None,
) -> bool:
    candidates = valid_events(character, events)
    if not candidates:
        return False
    chance = event_occurrence_chance(character, city_focus)
    chance = max(chance, *(event.min_event_chance or 0 for event in candidates))
    return random.random() <= chance


def event_weight(character: Character, event: LifeEvent, city_focus: list[str]) -> float:
    tags = set(event.tags or [])
    weight = max(0.05, event.base_weight)
    if tags.intersection(city_focus):
        weight += 1.25
    if character.career:
        career_tag = _career_tag(character.career)
        if career_tag in tags:
            weight += 1.75
        elif tags.intersection({"battle", "care", "contest", "academy"}) and "career_transition" not in tags:
            weight *= 0.75
    if character.team and tags.intersection({"pokemon", "battle", "care", "contest"}):
        weight += 0.55
    if character.inventory.get("Poke Ball", 0) > 0 and tags.intersection({"capture", "wild"}):
        weight += 0.5
    if character.attributes.POK >= 65 and tags.intersection({"academy", "research", "pokemon", "capture"}):
        weight += 0.45
    if character.attributes.PHY >= 65 and tags.intersection({"risk", "battle", "route"}):
        weight += 0.35
    if character.attributes.MEN >= 65 and tags.intersection({"academy", "work", "research"}):
        weight += 0.35
    if character.attributes.LUK >= 65 and tags.intersection({"rare", "capture", "money"}):
        weight += 0.4
    if character.health < 35 and tags.intersection({"risk", "battle"}):
        weight *= 0.65
    return max(0.05, weight)


def apply_choice(character: Character, event: LifeEvent, choice: EventChoice) -> str:
    return apply_choice_result(character, event, choice).history_entry


def apply_choice_result(character: Character, event: LifeEvent, choice: EventChoice) -> AppliedChoiceResult:
    succeeded = choice.chance is None or random.random() <= _effective_choice_chance(character, choice)
    effects = choice.effects if succeeded else (choice.failure_effects or {})
    character.attributes.modify(_normalize_attribute_effects(effects.get("attributes", {})))
    character.health = max(0, min(100, character.health + int(effects.get("health", 0))))
    character.money = max(0, character.money + int(effects.get("money", 0)))
    character.reputation += int(effects.get("reputation", 0))
    if "career" in effects and _can_apply_career_change(event):
        character.career = effects["career"]
    item_effects = dict(effects.get("inventory", {}))
    item_effects.update(effects.get("items", {}))
    for item, amount in item_effects.items():
        character.inventory[item] = max(0, character.inventory.get(item, 0) + int(amount))
        if character.inventory[item] == 0:
            del character.inventory[item]
    for flag, value in effects.get("flags", {}).items():
        character.flags[flag] = value
    history_entry = choice.history_entry if succeeded else (choice.failure_history_entry or choice.history_entry)
    if history_entry:
        character.add_history(history_entry)
    if event.once:
        seen = list(character.flags.get("seen_events", []))
        if event.event_id not in seen:
            seen.append(event.event_id)
        character.flags["seen_events"] = seen
    return AppliedChoiceResult(history_entry=history_entry, effects=effects, succeeded=succeeded)


def _effective_choice_chance(character: Character, choice: EventChoice) -> float:
    chance = choice.chance if choice.chance is not None else 1.0
    luck_bonus = (character.attributes.LUK - 50) / 500
    return max(0.02, min(0.98, chance + luck_bonus))


def _conditions_match(character: Character, conditions: dict) -> bool:
    if not conditions:
        return True
    if conditions.get("requires_pokemon") and not (character.team or character.box):
        return False
    if conditions.get("requires_no_pokemon") and (character.team or character.box):
        return False
    if "career" in conditions and character.career != conditions["career"]:
        return False
    for item, amount in conditions.get("min_items", {}).items():
        if character.inventory.get(item, 0) < int(amount):
            return False
    for attr, value in conditions.get("min_attributes", {}).items():
        if character.attributes.get(attr, 0) < int(value):
            return False
    for flag in conditions.get("required_flags", []):
        if not character.flags.get(flag):
            return False
    for flag in conditions.get("forbidden_flags", []):
        if character.flags.get(flag):
            return False
    return True


def _career_tag(career: str) -> str:
    return {
        "Estudante da academia": "academy",
        "Treinador": "battle",
        "Criador": "care",
        "Coordenador": "contest",
        "Pesquisador": "research",
        "Explorador": "route",
        "Cientista": "research",
    }.get(career, career.lower())




def _can_apply_career_change(event: LifeEvent) -> bool:
    return "career_transition" in set(event.tags or [])


def _normalize_attribute_effects(effects: dict[str, int]) -> dict[str, int]:
    normalized: dict[str, int] = {}
    legacy_map = {
        "coragem": "PHY",
        "empatia": "POK",
        "inteligencia": "MEN",
        "disciplina": "MEN",
        "carisma": "LUK",
        "conhecimento_pokemon": "POK",
        "instinto_de_batalha": "PHY",
    }
    for key, value in effects.items():
        target = key if key in ATTRIBUTE_KEYS else legacy_map.get(key)
        if target:
            normalized[target] = normalized.get(target, 0) + int(value)
    return normalized
