(function () {
  document.querySelectorAll("[data-hours]").forEach(function (box) {
    var range = box.querySelector("[data-hours-range]");
    var keepNote = box.querySelector("[data-keep-note]");
    var perDay = box.querySelector("[data-per-day]");
    var same = box.querySelector("[data-same-hours]");
    var week = box.querySelector("[data-week]");

    function sync() {
      var mode = box.querySelector('input[name="hours_mode"]:checked');
      var value = mode ? mode.value : "";
      range.hidden = value !== "range";
      if (keepNote) keepNote.hidden = value !== "keep";
      if (!perDay) return;
      same.hidden = perDay.checked;
      week.hidden = !perDay.checked;
      box.querySelectorAll("[data-day]").forEach(function (day) {
        var row = week.querySelector('[data-row="' + day.dataset.day + '"]');
        if (row) row.hidden = !day.checked;
      });
    }

    if (perDay) {
      perDay.addEventListener("change", function () {
        if (perDay.checked) {
          var from = same.querySelector('input[name="hours_from"]').value;
          var to = same.querySelector('input[name="hours_to"]').value;
          week.querySelectorAll("[data-row]").forEach(function (row) {
            var inputs = row.querySelectorAll("input");
            inputs[0].value = from;
            inputs[1].value = to;
          });
        }
        sync();
      });
    }
    box.querySelectorAll('input[name="hours_mode"], [data-day]').forEach(function (el) {
      el.addEventListener("change", sync);
    });
    sync();
  });
})();
