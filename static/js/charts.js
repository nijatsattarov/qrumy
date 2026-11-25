// Renders Qrumy charts from JSON embedded with Django's json_script (CSP-safe).
// <canvas data-chart="bars" data-source="id-of-json-script" data-label="Scans">
(function () {
  const ACCENT = "#4F7CFF";
  const ACCENT_HOVER = "#3a64e6";
  const INK = "#172033";
  const MUTED = "#687386";
  const GRID = "#E3E8F0";

  function render(canvas) {
    const source = document.getElementById(canvas.dataset.source);
    if (!source || !window.Chart) return;
    const rows = JSON.parse(source.textContent);
    const label = canvas.dataset.label || "";
    const locale = document.documentElement.lang || "en";
    const fmtDay = new Intl.DateTimeFormat(locale, { day: "numeric", month: "short" });
    const fmtLong = new Intl.DateTimeFormat(locale, { weekday: "short", day: "numeric", month: "long", year: "numeric" });
    const dates = rows.map((r) => new Date(r.day + "T00:00:00"));
    new window.Chart(canvas, {
      type: "bar",
      data: {
        labels: dates.map((d) => fmtDay.format(d)),
        datasets: [{
          label,
          data: rows.map((r) => r.scans),
          backgroundColor: ACCENT,
          hoverBackgroundColor: ACCENT_HOVER,
          borderRadius: { topLeft: 4, topRight: 4 },
          borderSkipped: "bottom",
          maxBarThickness: 28,
          categoryPercentage: 0.8,
          barPercentage: 0.9,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: INK, padding: 10, displayColors: false, cornerRadius: 8,
            titleFont: { family: "Inter Variable, sans-serif", weight: "600" },
            bodyFont: { family: "Inter Variable, sans-serif" },
            callbacks: {
              title: (items) => fmtLong.format(dates[items[0].dataIndex]),
              label: (item) => `${label}: ${item.formattedValue}`,
            },
          },
        },
        scales: {
          x: {
            grid: { display: false },
            border: { color: GRID },
            ticks: { color: MUTED, maxRotation: 0, autoSkipPadding: 16, font: { size: 11 } },
          },
          y: {
            beginAtZero: true,
            grid: { color: GRID, drawTicks: false },
            border: { display: false },
            ticks: { color: MUTED, precision: 0, padding: 8, maxTicksLimit: 5, font: { size: 11 } },
          },
        },
      },
    });
  }

  function init(root) {
    root.querySelectorAll("canvas[data-chart]").forEach((c) => {
      if (!c.dataset.rendered) { c.dataset.rendered = "1"; render(c); }
    });
  }
  document.addEventListener("DOMContentLoaded", () => init(document));
  document.addEventListener("htmx:afterSettle", (e) => init(e.target));
})();
