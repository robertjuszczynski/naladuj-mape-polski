(function () {
  var form = document.querySelector(".aed-single");
  if (!form) return;
  var lat = form.querySelector("[data-lat]");
  var lon = form.querySelector("[data-lon]");
  var status = form.querySelector("[data-locate-status]");
  var mapEl = form.querySelector("[data-map]");
  var map, pin;

  function fillAddress(la, lo) {
    fetch(form.dataset.locateUrl + "?lat=" + la + "&lon=" + lo, { credentials: "same-origin" })
      .then(function (r) { return r.json(); })
      .then(function (address) {
        Object.keys(address).forEach(function (key) {
          var input = form.querySelector('[data-field="' + key + '"]');
          if (input && address[key]) input.value = address[key];
        });
        if (address.miejscowosc) status.textContent = "Adres uzupełniony z lokalizacji. Sprawdź go i popraw, jeśli trzeba.";
      })
      .catch(function () {});
  }

  function place(la, lo, zoom) {
    lat.value = la.toFixed(6);
    lon.value = lo.toFixed(6);
    if (!map) return;
    if (pin) pin.setLatLng([la, lo]);
    else {
      pin = L.marker([la, lo], { draggable: true }).addTo(map);
      pin.on("dragend", function () {
        var p = pin.getLatLng();
        place(p.lat, p.lng);
      });
    }
    map.setView([la, lo], zoom || map.getZoom());
    fillAddress(lat.value, lon.value);
  }

  window.addEventListener("load", function () {
    if (!window.L || !mapEl) return;
    map = L.map(mapEl).setView([52.1, 19.4], 6);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "&copy; OpenStreetMap",
    }).addTo(map);
    map.on("click", function (e) { place(e.latlng.lat, e.latlng.lng, Math.max(map.getZoom(), 17)); });
    if (lat.value && lon.value) place(parseFloat(lat.value), parseFloat(lon.value), 18);
  });

  form.querySelector("[data-locate]").addEventListener("click", function () {
    if (!navigator.geolocation) {
      status.textContent = "Ta przeglądarka nie udostępnia lokalizacji – kliknij miejsce na mapie.";
      return;
    }
    status.textContent = "Ustalam lokalizację…";
    navigator.geolocation.getCurrentPosition(
      function (p) {
        place(p.coords.latitude, p.coords.longitude, 18);
        status.textContent = "Mamy lokalizację (dokładność ok. " + Math.round(p.coords.accuracy) + " m). Przesuń pinezkę, jeśli trzeba.";
      },
      function () { status.textContent = "Nie udało się ustalić lokalizacji – kliknij miejsce na mapie albo wpisz adres."; },
      { enableHighAccuracy: true, timeout: 10000 }
    );
  });

  var hoursText = form.querySelector("[data-hours-text]");
  function syncHours() {
    var other = form.querySelector('input[name="hours_mode"]:checked');
    hoursText.hidden = !other || other.value !== "other";
  }
  form.querySelectorAll('input[name="hours_mode"]').forEach(function (r) { r.addEventListener("change", syncHours); });
  syncHours();
})();
