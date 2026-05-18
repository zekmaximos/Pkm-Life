from __future__ import annotations

from dataclasses import dataclass

from .attributes import PlayerAttributes
from .economy import calculate_money_gain
from .utils import clamp


CAREER_STUDENT = "Estudante da academia"
CAREER_TRAINER = "Treinador"
CAREER_BREEDER = "Criador"
CAREER_COORDINATOR = "Coordenador"

CAREERS = (CAREER_STUDENT, CAREER_TRAINER, CAREER_BREEDER, CAREER_COORDINATOR)


@dataclass(frozen=True)
class CareerProgress:
    attribute_changes: dict[str, int]
    money_gain: int
    reputation_change: int
    pokemon_xp_bonus: int
    pokemon_happiness_bonus: int
    pokemon_health_bonus: int
    pokemon_beauty_bonus: int
    note: str


def available_careers(age: int, has_pokemon: bool) -> list[str]:
    if age < 10:
        return [CAREER_STUDENT]
    careers = [CAREER_STUDENT]
    if has_pokemon:
        careers.extend([CAREER_TRAINER, CAREER_BREEDER, CAREER_COORDINATOR])
    return careers


def default_career_for_age(age: int) -> str | None:
    if 5 <= age <= 15:
        return CAREER_STUDENT
    return None


def career_progress(career: str | None, attributes: PlayerAttributes, age: int) -> CareerProgress:
    if career == CAREER_STUDENT:
        money = 0
        return CareerProgress(
            attribute_changes={"MEN": 1, "POK": 2 if age <= 15 else 1},
            money_gain=money,
            reputation_change=0,
            pokemon_xp_bonus=1,
            pokemon_happiness_bonus=1,
            pokemon_health_bonus=0,
            pokemon_beauty_bonus=0,
            note="Os estudos na academia melhoraram sua leitura sobre Pokemon.",
        )
    if career == CAREER_TRAINER:
        money = calculate_money_gain(80, attributes, specialty_factor=_trainer_specialty(attributes))
        return CareerProgress(
            attribute_changes={"PHY": 1, "POK": 1},
            money_gain=money,
            reputation_change=1,
            pokemon_xp_bonus=10 + attributes.POK // 12,
            pokemon_happiness_bonus=1,
            pokemon_health_bonus=-2,
            pokemon_beauty_bonus=0,
            note="Treinos e pequenas batalhas deixaram sua equipe mais experiente.",
        )
    if career == CAREER_BREEDER:
        money = calculate_money_gain(65, attributes, specialty_factor=1 + ((attributes.POK + attributes.MEN) / 400))
        return CareerProgress(
            attribute_changes={"POK": 1, "MEN": 1},
            money_gain=money,
            reputation_change=1,
            pokemon_xp_bonus=4,
            pokemon_happiness_bonus=4,
            pokemon_health_bonus=3,
            pokemon_beauty_bonus=1,
            note="Cuidado constante fortaleceu a saude e o vinculo dos Pokemon.",
        )
    if career == CAREER_COORDINATOR:
        money = calculate_money_gain(70, attributes, specialty_factor=1 + ((attributes.POK + attributes.LUK) / 450))
        return CareerProgress(
            attribute_changes={"POK": 1, "LUK": 1},
            money_gain=money,
            reputation_change=2,
            pokemon_xp_bonus=5,
            pokemon_happiness_bonus=2,
            pokemon_health_bonus=0,
            pokemon_beauty_bonus=3,
            note="Ensaios e apresentacoes melhoraram a presenca da sua equipe.",
        )
    return CareerProgress({}, 0, 0, 0, 0, 0, 0, "Voce passou o ano sem uma rotina definida.")


def _trainer_specialty(attributes: PlayerAttributes) -> float:
    return float(clamp(0.85 + (attributes.POK + attributes.PHY + attributes.LUK) / 450, 0.85, 1.45))

