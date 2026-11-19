// One project: header, export menu and the five tabs.

import { api, downloadFile } from "./api.js";
import { renderChat } from "./chat.js";
import { renderConflicts } from "./conflicts.js";
import { renderDocuments } from "./documents.js";
import { renderGraph } from "./graph.js";
import { renderRequirements } from "./requirements.js";
import { $, $$, errorState, html, loadingState, mount, observeReveals, setCrumbs, toast } from "./util.js";

const TABS = [
  { key: "documents", label: "Documents", render: renderDocuments },
  { key: "requirements", label: "Requirements", render: renderRequirements },
  { key: "conflicts", label: "Conflicts", render: renderConflicts },
  { key: "graph", label: "Graph", render: renderGraph },
  { key: "chat", label: "Ask", render: renderChat },
];

// Everything the tabs need about the project, loaded together.
async function loadContext(projectId) {
  const base = `/projects/${projectId}`;
  const [project, documents, requirements, conflicts] = await Promise.all([
    api.get(base), api.get(`${base}/documents`), api.get(`${base}/requirements`), api.get(`${base}/conflicts`),
  ]);
  return { project, documents, requirements, conflicts, base };
}

function tabCounts(context) {
  return { documents: context.documents.length, requirements: context.requirements.length, conflicts: context.conflicts.length };
}

function headerHtml(context, activeTab) {
  const counts = tabCounts(context);
  const tabs = TABS.map((tab) => html`
    <a href="#project/${context.project.id}/${tab.key}" ${activeTab === tab.key ? html`aria-current="page"` : ""}>
      ${tab.label}${counts[tab.key] !== undefined ? html`<span class="count">${counts[tab.key]}</span>` : ""}</a>`);
  return html`
    <div class="project-head reveal">
      <div><h1>${context.project.name}</h1><p class="muted">${context.project.description || ""}</p></div>
      <div class="actions menu">
        <button class="button" type="button" id="export-button" aria-haspopup="true" aria-expanded="false">Export</button>
        <div class="menu-list" id="export-menu" hidden>
          <button type="button" data-format="docx">Word (.docx)</button>
          <button type="button" data-format="pdf">PDF</button>
          <button type="button" data-format="md">Markdown</button>
        </div>
      </div>
    </div>
    <nav class="tabs" aria-label="Project sections">${tabs}</nav>
    <section id="tab-body"></section>`;
}

function wireExport(container, context) {
  const button = $("#export-button", container);
  const menu = $("#export-menu", container);
  const close = () => { menu.hidden = true; button.setAttribute("aria-expanded", "false"); };
  button.addEventListener("click", (event) => {
    event.stopPropagation();
    menu.hidden = !menu.hidden;
    button.setAttribute("aria-expanded", String(!menu.hidden));
    if (!menu.hidden) document.addEventListener("click", close, { once: true });
  });
  $$("[data-format]", menu).forEach((item) => item.addEventListener("click", async () => {
    close();
    try {
      await downloadFile(`${context.base}/export?format=${item.dataset.format}`);
    } catch (problem) {
      toast(problem.message, "error");
    }
  }));
}

export async function renderProject(container, route) {
  const tab = TABS.find((item) => item.key === route.tab) || TABS[0];
  mount(container, loadingState(4));
  let context;
  try {
    context = await loadContext(route.id);
  } catch (problem) {
    mount(container, errorState(problem.status === 404 ? "This project does not exist or is not yours." : problem.message));
    return null;
  }
  setCrumbs([{ label: "Projects", href: "#projects" }, { label: context.project.name, href: `#project/${route.id}/documents` }, { label: tab.label }]);
  mount(container, headerHtml(context, tab.key));
  wireExport(container, context);
  observeReveals(container);
  // Re-run the route, so the old tab is cleaned up (stops polling) before the new render.
  const reload = () => window.dispatchEvent(new HashChangeEvent("hashchange"));
  return tab.render($("#tab-body", container), context, reload);
}
