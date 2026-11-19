// Ask tab: questions about the project's documents, answered with their sources.

import { api } from "./api.js";
import { $, $$, html, mount, toast } from "./util.js";

const SUGGESTIONS = ["Which requirements are about security?", "What happens after failed logins?", "How do users pay?"];
const threads = new Map(); // project id -> [{ question, answer }], kept while the page is open

function methodTag(method) {
  return method === "llm"
    ? html`<span class="tag t-ok">Answer checked against the passages</span>`
    : html`<span class="tag t-document">Matching passages</span>`;
}

function sourcesHtml(sources) {
  if (!sources.length) return "";
  return html`<div class="sources">${sources.map((source) => html`
    <details><summary>${source.filename}, part ${source.chunk_index + 1}</summary><p class="passage" style="margin-top:.5rem">${source.text}</p></details>`)}</div>`;
}

function entryHtml(entry) {
  const answer = entry.answer
    ? html`<div class="bubble answer"><p>${entry.answer.answer}</p>${sourcesHtml(entry.answer.sources)}
        <div class="answer-meta">${methodTag(entry.answer.method)}</div></div>`
    : html`<div class="bubble answer" aria-busy="true"><div class="skeleton" style="height:1.2rem;width:60%"></div></div>`;
  return html`<div class="bubble question">${entry.question}</div>${answer}`;
}

function threadHtml(entries) {
  if (!entries.length) {
    return html`<div class="state"><h3>Ask about your documents</h3>
      <p>Answers use only the uploaded documents, and show the passages they come from.</p>
      <div class="suggestions" style="justify-content:center;margin-top:1rem">${SUGGESTIONS.map((text) =>
        html`<button class="button small" type="button" data-suggestion="${text}">${text}</button>`)}</div></div>`;
  }
  return html`${entries.map(entryHtml)}`;
}

export function renderChat(container, context) {
  const entries = threads.get(context.project.id) || [];
  threads.set(context.project.id, entries);
  mount(container, html`<div class="chat">
    <div class="thread" id="thread"></div>
    <form class="ask card" id="ask" style="padding:.75rem">
      <input name="question" required maxlength="1000" placeholder="Ask a question about this project" aria-label="Question">
      <button class="button primary" type="submit">Ask</button>
    </form></div>`);
  const thread = $("#thread", container);
  const form = $("#ask", container);
  const draw = () => {
    mount(thread, threadHtml(entries));
    $$("[data-suggestion]", thread).forEach((button) => button.addEventListener("click", () => ask(button.dataset.suggestion)));
  };
  const ask = async (question) => {
    const entry = { question, answer: null };
    entries.push(entry);
    draw();
    form.scrollIntoView({ block: "end", behavior: "smooth" });
    try {
      entry.answer = await api.post(`${context.base}/chat`, { question });
    } catch (problem) {
      entries.pop();
      toast(problem.message, "error");
    }
    draw();
  };
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const question = new FormData(form).get("question").trim();
    if (!question) return;
    form.reset();
    ask(question);
  });
  draw();
  return null;
}
