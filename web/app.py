from __future__ import annotations

import random
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from flask import Flask, jsonify, render_template, request

from game.careers import CAREER_RANK_XP, career_rank_label
from game.character import Character
from game.engine import GameEngine
from game.save_system import list_saves, load_game, save_game


app = Flask(__name__)
engine = GameEngine()

CITY_DESCRIPTIONS: dict[str, str] = {
    "Pallet Town": "Vilarejo tranquilo entre campos abertos — o cheiro de grama fresca e o canto de Pokémon selvagens marcam cada manhã. Tudo começa aqui.",
    "Viridian City": "Cidade envolta em mistério, com uma floresta densa ao norte e um ginásio cujo líder raramente aparece. As ruas são largas e silenciosas demais.",
    "Pewter City": "Encostada nas montanhas cinzentas ricas em fósseis, Pewter cheira a pedra úmida e história antiga. O Museu guarda segredos de eras extintas.",
    "Cerulean City": "Banhada por rios cristalinos e cercada de flores azuis, o ar aqui é fresco e levemente úmido — ideal para quem gosta de Pokémon aquáticos.",
    "Vermilion City": "Porto fervilhante com cheiro de maresia e óleo de motor. Navios partem todo dia para destinos desconhecidos, levando consigo histórias e riscos.",
    "Lavender Town": "Pequena e sombria, dominada pela Torre Pokémon no horizonte. Diz-se que à meia-noite os espíritos dos que partiram ainda caminham pelas ruas.",
    "Celadon City": "Metrópole vibrante com grandes lojas e cassinos reluzentes. O aroma de perfume e poeira urbana se misturam no ar quente da cidade.",
    "Fuchsia City": "Cidade selvagem ao sul de Kanto, lar do Safari Zone e de treinadores de veneno. O cheiro de folhas úmidas e o som de animais ao longe nunca somem.",
    "Saffron City": "O coração pulsante de Kanto. Arranha-céus, a Silph Co. dominando o horizonte e uma energia psíquica inexplicável que faz os cabelos arrepiarem.",
    "Cinnabar Island": "Ilha vulcânica com um laboratório secreto e ruínas milenares. À noite, a lava brilha nas fendas das pedras e o cheiro de enxofre paira no ar.",
    "Indigo Plateau": "O topo do mundo para os treinadores de Kanto. Ventos frios cortam a névoa densa que envolve a Liga Pokémon — apenas os melhores chegam aqui.",
    "Seafoam Harbor": "Porto gelado entre cavernas de gelo, onde ventos cortantes chegam do mar. Os pescadores daqui conhecem os segredos mais frios de Kanto.",
}

BADGE_SYMBOLS: dict[str, str] = {
    "Rocha": "◆",
    "Cascata": "≋",
    "Trovão": "⚡",
    "Trovao": "⚡",
    "Arco": "☘",
    "Alma": "☠",
    "Pântano": "◈",
    "Pantano": "◈",
    "Vulcão": "▲",
    "Vulcao": "▲",
    "Terra": "⬟",
}

RIBBON_SYMBOLS: dict[str, str] = {
    "Beauty": "✦",
    "Cute": "♡",
    "Cool": "◆",
    "Smart": "◇",
    "Mysterious": "☾",
}

character: Character | None = None
feed: list[dict[str, Any]] = []
pending_event = None


def card(kind: str, text: str, title: str | None = None) -> dict[str, Any]:
    year = character.age if character is not None else 0
    text_value = str(text)
    return {
        "kind": kind,
        "title": title or kind.title(),
        "text": text_value,
        "time": f"Ano {year}",
        "pokemon_sprites": pokemon_mentions_for_text(text_value),
    }


def push(kind: str, text: str, title: str | None = None) -> None:
    feed.insert(0, card(kind, text, title))
    del feed[80:]


def pokemon_state(pokemon) -> dict[str, Any]:
    species = engine.pokemon.get(pokemon.species)
    can_see_battle_level = character is not None and character.career in {"Pesquisador", "Criador"}
    sprite = pokemon_sprite_path(species) if species else None
    return {
        "name": pokemon.display_name(),
        "species": pokemon.species,
        "sprite": sprite,
        "level": pokemon.level,
        "xp": pokemon.experience,
        "status": pokemon.status,
        "active": pokemon.active,
        "hp": pokemon.current_health,
        "max_hp": pokemon.max_health(species),
        "hp_percent": round(pokemon.health_percent(species) * 100),
        "combat": pokemon.combat,
        "beauty": pokemon.beauty,
        "healthy": pokemon.healthy,
        "occult": pokemon.occult,
        "happiness": pokemon.happiness,
        "types": list(pokemon.types or (species.types if species else [])),
        "battle_level": pokemon.battle_level if can_see_battle_level else None,
    }


def pokemon_sprite_path(species) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", species.name.lower()).strip("-") or "pokemon"
    return f"/static/sprites/pokemon/{species.pokedex_id:03d}-{slug}.png"


def pokemon_mentions_for_text(text: str) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    seen: set[str] = set()
    for species in sorted(engine.pokemon.values(), key=lambda item: len(item.name), reverse=True):
        pattern = rf"(?<![A-Za-z0-9]){re.escape(species.name)}(?![A-Za-z0-9])"
        if not re.search(pattern, text, flags=re.IGNORECASE):
            continue
        if species.name in seen:
            continue
        seen.add(species.name)
        matches.append({
            "name": species.name,
            "sprite": pokemon_sprite_path(species),
            "types": list(species.types),
        })
        if len(matches) >= 3:
            break
    return matches


def badge_symbol(name: str) -> str:
    for key, symbol in BADGE_SYMBOLS.items():
        if key.lower() in name.lower():
            return symbol
    return "●"


def ribbon_symbol(name: str) -> str:
    for key, symbol in RIBBON_SYMBOLS.items():
        if key.lower() in name.lower():
            return symbol
    return "✦"


def state() -> dict[str, Any]:
    if character is None:
        return {"ready": False}
    gym_preview = engine.gym_risk_preview(character)
    has_team = bool(character.team)
    age = character.age
    dead = bool(character.flags.get("dead"))
    career_years = dict(character.flags.get("career_years", {}))
    career_rank = character.career_rank() if character.career else 0
    career_xp = character.career_xp.get(character.career, 0) if character.career else 0
    career_needed = CAREER_RANK_XP[career_rank] if character.career and career_rank < 5 else 0
    has_business = bool(character.career and character.career in dict(character.flags.get("businesses", {})))
    has_retirement = bool(character.flags.get("retirement_pension"))
    action_availability = {
        "advance": not dead,
        "read": not dead and age >= 5,
        "work": not dead and age >= 5,
        "focus_career": not dead and age >= 5 and bool(character.career),
        "train": not dead and age >= 5 and has_team,
        "intensive_train": not dead and age >= 10 and has_team,
        "egg": not dead and age >= 10,
        "heal": not dead and age >= 5,
        "gym": not dead and age >= 10 and has_team,
        "steal": not dead and age >= 10,
        "set_career": not dead and age >= 5,
        "academy_focus": not dead and age >= 10 and character.career == "Estudante da academia",
        "buy_item": not dead and age >= 5,
        "use_item": not dead and age >= 5,
        "travel": not dead and age >= 10,
        "contest": not dead and age >= 10 and has_team and engine._period_action_available(character, "contest"),
        "breed": not dead and age >= 10 and len(character.team) >= 2 and engine._period_action_available(character, "breed"),
        "tournament": not dead and age >= 10 and has_team and engine._period_action_available(character, "tournament"),
        "hunt": not dead and age >= 10,
        "battle_search": not dead and age >= 10 and has_team,
        "hospital": not dead,
    }
    return {
        "ready": True,
        "name": character.name,
        "age": character.age,
        "phase": character.phase,
        "region": character.region,
        "city": engine.display_location_name(character.current_city),
        "city_description": CITY_DESCRIPTIONS.get(engine.display_location_name(character.current_city), ""),
        "health": character.health,
        "health_status": engine.health_status(character),
        "money": character.money,
        "reputation": character.reputation,
        "reputation_label": engine.reputation_info(character),
        "career": character.career or "Indefinida",
        "career_info": engine.career_rank_info(character),
        "career_goal": engine.career_goal_status(character) if character.career else "Sem carreira definida.",
        "career_summary": {
            "career": character.career or "Indefinida",
            "rank": career_rank,
            "rank_label": career_rank_label(character.career, character.career_ranks) if character.career else "",
            "xp": career_xp,
            "xp_needed": career_needed,
            "years": int(career_years.get(character.career, 0)) if character.career else 0,
            "has_business": has_business,
            "has_retirement": has_retirement,
            "breeder_infrastructure_level": int(character.flags.get("breeder_infrastructure_level", 0)),
            "academy_diplomas": list(character.flags.get("academy_diplomas", [])),
        },
        "academy_focus": engine.academy_focus_info(character),
        "attributes": character.attributes.to_dict(),
        "team": [pokemon_state(pokemon) for pokemon in character.team],
        "box": [pokemon_state(p) for p in character.box],
        "box_count": len(character.box),
        "period_used": {
            "tournament": not engine._period_action_available(character, "tournament"),
            "contest": not engine._period_action_available(character, "contest"),
            "breed": not engine._period_action_available(character, "breed"),
        },
        "eggs": [
            {
                "color": egg.color,
                "rarity": egg.rarity_label,
                "progress": egg.progress,
                "years_to_hatch": egg.years_to_hatch,
            }
            for egg in character.eggs
        ],
        "badges": character.badges,
        "badge_display": [{"name": badge, "symbol": badge_symbol(badge)} for badge in character.badges],
        "contest_ribbons": [
            {"name": ribbon, "symbol": ribbon_symbol(ribbon)}
            for ribbon in character.flags.get("contest_ribbons", [])
        ],
        "inventory": dict(sorted(character.inventory.items())),
        "has_kanto_map": engine._has_kanto_map(character),
        "travel_options": engine.travel_destinations(character),
        "history": [entry.to_dict() for entry in character.history[-12:]],
        "pokedex_seen": len(character.pokedex_seen),
        "pokedex_caught": len(character.pokedex_caught),
        "in_prison": bool(character.flags.get("in_prison")),
        "prison_months": int(character.flags.get("prison_months_remaining", 0)),
        "dead": dead,
        "death_cause": character.flags.get("death_cause"),
        "gym_preview": gym_preview,
        "action_availability": action_availability,
        "available_careers": engine.available_careers_for_character(character),
        "academy_options": engine.academy_focus_options(),
        "saves": list_saves(),
    }


def response(extra: dict[str, Any] | None = None):
    payload = {"state": state(), "feed": feed}
    if pending_event is not None:
        payload["pending_event"] = {
            "title": pending_event.title,
            "text": pending_event.text,
            "choices": pending_event_choices(),
        }
    else:
        payload["pending_event"] = None
    if extra:
        payload.update(extra)
    return jsonify(payload)


def pending_event_choices() -> list[dict[str, Any]]:
    if pending_event is None:
        return []
    if pending_event.event_id == "oak_starter":
        step = character.flags.get("oak_choice_step") if character is not None else None
        if step == "pokemon":
            options = list(character.flags.get("oak_pokemon_options", [])) if character is not None else []
            career = character.flags.get("oak_pending_career", "Jornada") if character is not None else "Jornada"
            return [
                {"index": index, "text": f"{name} - {career}"}
                for index, name in enumerate(options)
            ]
        if step == "academy_focus":
            return [
                {"index": index, "text": f"{option['name']} - Estudante"}
                for index, option in enumerate(engine.academy_focus_options())
            ]
        return [
            {"index": 0, "text": "Seguir como Treinador"},
            {"index": 1, "text": "Seguir como Criador"},
            {"index": 2, "text": "Seguir como Coordenador"},
            {"index": 3, "text": "Continuar como Estudante"},
        ]
    return [{"index": index, "text": choice.text} for index, choice in enumerate(pending_event.choices)]


def report_to_feed(report: str) -> None:
    if not report:
        return
    lines = [part.strip() for part in report.splitlines() if part.strip()]
    if not lines:
        return
    # First line is the header (e.g. "Resumo anual aos 7 anos")
    title = lines[0] if lines else "Resumo"
    body = "\n".join(lines[1:]) if len(lines) > 1 else ""
    text = body if body else title
    # Pick card kind based on content
    low = report.lower()
    if "game over" in low or "morreu" in low or "voce morreu" in low:
        kind = "health"
    elif "capturou" in low or "evolui" in low:
        kind = "pokemon"
    else:
        kind = "time"
    push(kind, text, title)


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/state")
def api_state():
    return response()


@app.get("/api/saves")
def api_saves():
    return jsonify(list_saves())


@app.post("/api/new")
def api_new():
    global character, feed, pending_event
    data = request.get_json(silent=True) or {}
    first_name = str(data.get("name") or "Red").strip() or "Red"
    first_name = first_name.split()[0]
    last_name = engine.name_database.random_last_name() if engine.name_database else ""
    name = f"{first_name} {last_name}".strip()
    cities = [loc.name for loc in engine.locations.values() if loc.kind == "city"]
    hometown = random.choice(cities) if cities else "Pallet Town"
    character = engine.create_character(name, hometown)
    character.flags["given_name"] = first_name
    character.flags["family_name"] = last_name
    feed = []
    pending_event = None
    desc = CITY_DESCRIPTIONS.get(hometown, "")
    birth_text = f"{character.name} nasceu em {hometown}, na regiao de Kanto."
    if desc:
        birth_text += f" {desc}"
    push("event", birth_text, "Nascimento")
    return response()


@app.post("/api/load")
def api_load():
    global character, feed, pending_event
    data = request.get_json(silent=True) or {}
    slot = str(data.get("slot") or "autosave")
    character = load_game(slot)
    feed = []
    pending_event = None
    push("event", f"Save carregado: {character.name}, {character.age} anos.", "Save")
    return response()


@app.post("/api/save")
def api_save():
    if character is None:
        return jsonify({"error": "Nenhum jogo ativo."}), 400
    data = request.get_json(silent=True) or {}
    slot = str(data.get("slot") or "autosave")
    path = save_game(character, slot)
    push("event", f"Jogo salvo em {path.name}.", "Save")
    return response()


@app.post("/api/advance")
def api_advance():
    global pending_event
    if character is None:
        return jsonify({"error": "Nenhum jogo ativo."}), 400
    if character.flags.get("dead"):
        push("health", "Game over: o tempo nao avanca apos a morte.", "Game Over")
        return response()
    if pending_event is not None:
        return jsonify({"error": "Responda o evento pendente antes de avançar o tempo."}), 400
    data = request.get_json(silent=True) or {}
    months = int(data.get("months") or 12)
    pending_event = engine.advance_time(character, months)
    report_to_feed(str(character.flags.get("last_year_report", "")))
    if pending_event is not None:
        push("event", pending_event.text, pending_event.title)
    return response()


@app.post("/api/event_choice")
def api_event_choice():
    global pending_event
    if character is None or pending_event is None:
        return jsonify({"error": "Nenhum evento pendente."}), 400
    data = request.get_json(silent=True) or {}
    index = int(data.get("index") or 0)
    if pending_event.event_id == "oak_starter":
        step = character.flags.get("oak_choice_step")
        if step == "pokemon":
            options = list(character.flags.get("oak_pokemon_options", []))
            if not options:
                return jsonify({"error": "Nenhum Pokemon disponivel para esta escolha."}), 400
            selected = options[max(0, min(index, len(options) - 1))]
            career = str(character.flags.get("oak_pending_career") or "Treinador")
            text = engine.choose_starter(character, selected, career)
            for key in ("oak_choice_step", "oak_pending_career", "oak_pokemon_options"):
                character.flags.pop(key, None)
            pending_event = None
        elif step == "academy_focus":
            options = engine.academy_focus_options()
            if not options:
                return jsonify({"error": "Nenhum foco academico disponivel."}), 400
            option = options[max(0, min(index, len(options) - 1))]
            focus_type = "Normal" if option["id"] == "pokemon_types" else None
            ok, text = engine.set_academy_focus(character, option["id"], focus_type)
            if ok:
                character.flags.pop("oak_choice_step", None)
                pending_event = None
        else:
            careers = ["Treinador", "Criador", "Coordenador", "Estudante da academia"]
            career = careers[max(0, min(index, len(careers) - 1))]
            if career == "Estudante da academia":
                text = engine.choose_starter(character, None, career)
                character.flags["oak_choice_step"] = "academy_focus"
            else:
                options = engine.oak_pokemon_options_for_career(career)
                character.flags["oak_pending_career"] = career
                character.flags["oak_pokemon_options"] = options
                character.flags["oak_choice_step"] = "pokemon"
                text = f"Professor Oak aprovou sua escolha: {career}. Agora escolha seu primeiro Pokemon."
    else:
        text = engine.apply_event_choice(character, pending_event, index)
        pending_event = None
    if text:
        push("event", text, "Escolha")
    return response()


@app.post("/api/action/<name>")
def api_action(name: str):
    if character is None:
        return jsonify({"error": "Nenhum jogo ativo."}), 400
    data = request.get_json(silent=True) or {}
    kind = "event"
    if name == "read":
        message = engine.manual_action_read_about_pokemon(character)
        kind = "career"
    elif name == "work":
        message = engine.manual_action_work_city(character)
        kind = "money"
    elif name == "focus_career":
        message = engine.manual_action_focus_career(character)
        kind = "career"
    elif name == "train":
        message = engine.manual_action_train_team(character)
        kind = "pokemon"
    elif name == "intensive_train":
        message = engine.manual_action_intensive_training(character)
        kind = "battle"
    elif name == "egg":
        message = engine.manual_action_search_for_egg(character)
        kind = "egg"
    elif name == "heal":
        message = engine.heal_team_in_city(character)
        kind = "health"
    elif name == "gym":
        ok, log = engine.challenge_city_gym(character)
        message = "\n".join(log)
        kind = "battle" if "BATALHA|" in message else "health"
    elif name == "steal":
        _, message = engine.steal_pokemon(character)
        kind = "crime"
    elif name == "set_career":
        career = str(data.get("career") or "")
        ok = engine.set_career(character, career)
        message = f"Agora voce segue {career}." if ok else "Carreira indisponivel aqui."
        kind = "career"
    elif name == "academy_focus":
        ok, message = engine.set_academy_focus(character, str(data.get("focus") or ""), data.get("type"))
        kind = "career" if ok else "event"
    elif name == "use_item":
        item_name = str(data.get("item") or "")
        item = engine.items.get(item_name)
        ok, message = engine.use_item(character, item_name)
        kind = "pokemon" if ok and item and item.item_type == "evolution" else ("health" if ok else "event")
    elif name == "buy_item":
        ok, message = engine.buy_item(character, str(data.get("item") or ""), int(data.get("quantity") or 1))
        kind = "money" if ok else "event"
    elif name == "travel":
        destination = str(data.get("city") or "").strip()
        if destination and re.match(r"^[A-Z]\d+$", destination):
            ok, message = engine.travel_to(character, destination)
        else:
            ok, message = engine.move_to_city(character, destination)
        kind = "travel"
    elif name == "contest":
        ok, result, message = engine.enter_contest(
            character,
            int(data.get("pokemon_index") or 0),
            str(data.get("difficulty") or "local"),
            str(data.get("category") or "beauty"),
        )
        if result:
            message = message + "\n" + "\n".join(result.log[:8])
        kind = "contest" if ok else "event"
    elif name == "breed":
        ok, message = engine.breed_pokemon(character, int(data.get("first") or 0), int(data.get("second") or 1))
        kind = "egg" if ok else "event"
    elif name == "hunt":
        ok, message = engine.manual_action_hunt_wild_pokemon(character)
        kind = "pokemon" if ok else "event"
    elif name == "battle_search":
        ok, message = engine.manual_action_search_trainer_battle(character)
        kind = "battle"
    else:
        return jsonify({"error": "Acao desconhecida."}), 404
    push(kind, message, "Acao")
    return response()


@app.get("/api/hospital")
def api_hospital_options():
    if character is None:
        return jsonify({"error": "Nenhum jogo ativo."}), 400
    return jsonify(engine.hospital_options(character))


@app.post("/api/hospital")
def api_hospital():
    if character is None:
        return jsonify({"error": "Nenhum jogo ativo."}), 400
    data = request.get_json(silent=True) or {}
    option_key = str(data.get("option") or "leve")
    ok, message = engine.go_to_hospital(character, option_key)
    push("health" if ok else "event", message, "Hospital")
    return response()


@app.post("/api/team/reorder")
def api_team_reorder():
    if character is None:
        return jsonify({"error": "Nenhum jogo ativo."}), 400
    data = request.get_json(silent=True) or {}
    ok, message = engine.reorder_team(
        character,
        int(data.get("from_index") or 0),
        int(data.get("to_index") or 0),
    )
    if not ok:
        return jsonify({"error": message}), 400
    push("pokemon", message, "Equipe")
    return response()


@app.post("/api/box/swap")
def api_box_swap():
    if character is None:
        return jsonify({"error": "Nenhum jogo ativo."}), 400
    data = request.get_json(silent=True) or {}
    ok, message = engine.swap_box_pokemon(
        character,
        int(data.get("team_index") or 0),
        int(data.get("box_index") or 0),
    )
    if not ok:
        return jsonify({"error": message}), 400
    push("pokemon", message, "Box")
    return response()


@app.get("/api/shop")
def api_shop():
    if character is None:
        return jsonify({"error": "Nenhum jogo ativo."}), 400
    return jsonify([
        {"name": item.name, "price": price, "type": item.item_type,
         "effect": item.effect or "", "healing": item.healing}
        for item, price in engine.city_shop_items(character)
    ])


@app.get("/api/cities")
def api_cities():
    return jsonify([location.name for location in engine.locations.values() if location.kind == "city"])


@app.get("/api/tournaments")
def api_tournaments():
    if character is None:
        return jsonify({"error": "Nenhum jogo ativo."}), 400
    return jsonify(engine.available_tournaments(character))


@app.post("/api/tournament")
def api_tournament():
    if character is None:
        return jsonify({"error": "Nenhum jogo ativo."}), 400
    data = request.get_json(silent=True) or {}
    ok, result, message = engine.enter_tournament(character, str(data.get("kind") or "city"))
    if result:
        message = message + "\n" + "\n".join(result.log[:12])
    push("tournament" if ok else "event", message, "Torneio")
    return response()


if __name__ == "__main__":
    app.run(debug=True, port=5000)
