// -----------------------------
// Map setup
// -----------------------------
const RKV = { lat: 64.1300, lon: -21.9400 };
const KEF = { lat: 63.9850, lon: -22.6056 };
const CIRCLE_CENTER = { lat: 64.111144, lon: -22.018662 };

window.map = L.map("map").setView([RKV.lat, RKV.lon], 10);
const map = window.map;

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
  .bindTooltip("<b>Sjávargata 20</b>", { direction: "top" })
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

const liveIconURL = "icons/airplane.png";
const unknownIconURL = "icons/unknown.svg";
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

async function updateLivePaths() {
  try {
    const response = await fetch("http://192.168.0.13:5000/live_paths", {
      cache: "no-store",
    });
    const geojson = await response.json();

    // Remove previous layer(s)
    if (window.livePathsLayer) {
      window.livePathsLayer.forEach((layer) => map.removeLayer(layer));
    }

    // Create new segments
    const newLayers = [];
    (geojson.features || []).forEach((feature) => {
      const segs = addGradientLine(feature);
      segs.forEach((s) => {
        s.addTo(map);
        newLayers.push(s);
      });
    });

    window.livePathsLayer = newLayers;
  } catch (err) {
    console.error("Failed to fetch live paths:", err);
  }
}

// Initial load + refresh
updateLivePaths();
setInterval(updateLivePaths, 2000);

// -----------------------------
// Update aircraft
// -----------------------------
async function updateLocalAircraft() {
  const now = Date.now() / 1000;

  try {
    const resp = await fetch("http://192.168.0.13:5000/live_aircraft", {
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
        flight: (flight || "").trim() || "Óþekkt vél",
        alt: alt_baro,
        lat,
        lon,
        track,
        category,
        hasPosition: lat != null && lon != null,
        lastSeen: lastSeenEpoch,
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
        `<b>${(ac.flight || "").trim()}</b> (ICAO: ${ac.hex}) <br>` +
          `- Flokkur: ${ac.category ? ac.category : "Óþekktur"} <br>` +
          `${altText} <br>` +
          (ac.hasPosition && ac.distanceKm != null
            ? `- Fjarlægð frá heimili: ${ac.distanceKm} km`
            : "- Staðsetning óþekkt")
      );

      if (ac.hasPosition) {
        li.onclick = () => {
          map.setView([ac.lat, ac.lon], 12);
          aircraftMarkers[ac.hex]?.openTooltip();
        };
      }

      listEl.appendChild(li);
    }
  } catch (err) {
    console.error("Failed to load live_aircraft:", err);
  }
}

// -----------------------------
// Start
// -----------------------------
updateLocalAircraft();
setInterval(updateLocalAircraft, 2000);