// Talks to the FastAPI backend under /api. Keeps the login token in localStorage.

const API_BASE = "/api";
const TOKEN_KEY = "reqmind_token";
const EMAIL_KEY = "reqmind_email";

export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

function readStorage(key) {
  try { return localStorage.getItem(key); } catch { return null; }
}

function writeStorage(key, value) {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch { /* storage can be blocked; the user then logs in again on reload */ }
}

export const session = {
  get token() { return readStorage(TOKEN_KEY); },
  get email() { return readStorage(EMAIL_KEY); },
  save(token, email) { writeStorage(TOKEN_KEY, token); writeStorage(EMAIL_KEY, email); },
  clear() { writeStorage(TOKEN_KEY, null); writeStorage(EMAIL_KEY, null); },
};

// FastAPI sends {"detail": "..."} or a list of validation errors.
function messageFrom(body, status) {
  if (typeof body?.detail === "string") return body.detail;
  if (Array.isArray(body?.detail)) return body.detail.map((item) => item.msg).join(". ");
  if (status === 0) return "The server is not reachable. Is the backend running?";
  return `The server answered with an error (${status}).`;
}

async function send(method, path, { json, form, raw } = {}) {
  const headers = {};
  if (session.token) headers.Authorization = `Bearer ${session.token}`;
  let body;
  if (json !== undefined) { headers["Content-Type"] = "application/json"; body = JSON.stringify(json); }
  if (form) body = form;
  let response;
  try {
    response = await fetch(API_BASE + path, { method, headers, body });
  } catch {
    throw new ApiError(0, messageFrom(null, 0));
  }
  if (response.status === 401 && path !== "/auth/login") {
    session.clear();
    window.location.hash = "#login";
  }
  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    throw new ApiError(response.status, messageFrom(errorBody, response.status));
  }
  if (raw) return response;
  return response.status === 204 ? null : response.json();
}

export const api = {
  get: (path) => send("GET", path),
  post: (path, json) => send("POST", path, { json }),
  patch: (path, json) => send("PATCH", path, { json }),
  del: (path) => send("DELETE", path),
  upload: (path, file) => {
    const form = new FormData();
    form.append("file", file);
    return send("POST", path, { form });
  },
};

// Download a file from the API (the token must go in the header, so a plain link does not work).
export async function downloadFile(path) {
  const response = await send("GET", path, { raw: true });
  const header = response.headers.get("Content-Disposition") || "";
  const name = (header.match(/filename="([^"]+)"/) || [])[1] || "download";
  const url = URL.createObjectURL(await response.blob());
  const link = Object.assign(document.createElement("a"), { href: url, download: name });
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
