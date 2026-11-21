(function () {
  "use strict";

  function initDropZone(zone) {
    var input = zone.querySelector("input[type=file]");
    var fileName = zone.querySelector("[data-aed-file-name]");

    function showSelectedFile() {
      if (input.files && input.files.length) {
        fileName.textContent = input.files[0].name;
        zone.classList.add("has");
      }
    }

    ["dragenter", "dragover"].forEach(function (type) {
      zone.addEventListener(type, function (event) {
        event.preventDefault();
        zone.classList.add("over");
      });
    });
    ["dragleave", "drop"].forEach(function (type) {
      zone.addEventListener(type, function (event) {
        event.preventDefault();
        zone.classList.remove("over");
      });
    });
    zone.addEventListener("drop", function (event) {
      if (event.dataTransfer.files.length) {
        input.files = event.dataTransfer.files;
        showSelectedFile();
      }
    });
    input.addEventListener("change", showSelectedFile);
  }

  document.querySelectorAll("[data-aed-drop]").forEach(initDropZone);
})();
