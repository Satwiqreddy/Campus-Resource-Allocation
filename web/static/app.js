const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const hh = (h) => `${String(h).padStart(2, "0")}:00`;
const rupees = (n) => "₹" + Number(n).toLocaleString("en-IN");

const LANES = { Coordinator: 1, ResourceAgent: 2, VolunteerAgent: 3, BudgetAgent: 4 };
const COLORS = ["--event", "--coord", "--resource", "--volunteer", "--budget"];
const lane = (name) => LANES[name] ?? 0;

let meta, fest, requests = [];
try { requests = JSON.parse(localStorage.getItem("fest-slips") || "[]"); } catch { requests = []; }
const saveSlips = () => { try { localStorage.setItem("fest-slips", JSON.stringify(requests)); } catch {} };

async function api(path, body) {
  const r = await fetch(path, body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {});
  const data = await r.json();
  if (!r.ok) throw new Error(typeof data.detail === "string" ? data.detail : data.detail.map((d) => `${d.loc.at(-1)}: ${d.msg}`).join("; "));
  return data;
}

/* ---------------------------------------------------------------- programme + board */
function nowHour() { return Number($("#now").value); }

function renderProgramme() {
  const now = nowHour();
  const mine = new Set(requests.map((r) => r.name));
  const booked = fest.events.filter((e) => e.booked);
  const statusOf = (e) => (!e.booked ? "rejected" : e.end <= now ? "done" : e.start <= now ? "now" : "upcoming");
  const label = { now: "Happening now", upcoming: "Upcoming", done: "Finished", rejected: "Not booked" };
  const rank = { now: 0, upcoming: 1, done: 2, rejected: 3 };
  const events = [...fest.events].sort((a, b) => rank[statusOf(a)] - rank[statusOf(b)] || a.start - b.start);

  $("#stats").innerHTML = [
    [booked.length + " / " + fest.events.length, "events booked"],
    [booked.filter((e) => statusOf(e) === "now").length, "happening now"],
    [booked.filter((e) => statusOf(e) === "upcoming").length, "still to come"],
    [rupees(fest.budget.remaining), "budget left of " + rupees(fest.budget.total)],
  ].map(([b, s]) => `<div><b>${b}</b><span>${s}</span></div>`).join("");

  $("#programme-list").innerHTML = events.map((e) => {
    const st = statusOf(e);
    const where = e.booked
      ? `${esc(e.venue)} · ${e.participants} people${e.changes.length ? " · " + esc(e.changes.join("; ")) : ""}`
      : esc(e.reason);
    return `<li class="${st} ${mine.has(e.event) ? "mine" : ""}">
      <span class="time">${hh(e.start)} – ${hh(e.end)}</span>
      <span class="what"><b>${esc(e.event)}</b><small>${where}</small></span>
      <span class="stamp ${st}">${label[st]}</span></li>`;
  }).join("");
}

function renderBoard() {
  const { hours, venues, equipment, volunteers } = fest.board;
  const now = nowHour();
  const mine = new Set(requests.map((r) => r.name));
  const cap = Object.fromEntries(meta.venues.map((v) => [v.id, v]));
  let html = `<div class="h">Venue</div>` + hours.map((h) => `<div class="h ${h === now ? "cur" : ""}">${hh(h)}</div>`).join("");
  for (const [venue, slots] of Object.entries(venues)) {
    html += `<div class="v">${esc(venue)}<small>${cap[venue].type} · ${cap[venue].capacity}</small></div>`;
    for (let i = 0; i < slots.length; ) {
      let j = i;
      while (j < slots.length && slots[j] === slots[i]) j++;
      if (slots[i]) html += `<div class="busy ${mine.has(slots[i]) ? "mine" : ""}" style="grid-column: span ${j - i}" title="${esc(slots[i])} ${hh(hours[i])}–${hh(hours[j - 1] + 1)}">${esc(slots[i])}</div>`;
      else html += `<div class="free" style="grid-column: span ${j - i}"></div>`;
      i = j;
    }
  }
  $("#board-grid").innerHTML = html;
  const table = (pool) => `<tr><th></th>${hours.map((h) => `<th>${String(h).padStart(2, "0")}</th>`).join("")}</tr>` +
    Object.entries(pool).map(([k, v]) => `<tr><td>${esc(k.replace("_", " "))}</td>${v.map((n) => `<td class="${n ? "" : "zero"}">${n}</td>`).join("")}</tr>`).join("");
  $("#equip-table").innerHTML = table(equipment);
  $("#vol-table").innerHTML = table(volunteers);
}

async function loadFest() {
  fest = await api("/api/fest", { requests, strategy: $("#strategy").value });
  renderProgramme();
  renderBoard();
}

/* ---------------------------------------------------------------- theatre */
const theatre = { queue: [], timer: null, playing: true };

function noteHTML(m) {
  if (m.divider) return `<div class="divider">${esc(m.divider)}</div>`;
  const s = lane(m.sender);
  if (m.receiver === "*") {
    return `<div class="note memo"><div class="msg" style="grid-column: 1 / -1; --c: var(--coord)">
      <span class="p">COORDINATOR'S NOTE</span> ${esc(m.text)}</div></div>`;
  }
  const r = lane(m.receiver);
  const [a, b] = [Math.min(s, r), Math.max(s, r)];
  const who = s === 0 ? m.sender : r === 0 ? m.receiver : "";
  return `<div class="note ${s < r ? "right" : "left"}"><div class="msg" style="grid-column: ${a + 1} / ${b + 2}; --c: var(${COLORS[s]})">
    <span class="p">${esc(m.performative)}</span>${who ? `<span class="who">${esc(who)}</span>` : ""}<br>${esc(m.text)}</div></div>`;
}

function flash(m) {
  document.querySelectorAll(".lane-head").forEach((el) => el.classList.remove("active"));
  if (m.divider) return;
  const heads = document.querySelectorAll(".lane-head");
  heads[lane(m.sender)].classList.add("active");
  if (m.receiver !== "*") heads[lane(m.receiver)].classList.add("active");
}

function showNext() {
  const m = theatre.queue.shift();
  if (!m) { stop(); flash({ divider: true }); return false; }
  const feed = $("#feed");
  feed.insertAdjacentHTML("beforeend", noteHTML(m));
  feed.scrollTop = feed.scrollHeight;
  flash(m);
  return true;
}

function stop() { clearTimeout(theatre.timer); theatre.timer = null; }
function tick() { if (showNext() && theatre.playing) theatre.timer = setTimeout(tick, Number($("#speed").value)); }

function play(log, caption) {
  stop();
  $("#feed").innerHTML = "";
  $("#theatre-caption").textContent = caption;
  let last = null;
  theatre.queue = [];
  for (const m of log) {
    if (m.tick !== last) { theatre.queue.push({ divider: `Step ${m.tick}` }); last = m.tick; }
    theatre.queue.push(m);
  }
  theatre.playing = !matchMedia("(prefers-reduced-motion: reduce)").matches;
  $("#play").textContent = theatre.playing ? "Pause" : "Play";
  if (theatre.playing) tick(); else while (showNext());
}

$("#play").onclick = () => {
  theatre.playing = !theatre.playing;
  $("#play").textContent = theatre.playing ? "Pause" : "Play";
  if (theatre.playing) tick(); else stop();
};
$("#step").onclick = () => { theatre.playing = false; $("#play").textContent = "Play"; stop(); showNext(); };
$("#skip").onclick = () => { stop(); while (showNext()); };

/* ---------------------------------------------------------------- booking slip */
function buildForm() {
  const hours = [];
  for (let h = meta.hours[0]; h <= meta.hours[1]; h++) hours.push(h);
  $("#now").innerHTML = hours.map((h) => `<option value="${h}">${hh(h)}</option>`).join("");
  const h = new Date().getHours();
  $("#now").value = h >= meta.hours[0] && h < meta.hours[1] ? h : 12;   // outside fest hours, show midday
  $("#f-start").innerHTML = hours.slice(0, -1).map((h) => `<option value="${h}" ${h === 11 ? "selected" : ""}>${hh(h)}</option>`).join("");
  $("#f-end").innerHTML = hours.slice(1).map((h) => `<option value="${h}" ${h === 13 ? "selected" : ""}>${hh(h)}</option>`).join("");
  $("#f-type").innerHTML = meta.venue_types.map((t) => `<option ${t === "classroom" ? "selected" : ""}>${t}</option>`).join("");
  $("#f-also").innerHTML = meta.venue_types.map((t) => `<label><input type="checkbox" value="${t}"> ${t}</label>`).join("");
  const fillVenues = () => {
    const types = [$("#f-type").value, ...[...document.querySelectorAll("#f-also input:checked")].map((c) => c.value)];
    $("#f-venue").innerHTML = `<option value="">any suitable</option>` +
      meta.venues.filter((v) => types.includes(v.type)).map((v) => `<option value="${v.id}">${v.id} (${v.capacity} seats)</option>`).join("");
  };
  $("#f-type").onchange = fillVenues;
  $("#f-also").onchange = fillVenues;
  fillVenues();
  const counts = (items, prefix) => items.map((k) => `<label>${k.replace("_", " ")}<input type="number" min="0" max="10" value="0" name="${prefix}${k}"></label>`).join("");
  $("#f-equip").innerHTML = counts(meta.equipment, "eq_");
  $("#f-vol").innerHTML = counts(meta.skills, "vol_");
  $("#slip [name=vol_general]").value = 1;
  $("#scenario-list").innerHTML = meta.scenarios.map((s) => `<button type="button">${esc(s)}</button>`).join("");
}

function readSlip() {
  const f = new FormData($("#slip"));
  const pick = (prefix) => Object.fromEntries([...f].filter(([k, v]) => k.startsWith(prefix) && Number(v) > 0).map(([k, v]) => [k.slice(prefix.length), Number(v)]));
  const also = [...document.querySelectorAll("#f-also input:checked")].map((c) => c.value).filter((t) => t !== f.get("venue_type"));
  return {
    name: f.get("name").trim(), priority: +f.get("priority"), participants: +f.get("participants"),
    start: +f.get("start"), end: +f.get("end"), venue_types: [f.get("venue_type"), ...also],
    preferred_venue: f.get("preferred_venue") || null, equipment: pick("eq_"), volunteers: pick("vol_"),
    extra_cost: +f.get("extra_cost") || 0, flexible_hours: +f.get("flexible_hours"), min_volunteer_ratio: +f.get("min_volunteer_ratio"),
  };
}

function showOutcome(name) {
  const e = fest.events.find((x) => x.event === name);
  const box = $("#outcome");
  box.hidden = false;
  box.className = "outcome " + (e.booked ? "" : "no");
  box.innerHTML = e.booked
    ? `<h3>${esc(name)} is booked.</h3>
       <p><b>${esc(e.venue)}</b>, ${hh(e.start)} – ${hh(e.end)} · ${rupees(e.cost)}</p>
       <ul>${e.changes.length ? e.changes.map((c) => `<li>Negotiated: ${esc(c)}</li>`).join("") : "<li>Exactly as requested.</li>"}
         ${e.equipment.length ? `<li>Equipment: ${esc(e.equipment.join(", "))}</li>` : ""}
         ${e.volunteers.length ? `<li>Volunteers: ${esc(e.volunteers.join(", "))}</li>` : ""}</ul>`
    : `<h3>${esc(name)} could not be booked.</h3><p>${esc(e.reason)}</p>`;
}

$("#slip").onsubmit = async (ev) => {
  ev.preventDefault();
  $("#slip-error").textContent = "";
  const slip = readSlip();
  if (slip.end <= slip.start) { $("#slip-error").textContent = "The event has to end after it starts."; return; }
  if (fest.events.some((e) => e.event === slip.name)) { $("#slip-error").textContent = "That name is already on the programme."; return; }
  const btn = $("#slip .stamp-btn");
  btn.disabled = true;
  try {
    fest = await api("/api/fest", { requests: [...requests, slip], strategy: $("#strategy").value });
    requests.push(slip);
    saveSlips();
    renderProgramme();
    renderBoard();
    showOutcome(slip.name);
    play(fest.log, `How the desks handled “${slip.name}” on top of the ${fest.events.length - 1} events already on the programme.`);
    $("#theatre").scrollIntoView();
  } catch (e) {
    $("#slip-error").textContent = e.message;
  } finally {
    btn.disabled = false;
  }
};

$("#clear").onclick = async () => {
  requests = [];
  saveSlips();
  $("#outcome").hidden = true;
  await loadFest();
};

/* ---------------------------------------------------------------- scenarios */
async function runScenario(name, btn) {
  document.querySelectorAll("#scenario-list button").forEach((b) => b.classList.toggle("on", b === btn));
  const strategy = $("#strategy").value;
  const r = await api("/api/scenario", { name, strategy });
  const other = strategy === "astar" ? "Greedy" : "A*";
  $("#scenario-result").innerHTML = `
    <div class="scores">
      <div><b>${r.metrics.score}</b>score (${strategy === "astar" ? "A*" : "Greedy"})</div>
      <div><b>${r.other.score}</b>score (${other})</div>
      <div><b>${r.events.filter((e) => e.booked).length} / ${r.events.length}</b>booked</div>
      <div><b>${r.metrics.C}</b>double bookings</div>
      <div><b>${rupees(r.budget.remaining)}</b>left of ${rupees(r.budget.total)}</div>
    </div>
    <div class="scroll"><table class="result-table">
      <tr><th>Event</th><th>Priority</th><th>Venue</th><th>Time</th><th>Cost</th><th>What the desks agreed</th></tr>
      ${r.events.map((e) => `<tr><td>${esc(e.event)}</td><td>${e.priority}</td><td>${esc(e.venue || "—")}</td>
        <td>${e.booked ? hh(e.start) + "–" + hh(e.end) : "—"}</td><td>${e.booked ? rupees(e.cost) : "—"}</td>
        <td>${e.booked ? esc(e.changes.join("; ") || "as requested") : "Not booked: " + esc(e.reason)}</td></tr>`).join("")}
    </table></div>`;
  play(r.log, `Scenario “${name}”, every note passed between the desks.`);
}
$("#scenario-list").onclick = (e) => { const b = e.target.closest("button"); if (b) runScenario(b.textContent, b); };
$("#strategy").onchange = () => { loadFest(); const on = $("#scenario-list .on"); if (on) runScenario(on.textContent, on); };
$("#now").onchange = () => { renderProgramme(); renderBoard(); };

(async () => {
  meta = await api("/api/meta");
  buildForm();
  await loadFest();
  const deep = location.hash.match(/^#scenario-(\d+)$/);   // e.g. /#scenario-5 opens that review scenario
  const btn = deep && document.querySelectorAll("#scenario-list button")[deep[1] - 1];
  if (btn) { $("#scenarios").scrollIntoView(); runScenario(btn.textContent, btn); }
})();
