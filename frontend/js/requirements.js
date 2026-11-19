// Requirements tab: counts, filters, the table, and a drawer to read, edit, add or delete one.

import { api } from "./api.js";
import {
  $, $$, STATUS_LABELS, TYPE_LABELS, countUp, html, mount, observeReveals, raw, toast, typeTag,
} from "./util.js";

const CATEGORIES = ["security", "performance", "usability", "data", "ui", "integration", "reliability", "other"];

function summaryHtml(requirements, conflicts) {
  const count = (type) => requirements.filter((item) => item.type === type).length;
  const tiles = [
    { key: "all", label: "Requirements", value: requirements.length },
    { key: "functional", label: "Functional", value: count("functional") },
    { key: "non_functional", label: "Non-functional", value: count("non_functional") },
    { key: "constraint", label: "Constraints", value: count("constraint") },
    { key: "vague", label: "Vague wording", value: requirements.filter((item) => item.is_ambiguous).length },
    { key: "conflict", label: "Conflicts", value: conflicts.length },
  ];
  return html`<div class="summary">${tiles.map((tile) => html`
    <div class="card s-${tile.key} reveal"><div class="number" data-count="${tile.value}">0</div><div class="label">${tile.label}</div></div>`)}</div>`;
}

function filtersHtml(documents) {
  const options = (labels) => Object.entries(labels).map(([value, label]) => html`<option value="${value}">${label}</option>`);
  return html`<form class="filters" id="filters">
    <label class="field grow">Search<input name="text" type="search" placeholder="Words in the title or text"></label>
    <label class="field">Type<select name="type"><option value="">All types</option>${options(TYPE_LABELS)}</select></label>
    <label class="field">Status<select name="status"><option value="">All</option>${options(STATUS_LABELS)}</select></label>
    <label class="field">Document<select name="document"><option value="">All documents</option>
      ${documents.map((item) => html`<option value="${item.id}">${item.filename}</option>`)}</select></label>
    <button class="button primary" type="button" id="add-requirement">Add requirement</button>
  </form>`;
}

function conflictIds(conflicts) {
  return new Set(conflicts.flatMap((item) => [item.requirement_a_id, item.requirement_b_id]));
}

function rowHtml(item, documentNames, inConflict) {
  const flags = [
    item.is_ambiguous ? html`<span class="vague-dot" title="Vague wording"></span>` : "",
    inConflict.has(item.id) ? html`<span class="tag t-conflict plain" title="Part of a conflict">conflict</span>` : "",
  ];
  const source = item.document_id ? documentNames[item.document_id] : "added by hand";
  return html`<tr data-id="${item.id}" tabindex="0">
    <td class="code">${item.code}</td>
    <td><div class="req-title">${item.title}</div><div class="req-source">${source || ""}${item.created_by === "ai" ? " · found by analysis" : ""}</div></td>
    <td>${typeTag(item.type)}</td>
    <td class="priority-${item.priority} hide-small">${item.priority}</td>
    <td class="hide-small">${STATUS_LABELS[item.status] || item.status}</td>
    <td>${flags}</td></tr>`;
}

function tableHtml(items, context) {
  if (!items.length) {
    const message = context.requirements.length ? "No requirement matches these filters." : "Analyze a document, or add a requirement by hand.";
    return html`<div class="state"><h3>Nothing here yet</h3><p>${message}</p></div>`;
  }
  const names = Object.fromEntries(context.documents.map((item) => [item.id, item.filename]));
  const inConflict = conflictIds(context.conflicts);
  return html`<div class="table-wrap reveal"><table>
    <thead><tr><th>Code</th><th>Requirement</th><th>Type</th><th class="hide-small">Priority</th><th class="hide-small">Status</th><th><span class="vague-dot"></span></th></tr></thead>
    <tbody>${items.map((item) => rowHtml(item, names, inConflict))}</tbody></table></div>`;
}

function applyFilters(requirements, values) {
  const words = values.text.trim().toLowerCase();
  return requirements.filter((item) => (!values.type || item.type === values.type)
    && (!values.status || item.status === values.status)
    && (!values.document || String(item.document_id) === values.document)
    && (!words || `${item.code} ${item.title} ${item.description}`.toLowerCase().includes(words)));
}

// ---------- drawer ----------

// The sentence of the passage that shares the most words with the requirement, marked.
function markClosestSentence(passage, description) {
  const words = new Set(description.toLowerCase().match(/[a-z0-9]{3,}/g) || []);
  const sentences = passage.split(/(?<=[.!?])\s+|\n/);
  let best = "";
  let bestScore = 0;
  for (const sentence of sentences) {
    const score = (sentence.toLowerCase().match(/[a-z0-9]{3,}/g) || []).filter((word) => words.has(word)).length;
    if (score > bestScore) { best = sentence; bestScore = score; }
  }
  const safe = html`${passage}`.__raw;
  if (!best.trim()) return raw(safe);
  const target = html`${best}`.__raw;
  return raw(safe.replace(target, `<span class="marker">${target}</span>`));
}

async function sourceHtml(item, context) {
  if (!item.document_id || !item.source_chunk_id) return "";
  try {
    const chunks = await api.get(`${context.base}/documents/${item.document_id}/chunks`);
    const chunk = chunks.find((entry) => entry.id === item.source_chunk_id);
    if (!chunk) return "";
    const page = chunk.page ? `, page ${chunk.page}` : "";
    return html`<h3 class="small muted" style="margin-top:1.5rem">Source passage${page} (closest sentence marked)</h3>
      <p class="passage">${markClosestSentence(chunk.text, item.description)}</p>`;
  } catch {
    return html`<p class="muted small">The source passage could not be loaded.</p>`;
  }
}

function formHtml(item) {
  const select = (name, labels, current) => html`<select name="${name}">${Object.entries(labels).map(([value, label]) =>
    html`<option value="${value}" ${value === current ? html`selected` : ""}>${label}</option>`)}</select>`;
  const categories = Object.fromEntries(CATEGORIES.map((name) => [name, name]));
  return html`<form class="stack" id="requirement-form">
    <label class="field">Title<input name="title" required value="${item.title || ""}"></label>
    <label class="field">Requirement<textarea name="description" required>${item.description || ""}</textarea></label>
    <div class="form-row">
      <label class="field">Type${select("type", TYPE_LABELS, item.type || "functional")}</label>
      <label class="field">Priority${select("priority", { high: "High", medium: "Medium", low: "Low" }, item.priority || "medium")}</label>
      <label class="field">Status${select("status", STATUS_LABELS, item.status || "draft")}</label>
      <label class="field">Category${select("category", categories, item.category || "other")}</label>
    </div>
    <label class="field">Entities (comma separated)<input name="entities" value="${(item.entities || []).join(", ")}"></label>
    <p class="form-error" role="alert"></p>
    <div style="display:flex;gap:.5rem;flex-wrap:wrap">
      <button class="button primary" type="submit">${item.id ? "Save changes" : "Add requirement"}</button>
      ${item.id ? html`<button class="button danger" type="button" id="delete-requirement">Delete</button>` : ""}
    </div></form>`;
}

function drawerHeadHtml(item) {
  if (!item.id) return html`<div><h2>New requirement</h2><p class="muted small">Added by hand, status draft.</p></div>`;
  const note = item.ambiguity_note ? html`<p class="small" style="margin-top:.5rem"><span class="vague-mark">Vague</span>: ${item.ambiguity_note}</p>` : "";
  return html`<div><p class="mono muted small">${item.code}</p><h2>${item.title}</h2>
    <p style="margin-top:.5rem">${typeTag(item.type)} <span class="tag plain">${item.created_by === "ai" ? "found by analysis" : "added by hand"}</span></p>${note}</div>`;
}

function readForm(form) {
  const values = Object.fromEntries(new FormData(form));
  values.entities = values.entities.split(",").map((word) => word.trim().toLowerCase()).filter(Boolean);
  return values;
}

function closeDrawer() {
  const open = [$(".drawer"), $(".drawer-backdrop")].filter(Boolean);
  open.forEach((element) => element.classList.remove("open"));
  setTimeout(() => open.forEach((element) => element.remove()), 260);
}

async function saveForm(form, item, context, reload) {
  const values = readForm(form);
  if (item.id) await api.patch(`${context.base}/requirements/${item.id}`, values);
  else await api.post(`${context.base}/requirements`, values);
  toast(item.id ? `${item.code} saved.` : "Requirement added.");
  closeDrawer();
  reload();
}

function wireDrawer(drawer, item, context, reload) {
  const form = $("#requirement-form", drawer);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    try { await saveForm(form, item, context, reload); } catch (problem) { $(".form-error", form).textContent = problem.message; }
  });
  $("#delete-requirement", drawer)?.addEventListener("click", async () => {
    if (!window.confirm(`Delete ${item.code}? Its conflicts are deleted too.`)) return;
    try {
      await api.del(`${context.base}/requirements/${item.id}`);
      toast(`${item.code} deleted.`);
      closeDrawer();
      reload();
    } catch (problem) { toast(problem.message, "error"); }
  });
  $("[data-close]", drawer).addEventListener("click", closeDrawer);
  $(".drawer-backdrop").addEventListener("click", closeDrawer);
  document.addEventListener("keydown", function onKey(event) {
    if (event.key === "Escape") { closeDrawer(); document.removeEventListener("keydown", onKey); }
  });
}

export async function openRequirement(item, context, reload) {
  closeDrawer();
  const backdrop = Object.assign(document.createElement("div"), { className: "drawer-backdrop" });
  const drawer = Object.assign(document.createElement("aside"), { className: "drawer" });
  drawer.setAttribute("aria-label", item.code || "New requirement");
  mount(drawer, html`<div class="drawer-head">${drawerHeadHtml(item)}<button class="button quiet" data-close aria-label="Close">✕</button></div>
    ${formHtml(item)}<div id="source"></div>`);
  document.body.append(backdrop, drawer);
  requestAnimationFrame(() => { backdrop.classList.add("open"); drawer.classList.add("open"); });
  wireDrawer(drawer, item, context, reload);
  $("input[name=title]", drawer).focus({ preventScroll: true });
  mount($("#source", drawer), html`${await sourceHtml(item, context)}`);
}

// ---------- tab ----------

function wireTable(container, items, context, reload) {
  $$("tbody tr", container).forEach((row) => {
    const open = () => openRequirement(items.find((item) => item.id === Number(row.dataset.id)), context, reload);
    row.addEventListener("click", open);
    row.addEventListener("keydown", (event) => event.key === "Enter" && open());
  });
}

export function renderRequirements(container, context, reload) {
  mount(container, html`${summaryHtml(context.requirements, context.conflicts)}${filtersHtml(context.documents)}<div id="table"></div>`);
  const form = $("#filters", container);
  const draw = () => {
    const items = applyFilters(context.requirements, Object.fromEntries(new FormData(form)));
    mount($("#table", container), tableHtml(items, context));
    wireTable(container, items, context, reload);
    observeReveals(container);
  };
  form.addEventListener("input", draw);
  form.addEventListener("submit", (event) => event.preventDefault());
  $("#add-requirement", container).addEventListener("click", () => openRequirement({}, context, reload));
  draw();
  countUp(container);
  return () => closeDrawer();
}
