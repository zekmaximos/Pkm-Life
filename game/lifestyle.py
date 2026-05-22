from __future__ import annotations

from dataclasses import dataclass

from .attributes import PlayerAttributes
from .pokemon import OwnedPokemon, PokemonSpecies


CITY_ECONOMY_TIERS = {
    "Pallet Town": 1,
    "Viridian City": 2,
    "Pewter City": 2,
    "Lavender Town": 2,
    "Cerulean City": 3,
    "Vermilion City": 3,
    "Fuchsia City": 3,
    "Seafoam Harbor": 3,
    "Celadon City": 5,
    "Saffron City": 6,
    "Cinnabar Island": 5,
    "Indigo Plateau": 6,
}


@dataclass(frozen=True)
class LifestyleOffer:
    offer_id: str
    name: str
    category: str
    tier: int
    price: int
    health_bonus: int = 0
    reputation_bonus: int = 0
    description: str = ""


@dataclass(frozen=True)
class CourseOffer:
    course_id: str
    name: str
    price: int
    min_city_tier: int
    attr_deltas: dict[str, int]
    description: str


@dataclass(frozen=True)
class TripOffer:
    trip_id: str
    name: str
    price: int
    min_city_tier: int
    health_gain: int
    attr_deltas: dict[str, int]
    description: str


LIFESTYLE_OFFERS = [
    LifestyleOffer("room_rental", "Quarto alugado simples", "casa", 1, 2500, 3, 0, "Um lugar pequeno para descansar melhor."),
    LifestyleOffer("small_house", "Casa pequena de cidade", "casa", 2, 9000, 6, 1, "Casa simples e estavel para uma vida local."),
    LifestyleOffer("route_cottage", "Casa de rota com quintal", "casa", 3, 22000, 9, 2, "Boa para quem cuida de Pokemon e ovos."),
    LifestyleOffer("city_apartment", "Apartamento urbano", "casa", 4, 45000, 10, 4, "Conforto em cidade grande."),
    LifestyleOffer("celadon_townhouse", "Casa nobre em Celadon", "casa", 5, 85000, 14, 7, "Imovel caro em centro comercial forte."),
    LifestyleOffer("saffron_penthouse", "Cobertura em Saffron", "casa", 6, 150000, 18, 12, "Luxo maximo dentro da economia de Kanto."),
    LifestyleOffer("used_bike", "Bicicleta usada", "veiculo", 1, 1800, 0, 0, "Facilita pequenas viagens."),
    LifestyleOffer("route_bike", "Bicicleta de rota", "veiculo", 2, 5000, 1, 0, "Boa para exploracao leve."),
    LifestyleOffer("delivery_scooter", "Moto de entregas", "veiculo", 3, 14000, 0, 1, "Ajuda trabalhos urbanos e comercio."),
    LifestyleOffer("travel_motorcycle", "Moto de viagem", "veiculo", 4, 32000, 1, 3, "Veiculo confiavel para rotas longas."),
    LifestyleOffer("compact_car", "Carro compacto", "veiculo", 5, 70000, 2, 5, "Conforto para cidade grande."),
    LifestyleOffer("luxury_car", "Carro de luxo", "veiculo", 6, 130000, 2, 10, "Simbolo de reputacao alta."),
    LifestyleOffer("plain_clothes", "Roupas simples", "roupa", 1, 600, 0, 0, "Visual limpo e barato."),
    LifestyleOffer("work_uniform", "Uniforme de trabalho", "roupa", 2, 1800, 0, 1, "Passa seriedade profissional."),
    LifestyleOffer("field_outfit", "Roupa de campo reforcada", "roupa", 3, 4200, 1, 1, "Boa para exploradores e coletores."),
    LifestyleOffer("contest_outfit", "Roupa de apresentacao", "roupa", 4, 9500, 0, 3, "Ajuda eventos sociais e coordenadores."),
    LifestyleOffer("executive_suit", "Roupa executiva", "roupa", 5, 18000, 0, 5, "Boa para comercio e corporativo."),
    LifestyleOffer("designer_collection", "Colecao de grife", "roupa", 6, 42000, 0, 9, "Moda cara para reputacao alta."),
]


COURSES = [
    CourseOffer("battle_strategy", "Curso de estrategia de batalha", 6500, 3, {"MEN": 2, "POK": 2}, "Melhora leitura de batalhas."),
    CourseOffer("pokemon_care", "Curso de cuidado Pokemon", 5200, 2, {"POK": 2, "MEN": 1}, "Ajuda criacao e saude da equipe."),
    CourseOffer("small_business", "Curso de pequenos negocios", 8000, 4, {"MEN": 3, "LUK": 1}, "Ajuda comercio e renda."),
    CourseOffer("field_survival", "Curso de sobrevivencia em rotas", 7000, 3, {"PHY": 2, "POK": 1}, "Ajuda exploracao e coleta."),
    CourseOffer("lab_methods", "Curso de metodos de laboratorio", 9000, 5, {"MEN": 3, "POK": 1}, "Ajuda pesquisa e ciencia."),
    CourseOffer("public_image", "Curso de imagem publica", 7500, 4, {"LUK": 2, "MEN": 1}, "Ajuda reputacao e eventos sociais."),
]


TRIPS = [
    TripOffer("seafoam_weekend", "Fim de semana em Seafoam", 3500, 3, 14, {"LUK": 1}, "Descanso costeiro acessivel."),
    TripOffer("cinnabar_spa", "Retiro termal em Cinnabar", 9000, 5, 26, {"MEN": 1}, "Viagem cara para recuperar saude."),
    TripOffer("sevii_island_trip", "Viagem relaxante para as Ilhas Sevii", 18000, 6, 38, {"LUK": 2}, "Ferias longas e restauradoras."),
]


BLACK_MARKET_RARITY_MULT = {
    "common": 1200,
    "uncommon": 3200,
    "rare": 9000,
    "very_rare": 22000,
    "legendary": 120000,
    "mythic": 180000,
}


def city_economy_tier(city_name: str) -> int:
    return int(CITY_ECONOMY_TIERS.get(city_name, 2))


def offers_for_tier(tier: int, category: str | None = None) -> list[LifestyleOffer]:
    return [
        offer for offer in LIFESTYLE_OFFERS
        if offer.tier <= tier and (category is None or offer.category == category)
    ]


def courses_for_tier(tier: int) -> list[CourseOffer]:
    return [course for course in COURSES if course.min_city_tier <= tier]


def trips_for_tier(tier: int) -> list[TripOffer]:
    return [trip for trip in TRIPS if trip.min_city_tier <= tier]


def course_effect_percent(attributes: PlayerAttributes, deltas: dict[str, int]) -> dict[str, int]:
    return {key: max(value, round(getattr(attributes, key, 0) * 0.04)) for key, value in deltas.items()}


def item_sell_price(price: int) -> int:
    return max(1, int(price * 0.45))


def egg_sell_price(tier: str) -> int:
    return {
        "C": 700,
        "I": 1600,
        "R": 4200,
        "RR": 9000,
        "SR": 18000,
    }.get(tier, 900)


def pokemon_market_value(pokemon: OwnedPokemon, species: PokemonSpecies | None) -> int:
    rarity = species.rarity if species else "rare"
    base = BLACK_MARKET_RARITY_MULT.get(rarity, 6000)
    stage = species.evolution_stage if species else pokemon.evolution_stage
    level_bonus = pokemon.level * 180
    stat_bonus = int((pokemon.combat + pokemon.beauty + pokemon.healthy + pokemon.occult) * 18)
    return int((base + level_bonus + stat_bonus) * (1 + max(0, stage - 1) * 0.35))
