// Makes any element with [data-row-href] behave like a link for mouse users,
// so a whole table row is clickable. A real <a> inside the row remains the
// accessible/keyboard target; this only adds the convenience click for the
// rest of the row. Clicks on actual interactive elements (links, buttons,
// inputs) are left alone, and an active text selection never triggers a nav.
(function () {
  document.addEventListener("click", function (e) {
    var row = e.target.closest("[data-row-href]");
    if (!row) return;
    // Let real interactive elements handle their own clicks.
    if (e.target.closest("a, button, input, label, select, textarea")) return;
    // Don't navigate if the user is selecting text.
    var selection = window.getSelection();
    if (selection && selection.toString().length > 0) return;
    window.location = row.getAttribute("data-row-href");
  });
})();
