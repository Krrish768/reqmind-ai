// Conflicts tab: each pair side by side with the reason.

import { openRequirement } from "./requirements.js";
import { $$, html, mount, observeReveals, typeTag } from "./util.js";

function sideHtml(item) {
  if (!item) return html`<div class="conflict-side"><p class="muted">This requirement was deleted.</p></div>`;
  return html`<div class="conflict-side" data-id="${item.id}" tabindex="0" role="button" aria-label="Open ${item.code}">
    <p class="mono small muted">${item.code} ${typeTag(item.type)}</p>
    <h3 style="font-size:1.05rem;margin:.35rem 0">${item.title}</h3>
    <p class="small">${item.description}</p></div>`;
}

function conflictHtml(conflict, byId) {
  return html`<article class="card conflict reveal">
    ${sideHtml(byId[conflict.requirement_a_id])}
    <span class="conflict-versus" aria-hidden="true">vs</span>
    ${sideHtml(byId[conflict.requirement_b_id])}
    <p class="conflict-reason"><strong>Why they clash:</strong> ${conflict.reason}</p></article>`;
}

export function renderConflicts(container, context, reload) {
  if (!context.conflicts.length) {
    const hint = context.requirements.length
      ? "None of the requirements contradict each other."
      : "Analyze a document first. Pairs that cannot both be true will show up here.";
    mount(container, html`<div class="state"><h3>No conflicts</h3><p>${hint}</p></div>`);
    return null;
  }
  const byId = Object.fromEntries(context.requirements.map((item) => [item.id, item]));
  mount(container, html`<p class="muted" style="margin-bottom:1rem">${context.conflicts.length} pair(s) that cannot both be true. Click a side to open it.</p>
    <div class="stack">${context.conflicts.map((conflict) => conflictHtml(conflict, byId))}</div>`);
  $$(".conflict-side[data-id]", container).forEach((side) => {
    const open = () => openRequirement(byId[Number(side.dataset.id)], context, reload);
    side.addEventListener("click", open);
    side.addEventListener("keydown", (event) => event.key === "Enter" && open());
  });
  observeReveals(container);
  return null;
}
