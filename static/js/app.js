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

  // Pop-up offer managed in the admin. Remembers per visitor when it was closed.
  Alpine.data("promo", () => ({
    visible: false,
    init() {
      const { key, frequency } = this.$el.dataset;
      const delay = Math.max(0, parseInt(this.$el.dataset.delay || "0", 10)) * 1000;
      if (!this.allowed(key, frequency)) return;
      setTimeout(() => { this.visible = true; }, delay);
    },
    store(frequency) { return frequency === "session" ? window.sessionStorage : window.localStorage; },
    allowed(key, frequency) {
      try {
        const seen = this.store(frequency).getItem(key);
        if (!seen) return true;
        if (frequency === "daily") return Date.now() - parseInt(seen, 10) > 24 * 3600 * 1000;
        return false;
      } catch (e) { return true; }
    },
    remember() {
      // $root: the buttons calling this are inside the component.
      const { key, frequency } = this.$root.dataset;
      try { this.store(frequency).setItem(key, String(Date.now())); } catch (e) { /* private mode */ }
    },
    close() { this.visible = false; this.remember(); },
    accept() { this.remember(); },
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

// Multi-link editor: add/remove rows, platform icon, recognise pasted links.
(function () {
  const templates = () => document.getElementById("social-icon-templates");
  function setIcon(row, key) {
    const tpl = templates();
    const slot = row.querySelector("[data-link-icon]");
    const icon = tpl && tpl.content.querySelector(`[data-platform="${key}"]`);
    if (slot && icon) slot.replaceChildren(icon.firstElementChild.cloneNode(true));
  }
  function detect(value) {
    const tpl = templates();
    if (!tpl) return null;
    let host = "";
    try { host = new URL(value.includes("//") ? value : "https://" + value).hostname.toLowerCase(); } catch (e) { return null; }
    host = host.replace(/^(www|m)\./, "");
    for (const el of tpl.content.querySelectorAll("[data-platform]")) {
      const domains = (el.dataset.domains || "").split(",").filter(Boolean);
      if (domains.some((d) => host === d || host.endsWith("." + d))) return el.dataset.platform;
    }
    return null;
  }
  document.addEventListener("change", (event) => {
    const select = event.target.closest && event.target.closest("[data-link-platform]");
    if (select) setIcon(select.closest("[data-link-row]"), select.value);
  });
  document.addEventListener("input", (event) => {
    const input = event.target.closest && event.target.closest("[data-link-value]");
    if (!input) return;
    const row = input.closest("[data-link-row]");
    const select = row.querySelector("[data-link-platform]");
    const found = detect(input.value.trim());
    if (found && (select.value === "website" || select.value === "link")) {
      select.value = found;
      setIcon(row, found);
    }
  });
  document.addEventListener("click", (event) => {
    const add = event.target.closest && event.target.closest("[data-link-add]");
    if (add) {
      const next = add.parentElement.querySelector("[data-link-row][hidden]");
      if (next) { next.hidden = false; next.querySelector("[data-link-value]").focus(); }
      if (!add.parentElement.querySelector("[data-link-row][hidden]")) add.hidden = true;
      return;
    }
    const clear = event.target.closest && event.target.closest("[data-link-clear]");
    if (clear) {
      const row = clear.closest("[data-link-row]");
      row.querySelectorAll("input").forEach((el) => { el.value = ""; });
      row.querySelector("[data-link-platform]").value = "website";
      setIcon(row, "website");
      row.dispatchEvent(new Event("change", { bubbles: true }));
    }
  });
})();

// Share buttons (Qrumy Card): native share sheet on phones, copy link elsewhere.
document.addEventListener("click", (event) => {
  const btn = event.target.closest && event.target.closest("[data-share]");
  if (!btn) return;
  const url = btn.dataset.shareUrl || window.location.href;
  const title = btn.dataset.shareTitle || document.title;
  if (navigator.share) {
    navigator.share({ title, url }).catch(() => {});
    return;
  }
  const label = btn.querySelector("span");
  const show = () => { if (label) { const old = label.textContent; label.textContent = btn.dataset.copiedText || "Copied"; setTimeout(() => { label.textContent = old; }, 1600); } };
  if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(url).then(show, () => { if (legacyCopy(url)) show(); });
  else if (legacyCopy(url)) show();
});

// Card design step: preset colour dots fill the custom colour input (the one that is saved).
document.addEventListener("change", (event) => {
  const el = event.target;
  if (!(el instanceof HTMLInputElement)) return;
  const form = el.form;
  if (!form) return;
  const custom = form.querySelector("[data-custom-color]");
  if (el.matches("[data-preset-color]") && custom) custom.value = el.value;
  if (el.matches("[data-custom-color]")) form.querySelectorAll("[data-preset-color]").forEach((r) => { r.checked = r.value.toLowerCase() === el.value.toLowerCase(); });
});

// Digital Menu page: item sheet, search, active category tab, anonymous stats beacon.
(function () {
  const root = document.querySelector("[data-menu]");
  if (!root) return;
  const endpoint = root.dataset.menu;
  const preview = root.hasAttribute("data-menu-preview");
  const sent = new Set();
  function beacon(t, id) {
    const key = t + id;
    if (preview || sent.has(key)) return;
    sent.add(key);
    const body = JSON.stringify({ t, id: Number(id) });
    if (navigator.sendBeacon) navigator.sendBeacon(endpoint, new Blob([body], { type: "application/json" }));
    else fetch(endpoint, { method: "POST", body, headers: { "Content-Type": "application/json" }, keepalive: true });
  }
  root.addEventListener("click", (event) => {
    const open = event.target.closest("[data-item-open]");
    if (open) {
      const dialog = document.getElementById("item-" + open.dataset.itemOpen);
      if (dialog && dialog.showModal) dialog.showModal();
      beacon("item", open.dataset.itemOpen);
      return;
    }
    const tab = event.target.closest("[data-menu-tab]");
    if (tab) beacon("category", tab.dataset.menuTab);
    if (event.target.matches("dialog.menu-sheet")) event.target.close(); // tap outside
  });
  const search = root.querySelector("[data-menu-search]");
  if (search) search.addEventListener("input", () => {
    const q = search.value.trim().toLowerCase();
    let any = false;
    root.querySelectorAll("[data-menu-section]").forEach((section) => {
      let visible = 0;
      section.querySelectorAll("[data-menu-item]").forEach((li) => {
        const hit = !q || li.dataset.search.includes(q);
        li.hidden = !hit;
        if (hit) visible += 1;
      });
      section.hidden = visible === 0;
      if (visible) any = true;
    });
    const empty = root.querySelector("[data-menu-empty]");
    if (empty) empty.classList.toggle("hidden", any);
  });
  const tabs = [...root.querySelectorAll("[data-menu-tab]")];
  if ("IntersectionObserver" in window && tabs.length) {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        const id = entry.target.dataset.menuSection;
        tabs.forEach((t) => t.classList.toggle("is-active", t.dataset.menuTab === id));
        const active = tabs.find((t) => t.dataset.menuTab === id);
        if (active) active.scrollIntoView({ block: "nearest", inline: "center" });
      });
    }, { rootMargin: "-40% 0px -55% 0px" });
    root.querySelectorAll("[data-menu-section]").forEach((s) => observer.observe(s));
  }
})();

// Generic "add row" for hidden form rows: [data-reveal-group] > [data-reveal-row][hidden] + [data-reveal-add].
document.addEventListener("click", (event) => {
  const add = event.target.closest && event.target.closest("[data-reveal-add]");
  if (!add) return;
  const group = add.closest("[data-reveal-group]");
  const next = group && group.querySelector("[data-reveal-row][hidden]");
  if (next) { next.hidden = false; const input = next.querySelector("input"); if (input) input.focus(); }
  if (group && !group.querySelector("[data-reveal-row][hidden]")) add.hidden = true;
});

// Anonymous funnel counters (no cookies, no personal data): CTA clicks on public pages,
// and "QR generated" counted once per page view.
(function () {
  const root = document.querySelector("[data-track-endpoint]");
  const endpoint = root && root.dataset.trackEndpoint;
  function send(name) {
    if (!endpoint) return;
    const body = JSON.stringify({ e: name, p: root.dataset.trackPage || "" });
    if (navigator.sendBeacon) navigator.sendBeacon(endpoint, new Blob([body], { type: "application/json" }));
  }
  document.addEventListener("click", (event) => {
    const el = event.target.closest && event.target.closest("[data-track]");
    if (el) send(el.dataset.track);
  });
  document.addEventListener("htmx:afterSwap", (event) => {
    if (event.target && event.target.id === "gen-preview" && event.target.querySelector(".qr-frame svg")) {
      const flag = document.querySelector("[data-gen-counted]");
      if (flag) flag.value = "1";
    }
  });
})();
