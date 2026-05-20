from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from flask import Flask, jsonify, render_template, request

from game.character import Character
from game.engine import GameEngine
from game.save_system import list_saves, load_game, save_game


app = Flask(__name__)
engine = GameEngine()

character: Character | None = None
feed: list[dict[str, Any]] = []
pending_event = None


def card(kind: str, text: str, title: str | None = None) -> dict[str, str]:
    year = character.age if character is not None else 0
    return {"kind": kind, "title": title or kind.title(), "text": str(text), "time": f"Ano {year}"}


def push(kind: str, text: str, title: str | None = None) -> None:
    feed.insert(0, card(kind, text, title))
    del feed[80:]


def pokemon_state(pokemon) -> dict[str, Any]:
    species = engine.pokemon.get(pokemon.species)
    return {
        "name": pokemon.display_name(),
        "species": pokemon.species,
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
    }


def state() -> dict[str, Any]:
    if character is None:
        return {"ready": False}
    gym_preview = engine.gym_risk_preview(character)
    has_team = bool(character.team)
    age = character.age
    action_availability = {
        "read": age >= 5,
        "work": age >= 5,
        "focus_career": age >= 5 and bool(character.career),
        "train": age >= 5 and has_team,
        "intensive_train": age >= 10 and has_team,
        "egg": age >= 10,
        "heal": age >= 5,
        "gym": age >= 10 and has_team,
        "steal": age >= 10,
        "set_career": age >= 5,
        "academy_focus": age >= 10 and character.career == "Estudante da academia",
        "buy_item": age >= 5,
        "use_item": age >= 5,
        "travel": age >= 10,
        "contest": age >= 10 and has_team,
        "breed": age >= 10 and len(character.team) >= 2,
        "tournament": age >= 10 and has_team,
    }
    return {
        "ready": True,
        "name": character.name,
        "age": character.age,
        "phase": character.phase,
        "region": character.region,
        "city": engine.display_location_name(character.current_city),
        "health": character.health,
        "health_status": engine.health_status(character),
        "money": character.money,
        "reputation": character.reputation,
        "reputation_label": engine.reputation_info(character),
        "career": character.career or "Indefinida",
        "career_info": engine.career_rank_info(character),
        "career_goal": engine.career_goal_status(character) if character.career else "Sem carreira definida.",
        "academy_focus": engine.academy_focus_info(character),
        "attributes": character.attributes.to_dict(),
        "team": [pokemon_state(pokemon) for pokemon in character.team],
        "box_count": len(character.box),
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
        "inventory": dict(sorted(character.inventory.items())),
        "history": [entry.to_dict() for entry in character.history[-12:]],
        "pokedex_seen": len(character.pokedex_seen),
        "pokedex_caught": len(character.pokedex_caught),
        "in_prison": bool(character.flags.get("in_prison")),
        "prison_months": int(character.flags.get("prison_months_remaining", 0)),
        "dead": bool(character.flags.get("dead")),
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
        return [
            {"index": 0, "text": "Bulbasaur - Treinador"},
            {"index": 1, "text": "Charmander - Treinador"},
            {"index": 2, "text": "Squirtle - Treinador"},
            {"index": 3, "text": "Bulbasaur - Criador"},
            {"index": 4, "text": "Charmander - Coordenador"},
            {"index": 5, "text": "Recusar por enquanto"},
        ]
    return [{"index": index, "text": choice.text} for index, choice in enumerate(pending_event.choices)]


def report_to_feed(report: str) -> None:
    if not report:
        return
    for line in reversed([part.strip() for part in report.splitlines() if part.strip()]):
        lower = line.lower()
        if lower.startswith("resumo"):
            push("time", line, "Tempo")
        elif "game over" in lower or "morreu" in lower or "saude" in lower:
            push("health", line, "Saude")
        elif "captur" in lower or "pokemon:" in lower:
            push("pokemon", line, "Pokemon")
        elif "batalha" in lower or "ginasio" in lower or "insignia" in lower:
            push("battle", line, "Batalhas")
        elif "dinheiro" in lower or "pokedollar" in lower or "renda" in lower:
            push("money", line, "Dinheiro")
        elif "ovo" in lower:
            push("egg", line, "Ovos")
        elif "profissao" in lower or "carreira" in lower or "academ" in lower:
            push("career", line, "Carreira")
        else:
            push("event", line, "Vida")


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
    name = str(data.get("name") or "Red").strip() or "Red"
    hometown = str(data.get("hometown") or "Pallet Town")
    character = engine.create_character(name, hometown)
    feed = []
    pending_event = None
    push("event", f"{character.name} nasceu em {hometown}, na regiao de Kanto.", "Nascimento")
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
        oak_choices = [
            ("Bulbasaur", "Treinador"),
            ("Charmander", "Treinador"),
            ("Squirtle", "Treinador"),
            ("Bulbasaur", "Criador"),
            ("Charmander", "Coordenador"),
            (None, None),
        ]
        starter, career = oak_choices[max(0, min(index, len(oak_choices) - 1))]
        text = engine.choose_starter(character, starter, career)
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
        kind = "battle" if ok else "health"
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
        ok, message = engine.use_item(character, str(data.get("item") or ""))
        kind = "health" if ok else "event"
    elif name == "buy_item":
        ok, message = engine.buy_item(character, str(data.get("item") or ""), int(data.get("quantity") or 1))
        kind = "money" if ok else "event"
    elif name == "travel":
        ok = engine.move_to_city(character, str(data.get("city") or ""))
        message = f"Voce viajou para {engine.display_location_name(character.current_city)}." if ok else "Viagem indisponivel."
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
    else:
        return jsonify({"error": "Acao desconhecida."}), 404
    push(kind, message, "Acao")
    return response()


@app.get("/api/shop")
def api_shop():
    if character is None:
        return jsonify({"error": "Nenhum jogo ativo."}), 400
    return jsonify([
        {"name": item.name, "price": price, "type": item.item_type, "description": item.description}
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
    print("Poke Life web: http://localhost:5000")
    app.run(host="127.0.0.1", port=5000, debug=True)
