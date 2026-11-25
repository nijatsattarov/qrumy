// Qrumy front-end behaviours. Registered before Alpine (CSP build) starts.
// Alpine's CSP build cannot evaluate inline expressions, so every component lives here.
document.addEventListener("alpine:init", () => {
  const Alpine = window.Alpine;

  Alpine.data("dropdown", () => ({
    open: false,
    toggle() { this.open = !this.open; },
    close() { this.open = false; },
  }));

  Alpine.data("shell", () => ({
    sidebarOpen: false,
    get sidebarClass() { return this.sidebarOpen ? "translate-x-0" : "-translate-x-full"; },
    openSidebar() { this.sidebarOpen = true; },
    closeSidebar() { this.sidebarOpen = false; },
  }));

  Alpine.data("flash", () => ({
    visible: true,
    dismiss() { this.visible = false; },
    init() { setTimeout(() => { this.visible = false; }, 6000); },
  }));

  // Copy text from data-copy to the clipboard.
  Alpine.data("copy", () => ({
    copied: false,
    get notCopied() { return !this.copied; },
    copy() {
      const text = this.$el.dataset.copy || "";
      navigator.clipboard?.writeText(text).then(() => {
        this.copied = true;
        setTimeout(() => { this.copied = false; }, 1600);
      });
    },
  }));

  // Bulk selection on the QR list.
  Alpine.data("selection", () => ({
    count: 0,
    get hasSelection() { return this.count > 0; },
    get noSelection() { return this.count === 0; },
    update() { this.count = this.$root.querySelectorAll("input[name=ids]:checked").length; },
    toggleAll(event) {
      this.$root.querySelectorAll("input[name=ids]").forEach((el) => { el.checked = event.target.checked; });
      this.update();
    },
  }));

  Alpine.data("disclosure", () => ({
    open: false,
    toggle() { this.open = !this.open; },
  }));
});

// Confirm destructive actions: <form data-confirm="Are you sure?">
document.addEventListener("submit", (event) => {
  const form = event.target;
  if (form instanceof HTMLFormElement && form.dataset.confirm && !window.confirm(form.dataset.confirm)) {
    event.preventDefault();
    event.stopImmediatePropagation();
  }
}, true);

// Language switcher: submit on change without inline JS (CSP-safe).
document.addEventListener("change", (event) => {
  const el = event.target;
  if (el instanceof HTMLSelectElement && el.dataset.autosubmit !== undefined) el.form?.submit();
});
