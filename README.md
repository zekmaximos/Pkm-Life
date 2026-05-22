# Poke Life

Poke Life e um simulador textual de vida inspirado na estrutura de BitLife, ambientado inicialmente em Kanto.

## MVP incluido

- Criacao de personagem nascido em Pallet Town, Kanto.
- Atributos centrais do jogador: PHY, MEN, POK e LUK, gerados de forma natural entre 0 e 100.
- Pokemon individuais com COMBAT, BEAUTY, HEALTHY, OCCULT, LEVEL, TYPE, ABILITY e condicao.
- HP de batalha separado de HEALTHY: o HP maximo deriva de HEALTHY, nivel e base da especie.
- Evolucoes por nivel com atualizacao de especie, tipos, habilidade, estagio e atributos individuais.
- Fases de vida por idade.
- Eventos de infancia carregados por JSON.
- Eventos aleatorios ao avancar tempo: podem acontecer ou nao, com chance influenciada por atributos, equipe, itens, carreira e cidade atual.
- Jornada pos-10 com 40 eventos distintos, incluindo ocorrencias comuns, incomuns e raras para estilos de Treinador, Criador, Coordenador e Estudante.
- Avanco de tempo ano a ano.
- Passagem de ano com efeitos reais: carreira, dinheiro, reputacao, XP, nivel, felicidade, saude e condicao dos Pokemon.
- Resumo anual estilo BitLife registrado no historico, com linhas para local, treino, Pokemon, encontros, dinheiro, ovos, ginasios e evento escolhido.
- Viagem manual bloqueada antes dos 10 anos.
- Acoes manuais do ano: Pokemon Center, estudar, trabalhar, treinar, treino intensivo e procurar ovos em habitats.
- Carreiras iniciais: Estudante da academia, Treinador, Criador e Coordenador.
- Evento especial do Professor Oak aos 10 anos.
- Escolha entre Bulbasaur, Charmander e Squirtle, recusa da jornada, ou suprimentos caso o jogador ja tenha um companheiro.
- Equipe ativa com ate 6 Pokemon e Box real para guardar Pokemon extras.
- Eventos podem conceder Pokemon antes dos 10 anos.
- Professor Oak so oferece Pokemon aos 10 anos se o personagem ainda nao tiver um Pokemon.
- O Pokemon de Oak exige escolher uma profissao: Treinador, Criador ou Coordenador.
- Poke Eggs com cor por tipo, raridade C/I/R/RR/SR, incubacao por anos e nascimento de Pokemon.
- Poke Eggs chocam no proximo ano, representando alguns meses de incubacao.
- Common Egg pode ser comprado em lojas selecionadas.
- Encontro selvagem simples.
- Encontros selvagens automaticos no avanco anual, com decisao probabilistica entre observar, batalhar ou tentar capturar.
- Captura probabilistica baseada em raridade, vida do Pokemon, POK, LUK, nivel, estagio evolutivo, bonus da bola e status.
- Itens iniciais de captura: Poke Ball, Great Ball, Ultra Ball, Net Ball, Dusk Ball e Master Ball.
- Itens comuns adicionais: Potion, Super Potion, Antidote e Repel.
- Itens de utilidade/treino: Rare Candy, Protein, Calcium, Grooming Kit, Lucky Charm e Escape Rope.
- Consumiveis influenciam a simulacao: Potion e Super Potion podem ser usados automaticamente antes de batalhas, e Repel reduz encontros anuais.
- Batalha automatica probabilistica com scores, chance de vitoria, vencedor, XP e perda de saude sugeridos.
- Calculo generico de dinheiro para eventos e trabalhos.
- Historico cronologico de vida.
- Save/load em JSON.
- Dados separados de logica.
- Banco local em JSON com os 151 Pokemon de Kanto.
- Banco de encontros por cidades, rotas, cavernas e areas especiais de Kanto.
- Banco de locais de Kanto com cidades, rotas e areas especiais usado para controlar onde Pokemon podem aparecer e ser capturados.
- Cidades como hubs: servicos, lojas, carreiras locais e ginasios.
- Cidades tambem puxam habitats/rotas proximas para encontros, deixando cada hub mais caracteristico.
- Database de nomes e sobrenomes para NPCs e lideres de ginasio.
- Liga de Kanto gerada no inicio do jogo: lideres aleatorios e times por tipo, persistidos no save.
- Ginasios usam Pokemon de Kanto do tipo do ginasio, com variedade e limite de raridade para evitar times discrepantes.
- Nivel dos ginasios escala no desafio conforme o Pokemon mais forte do jogador, mantendo a experiencia sandbox.

## Como rodar

```bash
pip install -r requirements.txt
python main.py
```

Interface web local:

```bash
pip install -r requirements.txt
python web/app.py
```

Depois acesse `http://127.0.0.1:5000`.
No Windows, tambem da para abrir com duplo clique em `abrir_poke_life_web.bat`.

## Estrutura

```text
poke-life/
+-- main.py
+-- abrir_poke_life_web.bat
+-- game/
|   +-- engine.py
|   +-- attributes.py
|   +-- character.py
|   +-- events.py
|   +-- pokemon.py
|   +-- battle.py
|   +-- capture.py
|   +-- economy.py
|   +-- utils.py
|   +-- careers.py
|   +-- progression.py
|   +-- gyms.py
|   +-- inventory.py
|   +-- history.py
|   +-- save_system.py
+-- data/
|   +-- pokemon_kanto.json
|   +-- locations_kanto.json
|   +-- encounters_kanto.json
|   +-- regions.json
|   +-- cities_kanto.json
|   +-- city_services_kanto.json
|   +-- name_database.json
|   +-- events_childhood.json
|   +-- events_journey.json
|   +-- gyms_kanto.json
|   +-- items.json
|   +-- starters.json
+-- saves/
+-- web/
|   +-- app.py
|   +-- templates/
|   |   +-- index.html
|   +-- static/
|       +-- style.css
|       +-- game.js
|       +-- sprites/
|           +-- pokemon/
```

## Banco de dados local

`data/pokemon_kanto.json` e a fonte mecanica principal das especies. Cada entrada possui nome, tipos, habilidade, raridade, evolucoes, estagio evolutivo, atributos base do jogo e disponibilidade.

`data/locations_kanto.json` descreve cidades, rotas e areas especiais. No momento, essa base influencia somente disponibilidade de encontros/captura.

`data/city_services_kanto.json` descreve o que cada cidade oferece: loja, Pokemon Center, carreiras locais, foco de eventos e ginasio quando houver.

`data/name_database.json` alimenta o RNG de nomes e sobrenomes de NPCs.

`data/gyms_kanto.json` define os templates dos 12 ginasios: os 8 oficiais de Kanto e 4 criados para hubs sem ginasio oficial. O lider e o time sao gerados no inicio de cada vida e salvos junto com o personagem.

`data/encounters_kanto.json` referencia os locais por `location_id` e descreve onde os Pokemon aparecem, com nivel minimo, nivel maximo e peso de encontro.

Eventos em JSON podem usar `tags`, `base_weight`, `min_event_chance` e `conditions` para controlar chance, peso e requisitos.

Eventos tambem podem conceder `random_area_pokemon` ou `eggs`. Ovos usam tiers C, I, R, RR e SR, com pesos configuraveis no proprio evento.

O script `tools/build_kanto_database.py` pode regenerar esses arquivos a partir da PokeAPI e das tabelas locais de disponibilidade de Kanto.

O script `tools/build_kanto_locations.py` sincroniza `locations_kanto.json` e adiciona `location_id` nas tabelas de encontro.

## Creditos de assets

Os icones de Pokemon usados na interface sao derivados da colecao HOMENatDexIcons:
https://chicoeevee.github.io/HOMENatDexIcons/

Pokemon e seus nomes sao marcas registradas de seus respectivos proprietarios.
Este projeto e um fan project sem fins comerciais.

## Proximos passos naturais

- Completar os 151 Pokemon em `data/pokemon_kanto.json`.
- Preencher `base_combat`, `base_beauty`, `base_healthy`, `base_occult` e `ability` para todas as especies.
- Expandir evolucoes especiais por pedra, troca, felicidade e eventos.
- Expandir ginasios para desafios completos.
- Adicionar carreiras com eventos proprios.
- Criar rotas separadas das cidades.
- Separar eventos por carreira em arquivos proprios conforme o volume crescer.
- Trocar a interface por Textual, PySide6 ou web sem reescrever o motor.
