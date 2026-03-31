// -----------------------------
// Map setup
// -----------------------------
const RKV = { lat: 64.1300, lon: -21.9400 };
const KEF = { lat: 63.9850, lon: -22.6056 };
const CIRCLE_CENTER = { lat: 64.1051092, lon: -22.018843 };

window.map = L.map("map").setView([RKV.lat, RKV.lon], 10);
const map = window.map;


// Midnight toggle
// Midnight toggle (single source of truth = window.PATHS_MODE)
window.PATHS_MODE = window.PATHS_MODE || "live"; // "live" | "midnight"


const PATHS_URL_LIVE = "/live_paths";
const PATHS_URL_MIDNIGHT = "/paths_since_midnight";


window.addEventListener("resize", () => map.invalidateSize());

// -----------------------------
// Base map tiles
// -----------------------------
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: "&copy; OpenStreetMap contributors",
}).addTo(map);

// -----------------------------
// Scale bar
// -----------------------------
L.control
  .scale({
    position: "bottomleft",
    metric: true,
    imperial: false,
    maxWidth: 200,
  })
  .addTo(map);

// -----------------------------
// Distance Measure Control Button
// -----------------------------
let measureActive = false;
let firstPoint = null;
let tempLine = null;
let tempMarkers = [];
let measurementDone = false;

function clearTempMeasurement() {
  if (tempLine) {
    map.removeLayer(tempLine);
    tempLine = null;
  }

  tempMarkers.forEach((m) => map.removeLayer(m));
  tempMarkers = [];
}

const MeasureControl = L.Control.extend({
  options: { position: "topleft" },

  onAdd: function () {
    const container = L.DomUtil.create(
      "div",
      "leaflet-bar leaflet-control leaflet-control-custom"
    );

    Object.assign(container.style, {
      width: "34px",
      height: "34px",
      cursor: "pointer",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: "white",
    });

    container.title = "Mæla fjarlægð (tveir smellir)";
    container.innerHTML = "📏";

    L.DomEvent.disableClickPropagation(container);

    container.onclick = function () {
      measureActive = !measureActive;

      // Reset measurement state
      firstPoint = null;
      measurementDone = false;
      clearTempMeasurement();

      // Toggle CSS class for active state
      container.classList.toggle("active", measureActive);
    };

    return container;
  },
});

map.addControl(new MeasureControl());

// -----------------------------
// Map click handler for distance
// -----------------------------
map.on("click", function (e) {
  if (!measureActive) return;

  // Reset if previous measurement is done
  if (measurementDone) {
    clearTempMeasurement();
    firstPoint = null;
    measurementDone = false;
  }

  // Place marker for each click
  const pointMarker = L.circleMarker(e.latlng, {
    radius: 5,
    color: "red",
    fillColor: "red",
    fillOpacity: 1,
  }).addTo(map);

  tempMarkers.push(pointMarker);

  if (!firstPoint) {
    firstPoint = e.latlng;
    return;
  }

  // Second click → draw line + popup
  const secondPoint = e.latlng;
  const distanceKm = firstPoint.distanceTo(secondPoint) / 1000;

  tempLine = L.polyline([firstPoint, secondPoint], { color: "red", weight: 2 }).addTo(map);

  L.popup()
    .setLatLng(secondPoint)
    .setContent(`<b>Fjarlægð:</b> ${distanceKm.toFixed(2)} km`)
    .openOn(map);

  measurementDone = true; // next click resets
});

// -----------------------------
// Sensor range circles (5, 10, 15, 20 km)
// -----------------------------
const distanceRings = [
  { km: 5, color: "#4da6ff" },
  { km: 10, color: "#3399ff" },
  { km: 15, color: "#1f78d1" },
  { km: 20, color: "#0b4fa3" },
];

distanceRings.forEach((ring) => {
  L.circle([CIRCLE_CENTER.lat, CIRCLE_CENTER.lon], {
    radius: ring.km * 1000,
    color: ring.color,
    weight: 1,
    opacity: 0.6,
    fill: false,
    interactive: false,
    dashArray: "4 6",
  }).addTo(map);
});

// -----------------------------
// Static markers
// -----------------------------
const homeIcon = L.icon({
  iconUrl: "icons/home.svg",
  iconSize: [32, 32],
  iconAnchor: [16, 16],
  tooltipAnchor: [0, -16],
});

const airportIcon = L.icon({
  iconUrl: "icons/airport.svg",
  iconSize: [30, 30],
  iconAnchor: [15, 15],
  tooltipAnchor: [0, -16],
});

L.marker([CIRCLE_CENTER.lat, CIRCLE_CENTER.lon], { icon: homeIcon, interactive: false })
  .bindTooltip("<b>Á</b>", { direction: "top" })
  .addTo(map);

L.marker([RKV.lat, RKV.lon], { icon: airportIcon, interactive: false })
  .bindTooltip("Reykjavíkurflugvöllur (RKV)", { direction: "top" })
  .addTo(map);

L.marker([KEF.lat, KEF.lon], { icon: airportIcon, interactive: false })
  .bindTooltip("Keflavíkurflugvöllur (KEF)", { direction: "top" })
  .addTo(map);

// -----------------------------
// Aircraft state
// -----------------------------
const aircraftLayer = L.layerGroup().addTo(map);
const aircraftMarkers = {};
const aircraftState = {};

const STALE_AFTER = 10;

function fmtTime(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleTimeString("is-IS", { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });
}

function fmtDurationSeconds(s) {
  if (s == null || !isFinite(s) || s < 0) return "—";
  const hh = Math.floor(s / 3600);
  const mm = Math.floor((s % 3600) / 60);
  const ss = Math.floor(s % 60);
  return `${hh.toString().padStart(2, "0")}:${mm.toString().padStart(2, "0")}:${ss.toString().padStart(2, "0")}`;
}

function fmtDurationPretty(s) {
  if (s == null || !isFinite(s) || s < 0) return "—";

  const minutes = Math.floor(s / 60);
  const seconds = Math.floor(s % 60);

  if (minutes > 0) {
    return `${minutes} mín ${seconds} sek`;
  } else {
    return `${seconds} sek`;
  }
}

function setSidebarTitle(text) {
  const el = document.getElementById("sidebar-title");
  if (el) el.textContent = text;
}

const liveIconURL = "icons/airplane.png";
const unknownIconURL = "icons/unknown2.svg";
const airplaneIconURL = "icons/airplane.png";
const airplaneIconCache = {};

function getAircraftIcon(color = "#ff0000") {
  if (airplaneIconCache[color]) return airplaneIconCache[color];

  const icon = L.icon({
    iconUrl: airplaneIconURL,
    iconSize: [40, 40],
    iconAnchor: [20, 20],
  });

  airplaneIconCache[color] = icon;
  return icon;
}

const homeLatLng = L.latLng(CIRCLE_CENTER.lat, CIRCLE_CENTER.lon);

// -----------------------------
// Live flight paths from Flask API (discrete yellow → blue)
// -----------------------------
const colorRamp = [
  [255, 255, 0], // bright yellow
  [255, 255, 100], // pale warm yellow
  [90, 170, 220], // calm sky blue
  [0, 120, 220], // strong blue
  [0, 80, 180], // deep blue
];

function getRampColor(t) {
  t = Math.max(0, Math.min(1, t));

  const idx = Math.min(colorRamp.length - 1, Math.floor(t * colorRamp.length));
  const [r, g, b] = colorRamp[idx];

  return `rgb(${r},${g},${b})`;
}

function addGradientLine(feature) {
  if (!feature.geometry || feature.geometry.type !== "LineString") return [];

  const coords = feature.geometry.coordinates;
  if (!coords || coords.length < 2) return [];

  const pts = coords.map(([lon, lat]) => L.latLng(lat, lon));

  // Cumulative distance (meters)
  const cumulative = [0];
  for (let i = 1; i < pts.length; i++) {
    cumulative[i] = cumulative[i - 1] + pts[i - 1].distanceTo(pts[i]);
  }

  const totalDistance = cumulative[cumulative.length - 1];
  if (totalDistance <= 0) return [];

  const segments = [];

  for (let i = 0; i < pts.length - 1; i++) {
    // Start yellow → end blue:
    const t = cumulative[i] / totalDistance;
    const color = getRampColor(t);

    segments.push(
      L.polyline([pts[i], pts[i + 1]], { color, weight: 2 }).bindTooltip(
        feature.properties?.flight || ""
      )
    );
  }

  return segments;
}

function escapeHtml(str) {
  const d = document.createElement("div");
  d.textContent = str ?? "";
  return d.innerHTML;
}

function updateSidebarFromMidnightPaths(geojson) {
  const listEl = document.getElementById("aircraft-list");
  if (!listEl) return;

  setSidebarTitle("Flugvélar frá miðnætti");

  const feats = Array.isArray(geojson?.features) ? geojson.features : [];
  const c = document.getElementById("sidebar-count");
  if (c) c.textContent = `Fj. í lista: ${feats.length}`;

  feats.sort((a, b) => {
    const ta = Date.parse(a?.properties?.end_time || "") || 0;
    const tb = Date.parse(b?.properties?.end_time || "") || 0;
    return tb - ta;
  });

  listEl.innerHTML = "";

  for (const f of feats) {
    const p = f.properties || {};
    const hex = p.hex || "—";
    const flightRaw = (p.flight || "").trim();
    const flight = flightRaw || "Flugnr óþekkt";
    const category = p.category || "Óþekktur";

    const t0 = Date.parse(p.start_time || "");
    const t1 = Date.parse(p.end_time || "");
    const durSec =
      Number.isFinite(t0) && Number.isFinite(t1) ? Math.max(0, (t1 - t0) / 1000) : null;

    // "Unknown" in midnight sidebar should behave like live sidebar:
    // If no callsign/flight is present, show the unknown icon.
    const isUnknown = !flightRaw;

    const li = document.createElement("li");
    li.className = "aircraft-item";

    const icon = document.createElement("img");
    icon.src = isUnknown ? unknownIconURL : liveIconURL;

    icon.style.width = "30px";
    icon.style.marginRight = "6px";
    icon.style.verticalAlign = "middle";
    li.appendChild(icon);

    li.insertAdjacentHTML(
      "beforeend",
      `<b>${escapeHtml(flight)}</b> (ICAO: ${escapeHtml(hex)}) <br>` +
      `- Flokkur: ${escapeHtml(category)} <br>` +
      `- Fyrst móttekið: ${fmtTime(p.start_time)} <br>` +
      `- Síðast móttekið: ${fmtTime(p.end_time)} <br>` +
      `- Merki frá vél móttekið í ${fmtDurationPretty(durSec)} <br>` +
      (typeof p.total_length_km === "number"
        ? `- Lengd flugs: ${p.total_length_km.toFixed(1)} km`
        : "")
    );
    //In your map.js you have two functions that build the sidebar list. Each one has a click handler on the list item
li.onclick = () => openAircraftDetail(hex);

    listEl.appendChild(li);
  }

  if (feats.length === 0) {
    const li = document.createElement("li");
    li.className = "aircraft-item";
    li.textContent = "Engar slóðir skráðar frá miðnætti.";
    listEl.appendChild(li);
  }
}

async function updateLivePaths() {
  try {
    const mode = window.PATHS_MODE || "live";
    const url = mode === "midnight" ? PATHS_URL_MIDNIGHT : PATHS_URL_LIVE;

    const response = await fetch(url, { cache: "no-store" });
    const geojson = await response.json();

    // Remove previous layer(s)
    if (Array.isArray(window.livePathsLayer)) {
      window.livePathsLayer.forEach((layer) => map.removeLayer(layer));
    }
    window.livePathsLayer = [];

    // Index segments by hex so sidebar clicks can zoom to paths
    window.pathsByHex = {};

    // Create new segments
    (geojson.features || []).forEach((feature) => {
      const hex = feature?.properties?.hex;
      const segs = addGradientLine(feature);

      if (hex && !window.pathsByHex[hex]) window.pathsByHex[hex] = [];

      segs.forEach((s) => {
        s.addTo(map);
        window.livePathsLayer.push(s);
        if (hex) window.pathsByHex[hex].push(s);
      });
    });

    // ✅ Update sidebar in midnight mode
    if (mode === "midnight") {
      updateSidebarFromMidnightPaths(geojson);
    } else {
      setSidebarTitle("Flugvélar undir eftirliti");
    }
  } catch (err) {
    console.error("Failed to fetch live paths:", err);
  }
}

// Make callable from HTML button script
window.updateLivePaths = updateLivePaths;

// Initial load + refresh
updateLivePaths();
setInterval(updateLivePaths, 2000);

// -----------------------------
// Update aircraft
// -----------------------------
async function updateLocalAircraft() {
  // ✅ In midnight mode, sidebar is driven by /paths_since_midnight
  // so live aircraft updates must NOT overwrite the sidebar.
  if ((window.PATHS_MODE || "live") === "midnight") {
    return;
  }

  const now = Date.now() / 1000;

  try {
    const resp = await fetch("/live_aircraft", {
      cache: "no-store",
    });
    const data = await resp.json();

    const aircraftArr = Array.isArray(data.aircraft) ? data.aircraft : [];
    const seenHexes = new Set();

    for (const ac of aircraftArr) {
      const {
        hex,
        lat,
        lon,
        alt_baro,
        flight,
        track,
        category,
        last_seen,
        last_seen_epoch,
        total_length_km,
      } = ac;

      if (!hex) continue;
      seenHexes.add(hex);

      if (!aircraftState[hex]) aircraftState[hex] = {};

      const lastSeenEpoch =
        typeof last_seen === "number"
          ? last_seen
          : typeof last_seen_epoch === "number"
            ? last_seen_epoch
            : now;

      Object.assign(aircraftState[hex], {
        hex,
        flight: (flight || "").trim() || "Flugnr óþekkt",
        alt: alt_baro,
        lat,
        lon,
        track,
        category,
        hasPosition: lat != null && lon != null,
        lastSeen: lastSeenEpoch,
        totalLengthKm: (typeof total_length_km === "number") ? total_length_km : null,
      });

      // Marker handling
      if (lat != null && lon != null) {
        const altNum = typeof alt_baro === "number" ? alt_baro : parseFloat(alt_baro);
        const color = altNum > 30000 ? "#ff0000" : altNum > 10000 ? "#ffa500" : "#00ff00";

        if (!aircraftMarkers[hex]) {
          aircraftMarkers[hex] = L.marker([lat, lon], {
            icon: getAircraftIcon(color),
            rotationAngle: track ?? 0,
            rotationOrigin: "center center",
          })
            .bindTooltip(aircraftState[hex].flight)
            .addTo(aircraftLayer);
        } else {
          aircraftMarkers[hex].setLatLng([lat, lon]);
          aircraftMarkers[hex].setRotationAngle(track ?? 0);
        }

        aircraftState[hex].distanceKm = (
          homeLatLng.distanceTo(L.latLng(lat, lon)) / 1000
        ).toFixed(1);
      } else if (aircraftMarkers[hex]) {
        aircraftLayer.removeLayer(aircraftMarkers[hex]);
        delete aircraftMarkers[hex];
        aircraftState[hex].distanceKm = null;
      }
    }

    // Remove aircraft no longer returned by API
    for (const hex of Object.keys(aircraftState)) {
      if (!seenHexes.has(hex)) {
        if (aircraftMarkers[hex]) {
          aircraftLayer.removeLayer(aircraftMarkers[hex]);
          delete aircraftMarkers[hex];
        }
        delete aircraftState[hex];
      }
    }

    // ---------- Sidebar ----------
    const listEl = document.getElementById("aircraft-list");
    listEl.innerHTML = "";

    const sorted = Object.values(aircraftState).sort(
      (a, b) => (b.lastSeen ?? 0) - (a.lastSeen ?? 0)
    );
    const c = document.getElementById("sidebar-count");
    if (c) c.textContent = `Fj. í lista: ${sorted.length}`;

    for (const ac of sorted) {
      const age = now - (ac.lastSeen ?? 0);

      const li = document.createElement("li");
      li.className = "aircraft-item";
      if (age > STALE_AFTER) li.style.opacity = "0.4";

      const icon = document.createElement("img");
      icon.src = ac.hasPosition ? liveIconURL : unknownIconURL;
      icon.style.width = "30px";
      icon.style.marginRight = "6px";
      icon.style.verticalAlign = "middle";
      li.appendChild(icon);

      const altText =
        ac.alt === "ground"
          ? "Á jörðinni"
          : ac.alt != null && ac.alt !== ""
            ? `${ac.alt} ft`
            : "Staðsetning óþekkt";

      li.insertAdjacentHTML(
        "beforeend",
        `<b>${escapeHtml((ac.flight || "").trim())}</b> (ICAO: ${escapeHtml(ac.hex)}) <br>` +
        `- Flokkur: ${escapeHtml(ac.category || "Óþekktur")} <br>` +
        `- Hæð: ${altText} <br>` +
        (ac.totalLengthKm != null
          ? `- Fluglengd: ${ac.totalLengthKm.toFixed(1)} km <br>`
          : "") +
        (ac.hasPosition && ac.distanceKm != null
          ? `- Fjarlægð frá heimili: ${ac.distanceKm} km`
          : "- Staðsetning óþekkt")
      );

li.onclick = () => openAircraftDetail(ac.hex);

      listEl.appendChild(li);
    }
  } catch (err) {
    console.error("Failed to load live_aircraft:", err);
  }
}

// -----------------------------
// Aircraft Detail Panel
// -----------------------------
const detailPanel = document.getElementById("detail-panel");
const detailBackdrop = document.getElementById("detail-backdrop");
const detailContent = document.getElementById("detail-content");
const detailCloseBtn = document.getElementById("detail-close");

function closeAircraftDetail() {
  detailPanel.classList.remove("open");
  detailPanel.setAttribute("aria-hidden", "true");
  detailBackdrop.classList.remove("open");
}

detailCloseBtn.addEventListener("click", closeAircraftDetail);
detailBackdrop.addEventListener("click", closeAircraftDetail);

function val(v, suffix = "") {
  if (v === null || v === undefined || v === "") return "—";
  return escapeHtml(String(v)) + suffix;
}

function detailRow(label, value, highlight = false) {
  if (value === null || value === undefined || value === "") return "";
  return `
    <div class="detail-row">
      <span class="detail-label">${label}</span>
      <span class="detail-value${highlight ? " highlight" : ""}">${val(value)}</span>
    </div>`;
}

async function openAircraftDetail(hex) {
  // Open panel immediately with loading state
  detailContent.innerHTML = '<div class="detail-loading">Hleður...</div>';
  detailPanel.classList.add("open");
  detailPanel.setAttribute("aria-hidden", "false");
  detailBackdrop.classList.add("open");

  try {
    const resp = await fetch(`/aircraft/${hex}`, { cache: "no-store" });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const d = await resp.json();

    const flight = (d.flight || "").trim() || "Flugnr óþekkt";
    const altText = d.alt_baro === "ground"
      ? "Á jörðinni"
      : d.alt_baro != null ? `${d.alt_baro} ft` : null;

    detailContent.innerHTML = `
      <div class="detail-header">
        <div class="detail-flight">✈ ${escapeHtml(flight)}</div>
        ${d.registration
          ? `<div class="detail-registration">${escapeHtml(d.registration)}</div>`
          : ""}
      </div>

      <div class="detail-section-title">Staða flugs</div>
      ${detailRow("Hæð", altText)}
      ${detailRow("Hraði", d.gs != null ? `${d.gs} kn` : null)}
      ${detailRow("Stefna", d.track != null ? `${d.track}°` : null)}
      ${detailRow("Squawk", d.squawk)}
      ${detailRow("RSSI", d.rssi != null ? `${d.rssi} dBFS` : null, true)}

      <div class="detail-section-title">Skráning vélag</div>
      ${detailRow("ICAO hex", d.hex)}
      ${detailRow("Skráningarnúmer", d.registration)}
      ${detailRow("Land", d.country)}
      ${detailRow("Eigandi", d.owner)}
      ${detailRow("Flugfélag", d.operator || d.operatorcallsign)}
      ${detailRow("ICAO flugfélag", d.operatoricao)}

      <div class="detail-section-title">Upplýsingar um vél</div>
      ${detailRow("Framleiðandi", d.manufacturername)}
      ${detailRow("Gerð", d.model)}
      ${detailRow("Tegundarkóði", d.typecode)}
      ${detailRow("Raðnúmer", d.serialnumber)}
      ${detailRow("Vélar", d.engines)}
      ${detailRow("Byggt", d.built)}

      <div class="detail-section-title">Flokkur</div>
      ${detailRow("Kóði", d.category)}
      ${detailRow("Íslenska", d.category_is)}
      ${detailRow("Enska", d.category_en)}

    `;
  } catch (err) {
    detailContent.innerHTML = `
      <div class="detail-loading">Ekki tókst að sækja gögn.</div>`;
    console.error("openAircraftDetail failed:", err);
  }
}

window.openAircraftDetail = openAircraftDetail;

// -----------------------------
// Start
// -----------------------------
updateLocalAircraft();
setInterval(updateLocalAircraft, 2000);