// The list of projects and the form to make a new one.

import { api } from "./api.js";
import { $, errorState, html, loadingState, mount, observeReveals, setCrumbs } from "./util.js";

function projectRow(project) {
  return html`
    <a class="card lift project-row reveal" href="#project/${project.id}/documents">
      <span class="project-initial" aria-hidden="true">${project.name.trim().charAt(0).toUpperCase()}</span>
      <span>
        <h3>${project.name}</h3>
        <span class="muted small">${project.description || "No description"}</span>
      </span>
      <span class="arrow" aria-hidden="true">→</span>
    </a>`;
}

function listHtml(projects) {
  if (!projects.length) {
    return html`<div class="state"><h3>No projects yet</h3><p>Make your first project above, then upload a requirements document into it.</p></div>`;
  }
  return html`${projects.map(projectRow)}`;
}

async function loadList(container) {
  const list = $(".project-list", container);
  mount(list, loadingState());
  try {
    const projects = await api.get("/projects");
    mount(list, listHtml(projects));
    observeReveals(list);
  } catch (problem) {
    mount(list, errorState(problem.message, "Try again"));
    $("[data-retry]", list)?.addEventListener("click", () => loadList(container));
  }
}

function wireCreate(container) {
  const form = $(".new-project", container);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const values = Object.fromEntries(new FormData(form));
    const error = $(".form-error", container);
    error.textContent = "";
    try {
      const project = await api.post("/projects", { name: values.name, description: values.description || null });
      window.location.hash = `#project/${project.id}/documents`;
    } catch (problem) {
      error.textContent = problem.message;
    }
  });
}

export function renderProjects(container) {
  setCrumbs([{ label: "Projects" }]);
  mount(container, html`
    <div class="page-head reveal">
      <div><h1>Projects</h1><p>One project per product or client. Everyone in your team sees the same projects.</p></div>
    </div>
    <form class="card new-project reveal">
      <label class="field">Name<input name="name" required maxlength="120" placeholder="Campus canteen app"></label>
      <label class="field">Description<input name="description" maxlength="300" placeholder="Optional"></label>
      <button class="button primary" type="submit">Create project</button>
    </form>
    <p class="form-error" role="alert"></p>
    <div class="project-list"></div>`);
  wireCreate(container);
  observeReveals(container);
  loadList(container);
}
