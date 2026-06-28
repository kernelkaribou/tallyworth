// Renders value-over-time line charts with Chart.js.
//
// Each chart is a <canvas> with:
//   data-chart-source   : id of a <script type="application/json"> holding an
//                         array of {x: epoch_ms, y: value} points
//   data-symbol         : currency symbol for axis/tooltip formatting (default $)
//   data-label          : dataset label (default "Value")
//   data-timezone       : IANA zone for date formatting (default UTC)
//   data-summary-target : optional id of an element to fill with a plain-language
//                         change summary for the currently selected timeframe
//
// A linear epoch-millisecond x-axis is used with manual date formatting so no
// Chart.js date adapter is required. Dates are rendered in the configured
// display timezone (data-timezone, default UTC) to match the tables.
(function () {
  if (typeof Chart === "undefined") {
    return;
  }

  var instances = [];
  var DAY_MS = 86400000;

  function isDark() {
    return document.documentElement.classList.contains("dark");
  }

  function theme() {
    if (isDark()) {
      return {
        line: "#56a476",
        fill: "rgba(86, 164, 118, 0.12)",
        text: "#d4d8d6",
        grid: "rgba(148, 184, 169, 0.15)",
        zero: "rgba(148, 184, 169, 0.55)",
      };
    }
    return {
      line: "#246241",
      fill: "rgba(36, 98, 65, 0.10)",
      text: "#47695b",
      grid: "rgba(148, 184, 169, 0.2)",
      zero: "rgba(100, 139, 123, 0.55)",
    };
  }

  // Year of a date in the given IANA zone, falling back to UTC. Used so the YTD
  // boundary lands on Jan 1 local time rather than UTC.
  function yearInZone(date, tz) {
    try {
      return Number(
        date.toLocaleDateString("en-US", { timeZone: tz || "UTC", year: "numeric" })
      );
    } catch (e) {
      return date.getUTCFullYear();
    }
  }

  // Format an epoch-ms value as a date in the given IANA zone (default UTC).
  function formatDate(ms, tz) {
    try {
      return new Date(ms).toLocaleDateString(undefined, { timeZone: tz || "UTC" });
    } catch (e) {
      return new Date(ms).toLocaleDateString(undefined, { timeZone: "UTC" });
    }
  }

  function formatMoney(symbol, value) {
    return (
      symbol +
      Number(value).toLocaleString(undefined, {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      })
    );
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
    instances.push({
      canvas: canvas,
      points: points,
      symbol: canvas.dataset.symbol || "$",
      label: canvas.dataset.label || "Value",
      tz: canvas.dataset.timezone || "UTC",
      summaryEl: canvas.dataset.summaryTarget
        ? document.getElementById(canvas.dataset.summaryTarget)
        : null,
      range: canvas.dataset.defaultRange || "lifetime",
      chart: renderChart(canvas, points),
    });
  });

  // Wire up any timeframe pill controls (data-timeframe-control on the canvas).
  instances.forEach(function (inst) {
    var ctrlId = inst.canvas.dataset.timeframeControl;
    if (!ctrlId) return;
    var ctrl = document.getElementById(ctrlId);
    if (!ctrl) return;
    var buttons = ctrl.querySelectorAll("[data-range]");
    Array.prototype.forEach.call(buttons, function (btn) {
      btn.addEventListener("click", function () {
        inst.range = btn.dataset.range;
        Array.prototype.forEach.call(buttons, function (other) {
          var active = other === btn;
          other.classList.toggle("is-active", active);
          other.setAttribute("aria-pressed", active ? "true" : "false");
        });
        applyRange(inst);
      });
    });
  });

  // Initial paint: set each chart's axis window and summary for its range.
  instances.forEach(applyRange);

  // Translate a timeframe key into the earliest x (epoch ms) to display, or
  // undefined for "lifetime" (show all history). Clamped to the first data
  // point so we never render empty space before the series starts.
  function rangeStart(range, points, tz) {
    var firstX = points[0].x;
    var now = Date.now();
    var minX;
    switch (range) {
      case "1m": minX = now - 30 * DAY_MS; break;
      case "3m": minX = now - 91 * DAY_MS; break;
      case "1y": minX = now - 365 * DAY_MS; break;
      case "ytd": minX = Date.UTC(yearInZone(new Date(), tz), 0, 1); break;
      case "3y": minX = now - 1095 * DAY_MS; break;
      case "5y": minX = now - 1825 * DAY_MS; break;
      default: return undefined;
    }
    return Math.max(minX, firstX);
  }

  // Apply the instance's selected timeframe to its chart by zooming the x-axis,
  // then refresh the change summary for the visible window.
  function applyRange(inst) {
    if (!inst.chart) return;
    var range = inst.range || "lifetime";
    var points = inst.points;
    var lastActual = points[points.length - 1].x;
    var minX = rangeStart(range, points, inst.tz);
    if (minX !== undefined && minX >= lastActual) minX = points[0].x;
    var startX = minX === undefined ? points[0].x : minX;

    inst.chart.options.scales.x.min = minX;
    inst.chart.options.scales.x.max = range === "lifetime" ? undefined : lastActual;
    inst.chart.update();

    updateSummary(inst, range, startX);
  }

  // Human-readable phrase for the period covered by a timeframe key.
  function periodLabel(range) {
    switch (range) {
      case "1m": return "the past month";
      case "3m": return "the past 3 months";
      case "1y": return "the past year";
      case "ytd": return "year to date";
      case "3y": return "the past 3 years";
      case "5y": return "the past 5 years";
      default: return "all time";
    }
  }

  // Fill the instance's summary element with the net change across the visible
  // window: first vs last actual point. Percentage is shown only when the
  // starting value is positive (a percent change off zero or a negative
  // liability impact would be meaningless).
  function updateSummary(inst, range, startX) {
    if (!inst.summaryEl) return;
    var visible = inst.points.filter(function (p) {
      return p.x >= startX;
    });
    if (visible.length < 2) {
      inst.summaryEl.textContent =
        "Not enough data to show the change over " + periodLabel(range) + ".";
      return;
    }
    var first = visible[0];
    var last = visible[visible.length - 1];
    var delta = last.y - first.y;
    var symbol = inst.symbol;

    var toneClass;
    if (delta > 0) {
      toneClass = "text-gain";
    } else if (delta < 0) {
      toneClass = "text-loss";
    } else {
      toneClass = "text-flat";
    }

    var changeText;
    if (delta === 0) {
      changeText = "unchanged";
    } else {
      changeText = (delta > 0 ? "up " : "down ") + formatMoney(symbol, Math.abs(delta));
      if (first.y > 0) {
        var pct = (delta / first.y) * 100;
        changeText +=
          " (" + (delta > 0 ? "+" : "-") + Math.abs(pct).toFixed(1) + "%)";
      }
    }

    var changeSpan = document.createElement("span");
    changeSpan.className = "font-medium " + toneClass;
    changeSpan.textContent = changeText;

    inst.summaryEl.textContent = inst.label + " ";
    inst.summaryEl.appendChild(changeSpan);
    inst.summaryEl.appendChild(
      document.createTextNode(
        " over " +
          periodLabel(range) +
          " \u00b7 " +
          formatMoney(symbol, first.y) +
          " \u2192 " +
          formatMoney(symbol, last.y)
      )
    );
  }

  function renderChart(canvas, points) {
    var symbol = canvas.dataset.symbol || "$";
    var label = canvas.dataset.label || "Value";
    var tz = canvas.dataset.timezone || "UTC";
    var colors = theme();
    var baseline = canvas.dataset.baseline === "zero";

    var yMin = null;
    var yMax = null;
    if (baseline) {
      points.forEach(function (p) {
        if (yMin === null || p.y < yMin) yMin = p.y;
        if (yMax === null || p.y > yMax) yMax = p.y;
      });
      // Always keep zero within view so the baseline is meaningful.
      yMin = Math.min(0, yMin === null ? 0 : yMin);
      yMax = Math.max(0, yMax === null ? 0 : yMax);
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
                return formatDate(value, tz);
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
                return formatMoney(symbol, value);
              },
            },
            grid: { color: colors.grid },
          },
        },
        plugins: {
          legend: {
            display: false,
          },
          tooltip: {
            callbacks: {
              title: function (items) {
                return formatDate(items[0].parsed.x, tz);
              },
              label: function (ctx) {
                return formatMoney(symbol, ctx.parsed.y);
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
        inst.chart = renderChart(inst.canvas, inst.points);
        applyRange(inst);
      });
    },
  };
})();
