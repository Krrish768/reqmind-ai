// How it works: the steps of the analysis, the models, and what the AI does not decide.

import { html, mount, observeReveals, setCrumbs } from "./util.js";

const STEPS = [
  ["Upload", "The file is stored, its text is read page by page and cut into short passages."],
  ["Find requirements", "Each passage goes to a local language model. A requirement is kept only if its sentence is really in the passage; otherwise the model gets one more try, and after that it is dropped."],
  ["Priority and vague words", "Simple text rules, not the model, decide priority (must and shall are high, should is medium, may is low) and mark vague words such as fast or user-friendly."],
  ["Conflicts", "Pairs that are close in meaning, or that give different numbers for the same thing, are checked. A reason is kept only if every number in it comes from the two requirements."],
  ["Graph and search", "Requirements and the things they mention go into the graph, and the passages go into the search index used by Ask."],
];

const MODELS = [
  ["qwen3:8b", "Finds requirements, judges conflicts, writes answers", "Apache-2.0"],
  ["nomic-embed-text", "Turns text into vectors for search and similarity", "Apache-2.0"],
];

export function renderAbout(container) {
  setCrumbs([{ label: "How it works" }]);
  mount(container, html`
    <div class="page-head reveal"><div><h1>How it works</h1>
      <p>Everything runs on your own machine. No document leaves it.</p></div></div>
    <div class="steps">${STEPS.map(([title, text]) => html`<div class="card reveal"><div><h3>${title}</h3><p class="muted" style="margin-top:.35rem">${text}</p></div></div>`)}</div>
    <h2 class="reveal" style="margin:2.5rem 0 1rem">Models</h2>
    <div class="table-wrap reveal"><table><thead><tr><th>Model</th><th>Used for</th><th>Licence</th></tr></thead>
      <tbody>${MODELS.map(([name, use, licence]) => html`<tr><td class="code">${name}</td><td>${use}</td><td>${licence}</td></tr>`)}</tbody></table></div>
    <h2 class="reveal" style="margin:2.5rem 0 1rem">When the model is off</h2>
    <p class="card reveal">If the language model is not running, requirements are found with the text rules (every sentence with must, shall, should, will, may or could),
      conflicts are found only from different numbers, and Ask shows the passages that match best instead of a written answer.</p>`);
  observeReveals(container);
}
