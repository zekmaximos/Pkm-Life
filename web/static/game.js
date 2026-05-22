let appState = null;
let currentFeed = [];
let isAdvancing = false;
let huntsLeft = 3;
let battlesLeft = 3;

const $ = (id) => document.getElementById(id);

// ── API ──────────────────────────────────────────────────────────────────────

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  let data;
  try {
    data = await res.json();
  } catch {
    throw new Error(`Erro do servidor (${res.status})`);
  }
  if (!res.ok) throw new Error(data?.error || `Erro ${res.status}`);
  return data;
}

// ── Toast ────────────────────────────────────────────────────────────────────

function toast(text, duration = 2800) {
  const node = $("toast");
  node.textContent = text;
  node.classList.remove("hidden");
  clearTimeout(node._timer);
  node._timer = setTimeout(() => node.classList.add("hidden"), duration);
}

// ── Screen transitions ───────────────────────────────────────────────────────

function showGame() {
  $("startScreen").classList.add("hidden");
  $("gameScreen").classList.remove("hidden");
}

function showStart() {
  $("gameScreen").classList.add("hidden");
  $("startScreen").classList.remove("hidden");
  loadSaves();
}

// ── State update ─────────────────────────────────────────────────────────────

function setData(payload) {
  appState = payload.state;
  // Copia pending_event para appState para que renderActionAvailability possa checar
  if (appState) appState.pending_event = payload.pending_event || null;
  currentFeed = payload.feed || [];
  if (appState?.ready) showGame();
  render();
  renderEvent(payload.pending_event);
}

// ── Render ───────────────────────────────────────────────────────────────────

function render() {
  if (!appState?.ready) return;
  const s = appState;

  // Topbar
  $("charName").textContent = s.name;
  $("avatar").textContent = initials(s.name);
  $("charSub").textContent = s.in_prison
    ? `Preso · ${s.prison_months} meses restantes`
    : `${s.career} · ${s.phase}`;
  $("topAge").textContent = `${s.age} anos`;
  $("topCity").textContent = s.city;

  // City description banner
  const banner = $("cityBanner");
  if (banner) {
    if (s.city_description) {
      banner.innerHTML = `<span class="city-banner-name">${s.city}</span> — ${s.city_description}`;
      banner.classList.remove("hidden");
    } else {
      banner.classList.add("hidden");
    }
  }
  $("topMoney").textContent = `${(s.money || 0).toLocaleString("pt-BR")} P`;
  $("topBadges").textContent = `${(s.badges || []).length}`;
  $("topRep").textContent = `${s.reputation}`;

  // Left panel — stats
  $("healthValue").textContent = s.health;
  $("repValue").textContent = s.reputation;
  $("moneyValue").textContent = (s.money || 0).toLocaleString("pt-BR");
  $("badgeValue").textContent = (s.badges || []).length;
  $("boxValue").textContent = s.box_count;

  // Health bar
  const hbar = $("healthBar");
  if (hbar) {
    hbar.style.width = `${s.health}%`;
    // Gradient position: vermelho em 0%, amarelo em 50%, verde em 100%
    hbar.style.backgroundPosition = `${100 - s.health}% 0`;
  }

  // Health badge
  const badge = $("healthStatusBadge");
  if (badge) {
    badge.textContent = s.health_status || "";
    badge.className = "health-badge" + (s.health < 30 ? " danger" : s.health < 60 ? " warning" : "");
  }

  // Phase tag
  const phaseTag = $("charPhaseTag");
  if (phaseTag) phaseTag.textContent = s.phase || "";

  // Pokémon ativo resumido
  const aps = $("activePokeSummary");
  if (aps) {
    const active = (s.team || []).find(p => p.active) || (s.team || [])[0];
    if (active) {
      aps.classList.remove("hidden");
      aps.innerHTML = `
        <div class="aps-label">Pokemon ativo</div>
        <div class="aps-body">
          ${pokemonIconHtml(active)}
          <div class="aps-main">
            <div class="aps-name">${escHtml(active.name)}</div>
            <div class="aps-detail">Lv.${active.level} · ${escHtml(active.status)}</div>
            <div class="aps-hp-bar"><div class="aps-hp-fill" style="width:${active.hp_percent}%"></div></div>
          </div>
          <div class="aps-hp">
            ${active.hp}/${active.max_hp}<br>HP
          </div>
        </div>
      `;
    } else {
      aps.classList.add("hidden");
    }
  }

  renderCareerSummary();

  renderAttributes();
  renderTeam();
  renderBox();
  renderBadgeRibbonShelf();
  renderInventory();
  renderCareers();
  renderAcademy();
  renderGymPreview();
  renderActionAvailability();
  renderFeed();
}

function renderCareerSummary() {
  const el = $("careerSummary");
  if (!el) return;
  const summary = appState.career_summary || {};
  const career = summary.career || appState.career || "Indefinida";
  if (!career || career === "Indefinida") {
    el.innerHTML = `<div class="career-empty">Sem profissão definida.</div>`;
    return;
  }
  const rank = Number(summary.rank || 0);
  const xp = Number(summary.xp || 0);
  const needed = Number(summary.xp_needed || 0);
  const xpLabel = rank >= 5 ? "rank máximo" : `${xp}/${needed} XP`;
  const pct = rank >= 5 ? 100 : Math.max(0, Math.min(100, needed ? Math.round((xp / needed) * 100) : 0));
  const years = Number(summary.years || 0);
  const focus = appState.academy_focus || "";
  const extras = [];
  if (summary.has_business) extras.push("negócio próprio");
  if (summary.has_retirement) extras.push("aposentadoria ativa");
  el.innerHTML = `
    <div class="career-card">
      <div class="career-card-head">
        <span class="career-title">${escHtml(career)}</span>
        <span class="career-rank">${escHtml(summary.rank_label || "Iniciante")}</span>
      </div>
      <div class="career-progress-line">
        <span>Rank ${rank}/5</span>
        <span>${escHtml(xpLabel)}</span>
      </div>
      <div class="career-progress-track"><div class="career-progress-fill" style="width:${pct}%"></div></div>
      <div class="career-meta">
        <span>${years} ano(s) de carreira</span>
        ${extras.length ? `<span>${escHtml(extras.join(" · "))}</span>` : ""}
      </div>
      ${focus ? `<div class="career-focus"><b>Foco</b><span>${escHtml(focus.replace(/^Foco academico:\\s*/i, ""))}</span></div>` : ""}
    </div>
  `;
}

function renderAttributes() {
  const attrs = appState.attributes || {};
  $("attributes").innerHTML = Object.entries(attrs).map(([key, val]) => `
    <div class="attr">
      <div class="attr-top">
        <span>${attrLabel(key)}</span>
        <span>${val}</span>
      </div>
      <div class="bar-track">
        <div class="bar-fill bar-${key}" style="width:${val}%"></div>
      </div>
    </div>
  `).join("");
}

function renderTeam() {
  const list = appState.team || [];
  $("team").innerHTML = list.length
    ? list.map((p, i) => `
      <div class="pokemon-card ${p.active ? "active" : ""}">
        <div class="poke-reorder">
          ${i > 0 ? `<button class="reorder-btn" onclick="reorderTeam(${i}, ${i-1})">&#8593;</button>` : ""}
          ${i < list.length-1 ? `<button class="reorder-btn" onclick="reorderTeam(${i}, ${i+1})">&#8595;</button>` : ""}
        </div>
        ${pokemonIconHtml(p)}
        <div style="flex:1;min-width:0">
          <div class="poke-name">${p.name}</div>
          <div class="poke-level">Lv.${p.level} · ${p.status}</div>
          <div class="bar-track" style="margin-top:3px">
            <div class="bar-fill bar-POK" style="width:${p.hp_percent}%"></div>
          </div>
        </div>
        <div style="font-size:10px;color:var(--color-text-tertiary);text-align:right;flex-shrink:0">
          ${p.hp}/${p.max_hp}<br>HP
          ${p.battle_level != null ? `<br><span style="color:var(--color-accent);font-weight:600" title="Battle Level — visivel apenas para Pesquisadores e Criadores">BL ${p.battle_level}</span>` : ""}
        </div>
      </div>
    `).join("")
    : `<p class="soft">Nenhum Pokemon na equipe.</p>`;
}

function renderInventory() {
  const items = Object.keys(appState.inventory || {});
  $("itemSelect").innerHTML = items.length
    ? items.map((name) => `<option value="${name}">${name} ×${appState.inventory[name]}</option>`).join("")
    : `<option value="">Inventario vazio</option>`;
}

function renderBox() {
  const box = appState.box || [];
  const boxEl = $("boxList");
  const countEl = $("boxCount");
  if (countEl) countEl.textContent = box.length ? `(${box.length})` : "";
  if (!boxEl) return;
  if (!box.length) {
    boxEl.innerHTML = '<p class="soft">Box vazia.</p>';
    return;
  }
  boxEl.innerHTML = box.map((p, bi) => `
    <div class="box-card">
      ${pokemonIconHtml(p)}
      <span class="poke-name">${escHtml(p.name)}</span>
      <span class="poke-level">Lv.${p.level}</span>
      <select class="box-swap-select" data-box="${bi}">
        ${(appState.team || []).map((t, ti) => `<option value="${ti}">${escHtml(t.name)}</option>`).join("")}
      </select>
      <button class="box-swap-btn" data-box="${bi}">Trocar</button>
    </div>
  `).join("");
  boxEl.querySelectorAll(".box-swap-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
      const bi = parseInt(btn.dataset.box);
      const sel = boxEl.querySelector(`.box-swap-select[data-box="${bi}"]`);
      const ti = parseInt(sel.value);
      try {
        const payload = await api("/api/box/swap", { method: "POST", body: JSON.stringify({ team_index: ti, box_index: bi }) });
        setData(payload);
      } catch(e) { toast(e.message); }
    });
  });
}

async function reorderTeam(fromIdx, toIdx) {
  try {
    const payload = await api("/api/team/reorder", { method: "POST", body: JSON.stringify({ from_index: fromIdx, to_index: toIdx }) });
    setData(payload);
  } catch(e) { toast(e.message || "Erro ao reordenar."); }
}

function renderCareers() {
  const careers = appState.available_careers || [];
  $("careerSelect").innerHTML = careers.length
    ? careers.map((c) => `<option value="${c}" ${c === appState.career ? "selected" : ""}>${c}</option>`).join("")
    : `<option value="">Sem opcoes ainda</option>`;
}

function renderAcademy() {
  $("academySelect").innerHTML = (appState.academy_options || [])
    .map((f) => `<option value="${f.id}">${f.name}</option>`)
    .join("");
}

function renderBadgeRibbonShelf() {
  const shelf = $("badgeRibbonShelf");
  if (!shelf) return;
  const badges = appState.badge_display || [];
  const ribbons = appState.contest_ribbons || [];
  if (!badges.length && !ribbons.length) {
    shelf.innerHTML = `<span class="symbol-empty">Sem insignias ou ribbons ainda.</span>`;
    return;
  }
  const badgeHtml = badges.map((b) => `
    <span class="symbol-chip badge" title="${escHtml(b.name)}">
      <span>${escHtml(b.symbol)}</span>${escHtml(b.name)}
    </span>
  `).join("");
  const ribbonHtml = ribbons.map((r) => `
    <span class="symbol-chip ribbon" title="${escHtml(r.name)}">
      <span>${escHtml(r.symbol)}</span>${escHtml(r.name)}
    </span>
  `).join("");
  shelf.innerHTML = badgeHtml + ribbonHtml;
}

function renderGymPreview() {
  const g = appState.gym_preview;
  if (!g || !g.available) {
    $("gymPreview").innerHTML = g?.summary
      ? `<span style="color:var(--color-text-tertiary)">${g.summary}</span>`
      : "Sem ginasio nesta cidade.";
    return;
  }
  const riskColor = g.estimated_win_chance >= 60
    ? "var(--green)" : g.estimated_win_chance >= 35
    ? "var(--amber)" : "var(--red)";
  $("gymPreview").innerHTML = `
    <b>${g.leader || "Lider"}</b> · ${g.main_type || "?"}<br>
    <span style="color:${riskColor}">Chance: ${g.estimated_win_chance}%</span> · ${g.risk}<br>
    <span style="color:var(--color-text-tertiary)">${g.summary}</span>
  `;
}

function updateHuntBtn() {
  const btn = $("huntBtn");
  const tag = $("huntTag");
  if (!btn) return;
  const canHunt = (appState?.action_availability?.hunt !== false) && huntsLeft > 0;
  btn.disabled = !canHunt;
  btn.title = huntsLeft <= 0 ? "Voce ja cacou 3 vezes neste periodo." : canHunt ? "" : "Disponivel mais tarde na vida.";
  if (tag) tag.textContent = huntsLeft;
}

function updateBattleSearchBtn() {
  const btn = $("battleSearchBtn");
  const tag = $("battleSearchTag");
  if (!btn) return;
  const canBattle = (appState?.action_availability?.battle_search !== false) && battlesLeft > 0;
  btn.disabled = !canBattle;
  btn.title = battlesLeft <= 0
    ? "Voce ja batalhou 3 vezes neste periodo."
    : canBattle ? "" : "Disponivel mais tarde na vida.";
  if (tag) tag.textContent = battlesLeft;
}

async function openHospital() {
  const panel = $("hospitalPanel");
  const optEl = $("hospitalOptions");
  if (!panel || !optEl) return;
  panel.classList.remove("hidden");
  optEl.innerHTML = '<p class="soft">Carregando opções...</p>';
  try {
    const opts = await api("/api/hospital");
    optEl.innerHTML = opts.map(opt => `
      <div class="hospital-opt ${opt.can_afford ? "" : "disabled"}" data-key="${escAttr(opt.key)}">
        <span class="hosp-cost">${opt.cost.toLocaleString("pt-BR")}P</span>
        <div class="hosp-title">${escHtml(opt.label)}</div>
        <div class="hosp-desc">${escHtml(opt.description)} · +${opt.heal} saúde</div>
      </div>
    `).join("");
    optEl.querySelectorAll(".hospital-opt:not(.disabled)").forEach(el => {
      el.addEventListener("click", async () => {
        const key = el.dataset.key;
        panel.classList.add("hidden");
        try {
          const payload = await api("/api/hospital", { method: "POST", body: JSON.stringify({ option: key }) });
          setData(payload);
        } catch(e) { toast(e.message); }
      });
    });
  } catch(e) {
    optEl.innerHTML = `<p class="soft">Erro ao carregar opções.</p>`;
  }
}

function renderActionAvailability() {
  const av = appState.action_availability || {};
  const hasPendingEvent = !!(appState.pending_event);
  document.querySelectorAll(".time-buttons button").forEach((btn) => {
    const allowed = av.advance !== false && !hasPendingEvent;
    btn.disabled = !allowed;
    btn.title = hasPendingEvent
      ? "⚠️ Responda o evento pendente antes de avançar o tempo."
      : (av.advance !== false ? "" : "Game over: o tempo nao avanca apos a morte.");
  });
  document.querySelectorAll("[data-action]").forEach((btn) => {
    const allowed = av[btn.dataset.action] !== false;
    btn.disabled = !allowed;
    btn.title = allowed ? "" : "Disponivel mais tarde na vida.";
  });
  [
    ["setCareerBtn",  "set_career"],
    ["setAcademyBtn", "academy_focus"],
    ["buyBtn",        "buy_item"],
    ["useItemBtn",    "use_item"],
    ["travelBtn",     "travel"],
    ["contestBtn",    "contest"],
    ["breedBtn",      "breed"],
    ["tournamentBtn", "tournament"],
  ].forEach(([id, key]) => {
    const node = $(id);
    if (!node) return;
    const allowed = av[key] !== false;
    node.disabled = !allowed;
    node.title = allowed ? "" : "Disponivel mais tarde na vida.";
  });
  updateHuntBtn();
  updateBattleSearchBtn();
}

function isSummaryCard(item) {
  return item.title && /^Resumo/.test(item.title);
}

function isBattleCard(item) {
  return ["battle", "gym", "tournament", "contest"].includes(item.kind);
}

function renderFeed() {
  const container = $("feed");
  container.innerHTML = currentFeed.length
    ? currentFeed.map((item) => {
      const summary = isSummaryCard(item);
      const battle = isBattleCard(item);
      const mentionedPokemon = (item.pokemon_sprites || []).map((p) => p.name);
      const textHtml = summary ? formatSummaryText(item.text, mentionedPokemon)
                     : battle ? formatBattleText(item.text)
                     : formatRichText(item.text, mentionedPokemon);
      const textClass = summary ? "event-text summary-text" : "event-text";
      return `
        <article class="feed-card ${item.kind || "event"}${summary ? " summary-card" : ""}">
          ${feedPokemonIconHtml(item)}
          <div style="min-width:0;flex:1">
            <div class="event-title">${formatRichText(item.title || "", mentionedPokemon)}</div>
            <div class="${textClass}">${textHtml}</div>
            <div class="event-time">${item.time || `Ano ${appState?.age ?? 0}`}</div>
          </div>
        </article>
      `;
    }).join("")
    : `<article class="feed-card event">
        <div class="event-icon">◆</div>
        <div><div class="event-text">A linha do tempo aparecera aqui.</div>
        <div class="event-time">Ano 0</div></div>
      </article>`;
  container.scrollTop = 0;
}

function renderEvent(event) {
  const box = $("eventChoice");
  if (!event) {
    box.classList.add("hidden");
    box.innerHTML = "";
    return;
  }
  box.classList.remove("hidden");
  box.innerHTML = `
    <div class="choice-label">${formatRichText(event.title)}</div>
    <div class="event-text event-choice-text">${formatRichText(event.text)}</div>
    <div class="choice-list">
      ${event.choices.map((c) => `<button onclick="chooseEvent(${c.index})">${formatRichText(c.text)}</button>`).join("")}
    </div>
  `;
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function escHtml(str) {
  return String(str || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function escAttr(str) {
  return escHtml(str).replace(/"/g, "&quot;");
}

function pokemonIconHtml(p) {
  const fallback = typeIcon(p?.types?.[0]);
  if (!p?.sprite) {
    return `<div class="poke-icon">${fallback}</div>`;
  }
  return `
    <div class="poke-icon has-sprite" data-fallback="${escAttr(fallback)}">
      <img src="${escAttr(p.sprite)}" alt="${escAttr(p.species || p.name || "Pokemon")}" onerror="this.parentElement.textContent=this.parentElement.dataset.fallback">
    </div>
  `;
}

function feedPokemonIconHtml(item) {
  const sprites = item?.pokemon_sprites || [];
  if (!sprites.length) {
    return `<div class="event-icon">${feedIcon(item?.kind)}</div>`;
  }
  const first = sprites[0];
  const extra = sprites.length > 1 ? `<span class="event-pokemon-extra">+${sprites.length - 1}</span>` : "";
  const fallback = feedIcon(item?.kind || "pokemon");
  return `
    <div class="event-pokemon-icon" title="${escAttr(first.name)}" data-fallback="${escAttr(fallback)}">
      <img src="${escAttr(first.sprite)}" alt="${escAttr(first.name)}" onerror="this.parentElement.textContent=this.parentElement.dataset.fallback">
      ${extra}
    </div>
  `;
}

function escapeRegex(str) {
  return String(str || "").replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function pokemonNameList(pokemonNames = []) {
  const basePokemonNames = ["Bulbasaur", "Charmander", "Squirtle", "Pikachu", "Eevee", "Pidgey", "Rattata", "Caterpie", "Weedle"];
  return Array.from(new Set([...pokemonNames, ...basePokemonNames].filter(Boolean)))
    .sort((a, b) => b.length - a.length);
}

function highlightPokemonHtml(html, pokemonNames = []) {
  let result = html;
  for (const name of pokemonNameList(pokemonNames)) {
    result = result.replace(new RegExp(`(?<![A-Za-z0-9])(${escapeRegex(name)})(?![A-Za-z0-9])`, "gi"), '<span class="rich-pokemon">$1</span>');
  }
  return result;
}

function formatRichText(text, pokemonNames = []) {
  let html = escHtml(text);
  html = highlightPokemonHtml(html, pokemonNames);
  const rules = [
    [/\b(Professor Oak|Oak)\b/g, "rich-oak"],
    [/\b(Pokemon|Pokémon)\b/g, "rich-pokemon"],
    [/\b(Treinador|Criador|Coordenador|Estudante|Pesquisador|Explorador|Cientista)\b/g, "rich-career"],
    [/\b(Kanto|Pallet Town|Viridian City|Pewter City|Cerulean City)\b/g, "rich-place"],
    [/\b(Saude|morte|Game Over|fugiu|golpes|risco)\b/gi, "rich-danger"],
    [/\b(Pokedollar|dinheiro|premio|salario)\b/gi, "rich-money"],
    [/\b(Insignia|Ribbon|Contest|Ginasio)\b/gi, "rich-achievement"],
  ];
  for (const [pattern, cls] of rules) {
    html = html.replace(pattern, `<span class="${cls}">$1</span>`);
  }
  return html;
}

// ── Summary text rich formatter ───────────────────────────────────────────────

function formatSummaryText(text, pokemonNames = []) {
  const lines = String(text || "").split("\n").filter(l => l.trim());

  // label → [display, color, style-hint]
  const LABELS = [
    ["Local:",     "Local",     "var(--blue)",                    "location"],
    ["Treino:",    "Treino",    "var(--blue)",                    "training"],
    ["Pokemon:",   "Pokémon",   "var(--green)",                   "pokemon"],
    ["Encontros:", "Encontros", "var(--amber)",                   "encounters"],
    ["Dinheiro:",  "Dinheiro",  "#9a7100",                        "money"],
    ["Profissao:", "Profissão", "var(--purple)",                  "career"],
    ["Itens:",     "Itens",     "#0d7c66",                        "items"],
    ["Reputacao:", "Reputação", "#be5a9b",                        "rep"],
    ["Ovos:",      "Ovos",      "var(--amber)",                   "eggs"],
    ["Ginasios:",  "Ginásios",  "#9a6f00",                        "gyms"],
    ["Saude:",     "Saúde",     "var(--red)",                     "health"],
    ["Registro:",  "Registro",  "var(--color-text-secondary)",    "log"],
  ];

  function esc(s) { return escHtml(s); }

  function applyArrow(h) {
    return h.replace(/-&gt;/g, '<span class="sum-arrow">→</span>');
  }

  function applyLevel(h) {
    return h.replace(/(Lv\.\d+)/g, '<span class="sum-lv">$1</span>');
  }

  function rich(h) {
    return highlightPokemonHtml(h, pokemonNames);
  }

  return lines.map(raw => {
    const line = raw.trim();

    for (const [key, display, color, hint] of LABELS) {
      if (!line.startsWith(key)) continue;
      const rest = line.slice(key.length).trim();

      const labelHtml = `<span class="sum-label" style="color:${color}">${display}</span>`;

      // ── Registro: split on | into bullet rows ──────────────────────────────
      if (hint === "log") {
        const parts = rest.split("|").map(p => p.trim()).filter(Boolean);
        if (!parts.length || (parts.length === 1 && /nada marcante/.test(parts[0]))) {
          return `<div class="sum-row">${labelHtml} <span class="sum-muted">${esc(rest)}</span></div>`;
        }
        const rows = parts.map(p => {
          let h = esc(p);
          const eggMoment = /ovo.*chocou|chocou.*revelou|revelou/i.test(p);
          h = h.replace(/(\d[\d.,]*)\s*Pokedollar/gi, '<span class="sum-money-n">$1 ₱</span>');
          h = rich(h);
          return `<span class="sum-log-item${eggMoment ? " sum-egg-log" : ""}">• ${h}</span>`;
        }).join("");
        return `<div class="sum-row sum-row-log">${labelHtml}<div class="sum-log-list">${rows}</div></div>`;
      }

      // ── Dinheiro ───────────────────────────────────────────────────────────
      if (hint === "money") {
        if (/ganhou/.test(rest)) {
          let h = esc(rest).replace(/(\d[\d.,]*)\s*Pokedollar/gi, '<span class="sum-gain">+$1 ₱</span>');
          return `<div class="sum-row">${labelHtml} <span class="sum-pos">${rich(h)}</span></div>`;
        }
        if (/gastou|perdeu/.test(rest)) {
          let h = esc(rest).replace(/(\d[\d.,]*)\s*Pokedollar/gi, '<span class="sum-loss">-$1 ₱</span>');
          return `<div class="sum-row">${labelHtml} <span class="sum-neg">${rich(h)}</span></div>`;
        }
        return `<div class="sum-row">${labelHtml} <span class="sum-muted">${esc(rest)}</span></div>`;
      }

      // ── Pokémon ────────────────────────────────────────────────────────────
      if (hint === "pokemon") {
        if (/sem novas/.test(rest)) {
          return `<div class="sum-row">${labelHtml} <span class="sum-muted">${esc(rest)}</span></div>`;
        }
        let h = applyLevel(applyArrow(esc(rest)));
        h = h.replace(/(evolucoes:)/gi, '<span class="sum-evo">evoluções:</span>');
        return `<div class="sum-row">${labelHtml} <span>${rich(h)}</span></div>`;
      }

      // ── Encontros ─────────────────────────────────────────────────────────
      if (hint === "encounters") {
        if (/nenhum encontro/.test(rest)) {
          return `<div class="sum-row">${labelHtml} <span class="sum-muted">${esc(rest)}</span></div>`;
        }
        let h = esc(rest);
        h = h.replace(/(\d+ vitoria\(s\))/g, '<span class="sum-win">$1</span>');
        h = h.replace(/(\d+ derrota\(s\))/g, '<span class="sum-lose">$1</span>');
        h = h.replace(/(\d+ captura\(s\))/g, '<span class="sum-cap">$1</span>');
        h = h.replace(/(\d+ tentativa\(s\) frustrada\(s\))/g, '<span class="sum-fail">$1</span>');
        return `<div class="sum-row">${labelHtml} <span>${rich(h)}</span></div>`;
      }

      // ── Ginásios ──────────────────────────────────────────────────────────
      if (hint === "gyms") {
        if (/conquistou/.test(rest)) {
          return `<div class="sum-row">${labelHtml} <span class="sum-badge">🏅 ${esc(rest)}</span></div>`;
        }
        return `<div class="sum-row">${labelHtml} <span class="sum-muted">${esc(rest)}</span></div>`;
      }

      // ── Saúde ─────────────────────────────────────────────────────────────
      if (hint === "health") {
        if (/caiu/.test(rest)) {
          return `<div class="sum-row">${labelHtml} <span class="sum-neg sum-health">${esc(rest)}</span></div>`;
        }
        if (/recuperou/.test(rest)) {
          return `<div class="sum-row">${labelHtml} <span class="sum-pos">${esc(rest)}</span></div>`;
        }
        return `<div class="sum-row">${labelHtml} <span class="sum-muted">${esc(rest)}</span></div>`;
      }

      // ── Treino ────────────────────────────────────────────────────────────
      if (hint === "training") {
        if (/ganhou/.test(rest)) {
          return `<div class="sum-row">${labelHtml} <span class="sum-train">${esc(rest)}</span></div>`;
        }
        return `<div class="sum-row">${labelHtml} <span class="sum-muted">${esc(rest)}</span></div>`;
      }

      // ── Local ─────────────────────────────────────────────────────────────
      if (hint === "location") {
        let h = applyArrow(esc(rest));
        return `<div class="sum-row">${labelHtml} <span class="sum-city">${rich(h)}</span></div>`;
      }

      // ── Reputação ─────────────────────────────────────────────────────────
      if (hint === "rep") {
        if (/subiu/.test(rest)) {
          return `<div class="sum-row">${labelHtml} <span class="sum-pos">${esc(rest)}</span></div>`;
        }
        if (/caiu/.test(rest)) {
          return `<div class="sum-row">${labelHtml} <span class="sum-neg">${esc(rest)}</span></div>`;
        }
        return `<div class="sum-row">${labelHtml} <span>${esc(rest)}</span></div>`;
      }

      // ── Generic (Profissao, Itens, Ovos) ──────────────────────────────────
      if (/sem mudanca|sem ovos|sem novas/.test(rest)) {
        return `<div class="sum-row">${labelHtml} <span class="sum-muted">${esc(rest)}</span></div>`;
      }
      let h = applyLevel(applyArrow(esc(rest)));
      h = h.replace(/(\d[\d.,]*)\s*Pokedollar/gi, '<span class="sum-money-n">$1 ₱</span>');
      if (hint === "eggs" && /chocados|chocou|revelou/i.test(rest)) {
        return `<div class="sum-row sum-egg-row">${labelHtml} <span class="sum-egg-birth">${rich(h)}</span></div>`;
      }
      return `<div class="sum-row">${labelHtml} <span>${rich(h)}</span></div>`;
    }

    // Fallback: plain
    return `<div class="sum-row sum-default">${esc(line)}</div>`;
  }).join("");
}

function formatBattleText(text) {
  const lines = String(text || "").split("\n").filter(l => l.trim());
  return lines.map(raw => {
    const line = raw.trim();
    if (line.startsWith("TREINADOR|")) {
      const [, name, total, wins, losses, outcome, chance] = line.split("|");
      const won = outcome === "win";
      return `<div class="trainer-header">
        <span class="trainer-name">${escHtml(name)}</span>
        <span class="trainer-result ${won ? "win" : "loss"}">${won ? "Serie vencida" : "Serie perdida"}</span>
        <span class="trainer-score">${wins}/${total} vitorias · ${losses} derrota(s) · ${chance}% chance</span>
      </div>`;
    }
    // Formato estruturado de batalha individual
    if (line.startsWith("BATALHA|")) {
      const [, player, enemy, chanceStr, outcome, pScore, eScore, xp, hpLoss] = line.split("|");
      const won = outcome === "win";
      const chance = parseFloat(chanceStr);
      const chanceCls = chance >= 60 ? "sum-win" : chance >= 40 ? "sum-money-n" : "sum-lose";
      const resultIcon = won ? "Vitoria" : "Derrota";
      const resultCls = won ? "sum-win" : "sum-lose";
      return `<div class="battle-row">
        <span class="${resultCls} battle-outcome">${resultIcon}</span>
        <span class="battle-vs">${escHtml(player)} vs <b>${escHtml(enemy)}</b></span>
        <span class="${chanceCls} battle-chance">${chance.toFixed(0)}% chance</span>
        <span class="battle-scores">Poder: ${parseFloat(pScore).toFixed(1)} vs ${parseFloat(eScore).toFixed(1)}</span>
        ${won ? `<span class="sum-pos battle-xp">+${xp} XP</span>` : `<span class="sum-neg battle-hp">-${hpLoss} HP</span>`}
      </div>`;
    }
    // Linhas de level up
    if (/subiu para o nivel|level up/i.test(line)) {
      return `<div class="battle-row"><span class="sum-train">${escHtml(line)}</span></div>`;
    }
    // Vitoria geral / derrota geral
    if (/vitoria|venceu|ganhou.*badge|recebeu.*badge/i.test(line)) {
      return `<div class="battle-row"><span class="sum-win battle-headline">${escHtml(line)}</span></div>`;
    }
    if (/derrota|perdeu|eliminado/i.test(line)) {
      return `<div class="battle-row"><span class="sum-neg battle-headline">${escHtml(line)}</span></div>`;
    }
    // Linha de chance/score geral
    if (/chance estimada|formato.*serie/i.test(line)) {
      return `<div class="battle-row battle-meta">${escHtml(line)}</div>`;
    }
    return `<div class="battle-row">${escHtml(line)}</div>`;
  }).join("");
}

function initials(name) {
  return String(name || "PL").split(/\s+/).map((p) => p[0]).join("").slice(0, 2).toUpperCase();
}

function attrLabel(key) {
  return { PHY: "Fisico", MEN: "Mental", POK: "Pokemon", LUK: "Sorte" }[key] || key;
}

function typeIcon(type) {
  const m = {
    Fire: "🔥", Water: "💧", Electric: "⚡", Grass: "🌿",
    Psychic: "🔮", Ghost: "👻", Dragon: "🐉", Ice: "❄",
    Dark: "🌑", Steel: "⚙", Fairy: "✨", Rock: "◈",
    Ground: "◉", Flying: "◎", Fighting: "◆",
    Poison: "☠", Bug: "◇", Normal: "○",
  };
  return m[type] || "◉";
}

function feedIcon(kind) {
  const m = {
    time:       "⏱",
    battle:     "⚔",
    money:      "₱",
    pokemon:    "★",
    career:     "◆",
    egg:        "○",
    health:     "♥",
    crime:      "⚠",
    contest:    "✦",
    tournament: "▲",
    travel:     "→",
    event:      "◆",
  };
  return m[kind] || "◆";
}

// ── Data loaders ─────────────────────────────────────────────────────────────

async function loadSaves() {
  try {
    const saves = await api("/api/saves");
    $("saveSelect").innerHTML = saves.length
      ? saves.map((s) => `<option value="${s}">${s}</option>`).join("")
      : `<option value="">Nenhum save</option>`;
  } catch {}
}

async function refreshShop() {
  if (!appState?.ready) return;
  try {
    const items = await api("/api/shop");
    $("shopSelect").innerHTML = items.length
      ? items.map((it) => `<option value="${it.name}">${it.name} — ${it.price}P</option>`).join("")
      : `<option value="">Loja indisponivel</option>`;
  } catch {
    $("shopSelect").innerHTML = `<option value="">Loja indisponivel</option>`;
  }
}

async function refreshCities() {
  try {
    const cities = await api("/api/cities");
    $("citySelect").innerHTML = cities.map((c) => `<option value="${c}">${c}</option>`).join("");
  } catch {}
}

// ── Actions ──────────────────────────────────────────────────────────────────

async function createGame() {
  try {
    const payload = await api("/api/new", {
      method: "POST",
      body: JSON.stringify({
        name: $("newName").value.trim() || "Red",
      }),
    });
    setData(payload);
    await refreshShop();
    toast("Nova vida criada.");
  } catch (e) {
    toast("Erro ao criar jogo: " + e.message);
  }
}

async function loadGame() {
  const slot = $("saveSelect").value;
  if (!slot) return toast("Nenhum save selecionado.");
  try {
    const payload = await api("/api/load", { method: "POST", body: JSON.stringify({ slot }) });
    setData(payload);
    await refreshShop();
    toast("Save carregado.");
  } catch (e) {
    toast("Erro ao carregar: " + e.message);
  }
}

async function saveGame() {
  try {
    const payload = await api("/api/save", {
      method: "POST",
      body: JSON.stringify({ slot: $("saveSlot").value || "autosave" }),
    });
    setData(payload);
    toast("Jogo salvo.");
  } catch (e) {
    toast("Erro ao salvar: " + e.message);
  }
}

async function advance(months) {
  if (isAdvancing) return;
  if (appState?.dead || appState?.action_availability?.advance === false) {
    toast("Game over: o tempo nao avanca apos a morte.");
    renderActionAvailability();
    return;
  }
  if (appState?.pending_event) {
    toast("⚠️ Responda o evento pendente antes de avançar o tempo.");
    return;
  }
  isAdvancing = true;
  const btns = document.querySelectorAll(".time-buttons button");
  btns.forEach((b) => (b.disabled = true));
  try {
    const payload = await api("/api/advance", {
      method: "POST",
      body: JSON.stringify({ months }),
    });
    huntsLeft = 3;
    battlesLeft = 3;
    setData(payload);
    await refreshShop();
  } catch (e) {
    toast("Erro ao avançar: " + e.message);
  } finally {
    isAdvancing = false;
    if (appState) renderActionAvailability();
  }
}

async function chooseEvent(index) {
  try {
    const payload = await api("/api/event_choice", {
      method: "POST",
      body: JSON.stringify({ index }),
    });
    setData(payload);
  } catch (e) {
    toast("Erro na escolha: " + e.message);
  }
}

async function action(name, body = {}) {
  try {
    const payload = await api(`/api/action/${name}`, {
      method: "POST",
      body: JSON.stringify(body),
    });
    setData(payload);
    if (["buy_item", "use_item", "work", "heal"].includes(name)) {
      await refreshShop();
    }
  } catch (e) {
    toast(e.message || "Acao falhou.");
  }
}

async function enterTournament() {
  try {
    const payload = await api("/api/tournament", {
      method: "POST",
      body: JSON.stringify({ kind: "city" }),
    });
    setData(payload);
  } catch (e) {
    toast(e.message || "Torneio falhou.");
  }
}

// ── Boot ─────────────────────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {
  // ── New game ───────────────────────────────────────────────────────────────
  $("newGameBtn").addEventListener("click", async () => {
    const name = $("newName").value.trim() || "Red";
    try {
      const payload = await api("/api/new", {
        method: "POST",
        body: JSON.stringify({ name }),
      });
      setData(payload);
      await refreshShop();
      $("startScreen").classList.add("hidden");
      $("gameScreen").classList.remove("hidden");
    } catch (e) {
      toast("Erro ao criar jogo: " + e.message);
    }
  });

  // ── Load game ──────────────────────────────────────────────────────────────
  $("loadBtn").addEventListener("click", async () => {
    const slot = $("saveSelect").value;
    if (!slot) return toast("Selecione um save.");
    try {
      const payload = await api("/api/load", {
        method: "POST",
        body: JSON.stringify({ slot }),
      });
      setData(payload);
      await refreshShop();
      $("startScreen").classList.add("hidden");
      $("gameScreen").classList.remove("hidden");
    } catch (e) {
      toast("Erro ao carregar: " + e.message);
    }
  });

  // ── Save ───────────────────────────────────────────────────────────────────
  $("saveBtn").addEventListener("click", async () => {
    const slot = $("saveSlot").value.trim() || "autosave";
    try {
      await api("/api/save", {
        method: "POST",
        body: JSON.stringify({ slot }),
      });
      toast('Salvo em "' + slot + '"');
    } catch (e) {
      toast("Erro ao salvar: " + e.message);
    }
  });

  // ── Home ───────────────────────────────────────────────────────────────────
  $("homeBtn").addEventListener("click", () => {
    $("gameScreen").classList.add("hidden");
    $("startScreen").classList.remove("hidden");
    loadSaves();
  });

  // ── Time advance buttons ───────────────────────────────────────────────────
  document.querySelectorAll("[data-months]").forEach((btn) => {
    btn.addEventListener("click", () => advance(parseInt(btn.dataset.months)));
  });

  // ── Action menu buttons ────────────────────────────────────────────────────
  document.querySelectorAll("[data-action]").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".menu-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      action(btn.dataset.action);
    });
  });

  // ── Hunt ──────────────────────────────────────────────────────────────────
  $("huntBtn").addEventListener("click", async () => {
    if (huntsLeft <= 0) return toast("Voce ja procurou Pokemon 3 vezes neste periodo. Avance o tempo.");
    document.querySelectorAll(".menu-btn").forEach((b) => b.classList.remove("active"));
    $("huntBtn").classList.add("active");
    try {
      const payload = await api("/api/action/hunt", { method: "POST", body: JSON.stringify({}) });
      huntsLeft = Math.max(0, huntsLeft - 1);
      setData(payload);
    } catch (e) {
      toast(e.message || "Caça falhou.");
    }
  });

  // ── Procurar Batalha ──────────────────────────────────────────────────────
  $("battleSearchBtn").addEventListener("click", async () => {
    if (battlesLeft <= 0) return toast("Voce ja buscou batalhas 3 vezes neste periodo. Avance o tempo.");
    document.querySelectorAll(".menu-btn").forEach((b) => b.classList.remove("active"));
    $("battleSearchBtn").classList.add("active");
    try {
      const payload = await api("/api/action/battle_search", { method: "POST", body: JSON.stringify({}) });
      battlesLeft = Math.max(0, battlesLeft - 1);
      setData(payload);
    } catch (e) {
      toast(e.message || "Batalha falhou.");
    }
  });

  // ── Hospital ──────────────────────────────────────────────────────────────
  $("hospitalBtn").addEventListener("click", () => openHospital());

  $("hospitalCancelBtn").addEventListener("click", () => {
    $("hospitalPanel").classList.add("hidden");
  });

  // ── Career ────────────────────────────────────────────────────────────────
  $("setCareerBtn").addEventListener("click", async () => {
    const career = $("careerSelect").value;
    if (!career) return;
    try {
      const payload = await api("/api/action/set_career", {
        method: "POST",
        body: JSON.stringify({ career }),
      });
      setData(payload);
    } catch (e) {
      toast(e.message || "Erro ao mudar carreira.");
    }
  });

  // ── Academy ───────────────────────────────────────────────────────────────
  $("setAcademyBtn").addEventListener("click", async () => {
    const academy = $("academySelect").value;
    const type = $("typeSelect").value;
    try {
      const payload = await api("/api/action/academy_focus", {
        method: "POST",
        body: JSON.stringify({ focus: academy, type }),
      });
      setData(payload);
    } catch (e) {
      toast(e.message || "Erro ao definir foco.");
    }
  });

  // ── Shop ──────────────────────────────────────────────────────────────────
  $("buyBtn").addEventListener("click", async () => {
    const item = $("shopSelect").value;
    const qty = parseInt($("shopQty").value) || 1;
    if (!item) return;
    try {
      const payload = await api("/api/action/buy_item", {
        method: "POST",
        body: JSON.stringify({ item, quantity: qty }),
      });
      setData(payload);
      await refreshShop();
    } catch (e) {
      toast(e.message || "Compra falhou.");
    }
  });

  // ── Use item ──────────────────────────────────────────────────────────────
  $("useItemBtn").addEventListener("click", async () => {
    const item = $("itemSelect").value;
    if (!item) return;
    try {
      const payload = await api("/api/action/use_item", {
        method: "POST",
        body: JSON.stringify({ item }),
      });
      setData(payload);
      await refreshShop();
    } catch (e) {
      toast(e.message || "Uso do item falhou.");
    }
  });

  // ── Travel ────────────────────────────────────────────────────────────────
  $("travelBtn").addEventListener("click", async () => {
    const city = $("citySelect").value;
    if (!city) return;
    try {
      const payload = await api("/api/action/travel", {
        method: "POST",
        body: JSON.stringify({ city }),
      });
      setData(payload);
    } catch (e) {
      toast(e.message || "Viagem falhou.");
    }
  });

  // ── Contest ───────────────────────────────────────────────────────────────
  $("contestBtn").addEventListener("click", async () => {
    try {
      const payload = await api("/api/action/contest", {
        method: "POST",
        body: JSON.stringify({ pokemon_index: 0, difficulty: "local", category: "beauty" }),
      });
      setData(payload);
    } catch (e) {
      toast(e.message || "Contest falhou.");
    }
  });

  // ── Breed ─────────────────────────────────────────────────────────────────
  $("breedBtn").addEventListener("click", async () => {
    const team = appState?.team || [];
    if (team.length < 2) return toast("Precisa de 2 Pokémon na equipe.");
    try {
      const payload = await api("/api/action/breed", {
        method: "POST",
        body: JSON.stringify({ first: 0, second: 1 }),
      });
      setData(payload);
    } catch (e) {
      toast(e.message || "Breed falhou.");
    }
  });

  // ── Tournament ────────────────────────────────────────────────────────────
  $("tournamentBtn").addEventListener("click", () => enterTournament());

  // ── Load saves on boot ────────────────────────────────────────────────────
  loadSaves();
});
