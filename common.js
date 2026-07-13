// Shared helpers for the flight-globe pages. Load after globe.gl's UMD bundle.
const FG = (() => {
  // flights.json times look like "16/06/2011T12:35Z" (DD/MM/YYYY)
  function parseTime(t) {
    const m = /^(\d{2})\/(\d{2})\/(\d{4})T(\d{2}):(\d{2})Z$/.exec(t || '');
    return m ? new Date(Date.UTC(+m[3], +m[2] - 1, +m[1], +m[4], +m[5])) : new Date(t);
  }

  function haversineKm(lat1, lng1, lat2, lng2) {
    const r = Math.PI / 180, R = 6371;
    const a = Math.sin((lat2 - lat1) * r / 2) ** 2 +
      Math.cos(lat1 * r) * Math.cos(lat2 * r) * Math.sin((lng2 - lng1) * r / 2) ** 2;
    return 2 * R * Math.asin(Math.sqrt(a));
  }

  async function loadFlights() {
    const res = await fetch('flights.json');
    if (!res.ok) throw new Error(`HTTP ${res.status} loading flights.json`);
    const raw = await res.json();
    return raw
      .map((f, i) => ({
        index: i,
        date: parseTime(f.time),
        startLat: f.from[0], startLng: f.from[1],
        endLat: f.to[0], endLng: f.to[1],
        distanceKm: haversineKm(f.from[0], f.from[1], f.to[0], f.to[1]),
      }))
      .sort((a, b) => a.date - b.date);
  }

  async function loadCountries() {
    const res = await fetch('data/countries.geojson');
    if (!res.ok) throw new Error(`HTTP ${res.status} loading countries.geojson`);
    return res.json();
  }

  // Ray-casting point-in-polygon over GeoJSON coordinates ([lng, lat] order)
  function inRing(lng, lat, ring) {
    let inside = false;
    for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
      const xi = ring[i][0], yi = ring[i][1], xj = ring[j][0], yj = ring[j][1];
      if ((yi > lat) !== (yj > lat) && lng < (xj - xi) * (lat - yi) / (yj - yi) + xi) inside = !inside;
    }
    return inside;
  }
  function inPolygon(lng, lat, coords) {
    if (!inRing(lng, lat, coords[0])) return false;
    for (let k = 1; k < coords.length; k++) if (inRing(lng, lat, coords[k])) return false;
    return true;
  }
  function countryOf(countries, lat, lng) {
    return countries.features.find(f => {
      const g = f.geometry;
      return g.type === 'Polygon' ? inPolygon(lng, lat, g.coordinates)
        : g.type === 'MultiPolygon' && g.coordinates.some(c => inPolygon(lng, lat, c));
    }) || null;
  }

  function centroid(flights) {
    let lat = 0, lng = 0, n = 0;
    for (const f of flights) {
      lat += f.startLat + f.endLat;
      lng += f.startLng + f.endLng;
      n += 2;
    }
    return n ? { lat: lat / n, lng: lng / n } : { lat: 40, lng: 0 };
  }

  function fitToWindow(globe) {
    const size = () => globe.width(window.innerWidth).height(window.innerHeight);
    size();
    window.addEventListener('resize', size);
  }

  // James-style control panel in the top-left corner. Returns the panel element.
  function panel() {
    const el = document.createElement('div');
    el.className = 'panel';
    const back = document.createElement('a');
    back.href = 'index.html';
    back.innerHTML = 'Back to <b>Globes</b> list';
    el.appendChild(back);
    document.body.appendChild(el);
    return el;
  }
  function toggleButton(panelEl, label, initial, onChange) {
    const btn = document.createElement('button');
    let state = initial;
    const render = () => { btn.innerHTML = `${label} <b>${state ? 'On' : 'Off'}</b>`; };
    btn.addEventListener('click', () => { state = !state; render(); onChange(state); });
    render();
    panelEl.appendChild(btn);
    return btn;
  }
  function showError(err) {
    const el = document.createElement('div');
    el.className = 'panel error';
    el.textContent = `Error: ${err.message || err}`;
    document.body.appendChild(el);
  }

  return { loadFlights, loadCountries, countryOf, centroid, fitToWindow, panel, toggleButton, showError, haversineKm };
})();

window.addEventListener('error', e => FG.showError(e));
