// Standardized confirmation dialog for destructive form submissions.
//
// Any <form> carrying a data-confirm attribute is intercepted on submit and a
// shared modal (rendered once in base.html as #confirm-dialog) is shown before
// the form is allowed through. Supported form attributes:
//   data-confirm        : the body message (required to opt in)
//   data-confirm-title  : heading text (default "Are you sure?")
//   data-confirm-label  : confirm-button text (default "Confirm")
//   data-confirm-tone   : "danger" (default) or "default" for the confirm button
//
// On confirm the form is resubmitted with a one-shot flag so it passes straight
// through. Cancel, backdrop click, and Escape all dismiss without submitting.
(function () {
  var modal = document.getElementById("confirm-dialog");
  if (!modal) return;

  var titleEl = modal.querySelector("[data-confirm-title]");
  var messageEl = modal.querySelector("[data-confirm-message]");
  var acceptBtn = modal.querySelector("[data-confirm-accept]");
  var cancelBtn = modal.querySelector("[data-confirm-cancel]");
  var toneDanger = modal.dataset.toneDanger || "";
  var toneDefault = modal.dataset.toneDefault || "";
  var pendingForm = null;
  var lastFocused = null;

  function open(form) {
    pendingForm = form;
    lastFocused = document.activeElement;
    var tone = form.dataset.confirmTone || "danger";
    titleEl.textContent = form.dataset.confirmTitle || "Are you sure?";
    messageEl.textContent =
      form.dataset.confirm || "This action cannot be undone.";
    acceptBtn.textContent = form.dataset.confirmLabel || "Confirm";
    acceptBtn.className = tone === "default" ? toneDefault : toneDanger;
    modal.classList.remove("hidden");
    modal.classList.add("flex");
    // For destructive (danger) actions focus Cancel first so an accidental
    // Enter/Space dismisses rather than confirms; default-tone actions focus
    // the primary button for quick confirmation.
    if (tone === "default") {
      acceptBtn.focus();
    } else {
      cancelBtn.focus();
    }
  }

  function close() {
    pendingForm = null;
    modal.classList.add("hidden");
    modal.classList.remove("flex");
    if (lastFocused && typeof lastFocused.focus === "function") {
      lastFocused.focus();
    }
    lastFocused = null;
  }

  document.addEventListener("submit", function (e) {
    var form = e.target;
    if (
      form.matches &&
      form.matches("form[data-confirm]") &&
      form.dataset.confirmed !== "true"
    ) {
      e.preventDefault();
      open(form);
    }
  });

  acceptBtn.addEventListener("click", function () {
    if (!pendingForm) return;
    var form = pendingForm;
    form.dataset.confirmed = "true";
    close();
    if (typeof form.requestSubmit === "function") {
      form.requestSubmit();
    } else {
      form.submit();
    }
  });

  cancelBtn.addEventListener("click", close);

  modal.addEventListener("click", function (e) {
    if (e.target === modal) close();
  });

  function focusable() {
    return Array.prototype.slice.call(
      modal.querySelectorAll(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
      )
    ).filter(function (el) {
      return !el.disabled && el.offsetParent !== null;
    });
  }

  document.addEventListener("keydown", function (e) {
    if (modal.classList.contains("hidden")) return;
    if (e.key === "Escape") {
      close();
      return;
    }
    // Trap Tab focus within the dialog so keyboard focus cannot reach the page
    // behind it. Derived from the dialog's actual focusable controls so it stays
    // correct if the dialog's contents change.
    if (e.key === "Tab") {
      var items = focusable();
      if (items.length === 0) return;
      var first = items[0];
      var last = items[items.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }
  });
})();
