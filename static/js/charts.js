/* Safe Chart.js helpers for full-page and SPA navigation. */
(function () {
  function resizeAll() {
    if (typeof Chart === "undefined") return;
    document.querySelectorAll("canvas").forEach(function (c) {
      var ch = Chart.getChart(c);
      if (ch) {
        try {
          ch.resize();
        } catch (e) {}
      }
    });
  }

  window.qpChart = function (canvasId, config) {
    var tries = 0;
    function draw() {
      if (typeof Chart === "undefined") {
        if (tries++ < 40) return setTimeout(draw, 50);
        return;
      }
      var el = document.getElementById(canvasId);
      if (!el) return;
      var existing = Chart.getChart(el);
      if (existing) existing.destroy();
      try {
        new Chart(el, config);
      } catch (e) {
        console.error("Chart failed:", canvasId, e);
        return;
      }
      requestAnimationFrame(function () {
        resizeAll();
        requestAnimationFrame(resizeAll);
      });
      setTimeout(resizeAll, 280);
    }
    draw();
  };

  window.addEventListener("resize", resizeAll);
})();
