// self-contained on purpose -- fetches its own /lines data instead of
// reaching into app.js's lineColors, since that's populated by an async
// init() with no guaranteed ordering against this script

const DELHI_CENTER = [28.6139, 77.2090];
const INTERCHANGE_COLOR = "#ffffff";

async function initMap() {
  const map = L.map("map").setView(DELHI_CENTER, 11);

  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap contributors",
    maxZoom: 19,
  }).addTo(map);

  const [lines, stations] = await Promise.all([
    fetch("/api/v1/lines").then((r) => r.json()),
    fetch("/api/v1/stations/map").then((r) => r.json()),
  ]);
  const lineColors = Object.fromEntries(lines.map((l) => [l.name, l.color]));

  for (const station of stations) {
    const isInterchange = station.lines.length > 1;
    const color = isInterchange ? INTERCHANGE_COLOR : lineColors[station.lines[0]] || "#888";

    const marker = L.circleMarker([station.coordinates.lat, station.coordinates.lng], {
      radius: isInterchange ? 6 : 4,
      color: isInterchange ? "#333" : color,
      fillColor: color,
      fillOpacity: 0.9,
      weight: isInterchange ? 2 : 1,
    }).addTo(map);

    const chips = station.lines
      .map((name) => `<span class="line-chip" style="background:${lineColors[name] || "#888"}">${name}</span>`)
      .join(" ");
    marker.bindPopup(`<strong>${station.name}</strong><br>${chips}`);
  }
}

initMap();
