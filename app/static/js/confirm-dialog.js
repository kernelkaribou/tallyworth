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
    titleEl.textContent = form.dataset.confirmTitle || "Are you sure?";
    messageEl.textContent =
      form.dataset.confirm || "This action cannot be undone.";
    acceptBtn.textContent = form.dataset.confirmLabel || "Confirm";
    acceptBtn.className =
      form.dataset.confirmTone === "default" ? toneDefault : toneDanger;
    modal.classList.remove("hidden");
    modal.classList.add("flex");
    acceptBtn.focus();
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

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && !modal.classList.contains("hidden")) close();
  });
})();
