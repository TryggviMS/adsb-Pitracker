// -----------------------------
// Map setup
// -----------------------------
const RKV = { lat: 64.1300, lon: -21.9400 };
const KEF = { lat: 63.9850, lon: -22.6056 };
const RADIUS_KM = 15;
const CIRCLE_CENTER = { lat: 64.111144, lon: -22.018662 };

window.map = L.map('map').setView([RKV.lat, RKV.lon], 10);
const map = window.map;
window.addEventListener('resize', () => map.invalidateSize());
// -----------------------------
// Base map tiles
// -----------------------------
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 19,
  attribution: '&copy; OpenStreetMap contributors'
}).addTo(map);

// -----------------------------
// Scale bar
// -----------------------------
L.control.scale({
  position: 'bottomleft',
  metric: true,
  imperial: false,
  maxWidth: 200
}).addTo(map);

// -----------------------------
// Distance Measure Control Button
// -----------------------------
let measureActive = false;
let firstPoint = null;
let tempLine = null;
let tempMarkers = [];
let measurementDone = false;

const MeasureControl = L.Control.extend({
  options: { position: 'topleft' },
  onAdd: function(map) {
    const container = L.DomUtil.create('div', 'leaflet-bar leaflet-control leaflet-control-custom');
    container.style.width = '34px';
    container.style.height = '34px';
    container.style.cursor = 'pointer';
    container.style.display = 'flex';
    container.style.alignItems = 'center';
    container.style.justifyContent = 'center';
    container.style.backgroundColor = 'white';
    container.title = 'Mæla fjarlægð (tveir smellir)';
    container.innerHTML = '📏';

    L.DomEvent.disableClickPropagation(container);

container.onclick = function() {
  measureActive = !measureActive;

  // Reset measurement state
  firstPoint = null;
  measurementDone = false;
  clearTempMeasurement();

  // Toggle CSS class for active state
  if (measureActive) container.classList.add('active');
  else container.classList.remove('active');
};


    return container;
  }
});

map.addControl(new MeasureControl());

// -----------------------------
// Helper: clear previous measurement
// -----------------------------
function clearTempMeasurement() {
  if (tempLine) { map.removeLayer(tempLine); tempLine = null; }
  tempMarkers.forEach(m => map.removeLayer(m));
  tempMarkers = [];
}

// -----------------------------
// Map click handler for distance
// -----------------------------
map.on('click', function(e) {
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
    color: 'red',
    fillColor: 'red',
    fillOpacity: 1
  }).addTo(map);
  tempMarkers.push(pointMarker);

  if (!firstPoint) {
    firstPoint = e.latlng;
    return;
  }

  // Second click → draw line + popup
  const secondPoint = e.latlng;
  const distanceKm = firstPoint.distanceTo(secondPoint) / 1000;

  tempLine = L.polyline([firstPoint, secondPoint], { color: 'red', weight: 2 }).addTo(map);

  L.popup()
    .setLatLng(secondPoint)
    .setContent(`<b>Fjarlægð:</b> ${distanceKm.toFixed(2)} km`)
    .openOn(map);

  measurementDone = true; // next click resets
});

// -----------------------------
// Sensor range circles
// -----------------------------
// Distance rings (5, 10, 15, 20 km)
// -----------------------------
const distanceRings = [
  { km: 5,  color: '#4da6ff' },
  { km: 10, color: '#3399ff' },
  { km: 15, color: '#1f78d1' },
  { km: 20, color: '#0b4fa3' }
];

distanceRings.forEach(ring => {
  L.circle([CIRCLE_CENTER.lat, CIRCLE_CENTER.lon], {
    radius: ring.km * 1000,
    color: ring.color,
    weight: 1,
    opacity: 0.6,
    fill: false,
    interactive: false,
    dashArray: '4 6'   // slightly dotted
  }).addTo(map);
});

// -----------------------------
// Static markers
// -----------------------------
const houseIcon = L.divIcon({
  html: '🏠',
  iconSize: [32, 32],
  iconAnchor: [16, 16]
});

const homeIcon = L.icon({
  iconUrl: 'icons/home.svg',
  iconSize: [32, 32],
  iconAnchor: [16, 16],
  tooltipAnchor: [0, -16]
});

L.marker([CIRCLE_CENTER.lat, CIRCLE_CENTER.lon], { 
    icon: homeIcon,
    interactive: false  // <- allow clicks to pass through
})
.bindTooltip('<b>Sjávargata 20</b>', { direction: 'top' })
.addTo(map);
const airportIcon = L.icon({
  iconUrl: 'icons/airport.svg',
  iconSize: [30, 30],
  iconAnchor: [15, 15],
  tooltipAnchor: [0, -16]
});

L.marker([RKV.lat, RKV.lon], { icon: airportIcon, interactive: false })
    .bindTooltip('Reykjavíkurflugvöllur (RKV)', { direction: 'top' })
    .addTo(map);

L.marker([KEF.lat, KEF.lon], { icon: airportIcon, interactive: false })
    .bindTooltip('Keflavíkurflugvöllur (KEF)', { direction: 'top' })
    .addTo(map);
// -----------------------------
// Aircraft state
// -----------------------------
const aircraftLayer = L.layerGroup().addTo(map);
const aircraftMarkers = {};
const aircraftState = {};

const STALE_AFTER = 10;
const EXPIRE_AFTER = 60;

const liveIconURL = 'icons/airplane.png';
const unknownIconURL = 'icons/unknown.svg';
const airplaneIconURL = 'icons/airplane.png';
const airplaneIconCache = {};

function getAircraftIcon(color = '#ff0000') {
  if (airplaneIconCache[color]) return airplaneIconCache[color];

  const icon = L.icon({
    iconUrl: airplaneIconURL,
    iconSize: [40, 40],
    iconAnchor: [20, 20]
  });

  airplaneIconCache[color] = icon;
  return icon;
}

const homeLatLng = L.latLng(CIRCLE_CENTER.lat, CIRCLE_CENTER.lon);


// -----------------------------
// Live flight paths from Flask API with dynamic yellow→dark blue gradient
// -----------------------------
let livePathsLayer = null;

// Smooth yellow → dark blue ramp with easing
const colorRamp = [
  [255, 255, 0],   // yellow
  [220, 220, 40],
  [180, 180, 80],
  [130, 130, 130],
  [80, 80, 180],
  [30, 30, 220],
  [0, 34, 76]      // dark blue
];

// Increase this value to keep yellow longer (2–3 works well)
const RAMP_EASE = 2.2;

function lerp(a, b, t) {
  return a + (b - a) * t;
}

function getRampColor(t) {
  // Clamp
  t = Math.max(0, Math.min(1, t));

  // Apply easing (slows the change at the beginning)
  t = Math.pow(t, RAMP_EASE);

  const n = colorRamp.length - 1;
  const scaled = t * n;

  const i = Math.floor(scaled);
  const fraction = scaled - i;

  const c0 = colorRamp[Math.min(i, n)];
  const c1 = colorRamp[Math.min(i + 1, n)];

  const r = Math.round(lerp(c0[0], c1[0], fraction));
  const g = Math.round(lerp(c0[1], c1[1], fraction));
  const b = Math.round(lerp(c0[2], c1[2], fraction));

  return `rgb(${r},${g},${b})`;
}

function addGradientLine(feature) {
  if (!feature.geometry || feature.geometry.type !== 'LineString') return [];
  const coords = feature.geometry.coordinates;
  const numSegments = coords.length - 1;
  if (numSegments <= 0) return [];

  const segments = [];
  for (let i = 0; i < numSegments; i++) {
    const [lon1, lat1] = coords[i];
    const [lon2, lat2] = coords[i + 1];

    // t=0 → start, t=1 → end
    const t = i / Math.max(numSegments - 1, 1); 
    const color = getRampColor(t);

    segments.push(
      L.polyline([[lat1, lon1], [lat2, lon2]], { color, weight: 2 })
        .bindTooltip(feature.properties.flight || '')
    );
  }

  return segments;
}

async function updateLivePaths() {
  try {
    const response = await fetch('http://192.168.0.13:5000/live_paths', { cache: 'no-store' });
    const geojson = await response.json();

    // Remove previous layer(s)
    if (window.livePathsLayer) {
      window.livePathsLayer.forEach(layer => map.removeLayer(layer));
    }

    // Create new segments
    const newLayers = [];
    geojson.features.forEach(feature => {
      const segs = addGradientLine(feature);
      segs.forEach(s => {
        s.addTo(map);
        newLayers.push(s);
      });
    });

    window.livePathsLayer = newLayers;
  } catch (err) {
    console.error('Failed to fetch live paths:', err);
  }
}

// Initial load
updateLivePaths();
setInterval(updateLivePaths, 2000);


// -----------------------------
// Update aircraft
// -----------------------------
async function updateLocalAircraft() {
  const now = Date.now() / 1000;

  // Helper: remove expired markers + state
  function pruneExpired() {
    for (const hex of Object.keys(aircraftState)) {
      const ac = aircraftState[hex];
      const age = now - (ac.lastSeen ?? 0);

      if (age > EXPIRE_AFTER) {
        if (aircraftMarkers[hex]) {
          aircraftLayer.removeLayer(aircraftMarkers[hex]);
          delete aircraftMarkers[hex];
        }
        delete aircraftState[hex];
      }
    }
  }

  // Helper: redraw sidebar from current state
  function renderSidebar() {
    const listEl = document.getElementById('aircraft-list');
    listEl.innerHTML = '';

    Object.values(aircraftState).forEach(ac => {
      const age = now - (ac.lastSeen ?? 0);

      const li = document.createElement('li');
      li.className = 'aircraft-item';
      if (age > STALE_AFTER) li.style.opacity = '0.4';

      const icon = document.createElement('img');
      icon.src = ac.hasPosition ? liveIconURL : unknownIconURL;
      icon.style.width = '30px';
      icon.style.marginRight = '6px';
      icon.style.verticalAlign = 'middle';
      li.appendChild(icon);

      const altText = ac.alt === 'ground'
        ? 'Á jörðinni'
        : (ac.alt ? `${ac.alt} ft` : 'Position unknown');

      li.insertAdjacentHTML(
        'beforeend',
        `<b>${(ac.flight || '').trim()}</b> (ICAO: ${ac.hex}) <br>` +
        `- Flokkur: ${ac.category ? ac.category : 'Óþekktur'} <br>` +
        `${altText} <br>` +
        (ac.hasPosition ? `- Fjarlægð frá heimili: ${ac.distanceKm} km` : '- Staðsetning óþekkt')
      );

      if (ac.hasPosition) {
        li.onclick = () => {
          map.setView([ac.lat, ac.lon], 12);
          aircraftMarkers[ac.hex]?.openTooltip();
        };
      }

      listEl.appendChild(li);
    });
  }

  try {
    // const resp = await fetch('data/aircraft.json', { cache: 'no-store' });
    const resp = await fetch('http://192.168.0.13:5000/live_aircraft', { cache: 'no-store' });
    const data = await resp.json();

    // If aircraft list missing, treat as empty (so we still prune/render)
    const aircraftArr = Array.isArray(data.aircraft) ? data.aircraft : [];

    aircraftArr.forEach(ac => {
      const { hex, lat, lon, alt_baro, flight, track, category } = ac;
      if (!hex) return;

      if (!aircraftState[hex]) aircraftState[hex] = {};

      Object.assign(aircraftState[hex], {
        hex,
        flight: flight?.trim() || 'Óþekkt vél',
        alt: alt_baro,
        lat,
        lon,
        track,
        hasPosition: lat != null && lon != null,
        lastSeen: now,
        category
      });

      if (lat != null && lon != null) {
        const color =
          alt_baro > 30000 ? '#ff0000' :
          alt_baro > 10000 ? '#ffa500' :
          '#00ff00';

        if (!aircraftMarkers[hex]) {
          aircraftMarkers[hex] = L.marker([lat, lon], {
            icon: getAircraftIcon(color),
            rotationAngle: (track ?? 0),
            rotationOrigin: 'center center'
          })
            .bindTooltip(aircraftState[hex].flight)
            .addTo(aircraftLayer);
        } else {
          aircraftMarkers[hex].setLatLng([lat, lon]);
          aircraftMarkers[hex].setRotationAngle(track ?? 0);
        }

        aircraftState[hex].distanceKm =
          (homeLatLng.distanceTo(L.latLng(lat, lon)) / 1000).toFixed(1);
      }
    });

  } catch (err) {
    console.error('Failed to load aircraft.json:', err);
    // IMPORTANT: we still prune + render below
  }

  // Always run these, even if fetch failed
  pruneExpired();
  renderSidebar();
}

// -----------------------------
// Start
// -----------------------------
updateLocalAircraft();
setInterval(updateLocalAircraft, 2000);
