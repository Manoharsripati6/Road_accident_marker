(() => {
  const mapNode = document.getElementById('map');
  if (!mapNode || !window.L) return;

  const map = L.map('map', { zoomControl: false }).setView([20.5937, 78.9629], 5);
  L.control.zoom({ position: 'bottomright' }).addTo(map);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
  }).addTo(map);

  const groups = { accidents: L.layerGroup().addTo(map), spots: L.layerGroup().addTo(map) };
  const colors = { High: '#d94b4b', Medium: '#e99a3c', Low: '#3f9874' };
  let data = { accidents: [], blackspots: [] };

  const safe = (value) => String(value || '').replace(/[&<>'"]/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[char]));
  const severity = document.getElementById('severity-filter');
  const type = document.getElementById('type-filter');
  const risk = document.getElementById('risk-filter');
  const search = document.getElementById('map-search');

  function render() {
    groups.accidents.clearLayers();
    groups.spots.clearLayers();
    const severityValue = severity.value;
    const typeValue = type.value;
    const riskValue = risk.value;
    const text = search.value.trim().toLowerCase();
    const bounds = [];

    data.accidents.filter(accident => {
      return (!severityValue || accident.severity === severityValue) &&
        (!typeValue || accident.type === typeValue) &&
        (!text || accident.location.toLowerCase().includes(text));
    }).forEach(accident => {
      const marker = L.circleMarker([accident.lat, accident.lng], {
        radius: 7, color: '#fff', weight: 2, fillColor: colors[accident.severity], fillOpacity: 1
      }).bindPopup(`<div class="map-popup"><span class="popup-severity ${accident.severity.toLowerCase()}">${safe(accident.severity)}</span><strong>${safe(accident.location)}</strong><span>${safe(accident.type)} · ${safe(accident.date)}</span><span>${accident.casualties} recorded casualties</span></div>`);
      groups.accidents.addLayer(marker);
      bounds.push([accident.lat, accident.lng]);
    });
    data.blackspots.filter(spot => !riskValue || spot.risk === riskValue).forEach(spot => {
      const color = colors[spot.risk];
      const circle = L.circle([spot.latitude, spot.longitude], { radius: spot.radius, color, weight: 2, fillColor: color, fillOpacity: .16 })
        .bindPopup(`<div class="map-popup"><span class="popup-severity ${spot.risk.toLowerCase()}">${safe(spot.risk)} risk</span><strong>Detected black spot</strong><span>${spot.count} verified nearby accidents</span><span>Score ${spot.score} · ${spot.casualties} casualties</span></div>`);
      groups.spots.addLayer(circle);
      bounds.push([spot.latitude, spot.longitude]);
    });
    if (bounds.length && !map._hasFitted) {
      map.fitBounds(bounds, { padding: [40, 40], maxZoom: 14 });
      map._hasFitted = true;
    }
  }

  fetch('/api/map-data')
    .then(response => response.ok ? response.json() : Promise.reject(new Error('Unable to load map data.')))
    .then(payload => {
      data = payload;
      [...new Set(data.accidents.map(item => item.type))].sort().forEach(item => {
        const option = document.createElement('option');
        option.value = item; option.textContent = item; type.appendChild(option);
      });
      [severity, type, risk].forEach(element => element.addEventListener('change', () => { map._hasFitted = false; render(); }));
      search.addEventListener('input', () => { map._hasFitted = false; render(); });
      render();
    })
    .catch(() => { mapNode.insertAdjacentHTML('afterend', '<p class="map-error">Map data could not be loaded. Refresh the page to try again.</p>'); });
})();
