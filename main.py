from __future__ import annotations

from pathlib import Path

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Prompt
    from rich.table import Table
except ImportError as exc:  # pragma: no cover
    raise SystemExit("Instale a dependencia com: pip install rich") from exc

from game.character import Character
from game.engine import GameEngine
from game.events import LifeEvent
from game.save_system import list_saves, load_game, save_game


console = Console()
engine = GameEngine()


def show_header(character: Character) -> None:
    table = Table.grid(expand=True)
    table.add_column(ratio=1)
    table.add_column(ratio=1)
    table.add_row(
        f"[bold]{character.name}[/bold]\n"
        f"Idade: {character.age}\n"
        f"Fase: {character.phase}\n"
        f"Local: {engine.display_location_name(character.current_city)}, {character.region}",
        f"Saude: {character.health} ({engine.health_status(character)})\n"
        f"Dinheiro: {character.money} Pokedollar\n"
        f"Reputacao: {engine.reputation_info(character)}\n"
        f"Carreira: {character.career or 'indefinida'}",
    )
    console.print(Panel(table, title="Poke Life"))


def show_character(character: Character) -> None:
    show_header(character)
    attrs = Table(title="Atributos")
    attrs.add_column("Atributo")
    attrs.add_column("Valor", justify="right")
    for key, value in character.attributes.as_items():
        attrs.add_row(key.replace("_", " ").title(), str(value))
    console.print(attrs)


def show_team(character: Character) -> None:
    table = Table(title="Equipe Pokemon")
    table.add_column("Pokemon")
    table.add_column("Nivel", justify="right")
    table.add_column("COMBAT", justify="right")
    table.add_column("BEAUTY", justify="right")
    table.add_column("HEALTHY", justify="right")
    table.add_column("HP", justify="right")
    table.add_column("OCCULT", justify="right")
    table.add_column("Condicao", justify="right")
    table.add_column("Ativo", justify="center")
    if not character.team:
        table.add_row("Nenhum Pokemon na equipe", "-", "-", "-", "-", "-", "-", "-", "-")
    for index, pokemon in enumerate(character.team):
        species = engine.pokemon.get(pokemon.species)
        table.add_row(
            pokemon.display_name(),
            str(pokemon.level),
            str(pokemon.combat),
            str(pokemon.beauty),
            str(pokemon.healthy),
            f"{pokemon.current_health}/{pokemon.max_health(species)}",
            str(pokemon.occult),
            pokemon.status,
            "*" if index == character.active_pokemon_index else "",
        )
    console.print(table)
    if character.box:
        console.print(f"Box: {', '.join(p.display_name() for p in character.box)}")


def show_history(character: Character, limit: int | None = None) -> None:
    entries = character.history[-limit:] if limit else character.history
    table = Table(title="Historico de vida")
    table.add_column("Idade", justify="right")
    table.add_column("Entrada")
    for entry in entries:
        table.add_row(str(entry.age), entry.text)
    console.print(table)


def show_badges(character: Character) -> None:
    badges = ", ".join(character.badges) if character.badges else "Nenhuma insignia ainda."
    console.print(Panel(badges, title="Insignias"))


def show_inventory(character: Character) -> None:
    table = Table(title="Inventario")
    table.add_column("Item")
    table.add_column("Qtd.", justify="right")
    if not character.inventory:
        table.add_row("Vazio", "0")
    for item, amount in sorted(character.inventory.items()):
        table.add_row(item, str(amount))
    console.print(table)
    if character.eggs:
        egg_table = Table(title="Poke Eggs")
        egg_table.add_column("Cor")
        egg_table.add_column("Raridade")
        egg_table.add_column("Progresso", justify="right")
        for egg in character.eggs:
            egg_table.add_row(egg.color, egg.rarity_label, f"{egg.progress}/{egg.years_to_hatch}")
        console.print(egg_table)


def use_item_menu(character: Character) -> None:
    usable = [(item, amount) for item, amount in sorted(character.inventory.items()) if amount > 0]
    if not usable:
        console.print("Inventario vazio.")
        return
    for index, (item, amount) in enumerate(usable, start=1):
        console.print(f"{index}. {item} x{amount}")
    console.print(f"{len(usable) + 1}. Voltar")
    selected = int(Prompt.ask("Usar item", choices=[str(i) for i in range(1, len(usable) + 2)]))
    if selected == len(usable) + 1:
        return
    item_name = usable[selected - 1][0]
    _, message = engine.use_item(character, item_name)
    console.print(message)


def career_menu(character: Character) -> None:
    careers = engine.available_careers_for_character(character)
    if not careers:
        console.print("Nenhuma carreira disponivel aqui agora.")
        return
    for index, career in enumerate(careers, start=1):
        marker = " (atual)" if career == character.career else ""
        console.print(f"{index}. {career}{marker}")
    selected = int(Prompt.ask("Escolha uma rotina/carreira", choices=[str(i) for i in range(1, len(careers) + 1)]))
    career = careers[selected - 1]
    if engine.set_career(character, career):
        console.print(f"Agora voce segue: {career}.")
    else:
        console.print("Essa carreira ainda nao esta disponivel.")


def active_pokemon_menu(character: Character) -> None:
    if not character.team:
        console.print("Voce ainda nao tem Pokemon.")
        return
    for index, pokemon in enumerate(character.team, start=1):
        marker = " (ativo)" if index - 1 == character.active_pokemon_index else ""
        console.print(f"{index}. {pokemon.display_name()} Lv.{pokemon.level}{marker}")
    selected = int(Prompt.ask("Pokemon ativo", choices=[str(i) for i in range(1, len(character.team) + 1)]))
    if engine.set_active_pokemon(character, selected - 1):
        console.print(f"{character.active_pokemon().display_name()} agora lidera a equipe.")


def box_menu(character: Character) -> None:
    while True:
        console.print("1. Mover equipe para Box")
        console.print("2. Mover Box para equipe")
        console.print("3. Voltar")
        choice = Prompt.ask("Box", choices=["1", "2", "3"], default="3")
        if choice == "1":
            if not character.team:
                console.print("Equipe vazia.")
                continue
            for index, pokemon in enumerate(character.team, start=1):
                console.print(f"{index}. {pokemon.display_name()} Lv.{pokemon.level}")
            selected = int(Prompt.ask("Enviar para Box", choices=[str(i) for i in range(1, len(character.team) + 1)]))
            _, message = engine.move_team_to_box(character, selected - 1)
            console.print(message)
        elif choice == "2":
            if not character.box:
                console.print("Box vazia.")
                continue
            for index, pokemon in enumerate(character.box, start=1):
                console.print(f"{index}. {pokemon.display_name()} Lv.{pokemon.level}")
            selected = int(Prompt.ask("Trazer para equipe", choices=[str(i) for i in range(1, len(character.box) + 1)]))
            _, message = engine.move_box_to_team(character, selected - 1)
            console.print(message)
        else:
            return


def yearly_actions_menu(character: Character) -> None:
    while True:
        rank_info = engine.career_rank_info(character)
        console.print(f"[dim]{rank_info}[/dim]")
        console.print("1. Ir ao Pokemon Center")
        console.print("2. Ler sobre Pokemon")
        console.print("3. Trabalhar na cidade (renda extra)")
        console.print("4. Focar na carreira (XP de rank + renda)")
        console.print("5. Treinar Pokemon ativo")
        console.print("6. Treino intensivo")
        console.print("7. Procurar ovos no habitat")
        console.print("8. Voltar")
        choice = Prompt.ask("Acao anual", choices=["1", "2", "3", "4", "5", "6", "7", "8"], default="8")
        if choice == "1":
            console.print(engine.heal_team_in_city(character))
        elif choice == "2":
            console.print(engine.manual_action_read_about_pokemon(character))
        elif choice == "3":
            console.print(engine.manual_action_work_city(character))
        elif choice == "4":
            console.print(engine.manual_action_focus_career(character))
        elif choice == "5":
            console.print(engine.manual_action_train_team(character))
        elif choice == "6":
            console.print(engine.manual_action_intensive_training(character))
        elif choice == "7":
            console.print(engine.manual_action_search_for_egg(character))
        else:
            return


def city_menu(character: Character) -> None:
    city = engine.get_city_services(character.current_city)
    if not city:
        console.print("Voce nao esta em uma cidade com servicos urbanos.")
        return

    while True:
        console.print(Panel(
            f"Servicos: {', '.join(city.services)}\n"
            f"Carreiras locais: {', '.join(city.careers) if city.careers else 'nenhuma'}",
            title=engine.display_location_name(character.current_city),
        ))
        console.print("1. Loja")
        console.print("2. Pokemon Center")
        console.print("3. Carreiras locais")
        console.print("4. Ginasio")
        console.print("5. Voltar")
        choice = Prompt.ask("Cidade", choices=["1", "2", "3", "4", "5"], default="5")
        if choice == "1":
            shop_menu(character)
        elif choice == "2":
            console.print(engine.heal_team_in_city(character))
        elif choice == "3":
            career_menu(character)
        elif choice == "4":
            gym = engine.get_city_gym(character)
            if not gym:
                console.print("Nao ha ginasio nesta cidade.")
                continue
            console.print(
                Panel(
                    f"Lider: {gym['leader']}\n"
                    f"Tipo: {gym['main_type']}\n"
                    f"Insignia: {gym['badge']}\n"
                    f"Nivel recomendado: {gym['recommended_level']}\n"
                    f"{_format_gym_risk(character)}",
                    title=f"Ginasio de {gym['city']}",
                )
            )
            if Prompt.ask("Desafiar agora?", choices=["s", "n"], default="n") == "s":
                _, log = engine.challenge_city_gym(character)
                console.print(Panel("\n".join(log), title="Resultado do ginasio"))
        else:
            return


def _format_gym_risk(character: Character) -> str:
    preview = engine.gym_risk_preview(character)
    if not preview:
        return "Previa: indisponivel."
    if not preview.get("available"):
        return f"Previa: {preview['summary']}"
    return (
        f"Previa: risco {preview['risk']} | chance estimada {preview['estimated_win_chance']}%\n"
        f"Seu time: media top 3 Lv.{preview['team_average']} | mais forte Lv.{preview['strongest_level']}\n"
        f"Nota: {preview['summary']}"
    )


def shop_menu(character: Character) -> None:
    items = engine.city_shop_items(character)
    if not items:
        console.print("Nao ha loja disponivel aqui.")
        return
    for index, (item, price) in enumerate(items, start=1):
        console.print(f"{index}. {item.name} - {price} Pokedollar")
    console.print(f"{len(items) + 1}. Voltar")
    selected = int(Prompt.ask("Comprar", choices=[str(i) for i in range(1, len(items) + 2)]))
    if selected == len(items) + 1:
        return
    item, _ = items[selected - 1]
    quantity = int(Prompt.ask("Quantidade", default="1"))
    _, message = engine.buy_item(character, item.name, quantity)
    console.print(message)


def handle_event(character: Character, event: LifeEvent | None) -> None:
    if event is None:
        console.print("Nada marcante aconteceu desta vez.")
        return

    console.print(Panel(event.text, title=event.title))
    if event.event_id == "oak_starter":
        career_choices = ["Treinador", "Criador", "Coordenador", "Recusar jornada por enquanto"]
        for index, choice in enumerate(career_choices, start=1):
            console.print(f"{index}. {choice}")
        career_selected = int(Prompt.ask("Profissao", choices=[str(i) for i in range(1, len(career_choices) + 1)], default="1"))
        career = career_choices[career_selected - 1]
        if career.startswith("Recusar"):
            console.print(engine.choose_starter(character, None))
            return
        starters = ["Bulbasaur", "Charmander", "Squirtle"]
        for index, starter_name in enumerate(starters, start=1):
            console.print(f"{index}. {starter_name}")
        starter_selected = int(Prompt.ask("Pokemon inicial", choices=["1", "2", "3"], default="1"))
        console.print(engine.choose_starter(character, starters[starter_selected - 1], career))
        return

    for index, choice in enumerate(event.choices, start=1):
        console.print(f"{index}. {choice.text}")
    selected = int(Prompt.ask("Escolha", choices=[str(i) for i in range(1, len(event.choices) + 1)]))
    history = engine.apply_event_choice(character, event, selected - 1)
    if history:
        console.print(f"[green]{history}[/green]")


def advance_time(character: Character) -> None:
    console.print("1. 3 meses")
    console.print("2. 6 meses")
    console.print("3. 1 ano")
    choice = Prompt.ask("Avancar", choices=["1", "2", "3"], default="3")
    months = {"1": 3, "2": 6, "3": 12}[choice]
    event = engine.advance_time(character, months)
    handle_event(character, event)
    report = character.flags.get("last_year_report")
    if report:
        console.print(Panel(str(report), title="Resumo do periodo"))


def explore(character: Character) -> None:
    species, level, text = engine.wild_encounter(character)
    console.print(Panel(text, title="Encontro selvagem"))
    while True:
        console.print("1. Tentar capturar")
        console.print("2. Batalhar")
        console.print("3. Observar")
        console.print("4. Fugir")
        choice = Prompt.ask("Acao", choices=["1", "2", "3", "4"], default="1")
        if choice == "1":
            ball = engine.best_available_ball(character, species)
            console.print(f"Voce prepara: {ball}.")
            _, message = engine.capture_wild(character, species.name, level)
            console.print(message)
            return
        if choice == "2":
            _, log = engine.battle_wild(character, species.name, level)
            console.print(Panel("\n".join(log), title="Batalha"))
            return
        if choice == "3":
            character.attributes.modify({"POK": 1})
            character.add_history(f"Voce observou um {species.name} selvagem em {character.current_city}.")
            console.print(f"Voce observa {species.name} e aprende um pouco mais sobre Pokemon.")
            return
        character.add_history(f"Voce evitou um encontro com {species.name} em {character.current_city}.")
        console.print("Voce se afasta com cuidado.")
        return


def _render_grid(character: Character) -> None:
    """Exibe a grade completa de Kanto estilo batalha naval (so com mapa)."""
    grid_data = engine.full_grid_for_display(character)
    if not grid_data:
        return
    t = Table(title="Mapa de Kanto", show_header=True, header_style="bold cyan")
    t.add_column(" ", style="bold cyan", width=2)
    cols = engine.grid.cols if engine.grid else list(range(1, 7))
    for col in cols:
        t.add_column(str(col), justify="center", width=14)
    for row_cells in grid_data:
        row_label = row_cells[0]["coord"][0]
        cells_rendered = []
        for cell in row_cells:
            if not cell.get("passable", False):
                cells_rendered.append("[dim]..[/dim]")
                continue
            icon = cell.get("icon", "~~")
            name = (cell.get("name") or cell["coord"])[:10]
            coord = cell["coord"]
            if cell.get("current", False):
                cells_rendered.append(f"[bold green]{icon} {coord}[/bold green]\n[bold green]{name}[/bold green]")
            else:
                kind = cell.get("kind", "route")
                color = {"city": "yellow", "cave": "red", "forest": "green", "route": "white"}.get(kind, "white")
                cells_rendered.append(f"[{color}]{icon} {coord}[/{color}]\n[dim]{name}[/dim]")
        t.add_row(row_label, *cells_rendered)
    console.print(t)


def travel_menu(character: Character) -> None:
    if character.age < 10:
        console.print("Voce ainda e jovem demais para viajar sozinho.")
        return

    has_map = bool(character.flags.get("has_kanto_map"))

    if not has_map:
        # Sem mapa: viagem aleatoria para setor adjacente — sem escolha do jogador
        if Prompt.ask("Partir sem saber para onde vai?", choices=["s", "n"], default="s") != "s":
            return
        ok, destination = engine.travel_random(character)
        if ok:
            console.print(f"Voce pegou a estrada e chegou a [bold]{destination}[/bold].")
        else:
            console.print(f"[red]{destination}[/red]")
        return

    # Com mapa: exibe grade visual e deixa o jogador escolher destino adjacente
    _render_grid(character)
    current_coord = engine.current_coord(character)
    console.print(f"\n[bold]Posicao atual:[/bold] {current_coord} — {character.current_city}")

    destinations = engine.travel_destinations(character)
    if not destinations:
        console.print("Nao ha para onde ir daqui.")
        return

    console.print("\n[bold]Destinos adjacentes:[/bold]")
    for index, dest in enumerate(destinations, start=1):
        coord = dest["coord"]
        name = dest.get("name", coord)
        gym_mark = " [bold yellow][Ginasio][/bold yellow]" if dest.get("has_gym") else ""
        svcs = ", ".join(dest.get("services", [])) or dest.get("kind", "rota")
        kind_icons = {"city": "[]", "cave": "^^", "forest": "%%", "route": "~~"}
        icon = kind_icons.get(dest.get("kind", "route"), "~~")
        console.print(f"  [cyan]{index}.[/cyan] {icon} [bold]{coord}[/bold] — {name}{gym_mark}  [dim]({svcs})[/dim]")
    console.print(f"  [cyan]{len(destinations) + 1}.[/cyan] Voltar")

    choice = Prompt.ask(
        "Viajar para",
        choices=[str(i) for i in range(1, len(destinations) + 2)],
        default=str(len(destinations) + 1),
    )
    idx = int(choice) - 1
    if idx >= len(destinations):
        return
    ok, msg = engine.travel_to(character, destinations[idx]["coord"])
    console.print(f"[green]{msg}[/green]" if ok else f"[red]{msg}[/red]")


def show_pokedex(character: Character) -> None:
    summary = engine.pokedex_summary(character)
    table = Table(title=f"Pokedex — {summary['caught']}/{summary['total']} capturados, {summary['seen']} vistos")
    table.add_column("Status")
    table.add_column("Pokemon")
    caught_set = set(summary["caught_list"])
    for name in summary["seen_list"]:
        status = "[green]Capturado[/green]" if name in caught_set else "[yellow]Visto[/yellow]"
        table.add_row(status, name)
    if not summary["seen_list"]:
        table.add_row("-", "Nenhum Pokemon registrado ainda.")
    console.print(table)


def tournament_menu(character: Character) -> None:
    tournaments = engine.available_tournaments(character)
    console.print(Panel(
        "\n".join(
            f"{'[green]' if t['available'] else '[red]'}{t['label']}[/] — "
            f"Inscricao: {t['entry_fee']}P | Premio total: ~{t['prize_pool']}P | "
            f"Rodadas: {t['rounds']} | Insignias min.: {t['min_badges']} | Rep min.: {t.get('min_reputation', 0)}"
            + (f"\n  [dim]{t['reason']}[/dim]" if not t['available'] else "")
            for t in tournaments
        ),
        title="Torneios disponíveis",
    ))
    available = [t for t in tournaments if t["available"]]
    if not available:
        console.print("Nenhum torneio disponivel no momento.")
        return
    for index, t in enumerate(available, start=1):
        console.print(f"{index}. {t['label']}")
    console.print(f"{len(available) + 1}. Voltar")
    choice = Prompt.ask(
        "Participar de",
        choices=[str(i) for i in range(1, len(available) + 2)],
        default=str(len(available) + 1),
    )
    idx = int(choice) - 1
    if idx >= len(available):
        return
    kind = available[idx]["kind"]
    ok, result, msg = engine.enter_tournament(character, kind)
    if not ok:
        console.print(f"[red]{msg}[/red]")
        return
    console.print(Panel("\n".join(result.log), title="Resultado do torneio"))


def contest_menu(character: Character) -> None:
    if not character.team:
        console.print("Voce precisa de Pokemon para participar de contests.")
        return
    for index, pokemon in enumerate(character.team, start=1):
        console.print(f"{index}. {pokemon.display_name()} Lv.{pokemon.level} | BEAUTY {pokemon.beauty}")
    pokemon_choice = int(Prompt.ask("Pokemon", choices=[str(i) for i in range(1, len(character.team) + 1)], default="1"))
    levels = ["local", "city", "regional"]
    for index, level in enumerate(levels, start=1):
        console.print(f"{index}. {level}")
    level_choice = int(Prompt.ask("Dificuldade", choices=["1", "2", "3"], default="1"))
    ok, result, msg = engine.enter_contest(character, pokemon_choice - 1, levels[level_choice - 1])
    if not ok:
        console.print(f"[red]{msg}[/red]")
        return
    console.print(Panel("\n".join(result.log), title="Contest"))


def breeding_menu(character: Character) -> None:
    if len(character.team) < 2:
        console.print("Voce precisa de pelo menos dois Pokemon na equipe.")
        return
    for index, pokemon in enumerate(character.team, start=1):
        console.print(f"{index}. {pokemon.display_name()} | Felicidade {pokemon.happiness} | Tipos: {', '.join(pokemon.types)}")
    first = int(Prompt.ask("Primeiro Pokemon", choices=[str(i) for i in range(1, len(character.team) + 1)], default="1")) - 1
    second = int(Prompt.ask("Segundo Pokemon", choices=[str(i) for i in range(1, len(character.team) + 1)], default="2")) - 1
    preview = engine.breeding_preview(character, first, second)
    if not preview.get("available"):
        console.print(preview["summary"])
        return
    console.print(Panel(
        f"{preview['first']} + {preview['second']}\nChance estimada: {preview['chance']}%\nBonus de criador: {'sim' if preview['career_bonus'] else 'nao'}",
        title="Criacao Pokemon",
    ))
    if Prompt.ask("Tentar gerar ovo?", choices=["s", "n"], default="s") == "s":
        _, message = engine.breed_pokemon(character, first, second)
        console.print(message)


def save_menu(character: Character) -> None:
    slot = Prompt.ask("Nome do save", default="autosave")
    path = save_game(character, slot)
    console.print(f"Jogo salvo em {path}.")


def load_menu() -> Character | None:
    saves = list_saves()
    if not saves:
        console.print("Nenhum save encontrado.")
        return None
    for index, save in enumerate(saves, start=1):
        console.print(f"{index}. {save}")
    selected = int(Prompt.ask("Carregar", choices=[str(i) for i in range(1, len(saves) + 1)]))
    return load_game(saves[selected - 1])


def new_game() -> Character:
    name = Prompt.ask("Nome do personagem", default="Red")
    character = engine.create_character(name)
    console.print(f"{character.name} nasceu em Pallet Town.")
    return character


def main() -> None:
    console.print(Panel("Simulador textual de vida em Kanto", title="Poke Life"))
    character: Character | None = None
    if list_saves() and Prompt.ask("Carregar save existente?", choices=["s", "n"], default="n") == "s":
        character = load_menu()
    if character is None:
        character = new_game()

    while True:
        show_header(character)
        show_history(character, limit=3)
        console.print("1.  Avancar tempo")
        console.print("2.  Ver personagem")
        console.print("3.  Ver equipe")
        console.print("4.  Ver historico")
        console.print("5.  Ver insignias")
        console.print("6.  Ver inventario")
        console.print("7.  Usar item")
        console.print("8.  Acoes da cidade")
        console.print("9.  Explorar cidade/rota")
        console.print("10. Viajar para outra cidade")
        console.print("11. Escolher rotina/carreira")
        console.print("12. Escolher Pokemon ativo")
        console.print("13. Box Pokemon")
        console.print("14. Acoes do ano")
        console.print("15. Torneios")
        console.print("16. Contests")
        console.print("17. Criacao Pokemon")
        console.print("18. Pokedex")
        console.print("19. Salvar jogo")
        console.print("20. Carregar jogo")
        console.print("21. Sair")
        choice = Prompt.ask("Menu", choices=[str(i) for i in range(1, 22)], default="1")

        if choice == "1":
            advance_time(character)
        elif choice == "2":
            show_character(character)
        elif choice == "3":
            show_team(character)
        elif choice == "4":
            show_history(character)
        elif choice == "5":
            show_badges(character)
        elif choice == "6":
            show_inventory(character)
        elif choice == "7":
            use_item_menu(character)
        elif choice == "8":
            city_menu(character)
        elif choice == "9":
            explore(character)
        elif choice == "10":
            travel_menu(character)
        elif choice == "11":
            career_menu(character)
        elif choice == "12":
            active_pokemon_menu(character)
        elif choice == "13":
            box_menu(character)
        elif choice == "14":
            yearly_actions_menu(character)
        elif choice == "15":
            tournament_menu(character)
        elif choice == "16":
            contest_menu(character)
        elif choice == "17":
            breeding_menu(character)
        elif choice == "18":
            show_pokedex(character)
        elif choice == "19":
            save_menu(character)
        elif choice == "20":
            loaded = load_menu()
            if loaded:
                character = loaded
        elif choice == "21":
            if Prompt.ask("Salvar antes de sair?", choices=["s", "n"], default="s") == "s":
                save_game(character, "autosave")
            console.print("Ate a proxima jornada.")
            break


if __name__ == "__main__":
    main()
