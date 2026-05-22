from __future__ import annotations

import random
from dataclasses import dataclass

from .utils import clamp


STUDENT_CAREER = "Estudante da academia"
KANTO_TYPES = (
    "Normal", "Fire", "Water", "Electric", "Grass", "Ice", "Fighting", "Poison",
    "Ground", "Flying", "Psychic", "Bug", "Rock", "Ghost", "Dragon",
)


@dataclass(frozen=True)
class AcademyFocus:
    focus_id: str
    name: str
    description: str
    attr_bonus: dict[str, int]
    capture_bonus: int = 0
    training_xp_bonus: int = 0
    care_bonus: int = 0
    beauty_bonus: int = 0
    work_bonus: int = 0


ACADEMY_FOCI: dict[str, AcademyFocus] = {
    "pokemon_types": AcademyFocus(
        "pokemon_types",
        "Tipos Pokemon",
        "Estuda vantagens, fraquezas e leitura de tipos.",
        {"POK": 2, "MEN": 1},
        training_xp_bonus=2,
    ),
    "capture_techniques": AcademyFocus(
        "capture_techniques",
        "Tecnicas de Captura",
        "Estuda abordagem, distancia, Pokebolas e comportamento de captura.",
        {"POK": 1, "LUK": 1},
        capture_bonus=8,
    ),
    "habitat_research": AcademyFocus(
        "habitat_research",
        "Habitats e Rotas",
        "Estuda onde especies aparecem e como ler sinais de ambiente.",
        {"POK": 1, "MEN": 1},
        capture_bonus=4,
        work_bonus=15,
    ),
    "battle_theory": AcademyFocus(
        "battle_theory",
        "Teoria de Batalha",
        "Estuda ritmo de combate, resistencia e tomada de decisao.",
        {"PHY": 1, "POK": 1},
        training_xp_bonus=7,
    ),
    "breeding_care": AcademyFocus(
        "breeding_care",
        "Cuidado e Criacao",
        "Estuda saude, felicidade, ovos e rotinas de cuidado.",
        {"POK": 1, "MEN": 1},
        care_bonus=3,
    ),
    "contest_culture": AcademyFocus(
        "contest_culture",
        "Cultura de Contest",
        "Estuda presenca, estilo, categorias e leitura de publico.",
        {"POK": 1, "LUK": 1},
        beauty_bonus=2,
    ),
}


def focus_choices() -> list[AcademyFocus]:
    return list(ACADEMY_FOCI.values())


def focus_by_id(focus_id: str | None) -> AcademyFocus | None:
    if not focus_id:
        return None
    return ACADEMY_FOCI.get(str(focus_id))


def current_focus(character) -> AcademyFocus | None:
    return focus_by_id(getattr(character, "flags", {}).get("academy_focus"))


def focus_label(character) -> str:
    focus = current_focus(character)
    if not focus:
        return "sem foco definido"
    studied_type = getattr(character, "flags", {}).get("academy_studied_type")
    if focus.focus_id == "pokemon_types" and studied_type:
        return f"{focus.name} ({studied_type})"
    return focus.name


def set_focus(character, focus_id: str, studied_type: str | None = None) -> bool:
    focus = focus_by_id(focus_id)
    if focus is None:
        return False
    character.flags["academy_focus"] = focus.focus_id
    if focus.focus_id == "pokemon_types":
        if studied_type not in KANTO_TYPES:
            studied_type = random.choice(KANTO_TYPES)
        character.flags["academy_studied_type"] = studied_type
    elif "academy_studied_type" in character.flags:
        character.flags.pop("academy_studied_type", None)
    return True


def ensure_focus(character) -> str | None:
    if getattr(character, "career", None) != STUDENT_CAREER or int(getattr(character, "age", 0)) < 10:
        return None
    if current_focus(character):
        return None
    focus_id = _suggest_focus_id(character)
    set_focus(character, focus_id)
    return f"Voce escolheu foco academico em {focus_label(character)}."


def apply_focus_progress(character, months: int = 12) -> str | None:
    if getattr(character, "career", None) != STUDENT_CAREER or int(getattr(character, "age", 0)) < 10:
        return None
    note = ensure_focus(character)
    focus = current_focus(character)
    if focus is None:
        return note
    progress = int(character.flags.get("academy_focus_progress", 0)) + max(1, months)
    completed_years = progress // 12
    character.flags["academy_focus_progress"] = progress % 12
    if completed_years <= 0:
        return note
    scaled_attrs = {
        key: value * completed_years
        for key, value in focus.attr_bonus.items()
        if value > 0
    }
    character.attributes.modify(scaled_attrs)
    years = dict(character.flags.get("academy_focus_years", {}))
    years[focus.focus_id] = int(years.get(focus.focus_id, 0)) + completed_years
    character.flags["academy_focus_years"] = years
    return note or f"Seus estudos em {focus_label(character)} renderam progresso academico."


def capture_bonus_for(character, species) -> int:
    focus = current_focus(character)
    if getattr(character, "career", None) != STUDENT_CAREER or focus is None:
        return 0
    bonus = focus.capture_bonus
    if focus.focus_id == "pokemon_types":
        studied_type = getattr(character, "flags", {}).get("academy_studied_type")
        if studied_type and studied_type in getattr(species, "types", []):
            bonus += 7
    return int(clamp(bonus, 0, 15))


def training_xp_bonus(character) -> int:
    focus = current_focus(character)
    if getattr(character, "career", None) != STUDENT_CAREER or focus is None:
        return 0
    return focus.training_xp_bonus


def care_bonus(character) -> int:
    focus = current_focus(character)
    if getattr(character, "career", None) != STUDENT_CAREER or focus is None:
        return 0
    return focus.care_bonus


def beauty_bonus(character) -> int:
    focus = current_focus(character)
    if getattr(character, "career", None) != STUDENT_CAREER or focus is None:
        return 0
    return focus.beauty_bonus


def work_bonus(character) -> int:
    focus = current_focus(character)
    if getattr(character, "career", None) != STUDENT_CAREER or focus is None:
        return 0
    return focus.work_bonus


def _suggest_focus_id(character) -> str:
    team = getattr(character, "team", [])
    if not team:
        return random.choice(("capture_techniques", "habitat_research", "pokemon_types"))
    if len(team) >= 2:
        return random.choice(("battle_theory", "breeding_care", "pokemon_types", "contest_culture"))
    return random.choice(tuple(ACADEMY_FOCI))
