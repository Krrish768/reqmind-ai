// Documents tab: upload, list, analyze with live progress, download, delete.

import { api, downloadFile } from "./api.js";
import { $, $$, documentStatusTag, formatBytes, formatDate, html, mount, observeReveals, toast } from "./util.js";

const POLL_MS = 2000;
const ACCEPT = ".pdf,.docx,.txt,.md";
// Where each analysis step starts, in percent (same numbers as backend/app/agents/workflow.py and pipeline.py)
const STAGES = [
  { from: 1, label: "Reading" },
  { from: 5, label: "Finding requirements" },
  { from: 65, label: "Comparing" },
  { from: 75, label: "Conflicts" },
  { from: 85, label: "Saving" },
  { from: 90, label: "Chat search" },
  { from: 95, label: "Graph" },
];

function stagesHtml(progress, finished) {
  const current = STAGES.findLastIndex((stage) => progress >= stage.from);
  return html`<ol class="stages">${STAGES.map((stage, index) => {
    const state = finished || index < current ? "done" : index === current ? "now" : "";
    return html`<li class="${state}">${stage.label}</li>`;
  })}</ol>`;
}

function jobHtml(job) {
  if (!job) return "";
  const active = job.status === "queued" || job.status === "running";
  if (!active) {
    const kind = job.status === "done" ? "t-ok" : "t-conflict";
    return html`<div class="job-box"><p class="job-message"><span class="tag ${kind} plain">Last analysis</span> ${job.message}</p></div>`;
  }
  return html`<div class="job-box" data-job="${job.id}">
    <div class="progress-line"><span style="width:${job.progress}%"></span></div>
    ${stagesHtml(job.progress, false)}
    <p class="job-message" aria-live="polite">${job.message || "Waiting…"}</p></div>`;
}

function canAnalyze(document, job) {
  const busy = job && (job.status === "queued" || job.status === "running");
  return !busy && ["parsed", "analyzed", "analyzing"].includes(document.status);
}

function documentRow(document, job) {
  const problem = document.status === "failed" ? html`<p class="form-error">${document.error}</p>` : "";
  const label = document.status === "analyzed" ? "Analyze again" : "Find requirements";
  return html`
    <article class="card doc-row reveal" data-id="${document.id}">
      <div>
        <div class="doc-title"><strong>${document.filename}</strong> ${documentStatusTag(document.status)}</div>
        <p class="doc-meta">${formatBytes(document.size_bytes)} · uploaded ${formatDate(document.created_at)}</p>
        ${problem}
      </div>
      <div class="doc-actions">
        <button class="button primary small" data-action="analyze" ${canAnalyze(document, job) ? "" : html`disabled`}>${label}</button>
        <button class="button small" data-action="download">Download</button>
        <button class="button small danger" data-action="delete">Delete</button>
      </div>
      ${jobHtml(job)}
    </article>`;
}

// The newest job of each document.
function latestJobs(jobs) {
  const byDocument = {};
  for (const job of jobs) {
    if (!byDocument[job.document_id] || job.id > byDocument[job.document_id].id) byDocument[job.document_id] = job;
  }
  return byDocument;
}

function bodyHtml(documents, jobs) {
  const list = documents.length
    ? html`${documents.map((document) => documentRow(document, jobs[document.id]))}`
    : html`<div class="state"><h3>No documents yet</h3><p>Upload a requirements document (PDF, Word, TXT or Markdown, up to 10 MB).</p></div>`;
  return html`
    <label class="dropzone reveal" id="dropzone">
      <input type="file" id="file-input" accept="${ACCEPT}" multiple hidden>
      <strong>Drop a document here</strong>
      <span class="muted">or click to choose a PDF, DOCX, TXT or MD file</span>
    </label>
    <div class="doc-list">${list}</div>`;
}

async function uploadFiles(files, context, reload) {
  const dropzone = $("#dropzone");
  for (const file of files) {
    $("strong", dropzone).textContent = `Uploading ${file.name}…`;
    try {
      const uploaded = await api.upload(`${context.base}/documents`, file);
      const failed = uploaded.status === "failed";
      toast(failed ? `${file.name}: ${uploaded.error}` : `${file.name} is ready to analyze.`, failed ? "error" : "info");
    } catch (problem) {
      toast(`${file.name}: ${problem.message}`, "error");
    }
  }
  reload();
}

function wireUpload(container, context, reload) {
  const dropzone = $("#dropzone", container);
  const input = $("#file-input", container);
  input.addEventListener("change", () => input.files.length && uploadFiles([...input.files], context, reload));
  dropzone.addEventListener("dragover", (event) => { event.preventDefault(); dropzone.classList.add("over"); });
  dropzone.addEventListener("dragleave", () => dropzone.classList.remove("over"));
  dropzone.addEventListener("drop", (event) => {
    event.preventDefault();
    dropzone.classList.remove("over");
    uploadFiles([...event.dataTransfer.files], context, reload);
  });
}

async function runAction(action, document, context, reload) {
  const path = `${context.base}/documents/${document.id}`;
  if (action === "download") return downloadFile(`${path}/file`);
  if (action === "delete") {
    if (!window.confirm(`Delete ${document.filename}? Its requirements stay in the list.`)) return null;
    await api.del(path);
    toast(`${document.filename} was deleted.`);
  } else {
    await api.post(`${path}/analyze`);
  }
  return reload();
}

function wireActions(container, context, reload) {
  $$("[data-action]", container).forEach((button) => button.addEventListener("click", async () => {
    const id = Number(button.closest("[data-id]").dataset.id);
    const document = context.documents.find((item) => item.id === id);
    button.disabled = true;
    try {
      await runAction(button.dataset.action, document, context, reload);
    } catch (problem) {
      toast(problem.message, "error");
    } finally {
      button.disabled = false;
    }
  }));
}

// Poll running jobs; update their bars in place and reload when one ends.
function pollJobs(container, reload) {
  const timer = setInterval(async () => {
    const boxes = $$("[data-job]", container);
    if (!boxes.length) return;
    for (const box of boxes) {
      const job = await api.get(`/jobs/${box.dataset.job}`).catch(() => null);
      if (!job) continue;
      if (job.status === "done" || job.status === "failed") {
        toast(job.status === "done" ? job.message : `Analysis failed: ${job.message}`, job.status === "done" ? "info" : "error");
        reload();
        return;
      }
      $(".progress-line span", box).style.width = `${job.progress}%`;
      $(".stages", box).outerHTML = stagesHtml(job.progress, false).__raw;
      $(".job-message", box).textContent = job.message || "";
    }
  }, POLL_MS);
  return () => clearInterval(timer);
}

export async function renderDocuments(container, context, reload) {
  const jobs = latestJobs(await api.get(`${context.base}/jobs`).catch(() => []));
  mount(container, bodyHtml(context.documents, jobs));
  wireUpload(container, context, reload);
  wireActions(container, context, reload);
  observeReveals(container);
  return pollJobs(container, reload);
}
