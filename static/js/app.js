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
      // data-copy sits on the component root, not on the clicked button.
      const text = this.$root.dataset.copy || "";
      const done = () => {
        this.copied = true;
        setTimeout(() => { this.copied = false; }, 1600);
      };
      if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(text).then(done, () => { if (legacyCopy(text)) done(); });
      } else if (legacyCopy(text)) {
        done(); // plain-HTTP pages have no Clipboard API
      }
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

// Fallback copy for pages without the Clipboard API (e.g. served over plain HTTP).
function legacyCopy(text) {
  const area = document.createElement("textarea");
  area.value = text;
  area.setAttribute("readonly", "");
  area.style.position = "fixed";
  area.style.opacity = "0";
  document.body.appendChild(area);
  area.select();
  let ok = false;
  try { ok = document.execCommand("copy"); } catch (e) { ok = false; }
  area.remove();
  return ok;
}

// Close an open language menu when clicking elsewhere.
document.addEventListener("click", (event) => {
  document.querySelectorAll("details.lang-menu[open]").forEach((el) => {
    if (!el.contains(event.target)) el.removeAttribute("open");
  });
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
