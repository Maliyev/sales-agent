const $ = id => document.getElementById(id);
const csrf = document.querySelector('meta[name="csrf-token"]').content;
const state = {view: "overview", period: "24h", sessions: [], selected: null,
  archived: false, messageSignature: "", logOffset: 0, logLines: [], logPaused: false, config: null};
const number = value => new Intl.NumberFormat("ru-RU").format(value || 0);
const time = value => value ? new Date(value.includes("T") ? value : value.replace(" ", "T") + "Z").toLocaleString("ru-RU") : "—";
const node = (tag, cls, text) => { const item = document.createElement(tag); if (cls) item.className = cls; if (text != null) item.textContent = text; return item; };

let noticeTimer;
function notice(message, error = false) {
  const box = $("notice"); box.textContent = message; box.className = "visible" + (error ? " error" : "");
  clearTimeout(noticeTimer); noticeTimer = setTimeout(() => box.className = "", 5000);
}
async function api(path, options = {}) {
  const headers = {...options.headers};
  if (options.body) headers["Content-Type"] = "application/json";
  if (options.method && options.method !== "GET") headers["X-CSRF-Token"] = csrf;
  const response = await fetch(`/admin/api${path}`, {...options, headers, cache: "no-store"});
  if (response.status === 401) { location.href = "/admin/login"; throw new Error("Требуется вход"); }
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Запрос не выполнен");
  return data;
}
function show(view) {
  state.view = view;
  document.querySelectorAll(".view").forEach(item => item.classList.toggle("active", item.id === view));
  document.querySelectorAll(".nav-item").forEach(item => item.classList.toggle("active", item.dataset.view === view));
  history.replaceState(null, "", `#${view}`);
  if (view === "overview") loadOverview();
  if (view === "chats") { loadSessions(); loadMessages(); }
  if (view === "logs") loadLogs();
  if (view === "sessions") { loadSessions(); loadBlocked(); }
  if (view === "settings") loadSettings();
}
document.querySelectorAll(".nav-item").forEach(button => button.addEventListener("click", () => show(button.dataset.view)));

const themeToggle = $("themeToggle");
const themeLabel = $("themeLabel");
function applyTheme(dark, save = false) {
  document.documentElement.dataset.theme = dark ? "dark" : "light";
  themeToggle.checked = dark;
  themeLabel.textContent = dark ? "Светлая тема" : "Тёмная тема";
  themeToggle.setAttribute("aria-label", `Включить ${dark ? "светлую" : "тёмную"} тему`);
  if (save) {
    try { localStorage.setItem("elen-admin-theme", dark ? "dark" : "light"); }
    catch (_) { /* The selected theme still applies for this page view. */ }
  }
}
applyTheme(document.documentElement.dataset.theme === "dark");
themeToggle.addEventListener("change", () => applyTheme(themeToggle.checked, true));

function stat(label, value, hint) {
  const card = node("div", "stat"); card.append(node("span", "label", label), node("strong", "", typeof value === "string" ? value : number(value)));
  if (hint) card.append(node("span", "hint", hint));
  return card;
}
function tokenSummary(t) {
  const input = Number(t.input) || 0, output = Number(t.output) || 0;
  const total = input + output, inputShare = total ? input / total * 100 : 0;
  const feature = node("article", "metric-total");
  const heading = node("div", "metric-total-heading");
  heading.append(node("span", "label", "Total tokens"), node("span", "metric-period", "за выбранный период"));
  feature.append(heading, node("strong", "metric-total-value", number(total)));
  const bar = node("div", "token-split");
  bar.setAttribute("role", "img");
  bar.setAttribute("aria-label", `Input ${number(input)}, Output ${number(output)}, Total ${number(total)}`);
  const inputPart = node("span", "token-split-input"), outputPart = node("span", "token-split-output");
  inputPart.style.width = `${inputShare}%`; outputPart.style.width = `${total ? 100 - inputShare : 0}%`;
  bar.append(inputPart, outputPart); feature.append(bar);
  const breakdown = node("div", "token-breakdown");
  [["Input tokens", input, "input"], ["Output tokens", output, "output"]].forEach(([label, value, kind]) => {
    const item = node("div", `token-part ${kind}`);
    item.append(node("span", "", label), node("strong", "", number(value)));
    breakdown.append(item);
  });
  feature.append(breakdown);
  return feature;
}
function drawChart(id, rows, fields) {
  const target = $(id); target.replaceChildren();
  if (!rows.length) { target.append(node("span", "", "Пока нет данных за этот период")); return; }
  const width = 600, height = 200, pad = 28;
  const max = Math.max(1, ...rows.flatMap(row => fields.map(field => row[field.key] || 0)));
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`); svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", fields.map(field => field.name).join(", "));
  for (let step = 0; step <= 4; step++) {
    const y = pad + step * (height - 2 * pad) / 4;
    const line = document.createElementNS(svg.namespaceURI, "line");
    line.setAttribute("x1", pad); line.setAttribute("x2", width - 5); line.setAttribute("y1", y); line.setAttribute("y2", y);
    line.setAttribute("stroke", "#293849"); line.setAttribute("stroke-width", "1"); svg.append(line);
    const label = document.createElementNS(svg.namespaceURI, "text");
    label.setAttribute("x", 0); label.setAttribute("y", y + 3); label.setAttribute("fill", "#8194a8"); label.setAttribute("font-size", "9");
    label.textContent = Math.round(max * (4 - step) / 4).toLocaleString("ru-RU"); svg.append(label);
  }
  fields.forEach(field => {
    const path = document.createElementNS(svg.namespaceURI, "polyline");
    path.setAttribute("points", rows.map((row, index) => {
      const x = pad + index * (width - pad - 6) / Math.max(1, rows.length - 1);
      const y = height - pad - (row[field.key] || 0) * (height - 2 * pad) / max;
      return `${x},${y}`;
    }).join(" "));
    path.setAttribute("fill", "none"); path.setAttribute("stroke", field.color);
    path.setAttribute("stroke-width", "2.5"); path.setAttribute("stroke-linecap", "round"); path.setAttribute("stroke-linejoin", "round");
    svg.append(path);
  });
  const first = node("small", "", rows[0].period), last = node("small", "", rows.at(-1).period);
  const labels = node("div", "chart-labels"); labels.style.cssText = "display:flex;justify-content:space-between;width:100%;color:#8194a8;font-size:10px";
  labels.append(first, last); target.style.display = "block"; target.append(svg, labels);
}
async function loadOverview() {
  if (state.view !== "overview") return;
  try {
    const data = await api(`/overview?period=${state.period}`);
    const t = data.totals, o = data.openrouter;
    const support = node("div", "metric-support-grid");
    support.append(
      stat("Customer messages", t.customer_messages), stat("Agent turns", t.agent_turns),
      stat("LLM API calls", t.llm_api_calls), stat("OpenRouter API calls", t.openrouter_api_calls));
    const main = $("mainStats"); main.replaceChildren(tokenSummary(t), support);
    const cost = o.priced_calls ? `$${Number(o.cost_usd).toLocaleString("en-US", {minimumFractionDigits:2, maximumFractionDigits:8})}` : "—";
    $("openrouterStats").replaceChildren(
      stat("Input", o.input), stat("Output", o.output), stat("Total", o.total),
      stat("Расход, USD", cost, `Цена известна для ${o.priced_calls} из ${o.calls} вызовов`));
    drawChart("tokenChart", data.series, [{key:"input",name:"Input tokens",color:"#087f72"},{key:"output",name:"Output tokens",color:"#5879ef"}]);
    drawChart("activityChart", data.series, [{key:"customer_messages",name:"Customer messages",color:"#0a9380"},{key:"agent_turns",name:"Agent turns",color:"#5879ef"},{key:"llm_api_calls",name:"LLM API calls",color:"#d9952d"}]);
    const top = $("topSessions"); top.replaceChildren();
    if (!data.top_sessions.length) top.append(node("tr", "", ""));
    data.top_sessions.forEach(row => {
      const tr = node("tr"), td = node("td"), link = node("button", "row-link", row.session_id);
      link.addEventListener("click", () => { show("chats"); selectSession(row.session_id); });
      td.append(link); tr.append(td);
      [row.tokens, row.messages, row.agent_turns].forEach(value => tr.append(node("td", "", number(value)))); top.append(tr);
    });
  } catch (error) { notice(error.message, true); }
}
$("period").addEventListener("change", event => { state.period = event.target.value; loadOverview(); });

const bakuTime = value => new Intl.DateTimeFormat("ru-RU", {
  timeZone: "Asia/Baku", day: "2-digit", month: "2-digit", year: "numeric",
  hour: "2-digit", minute: "2-digit"
}).format(new Date(value));
$("reportForm").addEventListener("submit", async event => {
  event.preventDefault();
  const days = Number($("reportDays").value);
  if (!Number.isInteger(days) || days < 1 || days > 30) return;
  const button = $("reportButton"), status = $("reportStatus");
  const label = button.textContent;
  button.disabled = true; button.classList.add("is-loading"); button.textContent = "Готовлю отчёт…";
  button.setAttribute("aria-busy", "true"); status.textContent = "Анализируем журнал…";
  try {
    const result = await api("/report", {method: "POST", body: JSON.stringify({days})});
    const period = `${bakuTime(result.start)} — ${bakuTime(result.end)}`;
    $("reportMeta").textContent = `${period} · ${number(result.log_lines)} строк · ${number(result.customer_sessions)} сессий с USER` +
      (result.coverage_warning ? ` · Внимание: доступный журнал начинается ${bakuTime(result.available_from)}, история может быть неполной` : "");
    $("reportText").textContent = result.report;
    $("reportResult").hidden = false;
    status.textContent = result.model_called ? "Готово" : "Нет данных за период";
  } catch (error) { status.textContent = error.message; notice(error.message, true); }
  finally { button.disabled = false; button.classList.remove("is-loading"); button.textContent = label; button.removeAttribute("aria-busy"); }
});

async function loadSessions() {
  try {
    state.sessions = (await api("/sessions")).sessions;
    $("chatCount").textContent = `${state.sessions.length} сессий`;
    const options = $("knownSessions"); options.replaceChildren();
    state.sessions.forEach(item => { const option = node("option"); option.value = item.session_id; options.append(option); });
    renderSessionList();
    if (state.view === "chats" && !state.selected && state.sessions.length) selectSession(state.sessions[0].session_id);
  } catch (error) { if (state.view === "chats" || state.view === "sessions") notice(error.message, true); }
}
function renderSessionList() {
  const query = $("chatSearch").value.toLowerCase(), channel = $("chatFilter").value, list = $("chatSessions");
  list.replaceChildren();
  for (const item of state.sessions) {
    if (!item.session_id.toLowerCase().includes(query) || (channel !== "all" && !item.session_id.startsWith(channel + ":"))) continue;
    const button = node("button", "chat-session" + (item.session_id === state.selected ? " active" : ""));
    button.append(node("strong", "", item.session_id), node("span", "preview", item.last_text || "Пустая история"),
                  node("small", "", `${item.message_count} сообщений · ${time(item.last_at)}`));
    button.addEventListener("click", () => selectSession(item.session_id)); list.append(button);
  }
  if (!list.childElementCount) list.append(node("p", "empty", "Нет сессий"));
}
function selectSession(id) {
  state.selected = id; state.messageSignature = ""; $("chatTitle").textContent = id;
  $("chatMeta").textContent = id.startsWith("whatsapp:") ? "WhatsApp" : id.startsWith("telegram:") ? "Telegram" : "Просмотр истории";
  const canSend = /^(whatsapp:[0-9]+|telegram:-?[0-9]+)$/.test(id);
  $("chatInput").disabled = !canSend; $("chatSend").disabled = !canSend; $("resetSession").disabled = false;
  renderSessionList(); loadMessages(true);
}
async function loadMessages(force = false) {
  if (state.view !== "chats" || !state.selected) return;
  const id = state.selected;
  try {
    const data = await api(`/sessions/${encodeURIComponent(id)}/messages?archived=${state.archived ? 1 : 0}`);
    if (id !== state.selected) return;
    $("contextSize").textContent = `Контекст ~${number(data.context_tokens)} токенов · активных ${data.active_count} · архивных ${data.archived_count}`;
    const signature = data.messages.map(item => `${item.id}:${item.status}:${item.archived}`).join("|");
    if (signature === state.messageSignature && !force) return;
    state.messageSignature = signature;
    const pane = $("chatMessages"), nearBottom = pane.scrollHeight - pane.scrollTop - pane.clientHeight < 90;
    pane.replaceChildren();
    if (!data.messages.length) pane.append(node("p", "empty", "Сообщений пока нет"));
    data.messages.forEach(message => {
      const bubble = node("div", `bubble ${message.role}${message.archived ? " archived" : ""}`, message.text);
      bubble.append(node("span", "meta", `${message.role} · ${time(message.created_at)} · ${message.status}${message.archived ? " · архив" : ""}`));
      pane.append(bubble);
    });
    if (force || nearBottom) pane.scrollTop = pane.scrollHeight;
  } catch (error) { notice(error.message, true); }
}
$("chatSearch").addEventListener("input", renderSessionList); $("chatFilter").addEventListener("change", renderSessionList);
$("showArchived").addEventListener("change", event => { state.archived = event.target.checked; state.messageSignature = ""; loadMessages(true); });
$("chatComposer").addEventListener("submit", async event => {
  event.preventDefault(); const text = $("chatInput").value.trim(); if (!state.selected || !text) return;
  const button = $("chatSend"), label = button.textContent;
  button.disabled = true; button.classList.add("is-loading"); button.textContent = "Отправляю…"; button.setAttribute("aria-busy", "true");
  try { await api(`/sessions/${encodeURIComponent(state.selected)}/messages`, {method:"POST", body:JSON.stringify({text})});
    $("chatInput").value = ""; notice("Сообщение отправлено"); await loadMessages(true); await loadSessions();
  } catch (error) { notice(error.message, true); } finally {
    button.disabled = false; button.classList.remove("is-loading"); button.textContent = label; button.removeAttribute("aria-busy");
  }
});
$("chatInput").addEventListener("keydown", event => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); $("chatComposer").requestSubmit(); } });
$("resetSession").addEventListener("click", async () => {
  if (!state.selected || !confirm(`Сбросить контекст ${state.selected}? История останется в архиве.`)) return;
  try { await api(`/sessions/${encodeURIComponent(state.selected)}/reset`, {method:"POST"}); notice("Контекст сброшен"); await loadMessages(true); await loadSessions(); }
  catch (error) { notice(error.message, true); }
});

async function loadLogs() {
  if (state.view !== "logs" || state.logPaused) return;
  try { const data = await api(`/logs?offset=${state.logOffset}`);
    if (data.offset < state.logOffset) state.logLines = [];
    const changed = data.lines.length || data.offset < state.logOffset;
    state.logOffset = data.offset; state.logLines.push(...data.lines);
    if (state.logLines.length > 1500) state.logLines = state.logLines.slice(-1500);
    if (changed) renderLogs();
  } catch (error) { notice(error.message, true); }
}
function renderLogs() {
  const pane = $("logLines"), nearBottom = pane.scrollHeight - pane.scrollTop - pane.clientHeight < 90;
  const sid = $("logSession").value.toLowerCase(), text = $("logText").value.toLowerCase();
  pane.replaceChildren();
  state.logLines.filter(line => (line.split(" | ")[1] || "").toLowerCase().includes(sid) && line.toLowerCase().includes(text))
    .forEach(line => pane.append(node("div", "log-line", line)));
  if (!pane.childElementCount) pane.append(node("p", "empty", "Нет строк для выбранного фильтра"));
  if (nearBottom && !state.logPaused) pane.scrollTop = pane.scrollHeight;
}
$("logSession").addEventListener("input", renderLogs); $("logText").addEventListener("input", renderLogs);
$("logPause").addEventListener("click", () => {
  state.logPaused = !state.logPaused; $("logPause").textContent = state.logPaused ? "Продолжить" : "Пауза";
  $("logLive").textContent = state.logPaused ? "● PAUSED" : "● LIVE";
  $("logLive").classList.toggle("paused", state.logPaused); if (!state.logPaused) loadLogs();
});

async function loadBlocked() {
  if (state.view !== "sessions") return;
  try { const data = await api("/blocked"), body = $("blockedSessions"); body.replaceChildren();
    if (!data.blocked.length) { const tr = node("tr"), td = node("td", "muted", "Заблокированных сессий нет"); td.colSpan = 4; tr.append(td); body.append(tr); }
    data.blocked.forEach(item => { const tr = node("tr");
      tr.append(node("td", "", item.session_id), node("td", "", item.reason), node("td", "", new Date(item.blocked_at * 1000).toLocaleString("ru-RU")));
      const td = node("td"), button = node("button", "outline", "Разблокировать");
      button.addEventListener("click", async () => { if (!confirm(`Разблокировать ${item.session_id}?`)) return;
        try { await api(`/blocked/${encodeURIComponent(item.session_id)}`, {method:"DELETE"}); notice("Сессия разблокирована"); loadBlocked(); }
        catch (error) { notice(error.message, true); }
      }); td.append(button); tr.append(td); body.append(tr);
    });
  } catch (error) { notice(error.message, true); }
}
$("blockForm").addEventListener("submit", async event => {
  event.preventDefault(); const session_id = $("blockSearch").value.trim(), reason = $("blockReason").value.trim();
  if (!confirm(`Заблокировать ${session_id}?`)) return;
  try { await api("/blocked", {method:"POST", body:JSON.stringify({session_id, reason})});
    $("blockReason").value = ""; notice("Сессия заблокирована"); loadBlocked();
  } catch (error) { notice(error.message, true); }
});

const titles = {gemini:"Gemini / модели",openrouter:"OpenRouter",limits:"Лимиты агента"};
const labels = {model:"Модель",vision_model:"Модель для изображений",tpm_limit:"TPM лимит",thinking_level:"Thinking level",
  enabled:"Включено",reasoning_effort:"Thinking effort",allowed_numbers:"Разрешённые номера (+...) ～ по одному на строку",
  max_search_rounds:"Раунды поиска",max_api_calls_per_reply:"Вызовы API за ответ",list_mode_enabled:"Режим списка",
  max_messages:"Максимум сообщений",window_seconds:"Окно, секунд",limit:"Лимит токенов",auto_reset:"Автосброс",
  auto_compaction:"Автосжатие",compaction_model:"Модель сжатия",context_token_limit:"Порог контекста, токенов",list_context_token_limit:"Порог контекста списка, токенов",
  delays:"Задержки, секунды",max_wait_seconds:"Максимальное ожидание, секунд"};
const groupTitles = {retry:"Повторные попытки",message_rate:"Частота сообщений",token_abuse:"Злоупотребление токенами",context_overflow:"Контекст и сжатие"};
function settingsField(path, value) {
  const row = node("div", "settings-field"), label = node("label", "", labels[path.at(-1)] || path.at(-1));
  const id = `setting-${path.join("-")}`; label.htmlFor = id; let input;
  if (typeof value === "boolean") { input = node("input"); input.type = "checkbox"; input.checked = value; }
  else if (Array.isArray(value)) { input = node("textarea"); input.value = value.join("\n"); }
  else if (typeof value === "number") { input = node("input"); input.type = "number"; input.step = "1"; input.value = value; }
  else if (path.at(-1) === "reasoning_effort") { input = node("select");
    ["", "none", "minimal", "low", "medium", "high", "xhigh", "max"].forEach(optionValue => { const option = node("option", "", optionValue || "Default"); option.value = optionValue; input.append(option); }); input.value = value;
  } else if (path.at(-1) === "thinking_level") { input = node("select");
    ["", "minimal", "low", "medium", "high"].forEach(optionValue => { const option = node("option", "", optionValue || "Default"); option.value = optionValue; input.append(option); }); input.value = value;
  } else { input = node("input"); input.type = "text"; input.value = value; }
  input.id = id; input.dataset.path = path.join("."); input.dataset.kind = Array.isArray(value) ? "array" : typeof value;
  row.append(label, input); return row;
}
function renderSettings() {
  const groups = $("settingsGroups"); groups.replaceChildren();
  Object.entries(state.config).forEach(([name, group]) => {
    const panel = node("div", "panel"); panel.append(node("h2", "", titles[name] || name));
    Object.entries(group).forEach(([key, value]) => {
      if (value && typeof value === "object" && !Array.isArray(value)) {
        panel.append(node("h3", "muted", groupTitles[key] || key));
        Object.entries(value).forEach(([subkey, subvalue]) => panel.append(settingsField([name,key,subkey], subvalue)));
      } else panel.append(settingsField([name,key], value));
    }); groups.append(panel);
  });
}
async function loadSettings() {
  if (state.view !== "settings") return;
  try { state.config = (await api("/settings")).config; renderSettings(); }
  catch (error) { notice(error.message, true); }
}
$("settingsForm").addEventListener("submit", async event => {
  event.preventDefault(); if (!state.config) return;
  const button = event.currentTarget.querySelector("button[type=submit]"), label = button.textContent;
  const config = structuredClone(state.config);
  document.querySelectorAll("[data-path]").forEach(input => {
    const path = input.dataset.path.split("."); let parent = config;
    for (const key of path.slice(0,-1)) parent = parent[key];
    let value;
    if (input.dataset.kind === "boolean") value = input.checked;
    else if (input.dataset.kind === "number") value = Number(input.value);
    else if (input.dataset.kind === "array") value = input.value.split(/[\n,]+/).map(x => x.trim()).filter(Boolean);
    else value = input.value.trim();
    if (input.dataset.kind === "array" && path.at(-1) === "delays") value = value.map(x => Number(x));
    parent[path.at(-1)] = value;
  });
  const status = $("settingsState"); status.textContent = "Сохранение…";
  button.disabled = true; button.classList.add("is-loading"); button.textContent = "Сохраняю…"; button.setAttribute("aria-busy", "true");
  try { const data = await api("/settings", {method:"PUT", body:JSON.stringify({config})});
    state.config = data.config; renderSettings(); status.textContent = "Сохранено · новые запросы используют эти настройки"; notice("Настройки сохранены");
  } catch (error) { status.textContent = error.message; notice(error.message, true); }
  finally { button.disabled = false; button.classList.remove("is-loading"); button.textContent = label; button.removeAttribute("aria-busy"); }
});

show(["overview","chats","logs","sessions","settings"].includes(location.hash.slice(1)) ? location.hash.slice(1) : "overview");
setInterval(() => { if (state.view === "overview") loadOverview(); }, 30000);
setInterval(() => { if (state.view === "chats" || state.view === "sessions") loadSessions(); }, 8000);
setInterval(() => { if (state.view === "chats") loadMessages(); }, 2000);
setInterval(() => { if (state.view === "logs") loadLogs(); }, 2000);
setInterval(() => { if (state.view === "sessions") loadBlocked(); }, 12000);
