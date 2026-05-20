from __future__ import annotations

from dataclasses import dataclass

from .attributes import PlayerAttributes
from .economy import calculate_money_gain
from .utils import clamp


CAREER_STUDENT = "Estudante da academia"
CAREER_TRAINER = "Treinador"
CAREER_BREEDER = "Criador"
CAREER_COORDINATOR = "Coordenador"
CAREER_RESEARCHER = "Pesquisador"
CAREER_EXPLORER = "Explorador"
CAREER_SCIENTIST = "Cientista"
CAREER_BERRY_COLLECTOR = "Coletor de Berrys"
CAREER_BALL_CRAFTER = "Construtor de Pokebolas"
CAREER_FARM_CARETAKER = "Cuidador de Fazenda"
CAREER_BUILDER = "Construtor"
CAREER_MERCHANT = "Comerciante"
CAREER_CRIMINAL = "Criminoso"

CAREERS = (
    CAREER_STUDENT,
    CAREER_TRAINER,
    CAREER_BREEDER,
    CAREER_COORDINATOR,
    CAREER_RESEARCHER,
    CAREER_EXPLORER,
    CAREER_SCIENTIST,
    CAREER_BERRY_COLLECTOR,
    CAREER_BALL_CRAFTER,
    CAREER_FARM_CARETAKER,
    CAREER_BUILDER,
    CAREER_MERCHANT,
    CAREER_CRIMINAL,
)

COMMON_CAREERS = (
    CAREER_BERRY_COLLECTOR,
    CAREER_BALL_CRAFTER,
    CAREER_FARM_CARETAKER,
    CAREER_BUILDER,
    CAREER_MERCHANT,
)

CAREER_RANK_XP = [30, 60, 100, 150, 220]

CAREER_RANK_LABELS = {
    0: "Iniciante",
    1: "Novato",
    2: "Intermediario",
    3: "Avancado",
    4: "Expert",
    5: "Mestre",
}


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
    if age < 5:
        return []
    if age < 10:
        return [CAREER_STUDENT]
    careers = [CAREER_STUDENT]
    if has_pokemon:
        careers.extend([CAREER_TRAINER, CAREER_BREEDER, CAREER_COORDINATOR])
    if age >= 16:
        careers.extend(COMMON_CAREERS)
        careers.append(CAREER_CRIMINAL)
    if age >= 18:
        careers.extend([CAREER_RESEARCHER, CAREER_EXPLORER, CAREER_SCIENTIST])
    return careers


def default_career_for_age(age: int) -> str | None:
    if 5 <= age <= 15:
        return CAREER_STUDENT
    return None


def rank_money_multiplier(rank: int) -> float:
    return 1.0 + min(rank, 5) * 0.25


def career_progress(
    career: str | None,
    attributes: PlayerAttributes,
    age: int,
    career_rank: int = 0,
) -> CareerProgress:
    if attributes is None:
        from .attributes import generate_initial_attributes
        attributes = generate_initial_attributes()

    rank_mult = rank_money_multiplier(career_rank)

    if career == CAREER_STUDENT:
        allowance = int(20 * (1 + career_rank * 0.5))
        return CareerProgress(
            attribute_changes={"MEN": 1, "POK": 2 if age <= 15 else 1},
            money_gain=allowance,
            reputation_change=0,
            pokemon_xp_bonus=1 + career_rank,
            pokemon_happiness_bonus=1,
            pokemon_health_bonus=0,
            pokemon_beauty_bonus=0,
            note="Os estudos na academia melhoraram sua leitura sobre Pokemon.",
        )
    if career == CAREER_TRAINER:
        base = calculate_money_gain(110, attributes, specialty_factor=_trainer_specialty(attributes))
        money = int(base * rank_mult)
        return CareerProgress(
            attribute_changes={"PHY": 1, "POK": 1},
            money_gain=money,
            reputation_change=1 + (career_rank // 3),
            pokemon_xp_bonus=12 + attributes.POK // 10 + career_rank * 3,
            pokemon_happiness_bonus=1,
            pokemon_health_bonus=-1,
            pokemon_beauty_bonus=0,
            note="Treinos e pequenas batalhas deixaram sua equipe mais experiente.",
        )
    if career == CAREER_BREEDER:
        base = calculate_money_gain(90, attributes, specialty_factor=1 + ((attributes.POK + attributes.MEN) / 350))
        money = int(base * rank_mult)
        return CareerProgress(
            attribute_changes={"POK": 1, "MEN": 1},
            money_gain=money,
            reputation_change=1,
            pokemon_xp_bonus=4 + career_rank,
            pokemon_happiness_bonus=3 + career_rank,
            pokemon_health_bonus=3 + career_rank,
            pokemon_beauty_bonus=1,
            note="Cuidado constante fortaleceu a saude e o vinculo dos Pokemon.",
        )
    if career == CAREER_COORDINATOR:
        base = calculate_money_gain(95, attributes, specialty_factor=1 + ((attributes.POK + attributes.LUK) / 400))
        money = int(base * rank_mult)
        return CareerProgress(
            attribute_changes={"POK": 1, "LUK": 1},
            money_gain=money,
            reputation_change=2 + (career_rank // 2),
            pokemon_xp_bonus=5 + career_rank,
            pokemon_happiness_bonus=2,
            pokemon_health_bonus=0,
            pokemon_beauty_bonus=3 + career_rank,
            note="Ensaios e apresentacoes melhoraram a presenca da sua equipe.",
        )
    if career == CAREER_RESEARCHER:
        base = calculate_money_gain(120, attributes, specialty_factor=1 + ((attributes.MEN + attributes.POK) / 320))
        money = int(base * rank_mult)
        return CareerProgress(
            attribute_changes={"MEN": 2, "POK": 1},
            money_gain=money,
            reputation_change=1 + (career_rank // 2),
            pokemon_xp_bonus=4 + career_rank,
            pokemon_happiness_bonus=1,
            pokemon_health_bonus=0,
            pokemon_beauty_bonus=0,
            note="Pesquisas e catalogacao ampliaram seu conhecimento sobre Pokemon.",
        )
    if career == CAREER_EXPLORER:
        base = calculate_money_gain(105, attributes, specialty_factor=1 + ((attributes.PHY + attributes.LUK + attributes.POK) / 420))
        money = int(base * rank_mult)
        return CareerProgress(
            attribute_changes={"PHY": 1, "POK": 1, "LUK": 1},
            money_gain=money,
            reputation_change=1,
            pokemon_xp_bonus=9 + career_rank * 2,
            pokemon_happiness_bonus=1,
            pokemon_health_bonus=-1,
            pokemon_beauty_bonus=0,
            note="Exploracoes por habitats perigosos renderam experiencia e descobertas.",
        )
    if career == CAREER_SCIENTIST:
        base = calculate_money_gain(135, attributes, specialty_factor=1 + ((attributes.MEN * 2 + attributes.POK) / 450))
        money = int(base * rank_mult)
        return CareerProgress(
            attribute_changes={"MEN": 2, "POK": 1},
            money_gain=money,
            reputation_change=1 + (career_rank // 3),
            pokemon_xp_bonus=3 + career_rank,
            pokemon_happiness_bonus=0,
            pokemon_health_bonus=1,
            pokemon_beauty_bonus=0,
            note="Trabalho cientifico em laboratorio trouxe renda e dados confiaveis.",
        )
    if career == CAREER_BERRY_COLLECTOR:
        base = calculate_money_gain(70, attributes, specialty_factor=1 + ((attributes.PHY + attributes.LUK + attributes.POK) / 500))
        money = int(base * rank_mult)
        return CareerProgress(
            attribute_changes={"PHY": 1, "POK": 1},
            money_gain=money,
            reputation_change=0,
            pokemon_xp_bonus=3 + career_rank,
            pokemon_happiness_bonus=1,
            pokemon_health_bonus=0,
            pokemon_beauty_bonus=0,
            note="Rotas de coleta renderam berries, pequenos contratos e conhecimento de habitats.",
        )
    if career == CAREER_BALL_CRAFTER:
        base = calculate_money_gain(100, attributes, specialty_factor=1 + ((attributes.MEN + attributes.POK) / 360))
        money = int(base * rank_mult)
        return CareerProgress(
            attribute_changes={"MEN": 1, "POK": 1},
            money_gain=money,
            reputation_change=1 if career_rank >= 2 else 0,
            pokemon_xp_bonus=2 + career_rank,
            pokemon_happiness_bonus=0,
            pokemon_health_bonus=0,
            pokemon_beauty_bonus=0,
            note="Oficinas de Pokebolas pagaram por precisao, paciencia e conhecimento tecnico.",
        )
    if career == CAREER_FARM_CARETAKER:
        base = calculate_money_gain(80, attributes, specialty_factor=1 + ((attributes.POK + attributes.MEN + attributes.PHY) / 460))
        money = int(base * rank_mult)
        return CareerProgress(
            attribute_changes={"POK": 1, "MEN": 1},
            money_gain=money,
            reputation_change=1 if career_rank >= 1 else 0,
            pokemon_xp_bonus=3 + career_rank,
            pokemon_happiness_bonus=3,
            pokemon_health_bonus=2,
            pokemon_beauty_bonus=0,
            note="Cuidados de fazenda melhoraram sua rotina com Pokemon domesticos e habitats calmos.",
        )
    if career == CAREER_BUILDER:
        base = calculate_money_gain(105, attributes, specialty_factor=1 + ((attributes.PHY * 2 + attributes.MEN) / 450))
        money = int(base * rank_mult)
        return CareerProgress(
            attribute_changes={"PHY": 2},
            money_gain=money,
            reputation_change=1,
            pokemon_xp_bonus=4 + career_rank,
            pokemon_happiness_bonus=0,
            pokemon_health_bonus=-1,
            pokemon_beauty_bonus=0,
            note="Obras, pontes e reparos urbanos trouxeram renda e resistencia fisica.",
        )
    if career == CAREER_MERCHANT:
        base = calculate_money_gain(115, attributes, specialty_factor=1 + ((attributes.MEN + attributes.LUK) / 340))
        money = int(base * rank_mult)
        return CareerProgress(
            attribute_changes={"MEN": 1, "LUK": 1},
            money_gain=money,
            reputation_change=1 + (career_rank // 2),
            pokemon_xp_bonus=2 + career_rank,
            pokemon_happiness_bonus=1,
            pokemon_health_bonus=0,
            pokemon_beauty_bonus=1,
            note="Compras, vendas e contatos locais fortaleceram sua presenca no comercio.",
        )
    if career == CAREER_CRIMINAL:
        base = calculate_money_gain(140, attributes, specialty_factor=1 + ((attributes.LUK + attributes.PHY + attributes.MEN) / 420))
        money = int(base * rank_mult)
        return CareerProgress(
            attribute_changes={"LUK": 1, "PHY": 1},
            money_gain=money,
            reputation_change=-(2 + career_rank // 2),
            pokemon_xp_bonus=8 + career_rank * 2,
            pokemon_happiness_bonus=-1,
            pokemon_health_bonus=-1,
            pokemon_beauty_bonus=0,
            note="Trabalhos suspeitos renderam dinheiro rapido, mas sua reputacao sofreu.",
        )
    return CareerProgress({}, 0, 0, 0, 0, 0, 0, "Voce passou o ano sem uma rotina definida.")


CAREER_POKEMON_BONUSES = {
    CAREER_TRAINER: {
        "species": {"Pidgeot", "Primeape", "Arcanine", "Gyarados", "Dragonite"},
        "types": {"Fighting", "Dragon"},
        "label": "Pokemon fortes ajudaram nos treinos e combates locais",
    },
    CAREER_BREEDER: {
        "species": {"Chansey", "Clefairy", "Jigglypuff", "Eevee", "Vulpix"},
        "types": {"Normal", "Fairy"},
        "label": "Pokemon gentis facilitaram cuidados e criacao",
    },
    CAREER_COORDINATOR: {
        "species": {"Vulpix", "Ninetales", "Persian", "Starmie", "Lapras", "Eevee"},
        "types": {"Psychic", "Ice"},
        "label": "Pokemon elegantes elevaram apresentacoes e eventos",
    },
    CAREER_RESEARCHER: {
        "species": {"Abra", "Kadabra", "Alakazam", "Magnemite", "Porygon", "Ditto"},
        "types": {"Psychic", "Electric"},
        "label": "Pokemon raros ou inteligentes aceleraram pesquisas",
    },
    CAREER_EXPLORER: {
        "species": {"Onix", "Dugtrio", "Lapras", "Scyther", "Pidgeot", "Rhyhorn"},
        "types": {"Ground", "Flying", "Water"},
        "label": "Pokemon de travessia ajudaram em rotas e cavernas",
    },
    CAREER_SCIENTIST: {
        "species": {"Magnemite", "Magneton", "Voltorb", "Electrode", "Porygon", "Grimer"},
        "types": {"Electric", "Poison"},
        "label": "Pokemon de laboratorio apoiaram experimentos controlados",
    },
    CAREER_BERRY_COLLECTOR: {
        "species": {"Oddish", "Gloom", "Bellsprout", "Weepinbell", "Paras", "Farfetchd"},
        "types": {"Grass", "Bug"},
        "label": "Pokemon de mata encontraram berries melhores",
    },
    CAREER_BALL_CRAFTER: {
        "species": {"Magnemite", "Magneton", "Voltorb", "Electrode", "Geodude", "Graveler"},
        "types": {"Electric", "Rock", "Steel"},
        "label": "Pokemon eletricos e minerais ajudaram na oficina",
    },
    CAREER_FARM_CARETAKER: {
        "species": {"Chansey", "Tauros", "Ponyta", "Rapidash", "Oddish", "Paras"},
        "types": {"Normal", "Grass"},
        "label": "Pokemon calmos e rurais mantiveram a fazenda estavel",
    },
    CAREER_BUILDER: {
        "species": {"Machop", "Machoke", "Machamp", "Geodude", "Graveler", "Golem", "Onix"},
        "types": {"Fighting", "Rock", "Ground"},
        "label": "Pokemon fortes ajudaram em obras e reparos",
    },
    CAREER_MERCHANT: {
        "species": {"Meowth", "Persian", "Porygon", "Abra", "Kadabra", "Eevee"},
        "types": {"Normal", "Psychic"},
        "label": "Pokemon carismaticos ou calculistas melhoraram negocios",
    },
    CAREER_CRIMINAL: {
        "species": {"Meowth", "Persian", "Koffing", "Weezing", "Ekans", "Arbok", "Zubat", "Golbat", "Gengar"},
        "types": {"Poison", "Dark", "Ghost"},
        "label": "Pokemon furtivos e intimidadores ajudaram em atividades suspeitas",
    },
}


def pokemon_work_bonus(career: str | None, pokemon_team: list) -> tuple[float, list[str]]:
    if not career or not pokemon_team:
        return 1.0, []
    rules = CAREER_POKEMON_BONUSES.get(career)
    if not rules:
        return 1.0, []
    matched = 0
    species_matches: list[str] = []
    wanted_species = set(rules.get("species", set()))
    wanted_types = set(rules.get("types", set()))
    for pokemon in pokemon_team:
        species = getattr(pokemon, "species", "")
        types = set(getattr(pokemon, "types", []) or [])
        if species in wanted_species or types.intersection(wanted_types):
            matched += 1
            if species and species not in species_matches:
                species_matches.append(species)
    if matched <= 0:
        return 1.0, []
    factor = float(clamp(1.0 + matched * 0.06, 1.0, 1.24))
    label = str(rules.get("label", "Seus Pokemon ajudaram no trabalho"))
    detail = ", ".join(species_matches[:3])
    note = f"{label}: {detail}." if detail else f"{label}."
    return factor, [note]


def try_career_rank_up(
    career: str,
    career_ranks: dict[str, int],
    career_xp: dict[str, int],
    xp_gained: int,
) -> tuple[dict[str, int], dict[str, int], str | None]:
    rank = int(career_ranks.get(career, 0))
    if rank >= 5:
        return career_ranks, career_xp, None
    xp = int(career_xp.get(career, 0)) + xp_gained
    needed = CAREER_RANK_XP[rank]
    message = None
    if xp >= needed:
        xp -= needed
        rank += 1
        career_ranks = {**career_ranks, career: rank}
        message = f"Sua dedicacao como {career} rendeu frutos: rank {CAREER_RANK_LABELS[rank]}!"
    career_xp = {**career_xp, career: xp}
    return career_ranks, career_xp, message


def career_rank_label(career: str, career_ranks: dict[str, int]) -> str:
    rank = int(career_ranks.get(career, 0))
    return CAREER_RANK_LABELS.get(rank, "Iniciante")


def _trainer_specialty(attributes: PlayerAttributes) -> float:
    return float(clamp(0.85 + (attributes.POK + attributes.PHY + attributes.LUK) / 420, 0.85, 1.55))
