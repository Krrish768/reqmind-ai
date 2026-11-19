// Hash router: #login, #signup, #projects, #project/<id>/<tab>, #about.
// Each page has render(container, params) and may return a cleanup function.

import { session } from "./api.js";
import { renderLogin, renderSignup } from "./auth.js";
import { renderProjects } from "./projects.js";
import { renderProject } from "./project.js";
import { renderAbout } from "./about.js";
import { $, setField } from "./util.js";

const PUBLIC_PAGES = new Set(["login", "signup", "about"]);
let cleanup = null;
let lastHash = "";

function parseHash() {
  const parts = window.location.hash.replace(/^#\/?/, "").split("/").filter(Boolean);
  return { page: parts[0] || "projects", id: Number(parts[1]) || null, tab: parts[2] || "documents" };
}

function updateTopbar() {
  const loggedIn = Boolean(session.token);
  $("#logout").hidden = !loggedIn;
  $("#user-email").textContent = loggedIn ? session.email || "" : "";
}

function pageFor(route) {
  const pages = { login: renderLogin, signup: renderSignup, projects: renderProjects, project: renderProject, about: renderAbout };
  return pages[route.page] || renderProjects;
}

async function showRoute() {
  if (cleanup) cleanup();
  cleanup = null;
  const route = parseHash();
  const loggedIn = Boolean(session.token);
  if (!loggedIn && !PUBLIC_PAGES.has(route.page)) { window.location.hash = "#login"; return; }
  if (loggedIn && (route.page === "login" || route.page === "signup")) { window.location.hash = "#projects"; return; }
  if (route.page === "project" && !route.id) { window.location.hash = "#projects"; return; }

  // Toasts belong to the page they were shown on; a reload of the same page keeps them.
  if (window.location.hash !== lastHash) $("#toasts").replaceChildren();
  lastHash = window.location.hash;
  updateTopbar();
  setField(route.page === "project" ? route.tab : "default");
  const container = $("#app");
  window.scrollTo(0, 0);
  const result = await pageFor(route)(container, route);
  cleanup = typeof result === "function" ? result : null;
}

$("#logout").addEventListener("click", () => {
  session.clear();
  window.location.hash = "#login";
});

window.addEventListener("hashchange", showRoute);
showRoute();
