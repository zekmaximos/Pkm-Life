from __future__ import annotations

from dataclasses import dataclass
import random

from .utils import clamp


CRIME_SENTENCES_MONTHS = {
    "attempted_pokemon_theft": 12,
    "pokemon_theft": 36,
    "black_market_trade": 10,
    "organized_rocket_activity": 60,
}


@dataclass(frozen=True)
class PrisonSentence:
    crime: str
    months: int
    fine: int
    text: str


def sentence_for_crime(crime: str, reputation: int = 0, career: str | None = None) -> PrisonSentence:
    base = CRIME_SENTENCES_MONTHS.get(crime, 6)
    if career == "Criminoso":
        base += 4
    if reputation <= -50:
        base += 6
    elif reputation <= -25:
        base += 3
    months = int(clamp(base, 1, 120))
    fine = {
        "attempted_pokemon_theft": 900,
        "pokemon_theft": 2600,
        "black_market_trade": 1800,
        "organized_rocket_activity": 5000,
    }.get(crime, 600)
    text = {
        "attempted_pokemon_theft": "tentativa de roubo de Pokemon",
        "pokemon_theft": "roubo de Pokemon",
        "black_market_trade": "negociacao no mercado negro",
        "organized_rocket_activity": "atividade organizada ligada a Equipe Rocket",
    }.get(crime, crime)
    return PrisonSentence(crime=crime, months=months, fine=fine, text=text)


def imprison(character, crime: str) -> PrisonSentence:
    sentence = sentence_for_crime(crime, getattr(character, "reputation", 0), getattr(character, "career", None))
    flags = character.flags
    flags["in_prison"] = True
    flags["prison_months_remaining"] = int(flags.get("prison_months_remaining", 0)) + sentence.months
    flags["prison_crime"] = sentence.crime
    flags["official_event_ban"] = True
    character.money = max(0, character.money - min(character.money, sentence.fine))
    if hasattr(character, "add_history"):
        character.add_history(
            f"Voce foi detido por {sentence.text} e recebeu pena de {sentence.months} meses.",
            ["crime", "prison"],
        )
    return sentence


def progress_prison_time(character, months: int) -> tuple[bool, str | None]:
    if not character.flags.get("in_prison"):
        return False, None
    remaining = int(character.flags.get("prison_months_remaining", 0))
    served = min(months, remaining)
    remaining -= served
    character.flags["prison_months_remaining"] = remaining
    health_loss = max(1, served // 3)
    note_parts: list[str] = []
    fight_chance = 0.04 * served
    if getattr(character, "career", None) == "Criminoso":
        fight_chance += 0.05
    if int(character.flags.get("suspicion", 0)) >= 20:
        fight_chance += 0.04
    if random.random() < min(0.45, fight_chance):
        extra_loss = random.randint(6, 18)
        health_loss += extra_loss
        character.flags["last_prison_fight"] = {
            "months_served": served,
            "health_loss": extra_loss,
        }
        note_parts.append(f"Voce se envolveu em uma briga na prisao e perdeu {extra_loss} de saude")
    character.health = max(0, min(100, character.health - health_loss))
    if remaining <= 0:
        character.flags["in_prison"] = False
        character.flags["prison_months_remaining"] = 0
        character.add_history("Voce saiu da prisao e voltou para Kanto livre, mas marcado pela reputacao.", ["crime", "prison"])
        release = "Voce cumpriu sua pena e saiu da prisao."
        if note_parts:
            release += " " + " ".join(note_parts) + "."
        return True, release
    base = f"Voce cumpriu {served} mes(es) de pena. Restam {remaining} mes(es)."
    if note_parts:
        base += " " + " ".join(note_parts) + "."
    return True, base
