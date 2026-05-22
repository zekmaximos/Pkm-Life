from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .academy import beauty_bonus, capture_bonus_for, care_bonus, training_xp_bonus, work_bonus
from .utils import clamp

if TYPE_CHECKING:
    from .character import Character
    from .pokemon import OwnedPokemon


CAREER_ACTIVITY_WEIGHTS: dict[str | None, dict[str, int]] = {
    "Treinador": {"battle": 35, "training": 30, "work": 10, "capture": 10, "care": 15},
    "Criador": {"battle": 5, "training": 20, "work": 10, "capture": 10, "care": 35, "criador_business": 20},
    "Coordenador": {"battle": 15, "training": 25, "work": 30, "capture": 5, "care": 25},
    "Estudante da academia": {"battle": 5, "training": 20, "work": 5, "capture": 10, "care": 60},
    "Pesquisador": {"battle": 5, "training": 20, "work": 35, "capture": 10, "care": 30},
    "Explorador": {"battle": 18, "training": 20, "work": 15, "capture": 22, "care": 25},
    "Cientista": {"battle": 5, "training": 15, "work": 50, "capture": 5, "care": 25},
    "Coletor de Berrys": {"battle": 5, "training": 15, "work": 35, "capture": 10, "care": 35},
    "Construtor de Pokebolas": {"battle": 5, "training": 10, "work": 55, "capture": 5, "care": 25},
    "Cuidador de Fazenda": {"battle": 5, "training": 15, "work": 30, "capture": 5, "care": 45},
    "Construtor": {"battle": 10, "training": 20, "work": 55, "capture": 0, "care": 15},
    "Comerciante": {"battle": 5, "training": 10, "work": 60, "capture": 5, "care": 20},
    "Criminoso": {"battle": 25, "training": 20, "work": 35, "capture": 10, "care": 10},
    None: {"battle": 10, "training": 10, "work": 5, "capture": 5, "care": 70},
}

CAREER_MISSIONS = {
    "Treinador": [
        ("batalha amistosa organizada", 85, {"PHY": 1, "POK": 1}, -4, {}, "batalha de exibicao cansou voce"),
        ("aula pratica para treinadores novatos", 65, {"POK": 1}, -1, {}, "aula pratica tomou energia"),
    ],
    "Criador": [
        ("turno extra no centro de cuidados", 70, {"POK": 1, "MEN": 1}, 4, {}, "rotina de cuidados ajudou sua saude"),
        ("avaliacao de ninhada Pokemon", 90, {"POK": 2}, -1, {}, "turno longo de criacao trouxe cansaco"),
    ],
    "Coordenador": [
        ("apresentacao pequena em palco local", 95, {"LUK": 1, "POK": 1}, -2, {}, "apresentacao exigiu preparo"),
        ("ensaio pago para evento social", 75, {"LUK": 1}, -1, {}, "ensaio prolongado cansou voce"),
    ],
    "Pesquisador": [
        ("catalogacao de habitat para professor local", 110, {"MEN": 1, "POK": 1}, -2, {}, "trabalho de campo consumiu energia"),
        ("relatorio de comportamento Pokemon", 125, {"MEN": 2}, 0, {}, None),
    ],
    "Explorador": [
        ("mapeamento de rota instavel", 115, {"PHY": 1, "POK": 1}, -6, {}, "exploracao perigosa causou desgaste"),
        ("escolta por caverna curta", 130, {"PHY": 2}, -8, {}, "caverna dificil machucou voce"),
    ],
    "Cientista": [
        ("turno em bancada experimental", 140, {"MEN": 2}, -1, {}, "turno de laboratorio foi exaustivo"),
        ("calibragem de equipamento Pokemon", 120, {"MEN": 1, "POK": 1}, 0, {}, None),
    ],
    "Coletor de Berrys": [
        ("colheita de berries em rota proxima", 70, {"PHY": 1, "POK": 1}, -3, {"Potion": 1}, "coleta em mata fechada arranhou voce"),
        ("triagem de berries para loja local", 55, {"POK": 1}, 0, {}, None),
    ],
    "Construtor de Pokebolas": [
        ("montagem de lote simples de Pokebolas", 105, {"MEN": 1, "POK": 1}, -1, {"Poke Ball": 1}, "oficina longa trouxe cansaco"),
        ("reparo de mecanismo de Great Ball", 130, {"MEN": 2}, -2, {}, "reparo delicado tensionou voce"),
    ],
    "Cuidador de Fazenda": [
        ("turno cuidando de Pokemon domesticos", 80, {"POK": 1, "MEN": 1}, 5, {}, "rotina ao ar livre fez bem"),
        ("organizar alimentacao da fazenda", 75, {"POK": 1}, 2, {}, "trabalho rural manteve voce ativo"),
    ],
    "Construtor": [
        ("reparo de ponte e cercas", 115, {"PHY": 2}, -7, {}, "obra pesada desgastou seu corpo"),
        ("obra de reforco em Pokemart", 130, {"PHY": 1, "MEN": 1}, -5, {}, "obra urbana cansou voce"),
    ],
    "Comerciante": [
        ("negociacao de lote para Pokemart", 125, {"MEN": 1, "LUK": 1}, -1, {}, "negociacao longa foi estressante"),
        ("feira itinerante de itens comuns", 105, {"LUK": 1}, -2, {"Repel": 1}, "dia inteiro de feira cansou voce"),
    ],
    "Criminoso": [
        ("entrega suspeita para contato da Equipe Rocket", 180, {"LUK": 1}, -4, {}, "fuga apressada desgastou voce"),
        ("intimidacao de apostadores ilegais", 160, {"PHY": 1, "LUK": 1}, -7, {}, "confronto ilegal deixou marcas"),
        ("estelionato em leilao de Pokemon falso", 210, {"MEN": 1, "LUK": 1}, -2, {}, "esquema de fraude estressou voce"),
        ("contrabando de itens raros pela Rota 8", 240, {"PHY": 1}, -6, {}, "transporte clandestino esgotou voce"),
        ("operacao de lavagem de dinheiro via comercio", 280, {"MEN": 2}, -3, {}, "trabalho de fachada foi exaustivo"),
    ],
}

BASE_XP = {
    "battle_win": 100,
    "battle_loss": 40,
    "training": 75,
    "capture": 30,
    "care": 25,
}


@dataclass
class ActivityResult:
    kind: str
    note: str
    xp_per_pokemon: int = 0
    money_delta: int = 0
    char_health_delta: int = 0
    attr_deltas: dict[str, int] = field(default_factory=dict)
    pokemon_stat_deltas: dict[str, int] = field(default_factory=dict)
    important: bool = False
    pokemon_name: str | None = None
    pokemon_level: int | None = None
    destination: str | None = None
    ball_used: str | None = None
    chance: float | None = None
    health_reason: str | None = None
    items_delta: dict[str, int] = field(default_factory=dict)
    mission_name: str | None = None
    mission_success: bool | None = None
    reputation_delta: int = 0


def _pick_activity(character: "Character", has_team: bool, has_balls: bool) -> str:
    weights = dict(CAREER_ACTIVITY_WEIGHTS.get(character.career, CAREER_ACTIVITY_WEIGHTS[None]))

    age = character.age

    # ── Age gates: restrições de coerência por fase de vida ──────────────────
    if age <= 2:
        # Bebê: somente cuidados. Nada mais faz sentido.
        return "care"
    if age <= 5:
        # Criança pequena: cuidados quase exclusivos, sem batalhas nem trabalho.
        weights["battle"] = 0
        weights["work"] = 0
        weights.pop("criador_business", None)
        weights["capture"] = 0          # nenhuma captura ativa — só eventos família
        weights["training"] = min(weights.get("training", 0), 5)
        weights["care"] = max(weights.get("care", 0), 90)
    elif age <= 9:
        # Criança: sem batalhas formais e sem trabalho, capturas muito raras perto de casa.
        weights["battle"] = 0
        weights["work"] = 0
        weights.pop("criador_business", None)
        weights["capture"] = min(weights.get("capture", 0), 5)
        weights["training"] = min(weights.get("training", 0), 10)
        weights["care"] = max(weights.get("care", 0), 50)

    if not has_team:
        weights["battle"] = 0
        weights["training"] = max(0, weights.get("training", 0) // 3)
    if not has_balls:
        weights["capture"] = 0
    if character.health < 35:
        weights = {key: (value // 3 if key not in {"care", "rest"} else value * 2) for key, value in weights.items()}

    activities = [key for key, value in weights.items() if value > 0]
    if not activities:
        return "care"
    return random.choices(activities, weights=[weights[key] for key in activities], k=1)[0]


def _best_pokemon(character: "Character") -> "OwnedPokemon | None":
    active = [pokemon for pokemon in character.team if pokemon.status != "badly_injured"]
    if not active:
        return None
    return max(active, key=lambda pokemon: pokemon.combat * _condition_factor(pokemon))


def _condition_factor(pokemon: "OwnedPokemon") -> float:
    return {
        "healthy": 1.0,
        "tired": 0.88,
        "injured": 0.70,
        "badly_injured": 0.45,
        "sick": 0.65,
        "inspired": 1.15,
    }.get(pokemon.status, 1.0)


def _has_battle_item(character: "Character") -> bool:
    return any(character.inventory.get(item, 0) > 0 for item in {"X Attack", "X Defense", "X Speed", "Dire Hit"})


def _has_training_item(character: "Character") -> bool:
    return any(character.inventory.get(item, 0) > 0 for item in {"HP Up", "Protein", "Iron", "Carbos", "Calcium", "Zinc"})


def _sim_battle(character: "Character") -> ActivityResult:
    pokemon = _best_pokemon(character)
    if pokemon is None:
        return ActivityResult("care", "Sem Pokemon disponivel para batalhar.")

    attrs = character.attributes
    condition = _condition_factor(pokemon)
    player_power = (
        pokemon.combat * 0.55
        + pokemon.healthy * 0.20
        + attrs.PHY * 0.15
        + attrs.POK * 0.10
    ) * condition
    if _has_battle_item(character):
        player_power *= 1.12

    enemy_power = pokemon.combat * random.uniform(0.70, 1.35)
    win_chance = clamp(0.35 + (player_power - enemy_power) / 220 + attrs.LUK / 800, 0.12, 0.88)
    won = random.random() < win_chance

    if won:
        xp = int(BASE_XP["battle_win"] * (1 + attrs.POK / 220) * condition)
        return ActivityResult(
            kind="battle_win",
            note=_battle_win_note(pokemon, attrs.PHY, win_chance),
            xp_per_pokemon=xp,
            char_health_delta=-random.randint(1, 5),
            health_reason="batalhas vencidas cansaram voce",
            attr_deltas={"PHY": 1} if random.random() < 0.4 else {},
            pokemon_stat_deltas={"combat": random.randint(1, 2), "healthy": -random.randint(1, 4), "battle_level": random.randint(2, 4)},
            important=win_chance < 0.40,
        )

    xp = int(BASE_XP["battle_loss"] * condition)
    return ActivityResult(
        kind="battle_loss",
        note=_battle_loss_note(pokemon, win_chance),
        xp_per_pokemon=xp,
        char_health_delta=-random.randint(2, 7),
        health_reason="derrotas em batalha cobraram um preco fisico",
        attr_deltas={"PHY": 1} if random.random() < 0.25 else {},
        pokemon_stat_deltas={"healthy": -random.randint(2, 7), "battle_level": random.randint(0, 2)},
    )


def _sim_training(character: "Character", species_by_name: dict) -> ActivityResult:
    pokemon = _best_pokemon(character)
    if pokemon is None:
        return ActivityResult("care", "Treino leve sem Pokemon.", xp_per_pokemon=4)

    attrs = character.attributes
    condition = _condition_factor(pokemon)
    happiness_bonus = max(0, (pokemon.happiness - 40) / 100)
    quality = clamp(
        0.50
        + attrs.POK * 0.006
        + attrs.MEN * 0.003
        + happiness_bonus * 0.25
        + (0.15 if _has_training_item(character) else 0.0)
        + (0.10 if character.career == "Treinador" else 0.0)
        + (0.08 if character.career == "Criador" else 0.0),
        0.25,
        1.40,
    )
    xp = int((BASE_XP["training"] + training_xp_bonus(character)) * quality * condition)
    stat_deltas: dict[str, int] = {}
    if character.career == "Criador":
        stat_deltas = {"happiness": random.randint(2, 4), "healthy": random.randint(1, 3)}
    elif character.career == "Coordenador":
        stat_deltas = {"beauty": random.randint(1, 2), "occult": 1 if random.random() < 0.35 else 0}
    elif character.career == "Treinador":
        stat_deltas = {"combat": 1 if random.random() < 0.5 else 0}
    else:
        stat_deltas = {"happiness": 1}
    focus_care = care_bonus(character)
    if focus_care:
        stat_deltas["happiness"] = stat_deltas.get("happiness", 0) + focus_care
        stat_deltas["healthy"] = stat_deltas.get("healthy", 0) + focus_care
    focus_beauty = beauty_bonus(character)
    if focus_beauty:
        stat_deltas["beauty"] = stat_deltas.get("beauty", 0) + focus_beauty

    return ActivityResult(
        kind="training",
        note=_training_note(pokemon, quality),
        xp_per_pokemon=xp,
        char_health_delta=-random.randint(1, 4),
        health_reason="treinos longos consumiram energia",
        attr_deltas={"POK": 1} if quality > 1.0 and random.random() < 0.3 else {},
        pokemon_stat_deltas=stat_deltas,
    )


def _sim_work(character: "Character") -> ActivityResult:
    from .economy import calculate_money_gain
    from .careers import pokemon_work_bonus

    attrs = character.attributes
    career = character.career or "Sem carreira"
    rank = character.career_rank()
    base = {
        "Treinador": 90,
        "Criador": 75,
        "Coordenador": 85,
        "Estudante da academia": 30,
        "Pesquisador": 105,
        "Explorador": 85,
        "Cientista": 120,
        "Coletor de Berrys": 65,
        "Construtor de Pokebolas": 95,
        "Cuidador de Fazenda": 75,
        "Construtor": 105,
        "Comerciante": 110,
        "Criminoso": 140,
    }.get(career, 40)
    pokemon_factor, pokemon_notes = pokemon_work_bonus(character.career, character.team)
    from .reputation import reputation_income_factor
    rep_mult = reputation_income_factor(character.reputation)
    rank_mult = 1.0 + rank * 0.20
    health_mult = clamp(0.65 + character.health / 280, 0.65, 1.10)
    income = int(calculate_money_gain(base + work_bonus(character), attrs) * rep_mult * rank_mult * health_mult * pokemon_factor * random.uniform(0.80, 1.30))
    if attrs.LUK > 60 and random.random() < 0.18:
        bonus = int(income * random.uniform(0.30, 0.70))
        income += bonus
        suffix = f" Um cliente especial trouxe +{bonus}P extra."
    else:
        suffix = ""
    note = _work_note(career, income, rank) + suffix
    if pokemon_notes and random.random() < 0.55:
        note += " " + pokemon_notes[0]
    return ActivityResult(
        kind="work",
        note=note,
        money_delta=income,
        char_health_delta=-random.randint(1, 3),
        health_reason="trabalho acumulado trouxe cansaco",
        attr_deltas={"MEN": 1} if random.random() < 0.20 else {},
    )


def _sim_career_mission(character: "Character") -> ActivityResult | None:
    from .economy import calculate_money_gain
    from .careers import pokemon_work_bonus

    career = character.career
    if not career or career == "Estudante da academia":
        return None
    missions = CAREER_MISSIONS.get(career)
    if not missions:
        return None
    mission_name, base_reward, attr_deltas, health_delta, items_delta, health_reason = random.choice(missions)
    rank = character.career_rank()
    pokemon_factor, pokemon_notes = pokemon_work_bonus(career, character.team)
    attrs = character.attributes
    skill = (attrs.MEN * 0.35 + attrs.POK * 0.30 + attrs.PHY * 0.20 + attrs.LUK * 0.15) / 100
    success_chance = clamp(0.42 + skill * 0.35 + rank * 0.05 + (pokemon_factor - 1.0), 0.18, 0.90)
    success = random.random() <= success_chance
    if success:
        reward = int(calculate_money_gain(base_reward, attrs) * (1 + rank * 0.10) * pokemon_factor)
        note = f"Missao de profissao: {mission_name} concluida (+{reward} Pokedollar)."
        if pokemon_notes:
            note += " " + pokemon_notes[0]
        return ActivityResult(
            kind="career_mission",
            note=note,
            money_delta=reward,
            char_health_delta=health_delta,
            health_reason=health_reason,
            attr_deltas=dict(attr_deltas),
            items_delta=dict(items_delta),
            mission_name=mission_name,
            mission_success=True,
            reputation_delta=-3 if career == "Criminoso" else 0,
            important=rank >= 3,
        )
    penalty = int(abs(base_reward) * random.uniform(0.05, 0.18))
    note = f"Missao de profissao: {mission_name} nao saiu como esperado."
    return ActivityResult(
        kind="career_mission",
        note=note,
        money_delta=-penalty,
        char_health_delta=min(-1, health_delta - random.randint(1, 4)),
        health_reason=health_reason or "missao de profissao mal sucedida desgastou voce",
        attr_deltas={"MEN": 1} if random.random() < 0.35 else {},
        mission_name=mission_name,
        mission_success=False,
        reputation_delta=-5 if career == "Criminoso" else 0,
    )


def _sim_capture(character: "Character", species_by_name: dict) -> ActivityResult:
    from .capture import attempt_capture
    from .pokemon import create_owned_pokemon

    candidates = [
        species for species in species_by_name.values()
        if species.can_be_wild and not species.is_legendary and species.rarity in {"common", "uncommon"}
    ]
    if not candidates:
        return ActivityResult("care", "Nao encontrou nada para capturar.")

    attrs = character.attributes
    species = random.choice(candidates)
    level = random.randint(3, max(5, min(25, character.age + 3)))
    ball_items = {"Master Ball": 100, "Ultra Ball": 25, "Great Ball": 12, "Poke Ball": 0}
    ball_used = "Poke Ball"
    ball_bonus = 0
    for ball, bonus in sorted(ball_items.items(), key=lambda item: -item[1]):
        if character.inventory.get(ball, 0) > 0:
            ball_used = ball
            ball_bonus = bonus
            character.inventory[ball] -= 1
            if character.inventory[ball] == 0:
                del character.inventory[ball]
            break
    ball_bonus += capture_bonus_for(character, species)

    health_percent = 60
    char_health_delta = 0
    if not character.team:
        health_percent = 95
        ball_bonus = max(-35, ball_bonus - 35)
        char_health_delta = -random.randint(2, 9)

    result = attempt_capture(
        rarity=species.rarity,
        pokemon_name=species.name,
        pokemon_health_percent=health_percent,
        player_attributes=attrs,
        ball_bonus=ball_bonus,
        pokemon_level=level,
        evolution_stage=species.evolution_stage,
    )

    if result.success:
        age = character.age
        if age <= 4:
            origin = f"acolhido pela familia aos {age} anos em {character.current_city}"
        elif age <= 9:
            origin = f"encontrado aos {age} anos perto de {character.current_city}"
        else:
            origin = f"capturado durante o ano em {character.current_city}"
        pokemon = create_owned_pokemon(species, level=level, origin=origin)
        destination = character.add_pokemon(pokemon)
        character.register_caught(species.name)
        return ActivityResult(
            kind="capture_ok",
            note=_capture_note(species.name, level, True, attrs.LUK, age),
            xp_per_pokemon=BASE_XP["capture"],
            char_health_delta=char_health_delta,
            health_reason="captura sem parceiro foi perigosa" if char_health_delta < 0 else None,
            attr_deltas={"LUK": 1} if attrs.LUK < 70 and random.random() < 0.3 else {},
            important=species.rarity in {"rare", "very_rare"},
            pokemon_name=species.name,
            pokemon_level=level,
            destination=destination,
            ball_used=ball_used,
            chance=result.chance,
        )

    character.register_seen(species.name)
    note = _capture_note(species.name, level, False, attrs.LUK, character.age)
    if not character.team:
        note += " Sem um Pokemon parceiro, a tentativa foi perigosa."
    return ActivityResult(
        kind="capture_fail",
        note=note,
        char_health_delta=char_health_delta,
        health_reason="tentativa de captura sem parceiro causou ferimentos" if char_health_delta < 0 else None,
        attr_deltas={"POK": 1} if random.random() < 0.25 else {},
        pokemon_name=species.name,
        pokemon_level=level,
        ball_used=ball_used,
        chance=result.chance,
    )


def _sim_care(character: "Character") -> ActivityResult:
    attrs = character.attributes
    care_skill = (attrs.POK + attrs.MEN) / 2
    hp_gain = int(clamp(4 + care_skill / 30, 4, 14))
    stat_deltas = {
        "happiness": random.randint(2, 5) + care_bonus(character),
        "healthy": random.randint(1, 3 + (1 if character.career == "Criador" else 0)) + care_bonus(character),
    }
    if beauty_bonus(character):
        stat_deltas["beauty"] = beauty_bonus(character)
    return ActivityResult(
        kind="care",
        note=_care_note(character.career, stat_deltas["happiness"]),
        xp_per_pokemon=BASE_XP["care"],
        char_health_delta=hp_gain,
        health_reason="descanso e cuidados recuperaram sua saude",
        attr_deltas={"MEN": 1} if character.career == "Criador" and random.random() < 0.25 else {},
        pokemon_stat_deltas=stat_deltas,
    )


def _sim_criador_business(character: "Character") -> ActivityResult:
    """Atividades de renda exclusivas do Criador: bagas, pokéblocos e venda de ovos."""
    from .economy import calculate_money_gain

    attrs = character.attributes
    rank = character.career_rank()
    rank_mult = 1.0 + rank * 0.15
    pok_bonus = attrs.POK / 200

    # Escolhe uma das três atividades com pesos dinâmicos
    has_eggs = bool(character.eggs)
    egg_weight = 40 if has_eggs else 10
    activity = random.choices(
        ["berry_farm", "pokeblock", "egg_sell"],
        weights=[35, 25, egg_weight],
        k=1,
    )[0]

    if activity == "berry_farm":
        base_income = int(60 + attrs.PHY * 0.4 + attrs.POK * 0.3)
        income = int(calculate_money_gain(base_income, attrs) * rank_mult * random.uniform(0.80, 1.30))
        items_gained: dict[str, int] = {}
        if random.random() < 0.35 + pok_bonus:
            items_gained["Potion"] = 1
        note = random.choice([
            f"Colheita e venda de bagas rendeu {income} Pokedollar.",
            f"Sua plantacao de bagas produziu bem este periodo: +{income}P.",
            f"Venda de bagas na rota local trouxe {income}P.",
        ])
        return ActivityResult(
            kind="criador_business",
            note=note,
            money_delta=income,
            char_health_delta=random.randint(0, 3),
            health_reason="trabalho ao ar livre com bagas fez bem",
            attr_deltas={"POK": 1} if random.random() < 0.25 else {},
            pokemon_stat_deltas={"happiness": 1},
            items_delta=items_gained,
        )

    if activity == "pokeblock":
        base_income = int(75 + attrs.MEN * 0.5 + attrs.POK * 0.25)
        income = int(calculate_money_gain(base_income, attrs) * rank_mult * random.uniform(0.75, 1.35))
        note = random.choice([
            f"Producao de Pokebloco para concursos rendeu {income} Pokedollar.",
            f"Lote de Pokeblocos vendido a coordenadores por {income}P.",
            f"Sua receita de Pokebloco ficou famosa: +{income}P neste periodo.",
        ])
        return ActivityResult(
            kind="criador_business",
            note=note,
            money_delta=income,
            char_health_delta=-random.randint(0, 2),
            health_reason="dias na cozinha de Pokeblocos cansaram um pouco",
            attr_deltas={"MEN": 1} if random.random() < 0.30 else {},
            pokemon_stat_deltas={"beauty": random.randint(1, 2)},
        )

    # egg_sell
    if has_eggs:
        egg = character.eggs[0]  # referência, não remove (engine pode remover via sell_egg)
        tier = getattr(egg, "rarity_tier", getattr(egg, "tier", "C"))
        tier_prices = {"S": 800, "A": 500, "B": 300, "C": 150, "D": 80}
        base_income = int(tier_prices.get(tier, 150) * rank_mult * random.uniform(0.85, 1.20))
    else:
        # Simula venda de ovo sem ter físico no inventário (ninhada informal)
        base_income = int(calculate_money_gain(100, attrs) * rank_mult * random.uniform(0.70, 1.10))
    note = random.choice([
        f"Venda legal de ovo Pokemon rendeu {base_income} Pokedollar.",
        f"Um criador local comprou um ovo da sua ninhada por {base_income}P.",
        f"Ovo vendido por {base_income}P no mercado regulamentado.",
    ])
    return ActivityResult(
        kind="criador_business",
        note=note,
        money_delta=base_income,
        char_health_delta=0,
        attr_deltas={"LUK": 1} if random.random() < 0.20 else {},
        pokemon_stat_deltas={"happiness": random.randint(1, 2)},
        important=base_income >= 400,
    )


def simulate_year_activities(
    character: "Character",
    species_by_name: dict,
    capture_species_available: bool = True,
    months: int = 12,
) -> list[ActivityResult]:
    period_factor = clamp(months / 12, 0.25, 1.0)
    n = 4
    if character.career:
        n += 1
    if character.health > 55:
        n += 1
    if len(character.team) >= 2:
        n += 1
    if character.attributes.total() > 200:
        n += 1
    n = int(clamp(round(n * period_factor), 1, 8))

    has_team = bool(character.team)
    has_balls = any(
        amount > 0 and name in {"Poke Ball", "Great Ball", "Ultra Ball", "Master Ball"}
        for name, amount in character.inventory.items()
    )
    results: list[ActivityResult] = []
    for _ in range(n):
        kind = _pick_activity(character, has_team, has_balls and capture_species_available)
        if kind == "battle":
            result = _sim_battle(character)
        elif kind == "training":
            result = _sim_training(character, species_by_name)
        elif kind == "work":
            result = _sim_work(character)
        elif kind == "capture":
            result = _sim_capture(character, species_by_name)
            has_team = bool(character.team)
            has_balls = any(
                amount > 0 and name in {"Poke Ball", "Great Ball", "Ultra Ball", "Master Ball"}
                for name, amount in character.inventory.items()
            )
        elif kind == "criador_business":
            result = _sim_criador_business(character)
        else:
            result = _sim_care(character)
        results.append(result)
    mission_chance = 0.32 + character.career_rank() * 0.04
    if character.career in {"Coletor de Berrys", "Construtor de Pokebolas", "Cuidador de Fazenda", "Construtor", "Comerciante"}:
        mission_chance += 0.10
    if character.career == "Criminoso":
        mission_chance += 0.15  # criminosos têm operações mais frequentes
    if random.random() < min(0.70, mission_chance):
        mission = _sim_career_mission(character)
        if mission:
            results.append(mission)
    return results


def apply_activity_results(
    character: "Character",
    results: list[ActivityResult],
    species_by_name: dict,
) -> tuple[list[str], dict[str, Any]]:
    from .progression import check_evolution, grant_pokemon_xp

    notes: list[str] = []
    important_notes: list[str] = []
    total_money = 0
    total_health_delta = 0
    total_xp = 0
    attr_totals: dict[str, int] = {}
    stat_totals: dict[str, int] = {}
    report: dict[str, Any] = {
        "captures": [],
        "capture_failures": [],
        "battles": {"wins": 0, "losses": 0},
        "money": 0,
        "eggs": [],
        "travel": [],
        "training": {"xp": 0, "level_ups": 0},
        "evolutions": [],
        "health_delta": 0,
        "health_reasons": [],
        "career_missions": [],
        "items": {},
        "reputation_delta": 0,
    }

    for result in results:
        total_money += result.money_delta
        total_health_delta += result.char_health_delta
        total_xp += result.xp_per_pokemon
        report["money"] += result.money_delta
        report["reputation_delta"] += result.reputation_delta
        report["health_delta"] += result.char_health_delta
        if result.char_health_delta and result.health_reason:
            report["health_reasons"].append({
                "delta": result.char_health_delta,
                "reason": result.health_reason,
            })
        report["training"]["xp"] += result.xp_per_pokemon
        if result.kind == "battle_win":
            report["battles"]["wins"] += 1
        elif result.kind == "battle_loss":
            report["battles"]["losses"] += 1
        elif result.kind == "capture_ok":
            report["captures"].append(_capture_report_entry(result))
        elif result.kind == "capture_fail":
            report["capture_failures"].append(_capture_report_entry(result))
        elif result.kind == "career_mission":
            report["career_missions"].append({
                "name": result.mission_name,
                "success": result.mission_success,
                "money": result.money_delta,
                "note": result.note,
                "reputation": result.reputation_delta,
            })
        for item_name, amount in result.items_delta.items():
            if amount:
                report["items"][item_name] = report["items"].get(item_name, 0) + amount
        for key, value in result.attr_deltas.items():
            attr_totals[key] = attr_totals.get(key, 0) + value
        for key, value in result.pokemon_stat_deltas.items():
            stat_totals[key] = stat_totals.get(key, 0) + value
        if result.important:
            important_notes.append(result.note)

    if total_health_delta < 0:
        months = int(getattr(character, "flags", {}).get("current_period_months", 12))
        passive_loss_cap = {3: 8, 6: 14, 12: 24}.get(months, 24)
        if character.career in {"Treinador", "Explorador", "Construtor"}:
            passive_loss_cap += 6
        if total_health_delta < -passive_loss_cap:
            total_health_delta = -passive_loss_cap
            report["health_delta"] = total_health_delta
            report["health_reasons"].append({
                "delta": total_health_delta,
                "reason": "o desgaste do periodo foi limitado por descanso e recuperacao basica",
            })

    if total_money:
        character.money = max(0, character.money + total_money)
    for result in results:
        for item_name, amount in result.items_delta.items():
            if amount > 0:
                character.inventory[item_name] = character.inventory.get(item_name, 0) + amount
            elif amount < 0:
                current = character.inventory.get(item_name, 0)
                character.inventory[item_name] = max(0, current + amount)
                if character.inventory[item_name] <= 0:
                    del character.inventory[item_name]
    character.health = int(clamp(character.health + total_health_delta, 0, 100))
    if report["reputation_delta"]:
        from .reputation import clamp_reputation
        character.reputation = clamp_reputation(character.reputation + int(report["reputation_delta"]))
        if character.reputation <= -35:
            character.flags["official_event_ban"] = True
    character.modify_attributes(attr_totals)

    for pokemon in character.team:
        if total_xp > 0 and pokemon.status != "badly_injured":
            xp_this = total_xp // 2 if pokemon.status in {"injured", "sick"} else total_xp
            for level_note in grant_pokemon_xp(pokemon, xp_this, species_by_name):
                if "subiu para o nivel" in level_note:
                    report["training"]["level_ups"] += 1
                important_notes.append(level_note)

        for stat, delta in stat_totals.items():
            if not delta or not hasattr(pokemon, stat):
                continue
            current = getattr(pokemon, stat)
            if stat in {"combat", "beauty", "occult"}:
                setattr(pokemon, stat, int(clamp(current + delta, 1, 100)))
            elif stat in {"healthy", "happiness"}:
                setattr(pokemon, stat, int(clamp(current + delta, 0, 100)))
            elif stat == "battle_level":
                setattr(pokemon, stat, max(0, current + delta))

        for evolution_note in check_evolution(pokemon, species_by_name):
            report["evolutions"].append(evolution_note)
            important_notes.append(evolution_note)

    work_income = sum(result.money_delta for result in results)
    battles = [result for result in results if result.kind in {"battle_win", "battle_loss"}]
    captures = [result for result in results if result.kind == "capture_ok"]
    failures = [result for result in results if result.kind == "capture_fail"]
    criador_biz = [result for result in results if result.kind == "criador_business"]
    age = character.age

    # ── Dinheiro ──────────────────────────────────────────────────────────────
    if work_income:
        if age <= 5:
            notes.append(random.choice([
                f"Sua familia deixou {work_income} Pokedollar para pequenas necessidades.",
                f"Voce ganhou {work_income} Pokedollar de mesada dos seus pais.",
                f"Um familiar generoso deu {work_income} Pokedollar de presente.",
            ]))
        elif age <= 9:
            notes.append(random.choice([
                f"Pequenas tarefas em casa renderam {work_income} Pokedollar.",
                f"Voce ganhou {work_income} Pokedollar ajudando na vizinhanca.",
                f"Sua mesada e um servico rapido somaram {work_income} Pokedollar.",
            ]))
        else:
            notes.append(f"Renda total no periodo: {work_income} Pokedollar.")

    # ── Criador business ──────────────────────────────────────────────────────
    if criador_biz:
        biz_income = sum(r.money_delta for r in criador_biz)
        notes.append(f"Negocios de criacao (bagas/pokeblocos/ovos): +{biz_income} Pokedollar.")

    # ── Batalhas ──────────────────────────────────────────────────────────────
    if battles:
        wins = sum(1 for result in battles if result.kind == "battle_win")
        notes.append(f"Batalhas: {wins} vitoria(s) e {len(battles) - wins} derrota(s).")

    # ── Capturas: usar a narrativa individual de cada resultado ───────────────
    if captures:
        for result in captures[:2]:
            if result.note:
                notes.append(result.note)
        if len(captures) > 2:
            extra_names = ", ".join(
                r.pokemon_name or "Pokemon" for r in captures[2:]
            )
            notes.append(f"Mais Pokemon capturado(s) no periodo: {extra_names}.")

    # ── Falhas de captura: narrativa individual ───────────────────────────────
    if failures:
        for result in failures[:1]:
            if result.note:
                notes.append(result.note)
        if len(failures) > 1:
            notes.append(f"Mais {len(failures) - 1} tentativa(s) de captura sem sucesso.")

    # ── Missões de carreira ───────────────────────────────────────────────────
    missions = [result for result in results if result.kind == "career_mission"]
    if missions:
        successes = sum(1 for result in missions if result.mission_success)
        notes.append(f"Missoes de profissao: {successes}/{len(missions)} concluida(s).")

    notes.extend(important_notes)
    return notes, report


def _capture_report_entry(result: ActivityResult) -> dict[str, Any]:
    return {
        "species": result.pokemon_name,
        "level": result.pokemon_level,
        "destination": result.destination,
        "ball": result.ball_used,
        "chance": round(result.chance or 0, 2),
    }


def _battle_win_note(pokemon: "OwnedPokemon", phy: int, win_chance: float) -> str:
    if win_chance < 0.40:
        options = [
            f"{pokemon.display_name()} venceu uma batalha dificil contra tudo que se esperava.",
            f"Foi muito disputado, mas {pokemon.display_name()} saiu vitorioso.",
        ]
    elif phy > 65:
        options = [
            f"Sua experiencia guiou {pokemon.display_name()} a uma vitoria solida.",
            f"{pokemon.display_name()} dominou o adversario com precisao.",
        ]
    else:
        options = [
            f"{pokemon.display_name()} venceu uma batalha durante o ano.",
            f"Uma boa batalha rendeu experiencia para {pokemon.display_name()}.",
        ]
    return random.choice(options)


def _battle_loss_note(pokemon: "OwnedPokemon", win_chance: float) -> str:
    if win_chance > 0.70:
        options = [
            f"{pokemon.display_name()} perdeu uma batalha que parecia ganha. Licao aprendida.",
            "Uma derrota inesperada fez voce repensar sua estrategia.",
        ]
    else:
        options = [
            f"{pokemon.display_name()} enfrentou um adversario mais forte e saiu derrotado.",
            f"A batalha foi dura e {pokemon.display_name()} nao conseguiu superar o oponente.",
        ]
    return random.choice(options)


def _training_note(pokemon: "OwnedPokemon", quality: float) -> str:
    if quality > 1.10:
        options = [
            f"Sessao de treino excelente: {pokemon.display_name()} evoluiu bastante.",
            f"{pokemon.display_name()} treinou com garra e mostrou muito potencial.",
        ]
    elif quality > 0.80:
        options = [
            f"Treino regular rendeu bons resultados para {pokemon.display_name()}.",
            f"Voce e {pokemon.display_name()} passaram horas praticando juntos.",
        ]
    else:
        options = [
            f"O treino foi limitado - {pokemon.display_name()} nao estava no seu melhor dia.",
            f"{pokemon.display_name()} treinou pouco, mas algo sempre fica.",
        ]
    return random.choice(options)


def _work_note(career: str, income: int, rank: int) -> str:
    if rank >= 3:
        options = [
            f"Sua reputacao como {career} rendeu {income}P este periodo.",
            f"Trabalho reconhecido: voce ganhou {income}P como {career}.",
        ]
    elif income > 150:
        options = [
            f"Um bom periodo de trabalho como {career} gerou {income}P.",
            f"Voce se dedicou ao trabalho e ganhou {income}P.",
        ]
    else:
        options = [
            f"Renda modesta de {income}P como {career}.",
            f"Trabalho simples rendeu {income}P.",
        ]
    return random.choice(options)


def _capture_note(name: str, level: int, caught: bool, luck: int, age: int = 15) -> str:
    if caught:
        if age <= 4:
            return random.choice([
                f"Um {name} perdido apareceu perto de casa e sua familia o acolheu. Ele escolheu ficar com voce.",
                f"Seus pais trouxeram um {name} filhote de presente. Desde o primeiro dia, ele so tem olhos para voce.",
                f"Um {name} ferido apareceu na sua varanda durante a chuva. Voce cuidou dele e ele nunca mais foi embora.",
                f"Uma vizinha criadora deixou um {name} aos seus cuidados por uns dias — e ele simplesmente nunca quis voltar.",
                f"Voce encontrou um {name} perdido no jardim de casa. Ele te seguiu ate o quarto e dormiu na sua cama.",
            ])
        if age <= 9:
            return random.choice([
                f"Voce encontrou um {name} ferido perto de casa e cuidou dele ate se recuperar. Ele decidiu ficar.",
                f"Um {name} te seguiu da escola durante dias ate voce convencer seus pais a deixa-lo ficar.",
                f"Um treinador mais velho viu seu potencial e te presenteou com um {name} jovem.",
                f"Voce salvou um {name} de uma armadilha esquecida na beira do rio. Ele nao quis mais ir embora.",
                f"Durante uma excursao escolar, um {name} se separou do grupo selvagem e veio direto ate voce.",
            ])
        if luck > 65:
            return f"Com sorte e habilidade, voce capturou um {name} de nivel {level}!"
        return f"Voce capturou um {name} de nivel {level}."
    if age <= 4:
        return random.choice([
            f"Um {name} apareceu perto de casa, mas fugiu rapido demais.",
            f"Voce tentou se aproximar de um {name}, mas ele desapareceu no mato.",
        ])
    if age <= 9:
        return random.choice([
            f"Voce tentou capturar um {name}, mas ele escapou antes que voce chegasse perto.",
            f"Um {name} apareceu no seu caminho, mas foi rapido demais para uma crianca.",
        ])
    return random.choice([
        f"Voce tentou capturar um {name} de nivel {level}, mas ele escapou.",
        f"Um {name} Lv.{level} fugiu antes de ser capturado.",
    ])


def _care_note(pokemon_name: str, kind: str) -> str:
    if kind == "heal":
        return random.choice([
            f"Voce levou {pokemon_name} ao Pokemon Center a tempo.",
            f"{pokemon_name} se recuperou apos um periodo de cuidados intensos.",
        ])
    if kind == "rest":
        return random.choice([
            f"{pokemon_name} descansou e voltou mais disposto.",
            f"Um dia tranquilo fez bem para {pokemon_name}.",
        ])
    return random.choice([
        f"Voce cuidou de {pokemon_name} com dedicacao.",
        f"{pokemon_name} parece mais feliz apos seus cuidados.",
    ])