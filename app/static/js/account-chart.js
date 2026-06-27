// Renders an account's value history as a line chart.
// Reads data points (epoch ms -> value in currency units) from an embedded
// JSON script tag and draws them with Chart.js. A linear time axis is used with
// manual date formatting so no Chart.js date adapter is required.
(function () {
  var dataEl = document.getElementById("account-history-data");
  var canvas = document.getElementById("account-history-chart");
  if (!dataEl || !canvas || typeof Chart === "undefined") {
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

  var symbol = canvas.dataset.symbol || "$";

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
          label: "Value",
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
})();
