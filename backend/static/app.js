// no framework, no build step -- just fetch()/WebSocket against the API
// and some DOM writes. Small enough that a bundler would be overkill.

const API = "/api/v1";
let lineColors = {};
let statusRows = [];

async function init() {
  const [stations, lines, status] = await Promise.all([
    getJSON(`${API}/stations`),
    getJSON(`${API}/lines`),
    getJSON(`${API}/lines/status`),
  ]);

  lineColors = Object.fromEntries(lines.map((l) => [l.name, l.color]));
  statusRows = status;

  fillStationList(stations);
  fillAvoidLines(lines);
  fillStatusLineSelect(lines);
  renderStatusTable(statusRows);
  loadSavedRoutes();
  connectLiveStatus();
}

async function getJSON(url, options) {
  const resp = await fetch(url, options);
  const body = await resp.json();
  if (!resp.ok) throw new Error(body.detail || resp.statusText);
  return body;
}

// per-device id, no login system yet -- see the hint text next to the
// saved routes list
function deviceId() {
  let id = localStorage.getItem("metro_user_id");
  if (!id) {
    id = "device-" + Math.random().toString(36).slice(2, 10);
    localStorage.setItem("metro_user_id", id);
  }
  return id;
}

function fillStationList(stations) {
  const list = document.getElementById("station-list");
  list.innerHTML = stations.map((s) => `<option value="${s.name}">`).join("");
}

function fillAvoidLines(lines) {
  const box = document.getElementById("avoid-lines");
  box.innerHTML = lines
    .map(
      (l) => `<label><input type="checkbox" value="${l.name}" /> ${l.name}</label>`
    )
    .join("");
}

function fillStatusLineSelect(lines) {
  const select = document.getElementById("status-line");
  select.innerHTML = lines.map((l) => `<option>${l.name}</option>`).join("");
}

function renderStatusTable(rows) {
  const body = document.querySelector("#status-table tbody");
  body.innerHTML = rows
    .map(
      (r) => `
      <tr>
        <td>${r.line}</td>
        <td><span class="status-pill status-${r.status}">${r.status}</span></td>
        <td>${r.delay_seconds ? Math.round(r.delay_seconds / 60) + " min" : "-"}</td>
        <td>${r.reason || "-"}</td>
      </tr>`
    )
    .join("");
}

function connectLiveStatus() {
  const indicator = document.getElementById("ws-indicator");
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  const ws = new WebSocket(`${proto}//${location.host}${API}/disruptions/live`);

  ws.onopen = () => (indicator.textContent = "(live)");
  ws.onclose = () => (indicator.textContent = "(disconnected)");
  ws.onerror = () => (indicator.textContent = "(connection error)");

  ws.onmessage = (event) => {
    const update = JSON.parse(event.data);
    const row = statusRows.find((r) => r.line === update.line);
    if (row) {
      row.status = update.status;
      row.delay_seconds = update.delay_seconds;
      row.reason = update.reason;
    } else {
      statusRows.push(update);
    }
    renderStatusTable(statusRows);
  };
}

function lineChip(name) {
  const color = lineColors[name] || "#888";
  return `<span class="line-chip" style="background:${color}">${name}</span>`;
}

function renderRoutes(routes) {
  const results = document.getElementById("results");
  if (!routes.length) {
    results.innerHTML = `<p class="error">No routes found.</p>`;
    return;
  }

  results.innerHTML = routes
    .map((route, i) => {
      const from = route.segments[0].from_station;
      const to = route.segments[route.segments.length - 1].to_station;

      const segments = route.segments
        .map(
          (seg) => `
          <div class="segment">
            ${lineChip(seg.line)}
            <span>${seg.from_station} &rarr; ${seg.to_station}</span>
            <span style="color:var(--muted)">(${seg.stops_count} stops)</span>
          </div>`
        )
        .join("");

      const alerts = (route.alerts || [])
        .map((a) => `<div class="alert">${a.message}</div>`)
        .join("");

      return `
        <div class="route-card">
          <div class="route-summary">
            <span>${route.eta_minutes} min &middot; ${route.total_transfers} transfer(s) &middot; ${route.total_distance_km} km</span>
            <button type="button" class="save-route" data-from="${from}" data-to="${to}">Save</button>
          </div>
          ${segments}
          ${alerts}
        </div>`;
    })
    .join("");
}

async function loadSavedRoutes() {
  const list = document.getElementById("saved-routes");
  try {
    const rows = await getJSON(`${API}/routes/saved?user_id=${encodeURIComponent(deviceId())}`);
    list.innerHTML = rows.length
      ? rows.map((r) => `<li>${r.from_station} &rarr; ${r.to_station} <span class="hint">(used ${r.frequency_count}x)</span></li>`).join("")
      : `<li class="hint">Nothing saved yet -- find a route and hit Save.</li>`;
  } catch (err) {
    list.innerHTML = `<li class="error">${err.message}</li>`;
  }
}

document.getElementById("route-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const avoidLines = [...document.querySelectorAll("#avoid-lines input:checked")].map((i) => i.value);

  try {
    const body = await getJSON(`${API}/routes/find`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        from_station: document.getElementById("from-station").value,
        to_station: document.getElementById("to-station").value,
        preferences: {
          max_transfers: Number(document.getElementById("max-transfers").value),
          alternatives: Number(document.getElementById("alternatives").value),
          avoid_lines: avoidLines,
        },
      }),
    });
    renderRoutes(body.routes);
  } catch (err) {
    document.getElementById("results").innerHTML = `<p class="error">${err.message}</p>`;
  }
});

document.getElementById("nl-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const query = document.getElementById("nl-query").value;

  try {
    const body = await getJSON(`${API}/query/natural`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
    });
    renderRoutes(body.routes);
  } catch (err) {
    document.getElementById("results").innerHTML = `<p class="error">${err.message}</p>`;
  }
});

// event delegation -- route cards (and their Save buttons) get replaced
// on every search, so a listener bound to a button that no longer exists
// would just go quiet
document.getElementById("results").addEventListener("click", async (e) => {
  if (!e.target.classList.contains("save-route")) return;
  const { from, to } = e.target.dataset;

  try {
    await getJSON(`${API}/routes/save`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: deviceId(), from_station: from, to_station: to }),
    });
    e.target.textContent = "Saved";
    loadSavedRoutes();
  } catch (err) {
    alert(err.message);
  }
});

document.getElementById("status-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const line = document.getElementById("status-line").value;

  try {
    await getJSON(`${API}/lines/${encodeURIComponent(line)}/status`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        status: document.getElementById("status-value").value,
        delay_seconds: Number(document.getElementById("status-delay").value) || 0,
        reason: document.getElementById("status-reason").value || null,
      }),
    });
    // no need to refetch -- the websocket message will update the table
  } catch (err) {
    alert(err.message);
  }
});

init();
