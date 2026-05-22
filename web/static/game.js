let appState = null;
let currentFeed = [];
let isAdvancing = false;
let huntsLeft = 3;

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
    : `${s.career} · ${s.age} anos · ${s.city}`;
  $("topAge").textContent = `${s.age} anos · ${s.phase}`;
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
  $("topBadges").textContent = `${(s.badges || []).length} badges`;
  $("topRep").textContent = `${s.reputation} rep`;

  // Left panel stats
  $("healthValue").textContent = s.health;
  $("repValue").textContent = s.reputation;
  $("badgeValue").textContent = (s.badges || []).length;
  $("boxValue").textContent = s.box_count;

  // Health badge
  const badge = $("healthStatusBadge");
  if (badge) {
    badge.textContent = s.health_status || "";
    badge.className = "health-badge" + (s.health < 30 ? " danger" : s.health < 60 ? " warning" : "");
  }

  // Career lines
  const careerParts = [s.career_info, s.career_goal].filter(Boolean);
  $("careerLine").textContent = careerParts.join("  ·  ") || "Sem carreira definida.";
  $("academyLine").textContent = s.academy_focus || "";

  renderAttributes();
  renderTeam();
  renderBox();
  renderInventory();
  renderCareers();
  renderAcademy();
  renderGymPreview();
  renderActionAvailability();
  renderFeed();
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
        <div class="poke-icon">${typeIcon(p.types?.[0])}</div>
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
      <span class="poke-icon">${typeIcon(p.types?.[0])}</span>
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

function renderActionAvailability() {
  const av = appState.action_availability || {};
  document.querySelectorAll(".time-buttons button").forEach((btn) => {
    const allowed = av.advance !== false;
    btn.disabled = !allowed;
    btn.title = allowed ? "" : "Game over: o tempo nao avanca apos a morte.";
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
      const textHtml = summary ? formatSummaryText(item.text)
                     : battle ? formatBattleText(item.text)
                     : escHtml(item.text);
      const textClass = summary ? "event-text summary-text" : "event-text";
      return `
        <article class="feed-card ${item.kind || "event"}${summary ? " summary-card" : ""}">
          <div class="event-icon">${feedIcon(item.kind)}</div>
          <div style="min-width:0;flex:1">
            <div class="event-title">${item.title || ""}</div>
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
    <div class="choice-label">${escHtml(event.title)}</div>
    <div class="event-text" style="margin-bottom:8px">${escHtml(event.text)}</div>
    <div class="choice-list">
      ${event.choices.map((c) => `<button onclick="chooseEvent(${c.index})">${escHtml(c.text)}</button>`).join("")}
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

// ── Summary text rich formatter ───────────────────────────────────────────────

function formatSummaryText(text) {
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
          h = h.replace(/(\d[\d.,]*)\s*Pokedollar/gi, '<span class="sum-money-n">$1 ₱</span>');
          return `<span class="sum-log-item">• ${h}</span>`;
        }).join("");
        return `<div class="sum-row sum-row-log">${labelHtml}<div class="sum-log-list">${rows}</div></div>`;
      }

      // ── Dinheiro ───────────────────────────────────────────────────────────
      if (hint === "money") {
        if (/ganhou/.test(rest)) {
          let h = esc(rest).replace(/(\d[\d.,]*)\s*Pokedollar/gi, '<span class="sum-gain">+$1 ₱</span>');
          return `<div class="sum-row">${labelHtml} <span class="sum-pos">${h}</span></div>`;
        }
        if (/gastou|perdeu/.test(rest)) {
          let h = esc(rest).replace(/(\d[\d.,]*)\s*Pokedollar/gi, '<span class="sum-loss">-$1 ₱</span>');
          return `<div class="sum-row">${labelHtml} <span class="sum-neg">${h}</span></div>`;
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
        return `<div class="sum-row">${labelHtml} <span>${h}</span></div>`;
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
        return `<div class="sum-row">${labelHtml} <span>${h}</span></div>`;
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
        return `<div class="sum-row">${labelHtml} <span class="sum-city">${h}</span></div>`;
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
      return `<div class="sum-row">${labelHtml} <span>${h}</span></div>`;
    }

    // Fallback: plain
    return `<div class="sum-row sum-default">${esc(line)}</div>`;
  }).join("");
}

function formatBattleText(text) {
  const lines = String(text || "").split("\n").filter(l => l.trim());
  return lines.map(raw => {
    const line = raw.trim();
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
  isAdvancing = true;
  const btns = document.querySelectorAll(".time-buttons button");
  btns.forEach((b) => (b.disabled = true));
  try {
    const payload = await api("/api/advance", {
      method: "POST",
      body: JSON.stringify({ months }),
    });
    huntsLeft = 3;
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

document.addEventListener("DOMContentLoaded", async () => {
  $("newGameBtn").addEventListener("click", createGame);
  $("loadBtn").addEventListener("click", loadGame);
  $("saveBtn").addEventListener("click", saveGame);
  $("homeBtn").addEventListener("click", showStart);

  document.querySelectorAll(".time-buttons button").forEach((btn) => {
    btn.addEventListener("click", () => advance(Number(btn.dataset.months)));
  });

  document.querySelectorAll("[data-action]").forEach((btn) => {
    btn.addEventListener("click", () => action(btn.dataset.action));
  });

  $("setCareerBtn").addEventListener("click", () => {
    const career = $("careerSelect").value;
    if (career && career !== "Sem opcoes ainda") action("set_career", { career });
    else toast("Nenhuma carreira disponivel no momento.");
  });

  $("setAcademyBtn").addEventListener("click", () =>
    action("academy_focus", {
      focus: $("academySelect").value,
      type: $("typeSelect").value,
    })
  );

  $("buyBtn").addEventListener("click", () => {
    const item = $("shopSelect").value;
    const qty = parseInt($("shopQty")?.value || "1") || 1;
    if (item && item !== "Loja indisponivel") action("buy_item", { item, quantity: qty });
  });

  $("useItemBtn").addEventListener("click", () => {
    const item = $("itemSelect").value;
    if (item && item !== "Inventario vazio") action("use_item", { item });
    else toast("Inventario vazio.");
  });

  $("travelBtn").addEventListener("click", () =>
    action("travel", { city: $("citySelect").value })
  );

  $("contestBtn").addEventListener("click", () =>
    action("contest", { pokemon_index: 0, difficulty: "local", category: "beauty" })
  );

  $("breedBtn").addEventListener("click", () =>
    action("breed", { first: 0, second: 1 })
  );

  $("tournamentBtn").addEventListener("click", enterTournament);

  $("huntBtn").addEventListener("click", async () => {
    if (huntsLeft <= 0) return toast("Voce ja cacou 3 vezes neste periodo. Avance o tempo.");
    huntsLeft--;
    updateHuntBtn();
    await action("hunt");
  });

  await loadSaves();
  await refreshCities();

  try {
    const payload = await api("/api/state");
    if (payload?.state?.ready) {
      setData(payload);
      await refreshShop();
    }
  } catch {}
});
