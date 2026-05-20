let appState = null;
let currentFeed = [];

const $ = (id) => document.getElementById(id);

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || "Erro na API");
  return data;
}

function toast(text) {
  const node = $("toast");
  node.textContent = text;
  node.classList.remove("hidden");
  setTimeout(() => node.classList.add("hidden"), 2400);
}

function showGame() {
  $("startScreen").classList.add("hidden");
  $("gameScreen").classList.remove("hidden");
}

function showStart() {
  $("gameScreen").classList.add("hidden");
  $("startScreen").classList.remove("hidden");
  loadSaves();
}

function setData(payload) {
  appState = payload.state;
  currentFeed = payload.feed || [];
  if (appState?.ready) showGame();
  render();
  renderEvent(payload.pending_event);
}

function render() {
  if (!appState?.ready) return;
  $("charName").textContent = appState.name;
  $("avatar").textContent = initials(appState.name);
  $("charSub").textContent = `${appState.career} - ${appState.age} anos - ${appState.city}`;
  $("topAge").textContent = `${appState.age} anos - ${appState.phase}`;
  $("topCity").textContent = appState.city;
  $("topMoney").textContent = `${appState.money} P`;
  $("topBadges").textContent = `${appState.badges.length} badges`;
  $("topRep").textContent = `${appState.reputation} rep`;
  $("healthValue").textContent = appState.health;
  $("repValue").textContent = appState.reputation;
  $("badgeValue").textContent = appState.badges.length;
  $("boxValue").textContent = appState.box_count;
  $("careerLine").textContent = `${appState.career_info} | ${appState.career_goal}`;
  $("academyLine").textContent = appState.academy_focus;
  renderAttributes();
  renderTeam();
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
      <div class="attr-top"><span>${key}</span><span>${val}</span></div>
      <div class="bar-track"><div class="bar-fill bar-${key}" style="width:${val}%"></div></div>
    </div>
  `).join("");
}

function renderTeam() {
  const list = appState.team || [];
  $("team").innerHTML = list.length ? list.map((p) => `
    <div class="pokemon-card ${p.active ? "active" : ""}">
      <div class="poke-icon">${typeIcon(p.types[0])}</div>
      <div>
        <div class="poke-name">${p.name}</div>
        <div class="poke-level">Lv. ${p.level} - ${p.status}</div>
        <div class="bar-track"><div class="bar-fill bar-POK" style="width:${p.hp_percent}%"></div></div>
      </div>
    </div>
  `).join("") : `<p class="soft">Nenhum Pokemon na equipe.</p>`;
}

function renderInventory() {
  const items = Object.keys(appState.inventory || {});
  $("itemSelect").innerHTML = items.length
    ? items.map((name) => `<option value="${name}">${name} x${appState.inventory[name]}</option>`).join("")
    : `<option value="">Inventario vazio</option>`;
}

function renderCareers() {
  $("careerSelect").innerHTML = (appState.available_careers || [])
    .map((career) => `<option value="${career}" ${career === appState.career ? "selected" : ""}>${career}</option>`)
    .join("");
}

function renderAcademy() {
  $("academySelect").innerHTML = (appState.academy_options || [])
    .map((focus) => `<option value="${focus.id}">${focus.name}</option>`)
    .join("");
}

function renderGymPreview() {
  const g = appState.gym_preview;
  $("gymPreview").innerHTML = g
    ? `<b>Ginasio local</b><br>${g.leader || "-"} | ${g.main_type || "-"}<br>Risco: ${g.risk} | Chance: ${g.estimated_win_chance}%<br>${g.summary}`
    : "Sem ginasio nesta cidade.";
}

function renderActionAvailability() {
  const availability = appState.action_availability || {};
  document.querySelectorAll("[data-action]").forEach((btn) => {
    const allowed = availability[btn.dataset.action] !== false;
    btn.disabled = !allowed;
    btn.title = allowed ? "" : "Disponivel mais tarde na vida.";
  });
  [
    ["setCareerBtn", "set_career"],
    ["setAcademyBtn", "academy_focus"],
    ["buyBtn", "buy_item"],
    ["useItemBtn", "use_item"],
    ["travelBtn", "travel"],
    ["contestBtn", "contest"],
    ["breedBtn", "breed"],
    ["tournamentBtn", "tournament"],
  ].forEach(([id, key]) => {
    const node = $(id);
    if (!node) return;
    const allowed = availability[key] !== false;
    node.disabled = !allowed;
    node.title = allowed ? "" : "Disponivel mais tarde na vida.";
  });
}

function renderFeed() {
  $("feed").innerHTML = currentFeed.length ? currentFeed.map((item) => `
    <article class="feed-card ${item.kind}">
      <div class="event-icon">${feedIcon(item.kind)}</div>
      <div>
        <div class="event-text">${item.text}</div>
        <div class="event-time">${item.time || `Ano ${appState.age}`} - ${item.title}</div>
      </div>
    </article>
  `).join("") : `<article class="feed-card event"><div class="event-icon">V</div><div><div class="event-text">A linha do tempo aparecera aqui.</div><div class="event-time">Ano 0 - Comeco</div></div></article>`;
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
    <div class="choice-label">${event.title}</div>
    <div class="event-text">${event.text}</div>
    <div class="choice-list">
      ${event.choices.map((choice) => `<button onclick="chooseEvent(${choice.index})">${choice.text}</button>`).join("")}
    </div>
  `;
}

function initials(name) {
  return String(name || "PL").split(/\s+/).map((part) => part[0]).join("").slice(0, 2).toUpperCase();
}

function typeIcon(type) {
  const icons = { Fire: "F", Water: "W", Electric: "E", Grass: "G", Rock: "R", Ground: "G", Psychic: "P", Ghost: "O", Dragon: "D", Ice: "I", Poison: "P", Bug: "B", Flying: "F", Fighting: "F", Normal: "N" };
  return icons[type] || "P";
}

function feedIcon(kind) {
  return { time: "T", battle: "B", money: "P", pokemon: "P", career: "C", egg: "O", health: "S", crime: "!", contest: "C", tournament: "T" }[kind] || "V";
}

async function loadSaves() {
  const saves = await api("/api/saves");
  $("saveSelect").innerHTML = saves.length
    ? saves.map((slot) => `<option value="${slot}">${slot}</option>`).join("")
    : `<option value="">Nenhum save</option>`;
}

async function refreshShop() {
  if (!appState?.ready) return;
  try {
    const items = await api("/api/shop");
    $("shopSelect").innerHTML = items.length
      ? items.map((item) => `<option value="${item.name}">${item.name} - ${item.price}P</option>`).join("")
      : `<option value="">Loja indisponivel</option>`;
  } catch {
    $("shopSelect").innerHTML = `<option value="">Loja indisponivel</option>`;
  }
}

async function refreshCities() {
  const cities = await api("/api/cities");
  $("citySelect").innerHTML = cities.map((city) => `<option value="${city}">${city}</option>`).join("");
}

async function createGame() {
  const payload = await api("/api/new", {
    method: "POST",
    body: JSON.stringify({ name: $("newName").value || "Red", hometown: $("newHometown").value }),
  });
  setData(payload);
  await refreshShop();
  toast("Nova vida criada.");
}

async function loadGame() {
  const slot = $("saveSelect").value;
  if (!slot) return toast("Nenhum save selecionado.");
  const payload = await api("/api/load", { method: "POST", body: JSON.stringify({ slot }) });
  setData(payload);
  await refreshShop();
}

async function saveGame() {
  const payload = await api("/api/save", {
    method: "POST",
    body: JSON.stringify({ slot: $("saveSlot").value || "autosave" }),
  });
  setData(payload);
  toast("Jogo salvo.");
}

async function advance(months) {
  const payload = await api("/api/advance", { method: "POST", body: JSON.stringify({ months }) });
  setData(payload);
  await refreshShop();
}

async function chooseEvent(index) {
  const payload = await api("/api/event_choice", { method: "POST", body: JSON.stringify({ index }) });
  setData(payload);
}

async function action(name, body = {}) {
  const payload = await api(`/api/action/${name}`, { method: "POST", body: JSON.stringify(body) });
  setData(payload);
  await refreshShop();
}

async function enterTournament() {
  const payload = await api("/api/tournament", { method: "POST", body: JSON.stringify({ kind: "city" }) });
  setData(payload);
}

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
  $("setCareerBtn").addEventListener("click", () => action("set_career", { career: $("careerSelect").value }));
  $("setAcademyBtn").addEventListener("click", () => action("academy_focus", { focus: $("academySelect").value, type: $("typeSelect").value }));
  $("buyBtn").addEventListener("click", () => action("buy_item", { item: $("shopSelect").value, quantity: 1 }));
  $("useItemBtn").addEventListener("click", () => action("use_item", { item: $("itemSelect").value }));
  $("travelBtn").addEventListener("click", () => action("travel", { city: $("citySelect").value }));
  $("contestBtn").addEventListener("click", () => action("contest", { pokemon_index: 0, difficulty: "local", category: "beauty" }));
  $("breedBtn").addEventListener("click", () => action("breed", { first: 0, second: 1 }));
  $("tournamentBtn").addEventListener("click", enterTournament);
  await loadSaves();
  await refreshCities();
  try {
    const payload = await api("/api/state");
    setData(payload);
    await refreshShop();
  } catch {}
});
