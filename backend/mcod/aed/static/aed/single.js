(function () {
  var form = document.querySelector(".aed-single");
  if (!form) return;
  var lat = form.querySelector("[data-lat]");
  var lon = form.querySelector("[data-lon]");
  var mapEl = form.querySelector("[data-map]");
  var search = form.querySelector("[data-search]");
  var list = form.querySelector("[data-results]");
  var searchStatus = form.querySelector("[data-search-status]");
  var locateStatus = form.querySelector("[data-locate-status]");
  var searchSpin = form.querySelector("[data-search-spin]");
  var locateButton = form.querySelector("[data-locate]");
  var locateSpin = form.querySelector("[data-locate-spin]");
  var locateLabel = form.querySelector("[data-locate-label]");
  var LOCATE_TEXT = locateLabel.textContent;
  var loading = 0, searchId = 0;
  var ORTO = "https://mapy.geoportal.gov.pl/wss/service/PZGIK/ORTO/WMS/StandardResolution";
  var IMPRECISE_M = 150;
  var map, pin, layers, results = [], active = -1, timer;

  function field(name) {
    return form.querySelector('[data-field="' + name + '"]');
  }

  function fill(address) {
    ["ulica", "numer_budynku", "kod_pocztowy", "miejscowosc"].forEach(function (key) {
      if (address[key] && field(key)) field(key).value = address[key];
    });
  }

  function busy(on) {
    loading = Math.max(0, loading + (on ? 1 : -1));
    searchSpin.hidden = !loading;
    search.setAttribute("aria-busy", loading ? "true" : "false");
  }

  function reverse(la, lo) {
    busy(true);
    var previous = search.placeholder;
    search.placeholder = "Ustalam adres…";
    return fetch(form.dataset.locateUrl + "?lat=" + la + "&lon=" + lo, { credentials: "same-origin" })
      .then(function (r) { return r.json(); })
      .then(function (address) {
        fill(address);
        if (address.label) search.value = address.label;
        return address;
      })
      .catch(function () { return {}; })
      .then(function (address) {
        search.placeholder = previous;
        busy(false);
        return address;
      });
  }

  function place(la, lo, zoom, lookup) {
    lat.value = la.toFixed(6);
    lon.value = lo.toFixed(6);
    if (!map) return;
    if (pin) pin.setLatLng([la, lo]);
    else {
      pin = L.marker([la, lo], { draggable: true, keyboard: true, title: "Miejsce AED" }).addTo(map);
      pin.on("dragend", function () {
        var p = pin.getLatLng();
        place(p.lat, p.lng, null, true);
      });
    }
    map.setView([la, lo], zoom || map.getZoom());
    if (lookup) reverse(lat.value, lon.value);
  }

  function setLayer(name) {
    Object.keys(layers).forEach(function (key) {
      if (key === name) layers[key].addTo(map);
      else map.removeLayer(layers[key]);
    });
    form.querySelectorAll("[data-layer]").forEach(function (b) {
      var on = b.dataset.layer === name;
      b.classList.toggle("on", on);
      b.setAttribute("aria-pressed", on ? "true" : "false");
    });
  }

  window.addEventListener("load", function () {
    if (!window.L || !mapEl) return;
    map = L.map(mapEl).setView([52.1, 19.4], 6);
    layers = {
      map: L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19, attribution: "&copy; OpenStreetMap" }),
      orto: L.tileLayer.wms(ORTO, { layers: "Raster", format: "image/jpeg", maxZoom: 20, attribution: "Ortofotomapa &copy; GUGiK" }),
    };
    setLayer("map");
    form.querySelectorAll("[data-layer]").forEach(function (b) {
      b.addEventListener("click", function () { setLayer(b.dataset.layer); });
    });
    map.on("click", function (e) { place(e.latlng.lat, e.latlng.lng, Math.max(map.getZoom(), 18), true); });
    if (lat.value && lon.value) {
      var noAddress = !field("ulica").value && !field("miejscowosc").value;
      place(parseFloat(lat.value), parseFloat(lon.value), 18, noAddress);
    }
  });

  // Address combobox
  function close() {
    list.hidden = true;
    search.setAttribute("aria-expanded", "false");
    active = -1;
  }

  function render() {
    list.innerHTML = "";
    results.forEach(function (r, i) {
      var li = document.createElement("li");
      li.id = "address-opt-" + i;
      li.setAttribute("role", "option");
      li.setAttribute("aria-selected", i === active ? "true" : "false");
      li.textContent = r.label;
      if (!r.exact) {
        var note = document.createElement("small");
        note.textContent = r.kind === "place" ? "miejscowość" : "ulica";
        li.appendChild(note);
      }
      li.addEventListener("mousedown", function (e) { e.preventDefault(); choose(i); });
      list.appendChild(li);
    });
    list.hidden = !results.length;
    search.setAttribute("aria-expanded", results.length ? "true" : "false");
    search.setAttribute("aria-activedescendant", active >= 0 ? "address-opt-" + active : "");
  }

  function choose(i) {
    var r = results[i];
    if (!r) return;
    search.value = r.label;
    fill(r);
    place(r.lat, r.lon, r.exact ? 19 : r.kind === "street" ? 17 : 14, false);
    if (map && r.exact) setLayer("orto");
    searchStatus.textContent = r.exact
      ? "Pinezka stoi przy budynku. Przesuń ją na wejście albo miejsce, gdzie wisi AED."
      : "Pokazujemy " + (r.kind === "place" ? "miejscowość" : "ulicę") + ". Kliknij na mapie dokładne miejsce AED.";
    close();
  }

  search.addEventListener("input", function () {
    clearTimeout(timer);
    var q = search.value.trim();
    if (q.length < 3) {
      results = [];
      return render();
    }
    timer = setTimeout(function () {
      var id = ++searchId;
      searchStatus.textContent = "Szukam adresu…";
      busy(true);
      fetch(form.dataset.searchUrl + "?q=" + encodeURIComponent(q), { credentials: "same-origin" })
        .then(function (r) { return r.json(); })
        .finally(function () { busy(false); })
        .then(function (data) {
          if (id !== searchId) return;
          results = data.results || [];
          active = -1;
          render();
          searchStatus.textContent = results.length
            ? results.length + " podpowiedzi – wybierz jedną."
            : "Brak podpowiedzi. Spróbuj: „Miejscowość, ulica numer” albo kliknij miejsce na mapie.";
        })
        .catch(function () { searchStatus.textContent = "Wyszukiwarka adresów nie odpowiada – kliknij miejsce na mapie."; });
    }, 300);
  });

  search.addEventListener("keydown", function (e) {
    if (list.hidden) return;
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      active = (active + (e.key === "ArrowDown" ? 1 : -1) + results.length) % results.length;
      render();
    } else if (e.key === "Enter") {
      e.preventDefault();
      choose(active >= 0 ? active : 0);
    } else if (e.key === "Escape") {
      close();
    }
  });
  search.addEventListener("blur", function () { setTimeout(close, 150); });

  // Device location: on Wi-Fi desktops it is often only the city, so say so and ask for the exact point.
  function locating(text) {
    locateButton.disabled = !!text;
    locateSpin.hidden = !text;
    locateLabel.textContent = text || LOCATE_TEXT;
  }

  locateButton.addEventListener("click", function () {
    if (!navigator.geolocation) {
      locateStatus.textContent = "Ta przeglądarka nie udostępnia lokalizacji.";
      return;
    }
    locating("Ustalam lokalizację…");
    locateStatus.textContent = "";
    navigator.geolocation.getCurrentPosition(
      function (p) {
        var accuracy = Math.round(p.coords.accuracy);
        place(p.coords.latitude, p.coords.longitude, accuracy > IMPRECISE_M ? 16 : 19, false);
        locating("Szukam adresu…");
        reverse(lat.value, lon.value).then(function () {
          locating("");
          locateStatus.textContent =
            accuracy > IMPRECISE_M
              ? "Lokalizacja przybliżona (±" + accuracy + " m, np. z sieci Wi-Fi). Sprawdź adres albo kliknij dokładne miejsce."
              : "Dokładność ±" + accuracy + " m. Przesuń pinezkę, jeśli trzeba.";
        });
      },
      function () {
        locating("");
        locateStatus.textContent = "Nie udało się ustalić lokalizacji – wpisz adres.";
      },
      { enableHighAccuracy: true, timeout: 10000 }
    );
  });

  // Hours: day buttons with one range for all, or a range per chosen day
  var range = form.querySelector("[data-hours-range]");
  var same = form.querySelector("[data-same-hours]");
  var week = form.querySelector("[data-week]");
  var perDay = form.querySelector("[data-per-day]");
  var sameFrom = form.querySelector('input[name="hours_from"]');
  var sameTo = form.querySelector('input[name="hours_to"]');

  function syncHours() {
    var mode = form.querySelector('input[name="hours_mode"]:checked');
    range.hidden = !mode || mode.value !== "range";
    same.hidden = perDay.checked;
    week.hidden = !perDay.checked;
    form.querySelectorAll("[data-day]").forEach(function (day) {
      var row = week.querySelector('[data-row="' + day.dataset.day + '"]');
      if (row) row.hidden = !day.checked;
    });
  }

  perDay.addEventListener("change", function () {
    if (perDay.checked) {
      week.querySelectorAll("[data-row]").forEach(function (row) {
        var inputs = row.querySelectorAll("input");
        inputs[0].value = sameFrom.value;
        inputs[1].value = sameTo.value;
      });
    }
    syncHours();
  });
  form.querySelectorAll('input[name="hours_mode"], [data-day]').forEach(function (el) {
    el.addEventListener("change", syncHours);
  });
  syncHours();
})();
