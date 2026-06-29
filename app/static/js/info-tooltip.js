// Click-to-toggle disclosure for the standard info tooltip (the "?" icon).
// Markup is produced by the info_tooltip() Jinja macro:
//   .info-tooltip            wrapper
//   .info-tooltip-trigger    button
//   .info-tooltip-panel      hidden disclosure panel
(function () {
  function closeAll(except) {
    var panels = document.querySelectorAll(".info-tooltip-panel");
    Array.prototype.forEach.call(panels, function (panel) {
      if (panel === except) return;
      panel.classList.add("hidden");
      var trigger = panel.parentElement.querySelector(".info-tooltip-trigger");
      if (trigger) trigger.setAttribute("aria-expanded", "false");
    });
  }

  document.addEventListener("click", function (e) {
    var trigger = e.target.closest(".info-tooltip-trigger");
    if (trigger) {
      e.preventDefault();
      var wrap = trigger.closest(".info-tooltip");
      var panel = wrap.querySelector(".info-tooltip-panel");
      var wasHidden = panel.classList.contains("hidden");
      closeAll(panel);
      if (wasHidden) {
        panel.classList.remove("hidden");
        trigger.setAttribute("aria-expanded", "true");
      } else {
        panel.classList.add("hidden");
        trigger.setAttribute("aria-expanded", "false");
      }
      return;
    }
    if (!e.target.closest(".info-tooltip-panel")) {
      closeAll(null);
    }
  });

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") closeAll(null);
  });
})();
