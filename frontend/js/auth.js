// Login and signup pages.

import { api, session } from "./api.js";
import { $, html, mount, observeReveals, setCrumbs } from "./util.js";

// The left side shows what the app does, with a sentence marked the way the analysis marks it.
function story() {
  return html`
    <section class="auth-story reveal">
      <h1>Read the spec once. <em class="accent">Let the list write itself.</em></h1>
      <p class="muted">Upload a requirements document. Every requirement comes back with the sentence it came from,
        and pairs that cannot both be true are shown side by side.</p>
      <p class="passage">The system <span class="marker" style="--marker: var(--functional-bg)">shall lock an account after 5 failed login attempts</span>.
        A student session <span class="marker" style="--marker: var(--conflict-bg)">shall expire after 15 minutes</span> of inactivity.
        The menu page should be <span class="vague-mark">user-friendly</span>.</p>
      <div class="auth-legend">
        <span class="tag t-functional">Requirement</span>
        <span class="tag t-conflict">Conflict</span>
        <span class="tag plain"><span class="vague-dot"></span> Vague word</span>
      </div>
    </section>`;
}

function formCard(title, fields, button, switchText) {
  return html`
    <section class="card reveal">
      <form class="auth-form" novalidate>
        <h2>${title}</h2>
        ${fields}
        <p class="form-error" role="alert"></p>
        <button class="button primary" type="submit">${button}</button>
        <p class="auth-switch">${switchText}</p>
      </form>
    </section>`;
}

const EMAIL_FIELD = html`<label class="field">Email<input name="email" type="email" autocomplete="email" required></label>`;

async function logIn(email, password) {
  const token = await api.post("/auth/login", { email, password });
  session.save(token.access_token, email);
  window.location.hash = "#projects";
}

function wireForm(container, onSubmit) {
  const form = $("form", container);
  const error = $(".form-error", form);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = $("button[type=submit]", form);
    error.textContent = "";
    button.disabled = true;
    try {
      await onSubmit(Object.fromEntries(new FormData(form)));
    } catch (problem) {
      error.textContent = problem.message;
    } finally {
      button.disabled = false;
    }
  });
}

export function renderLogin(container) {
  setCrumbs([{ label: "Log in" }]);
  const fields = html`${EMAIL_FIELD}
    <label class="field">Password<input name="password" type="password" autocomplete="current-password" required></label>`;
  mount(container, html`<div class="auth">${story()}${formCard("Log in", fields, "Log in",
    html`New here? <a href="#signup">Create an account</a>`)}</div>`);
  wireForm(container, (values) => logIn(values.email, values.password));
  observeReveals(container);
}

export function renderSignup(container) {
  setCrumbs([{ label: "Sign up" }]);
  const fields = html`${EMAIL_FIELD}
    <label class="field">Password (at least 6 characters)<input name="password" type="password" minlength="6" autocomplete="new-password" required></label>
    <label class="field">Team or company name<input name="company_name" required placeholder="People with the same name share projects"></label>`;
  mount(container, html`<div class="auth">${story()}${formCard("Create an account", fields, "Create account",
    html`Already have an account? <a href="#login">Log in</a>`)}</div>`);
  wireForm(container, async (values) => {
    await api.post("/auth/signup", values);
    await logIn(values.email, values.password);
  });
  observeReveals(container);
}
