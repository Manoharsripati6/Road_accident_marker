(() => {
  const toggle = document.querySelector('[data-sidebar-toggle]');
  if (toggle) {
    toggle.addEventListener('click', () => document.body.classList.toggle('sidebar-open'));
  }

  const palette = { navy: '#173f67', blue: '#3788cb', orange: '#e99a3c', red: '#d94b4b', teal: '#2a918b', green: '#4c9a74' };
  const chartDefaults = {
    color: '#627184',
    font: { family: 'DM Sans' },
  };

  document.addEventListener('DOMContentLoaded', () => {
    if (window.Chart) {
      Chart.defaults.color = chartDefaults.color;
      Chart.defaults.font.family = chartDefaults.font.family;
      if (window.dashboardCharts) {
        const monthly = document.getElementById('monthlyChart');
        const severity = document.getElementById('severityChart');
        if (monthly) new Chart(monthly, {
          type: 'line', data: { labels: window.dashboardCharts.monthly.labels, datasets: [{ data: window.dashboardCharts.monthly.values, borderColor: palette.blue, backgroundColor: 'rgba(55, 136, 203, .12)', pointBackgroundColor: palette.blue, pointRadius: 3, borderWidth: 3, tension: .38, fill: true }] },
          options: { maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: '#eaf0f5' } }, x: { grid: { display: false } } } }
        });
        if (severity) new Chart(severity, {
          type: 'doughnut', data: { labels: window.dashboardCharts.severity.labels, datasets: [{ data: window.dashboardCharts.severity.values, backgroundColor: [palette.green, palette.orange, palette.red], borderWidth: 0, hoverOffset: 4 }] },
          options: { cutout: '74%', plugins: { legend: { position: 'bottom', labels: { usePointStyle: true, boxWidth: 8, padding: 16 } } } }
        });
      }
      if (window.analyticsCharts) {
        const type = document.getElementById('typeChart');
        const hour = document.getElementById('hourChart');
        if (type) new Chart(type, {
          type: 'bar', data: { labels: window.analyticsCharts.type.labels, datasets: [{ data: window.analyticsCharts.type.values, backgroundColor: [palette.navy, palette.blue, palette.teal, palette.orange, palette.red, '#8573bf'], borderRadius: 7, maxBarThickness: 48 }] },
          options: { maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: '#eaf0f5' } }, x: { grid: { display: false } } } }
        });
        if (hour) new Chart(hour, {
          type: 'line', data: { labels: window.analyticsCharts.hours.labels, datasets: [{ data: window.analyticsCharts.hours.values, borderColor: palette.orange, backgroundColor: 'rgba(233, 154, 60, .1)', borderWidth: 3, tension: .35, fill: true, pointRadius: 3 }] },
          options: { maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: '#eaf0f5' } }, x: { grid: { display: false } } } }
        });
      }
    }

    if (window.coordinatePicker && window.L) {
      const latitude = document.getElementById('latitude');
      const longitude = document.getElementById('longitude');
      const initialLat = Number(latitude.value) || 20.5937;
      const initialLng = Number(longitude.value) || 78.9629;
      const map = L.map('coordinate-map').setView([initialLat, initialLng], latitude.value ? 14 : 5);
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19, attribution: '&copy; OpenStreetMap contributors' }).addTo(map);
      let marker = latitude.value && longitude.value ? L.marker([initialLat, initialLng]).addTo(map) : null;
      const setPoint = (point) => {
        latitude.value = point.lat.toFixed(6);
        longitude.value = point.lng.toFixed(6);
        if (marker) marker.setLatLng(point); else marker = L.marker(point).addTo(map);
      };
      map.on('click', (event) => setPoint(event.latlng));
    }
  });
})();
