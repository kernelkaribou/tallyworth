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
    renderChart(canvas, points);
  });

  function renderChart(canvas, points) {
    var symbol = canvas.dataset.symbol || "$";
    var label = canvas.dataset.label || "Value";

    function formatMoney(value) {
      return (
        symbol +
        Number(value).toLocaleString(undefined, {
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
        })
      );
    }

    new Chart(canvas, {
      type: "line",
      data: {
        datasets: [
          {
            label: label,
            data: points,
            borderColor: "#0f172a",
            backgroundColor: "rgba(15, 23, 42, 0.08)",
            borderWidth: 2,
            tension: 0.25,
            fill: true,
            pointRadius: 3,
            pointHoverRadius: 5,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        parsing: false,
        scales: {
          x: {
            type: "linear",
            ticks: {
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
            ticks: {
              callback: function (value) {
                return formatMoney(value);
              },
            },
          },
        },
        plugins: {
          legend: { display: false },
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
})();
