// Small helpers shared by every page: safe HTML, formatting, toasts, motion.

const ESCAPES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };

export function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ESCAPES[char]);
}

// Marks a string as already-safe HTML so html`` does not escape it again.
export function raw(text) {
  return { __raw: text };
}

function render(value) {
  if (Array.isArray(value)) return value.map(render).join("");
  if (value && value.__raw !== undefined) return value.__raw;
  return escapeHtml(value);
}

// Tagged template: html`<p>${userText}</p>` escapes every value.
export function html(strings, ...values) {
  let out = strings[0];
  values.forEach((value, index) => { out += render(value) + strings[index + 1]; });
  return raw(out);
}

export function mount(container, content) {
  container.innerHTML = content.__raw;
}

export const $ = (selector, root = document) => root.querySelector(selector);
export const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

export const TYPE_LABELS = { functional: "Functional", non_functional: "Non-functional", constraint: "Constraint" };
export const STATUS_LABELS = { draft: "Draft", approved: "Approved", rejected: "Rejected" };

export function typeTag(type) {
  return html`<span class="tag t-${type}">${TYPE_LABELS[type] || type}</span>`;
}

export function documentStatusTag(status) {
  const kinds = { uploaded: "t-document", parsed: "t-entity", analyzing: "t-non_functional", analyzed: "t-ok", failed: "t-conflict" };
  const words = { uploaded: "Uploaded", parsed: "Ready to analyze", analyzing: "Analyzing", analyzed: "Analyzed", failed: "Failed" };
  return html`<span class="tag ${kinds[status] || ""}">${words[status] || status}</span>`;
}

export function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function formatDate(iso) {
  if (!iso) return "";
  return new Date(iso).toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

export function toast(message, kind = "info") {
  const area = $("#toasts");
  const item = document.createElement("div");
  item.className = `toast ${kind === "error" ? "error" : ""}`;
  item.textContent = message;
  area.append(item);
  setTimeout(() => item.remove(), 4500);
}

export function errorState(message, retryLabel = "") {
  return html`<div class="state error" role="alert"><h3>Something went wrong</h3><p>${message}</p>
    ${retryLabel ? html`<p style="margin-top:1rem"><button class="button" data-retry>${retryLabel}</button></p>` : ""}</div>`;
}

export function loadingState(rows = 3) {
  return raw(`<div aria-busy="true" aria-label="Loading">${'<div class="skeleton"></div>'.repeat(rows)}</div>`);
}

const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

// Fade elements in when they scroll into view, and out again when they leave.
let observer = null;
export function observeReveals(root) {
  if (!("IntersectionObserver" in window) || reducedMotion.matches) {
    $$(".reveal", root).forEach((element) => element.classList.add("is-visible"));
    return;
  }
  observer ??= new IntersectionObserver((entries) => {
    entries.forEach((entry) => entry.target.classList.toggle("is-visible", entry.isIntersecting));
  }, { threshold: 0.08 });
  $$(".reveal", root).forEach((element) => observer.observe(element));
}

// Numbers with data-count go up from 0 once.
export function countUp(root) {
  $$("[data-count]", root).forEach((element) => {
    const target = Number(element.dataset.count);
    if (reducedMotion.matches || target === 0) { element.textContent = target; return; }
    const started = performance.now();
    const step = (now) => {
      const share = Math.min(1, (now - started) / 700);
      element.textContent = Math.round(target * (1 - (1 - share) ** 3));
      if (share < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  });
}

// The soft background fields take the colour of the current section.
const FIELDS = {
  documents: ["--document-bg", "--entity-bg"],
  requirements: ["--functional-bg", "--nonfunctional-bg"],
  conflicts: ["--conflict-bg", "--document-bg"],
  graph: ["--entity-bg", "--constraint-bg"],
  chat: ["--functional-bg", "--entity-bg"],
  default: ["--document-bg", "--functional-bg"],
};
export function setField(section) {
  const [a, b] = FIELDS[section] || FIELDS.default;
  const styles = getComputedStyle(document.documentElement);
  document.body.style.setProperty("--field-a", styles.getPropertyValue(a).trim());
  document.body.style.setProperty("--field-b", styles.getPropertyValue(b).trim());
}

// Breadcrumb in the top bar: [{ label, href }], the last item is the current page.
export function setCrumbs(items) {
  const parts = items.map((item, index) => (index < items.length - 1 && item.href
    ? html`<a href="${item.href}">${item.label}</a>`
    : html`<span aria-current="page">${item.label}</span>`));
  $("#crumbs").innerHTML = parts.map((part) => part.__raw).join(' <span aria-hidden="true">/</span> ');
}
