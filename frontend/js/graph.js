// Graph tab: documents, requirements and entities drawn with a small force layout in SVG.

import { api } from "./api.js";
import { $, errorState, html, loadingState, mount } from "./util.js";

const WIDTH = 1000;
const HEIGHT = 640;
const TICKS = 320;
const TOP_SPACE = 70; // keeps nodes below the legend
const RADIUS = { document: 15, requirement: 9, entity: 6 };
const NODE_COLOURS = {
  document: "--document", entity: "--entity",
  functional: "--functional", non_functional: "--nonfunctional", constraint: "--constraint",
};
const SVG_NS = "http://www.w3.org/2000/svg";

function colourOf(node) {
  const key = node.type === "requirement" ? node.data.type : node.type;
  return getComputedStyle(document.documentElement).getPropertyValue(NODE_COLOURS[key] || "--ink-faint").trim();
}

function shortLabel(node) {
  return node.type === "requirement" ? node.label.split(" ")[0] : node.label;
}

// Start on a circle so the layout is the same on every load.
function placeNodes(nodes) {
  nodes.forEach((node, index) => {
    const angle = (index / nodes.length) * Math.PI * 2;
    node.x = WIDTH / 2 + Math.cos(angle) * 220;
    node.y = HEIGHT / 2 + Math.sin(angle) * 180;
    node.vx = 0;
    node.vy = 0;
  });
}

function repel(nodes, strength) {
  for (let i = 0; i < nodes.length; i += 1) {
    for (let j = i + 1; j < nodes.length; j += 1) {
      const dx = nodes[j].x - nodes[i].x || 0.1;
      const dy = nodes[j].y - nodes[i].y || 0.1;
      const force = strength / Math.max(dx * dx + dy * dy, 40);
      nodes[i].vx -= dx * force; nodes[i].vy -= dy * force;
      nodes[j].vx += dx * force; nodes[j].vy += dy * force;
    }
  }
}

function pull(links, length) {
  for (const link of links) {
    const dx = link.target.x - link.source.x;
    const dy = link.target.y - link.source.y;
    const distance = Math.hypot(dx, dy) || 1;
    const force = ((distance - length) / distance) * 0.04;
    link.source.vx += dx * force; link.source.vy += dy * force;
    link.target.vx -= dx * force; link.target.vy -= dy * force;
  }
}

// One step of the simulation; cooling goes from 1 to 0.
function tick(nodes, links, cooling) {
  repel(nodes, 260);
  pull(links, 60);
  for (const node of nodes) {
    node.vx += (WIDTH / 2 - node.x) * 0.01;
    node.vy += (HEIGHT / 2 + TOP_SPACE / 2 - node.y) * 0.012;
    if (node.fixed) continue;
    node.x = Math.min(WIDTH - 20, Math.max(20, node.x + node.vx * cooling));
    node.y = Math.min(HEIGHT - 20, Math.max(TOP_SPACE, node.y + node.vy * cooling));
    node.vx *= 0.6; node.vy *= 0.6;
  }
}

function svgElement(name, attributes) {
  const element = document.createElementNS(SVG_NS, name);
  Object.entries(attributes).forEach(([key, value]) => element.setAttribute(key, value));
  return element;
}

function drawGraph(svg, nodes, links) {
  svg.replaceChildren();
  const conflictColour = getComputedStyle(document.documentElement).getPropertyValue("--conflict").trim();
  for (const link of links) {
    const conflict = link.type === "CONFLICTS_WITH";
    link.line = svgElement("line", { stroke: conflict ? conflictColour : "#cfc3ad", "stroke-width": conflict ? 2.2 : 1,
      "stroke-dasharray": conflict ? "5 4" : "" });
    svg.append(link.line);
  }
  for (const node of nodes) {
    node.group = svgElement("g", { class: "node" });
    node.group.append(svgElement("circle", { r: RADIUS[node.type], fill: colourOf(node), stroke: "#fffdf8", "stroke-width": 2 }));
    if (node.type !== "requirement" || nodes.length < 60) {
      const text = svgElement("text", { x: RADIUS[node.type] + 4, y: 4 });
      text.textContent = shortLabel(node);
      node.group.append(text);
    }
    svg.append(node.group);
  }
}

function updatePositions(nodes, links) {
  for (const link of links) {
    link.line.setAttribute("x1", link.source.x); link.line.setAttribute("y1", link.source.y);
    link.line.setAttribute("x2", link.target.x); link.line.setAttribute("y2", link.target.y);
  }
  for (const node of nodes) node.group.setAttribute("transform", `translate(${node.x},${node.y})`);
}

// Animate the first ticks, so the graph settles in front of the user.
function animate(nodes, links, state) {
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reduced) {
    for (let step = 0; step < TICKS; step += 1) tick(nodes, links, 1 - step / TICKS);
    updatePositions(nodes, links);
    return;
  }
  let step = 0;
  const frame = () => {
    if (state.stopped) return;
    for (let repeat = 0; repeat < 3 && step < TICKS; repeat += 1, step += 1) tick(nodes, links, 1 - step / TICKS);
    updatePositions(nodes, links);
    if (step < TICKS || state.dragging) state.frame = requestAnimationFrame(frame);
  };
  state.frame = requestAnimationFrame(frame);
}

function svgPoint(svg, event) {
  const point = svg.createSVGPoint();
  point.x = event.clientX; point.y = event.clientY;
  return point.matrixTransform(svg.getScreenCTM().inverse());
}

function wirePointer(svg, nodes, links, tip) {
  let held = null;
  nodes.forEach((node) => {
    node.group.addEventListener("pointerdown", (event) => { held = node; node.fixed = true; svg.setPointerCapture(event.pointerId); });
    node.group.addEventListener("pointerenter", () => { tip.hidden = false; tip.textContent = node.label; });
    node.group.addEventListener("pointerleave", () => { tip.hidden = true; });
  });
  svg.addEventListener("pointermove", (event) => {
    const box = svg.parentElement.getBoundingClientRect();
    tip.style.left = `${event.clientX - box.left + 12}px`;
    tip.style.top = `${event.clientY - box.top + 12}px`;
    if (!held) return;
    const point = svgPoint(svg, event);
    held.x = point.x; held.y = point.y;
    updatePositions(nodes, links);
  });
  svg.addEventListener("pointerup", () => { if (held) held.fixed = false; held = null; });
}

function legendHtml(graph) {
  const entries = [["t-document", "Document"], ["t-functional", "Functional"], ["t-non_functional", "Non-functional"],
    ["t-constraint", "Constraint"], ["t-entity", "Entity"], ["t-conflict", "Conflict link"]];
  return html`<div class="graph-legend">${entries.map(([kind, label]) => html`<span class="tag ${kind}">${label}</span>`)}</div>
    <div class="graph-info tag plain">${graph.nodes.length} nodes · from ${graph.source === "neo4j" ? "Neo4j" : "the database"}</div>`;
}

export async function renderGraph(container, context) {
  mount(container, loadingState(1));
  let graph;
  try {
    graph = await api.get(`${context.base}/graph`);
  } catch (problem) {
    mount(container, errorState(problem.message));
    return null;
  }
  if (!graph.nodes.some((node) => node.type === "requirement")) {
    mount(container, html`<div class="state"><h3>The graph is empty</h3><p>Analyze a document to see its requirements and the things they mention.</p></div>`);
    return null;
  }
  mount(container, html`<div class="card graph-card">${legendHtml(graph)}
    <svg viewBox="0 0 ${WIDTH} ${HEIGHT}" role="img" aria-label="Knowledge graph of the project"></svg>
    <div class="graph-tip" hidden></div></div>
    <p class="muted small" style="margin-top:.75rem">Drag a dot to move it. Hover to read its name. Dashed red lines join requirements that conflict.</p>`);
  const nodes = graph.nodes.map((node) => ({ ...node }));
  const byId = Object.fromEntries(nodes.map((node) => [node.id, node]));
  const links = graph.edges.filter((edge) => byId[edge.source] && byId[edge.target])
    .map((edge) => ({ source: byId[edge.source], target: byId[edge.target], type: edge.type }));
  const svg = $("svg", container);
  placeNodes(nodes);
  drawGraph(svg, nodes, links);
  wirePointer(svg, nodes, links, $(".graph-tip", container));
  const state = { stopped: false, frame: 0 };
  animate(nodes, links, state);
  return () => { state.stopped = true; cancelAnimationFrame(state.frame); };
}
