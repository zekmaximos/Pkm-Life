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
        f"Local: {character.current_city}, {character.region}",
        f"Saude: {character.health}\n"
        f"Dinheiro: {character.money} Pokedollar\n"
        f"Reputacao: {character.reputation}\n"
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
    table.add_column("OCCULT", justify="right")
    table.add_column("Condicao", justify="right")
    table.add_column("Ativo", justify="center")
    if not character.team:
        table.add_row("Nenhum Pokemon na equipe", "-", "-", "-", "-", "-", "-", "-")
    for index, pokemon in enumerate(character.team):
        table.add_row(
            pokemon.display_name(),
            str(pokemon.level),
            str(pokemon.combat),
            str(pokemon.beauty),
            str(pokemon.healthy),
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
        console.print("1. Ir ao Pokemon Center")
        console.print("2. Ler sobre Pokemon")
        console.print("3. Trabalhar na cidade")
        console.print("4. Treinar Pokemon ativo")
        console.print("5. Procurar ovos no habitat")
        console.print("6. Voltar")
        choice = Prompt.ask("Acao anual", choices=["1", "2", "3", "4", "5", "6"], default="6")
        if choice == "1":
            console.print(engine.heal_team_in_city(character))
        elif choice == "2":
            console.print(engine.manual_action_read_about_pokemon(character))
        elif choice == "3":
            console.print(engine.manual_action_work_city(character))
        elif choice == "4":
            console.print(engine.manual_action_train_team(character))
        elif choice == "5":
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
            title=character.current_city,
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
                    f"Nivel recomendado: {gym['recommended_level']}",
                    title=f"Ginasio de {gym['city']}",
                )
            )
            if Prompt.ask("Desafiar agora?", choices=["s", "n"], default="n") == "s":
                _, log = engine.challenge_city_gym(character)
                console.print(Panel("\n".join(log), title="Resultado do ginasio"))
        else:
            return


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
    event = engine.advance_year(character)
    handle_event(character, event)


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
        console.print("1. Avancar tempo")
        console.print("2. Ver personagem")
        console.print("3. Ver equipe")
        console.print("4. Ver historico")
        console.print("5. Ver insignias")
        console.print("6. Ver inventario")
        console.print("7. Usar item")
        console.print("8. Acoes da cidade")
        console.print("9. Explorar cidade/rota")
        console.print("10. Escolher rotina/carreira")
        console.print("11. Escolher Pokemon ativo")
        console.print("12. Box Pokemon")
        console.print("13. Acoes do ano")
        console.print("14. Salvar jogo")
        console.print("15. Carregar jogo")
        console.print("16. Sair")
        choice = Prompt.ask("Menu", choices=[str(i) for i in range(1, 17)], default="1")

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
            career_menu(character)
        elif choice == "11":
            active_pokemon_menu(character)
        elif choice == "12":
            box_menu(character)
        elif choice == "13":
            yearly_actions_menu(character)
        elif choice == "14":
            save_menu(character)
        elif choice == "15":
            loaded = load_menu()
            if loaded:
                character = loaded
        elif choice == "16":
            if Prompt.ask("Salvar antes de sair?", choices=["s", "n"], default="s") == "s":
                save_game(character, "autosave")
            console.print("Ate a proxima jornada.")
            break


if __name__ == "__main__":
    main()
