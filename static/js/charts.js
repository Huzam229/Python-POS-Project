/* Safe Chart.js helpers for full-page, SPA navigation, and live theme switching. */
(function () {
  var registry = {};

  function isDark() {
    return document.documentElement.classList.contains("dark");
  }

  function chartTheme() {
    var dark = isDark();
    return {
      color: dark ? "#f3f4f6" : "#111827",
      grid: dark ? "rgba(243,244,246,0.14)" : "rgba(17,24,39,0.12)",
      surface: dark ? "#111827" : "#ffffff",
    };
  }

  function cloneOptions(options) {
    if (!options) return {};
    var out = Object.assign({}, options);
    if (options.plugins) {
      out.plugins = Object.assign({}, options.plugins);
      if (options.plugins.legend) {
        out.plugins.legend = Object.assign({}, options.plugins.legend);
        if (options.plugins.legend.labels) {
          out.plugins.legend.labels = Object.assign({}, options.plugins.legend.labels);
        }
      }
      if (options.plugins.tooltip) {
        out.plugins.tooltip = Object.assign({}, options.plugins.tooltip);
      }
    }
    if (options.scales) {
      out.scales = {};
      Object.keys(options.scales).forEach(function (key) {
        var scale = options.scales[key] || {};
        out.scales[key] = Object.assign({}, scale);
        if (scale.ticks) out.scales[key].ticks = Object.assign({}, scale.ticks);
        if (scale.grid) out.scales[key].grid = Object.assign({}, scale.grid);
        if (scale.title) out.scales[key].title = Object.assign({}, scale.title);
      });
    }
    if (options.font) out.font = Object.assign({}, options.font);
    return out;
  }

  function cloneConfig(config) {
    config = config || {};
    return {
      type: config.type,
      data: {
        labels: config.data && config.data.labels ? config.data.labels.slice() : [],
        datasets: ((config.data && config.data.datasets) || []).map(function (ds) {
          var next = Object.assign({}, ds);
          if (Array.isArray(ds.data)) next.data = ds.data.slice();
          if (Array.isArray(ds.backgroundColor)) next.backgroundColor = ds.backgroundColor.slice();
          if (Array.isArray(ds.borderColor)) next.borderColor = ds.borderColor.slice();
          return next;
        }),
      },
      options: cloneOptions(config.options),
    };
  }

  function applyScaleColors(scale, t) {
    if (!scale || typeof scale !== "object") return;
    scale.ticks = scale.ticks || {};
    scale.ticks.color = t.color;
    scale.grid = scale.grid || {};
    scale.grid.color = t.grid;
    if (scale.title) scale.title.color = t.color;
  }

  function decorateConfig(config, t) {
    config.options = config.options || {};
    config.options.color = t.color;
    config.options.font = Object.assign(
      { family: "Inter, system-ui, sans-serif", size: 11, weight: "500" },
      config.options.font || {}
    );

    var type = config.type || "";
    var cartesian = type === "line" || type === "bar" || type === "scatter" || type === "bubble";
    if (cartesian) {
      config.options.scales = config.options.scales || {};
      ["x", "y"].forEach(function (axis) {
        config.options.scales[axis] = config.options.scales[axis] || {};
        applyScaleColors(config.options.scales[axis], t);
      });
    } else if (config.options.scales) {
      Object.keys(config.options.scales).forEach(function (key) {
        applyScaleColors(config.options.scales[key], t);
      });
    }

    config.options.plugins = config.options.plugins || {};
    config.options.plugins.legend = config.options.plugins.legend || {};
    config.options.plugins.legend.labels = Object.assign(
      { boxWidth: 10, font: { size: 11 } },
      config.options.plugins.legend.labels || {}
    );
    config.options.plugins.legend.labels.color = t.color;

    if (config.data && config.data.datasets) {
      config.data.datasets.forEach(function (ds) {
        var border = ds.borderColor;
        if (typeof border === "string") {
          var compact = border.replace(/\s/g, "");
          if (border === "#ffffff" || border === "#fff" || compact === "rgba(255,255,255,1)") {
            ds.borderColor = t.surface;
          }
        }
      });
    }
    return config;
  }

  function drawChart(canvasId) {
    if (typeof Chart === "undefined") return;
    var original = registry[canvasId];
    if (!original) return;
    var el = document.getElementById(canvasId);
    if (!el) {
      delete registry[canvasId];
      return;
    }
    var existing = Chart.getChart(el);
    if (existing) existing.destroy();
    try {
      new Chart(el, decorateConfig(cloneConfig(original), chartTheme()));
    } catch (e) {
      console.error("Chart failed:", canvasId, e);
    }
  }

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

  window.qpApplyChartTheme = function () {
    Object.keys(registry).forEach(function (id) {
      drawChart(id);
    });
    requestAnimationFrame(resizeAll);
  };

  window.qpChart = function (canvasId, config) {
    registry[canvasId] = config;
    var tries = 0;
    function draw() {
      if (typeof Chart === "undefined") {
        if (tries++ < 40) return setTimeout(draw, 50);
        return;
      }
      drawChart(canvasId);
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
