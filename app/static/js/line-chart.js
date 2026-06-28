// Renders value-over-time line charts with Chart.js.
//
// Each chart is a <canvas> with:
//   data-chart-source : id of a <script type="application/json"> holding an
//                       array of {x: epoch_ms, y: value} points
//   data-symbol       : currency symbol for axis/tooltip formatting (default $)
//   data-label        : dataset label (default "Value")
//
// A linear epoch-millisecond x-axis is used with manual UTC date formatting so
// no Chart.js date adapter is required. Dates are rendered in UTC to match the
// timestamps shown elsewhere in the UI.
(function () {
  if (typeof Chart === "undefined") {
    return;
  }

  var instances = [];

  function isDark() {
    return document.documentElement.classList.contains("dark");
  }

  function theme() {
    if (isDark()) {
      return {
        line: "#e2e8f0",
        fill: "rgba(226, 232, 240, 0.08)",
        projection: "#94a3b8",
        text: "#94a3b8",
        grid: "rgba(148, 163, 184, 0.15)",
        zero: "rgba(148, 163, 184, 0.55)",
      };
    }
    return {
      line: "#0f172a",
      fill: "rgba(15, 23, 42, 0.08)",
      projection: "#64748b",
      text: "#475569",
      grid: "rgba(148, 163, 184, 0.2)",
      zero: "rgba(100, 116, 139, 0.55)",
    };
  }

  // Draws a solid horizontal line at y = 0 so liabilities (plotted as negative
  // net-worth impact) read clearly as sitting below zero and rising toward it.
  function zeroLinePlugin(colors) {
    return {
      id: "zeroLine",
      afterDraw: function (chart) {
        var yScale = chart.scales.y;
        if (!yScale) return;
        var y = yScale.getPixelForValue(0);
        var area = chart.chartArea;
        if (y < area.top || y > area.bottom) return;
        var ctx = chart.ctx;
        ctx.save();
        ctx.beginPath();
        ctx.moveTo(area.left, y);
        ctx.lineTo(area.right, y);
        ctx.lineWidth = 1;
        ctx.strokeStyle = colors.zero;
        ctx.stroke();
        ctx.restore();
      },
    };
  }

  var canvases = document.querySelectorAll("canvas[data-chart-source]");
  Array.prototype.forEach.call(canvases, function (canvas) {
    var dataEl = document.getElementById(canvas.dataset.chartSource);
    if (!dataEl) {
      return;
    }
    var points;
    try {
      points = JSON.parse(dataEl.textContent);
    } catch (e) {
      return;
    }
    if (!points || points.length === 0) {
      return;
    }
    var projection = null;
    if (canvas.dataset.projectionSource) {
      var projEl = document.getElementById(canvas.dataset.projectionSource);
      if (projEl) {
        try {
          var parsed = JSON.parse(projEl.textContent);
          if (parsed && parsed.length > 0) {
            projection = parsed;
          }
        } catch (e) {
          projection = null;
        }
      }
    }
    instances.push({
      canvas: canvas,
      points: points,
      projection: projection,
      chart: renderChart(canvas, points, projection),
    });
  });

  function renderChart(canvas, points, projection) {
    var symbol = canvas.dataset.symbol || "$";
    var label = canvas.dataset.label || "Value";
    var projectionLabel = canvas.dataset.projectionLabel || "Projected";
    var colors = theme();
    var baseline = canvas.dataset.baseline === "zero";

    var yMin = null;
    var yMax = null;
    if (baseline) {
      var all = points.slice();
      if (projection) all = all.concat(projection);
      all.forEach(function (p) {
        if (yMin === null || p.y < yMin) yMin = p.y;
        if (yMax === null || p.y > yMax) yMax = p.y;
      });
      // Always keep zero within view so the baseline is meaningful.
      yMin = Math.min(0, yMin === null ? 0 : yMin);
      yMax = Math.max(0, yMax === null ? 0 : yMax);
    }

    function formatMoney(value) {
      return (
        symbol +
        Number(value).toLocaleString(undefined, {
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
        })
      );
    }

    var datasets = [
      {
        label: label,
        data: points,
        borderColor: colors.line,
        backgroundColor: colors.fill,
        borderWidth: 2,
        tension: 0.25,
        fill: true,
        pointRadius: 3,
        pointHoverRadius: 5,
      },
    ];

    if (projection) {
      datasets.push({
        label: projectionLabel,
        data: projection,
        borderColor: colors.projection,
        backgroundColor: "transparent",
        borderWidth: 2,
        borderDash: [6, 6],
        tension: 0,
        fill: false,
        pointRadius: 0,
        pointHoverRadius: 4,
      });
    }

    return new Chart(canvas, {
      type: "line",
      data: {
        datasets: datasets,
      },
      plugins: baseline ? [zeroLinePlugin(colors)] : [],
      options: {
        responsive: true,
        maintainAspectRatio: false,
        parsing: false,
        scales: {
          x: {
            type: "linear",
            ticks: {
              color: colors.text,
              autoSkip: true,
              maxRotation: 0,
              callback: function (value) {
                return new Date(value).toLocaleDateString(undefined, {
                  timeZone: "UTC",
                });
              },
            },
            grid: { display: false },
          },
          y: {
            suggestedMin: baseline ? yMin : undefined,
            suggestedMax: baseline ? yMax : undefined,
            ticks: {
              color: colors.text,
              callback: function (value) {
                return formatMoney(value);
              },
            },
            grid: { color: colors.grid },
          },
        },
        plugins: {
          legend: {
            display: !!projection,
            position: "bottom",
            labels: { color: colors.text },
          },
          tooltip: {
            callbacks: {
              title: function (items) {
                return (
                  new Date(items[0].parsed.x).toLocaleString(undefined, {
                    timeZone: "UTC",
                  }) + " UTC"
                );
              },
              label: function (ctx) {
                return formatMoney(ctx.parsed.y);
              },
            },
          },
        },
      },
    });
  }

  // Re-render all charts with the current theme (called when dark mode toggles).
  window.TallyworthCharts = {
    refresh: function () {
      instances.forEach(function (inst) {
        if (inst.chart) {
          inst.chart.destroy();
        }
        inst.chart = renderChart(inst.canvas, inst.points, inst.projection);
      });
    },
  };
})();
