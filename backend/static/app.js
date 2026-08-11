// no framework, no build step -- just fetch() against the API and some
// DOM writes. Small enough that a bundler would be overkill.

const API = "/api/v1";
let lineColors = {};

async function init() {
  const [stations, lines, status] = await Promise.all([
    getJSON(`${API}/stations`),
    getJSON(`${API}/lines`),
    getJSON(`${API}/lines/status`),
  ]);

  lineColors = Object.fromEntries(lines.map((l) => [l.name, l.color]));

  fillStationList(stations);
  fillAvoidLines(lines);
  fillStatusLineSelect(lines);
  renderStatusTable(status);
}

async function getJSON(url, options) {
  const resp = await fetch(url, options);
  const body = await resp.json();
  if (!resp.ok) throw new Error(body.detail || resp.statusText);
  return body;
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
    .map((route) => {
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
          </div>
          ${segments}
          ${alerts}
        </div>`;
    })
    .join("");
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
    const status = await getJSON(`${API}/lines/status`);
    renderStatusTable(status);
  } catch (err) {
    alert(err.message);
  }
});

init();
