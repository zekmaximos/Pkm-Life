from __future__ import annotations

from dataclasses import dataclass
import random

from .utils import clamp


@dataclass(frozen=True)
class MortalityCheck:
    died: bool
    chance: float
    cause: str | None = None


def is_dead(character) -> bool:
    return bool(getattr(character, "flags", {}).get("dead"))


def mortality_chance(character, months: int, context: str = "life", health_delta: int = 0) -> tuple[float, str]:
    age = int(getattr(character, "age", 0))
    health = int(getattr(character, "health", 100))
    period = max(1, months) / 12

    chance = 0.0002 * period
    cause = "complicacoes inesperadas"

    if age >= 50:
        chance += ((age - 49) ** 1.55) / 18000 * period
        cause = "velhice"
    if age >= 70:
        chance += ((age - 69) ** 1.45) / 4500 * period
        cause = "complicacoes da idade avancada"
    if age >= 90:
        chance += 0.08 * period

    if health <= 0:
        chance += 0.32
        cause = "colapso de saude"
    elif health < 15:
        chance += 0.12 * period
        cause = "estado critico de saude"
    elif health < 30:
        chance += 0.045 * period
        cause = "doenca e fragilidade"
    elif health < 50:
        chance += 0.012 * period
        cause = "saude debilitada"

    if health_delta <= -20:
        chance += min(0.045, abs(health_delta) / 900)
        cause = "ferimentos recentes"

    if context == "prison":
        chance *= 2.4
        if health < 45:
            chance += 0.025 * period
        cause = "complicacoes durante a prisao"
    elif context == "fight":
        chance += 0.003 * period
        if health < 25:
            chance += 0.015 * period
        cause = "ferimentos em briga"
    elif context == "crime":
        chance *= 0.72
        if health < 25:
            chance += 0.006 * period
        cause = "ferimentos em atividade criminal"
    elif context == "illness":
        chance += 0.020 * period
        cause = "doenca"

    if getattr(character, "career", None) == "Criminoso" and context not in {"prison"}:
        chance *= 0.82

    return float(clamp(chance, 0.0, 0.85)), cause


def check_mortality(character, months: int, context: str = "life", health_delta: int = 0) -> MortalityCheck:
    if is_dead(character):
        return MortalityCheck(True, 1.0, character.flags.get("death_cause", "morte"))
    chance, cause = mortality_chance(character, months, context, health_delta)
    if random.random() <= chance:
        mark_dead(character, cause)
        return MortalityCheck(True, chance, cause)
    character.flags["last_mortality_chance"] = round(chance, 4)
    return MortalityCheck(False, chance, None)


def mark_dead(character, cause: str) -> None:
    character.flags["dead"] = True
    character.flags["death_cause"] = cause
    character.flags["death_age"] = int(getattr(character, "age", 0))
    character.health = 0
    if hasattr(character, "add_history"):
        character.add_history(f"Voce morreu aos {character.age} anos por {cause}.", ["death", "game_over"])
