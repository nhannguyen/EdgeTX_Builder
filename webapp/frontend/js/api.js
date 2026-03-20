/**
 * api.js — All fetch() calls to the backend REST API.
 *
 * Every function returns a Promise that resolves to the parsed JSON response body,
 * or throws an Error with a user-friendly .message property.
 */

const BASE = "/api";

/**
 * Internal fetch helper. Throws on non-2xx responses with the error detail
 * extracted from the JSON body (or a fallback message).
 *
 * @param {string} path
 * @param {RequestInit} [options]
 * @returns {Promise<Response>}
 */
async function _fetch(path, options = {}) {
  const resp = await fetch(BASE + path, options);
  if (resp.ok) return resp;

  // Try to extract error detail from JSON body
  let detail = `HTTP ${resp.status}`;
  try {
    const body = await resp.json();
    detail = body.detail || body.error || JSON.stringify(body);
  } catch (_) {
    // Body wasn't JSON; use status text
    detail = resp.statusText || detail;
  }
  const err = new Error(detail);
  err.status = resp.status;
  throw err;
}

async function _json(path, options = {}) {
  const resp = await _fetch(path, options);
  if (resp.status === 204) return null;
  return resp.json();
}

// ---------------------------------------------------------------------------
// Models
// ---------------------------------------------------------------------------

export async function fetchModels() {
  return _json("/models");
}

export async function fetchModel(key) {
  return _json(`/models/${encodeURIComponent(key)}`);
}

export async function createModel(data) {
  return _json("/models", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function updateModel(key, data) {
  return _json(`/models/${encodeURIComponent(key)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function deleteModel(key) {
  return _json(`/models/${encodeURIComponent(key)}`, { method: "DELETE" });
}

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

export async function fetchConfig() {
  return _json("/config");
}

export function getExportUrl() {
  return `${BASE}/config/export`;
}

export async function importConfig(file) {
  const form = new FormData();
  form.append("file", file);
  return _json("/config/import", {
    method: "POST",
    body: form,
  });
}

// ---------------------------------------------------------------------------
// Builds
// ---------------------------------------------------------------------------

export async function startBuild(data) {
  return _json("/builds", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function fetchActiveBuild() {
  const resp = await _fetch("/builds/active");
  if (resp.status === 204) return null;
  return resp.json();
}

export async function fetchBuild(buildId) {
  return _json(`/builds/${encodeURIComponent(buildId)}`);
}

export async function abortBuild(buildId) {
  return _json(`/builds/${encodeURIComponent(buildId)}`, { method: "DELETE" });
}

/**
 * Returns an EventSource for SSE log streaming.
 * The caller is responsible for calling .close() when done.
 *
 * @param {string} buildId
 * @param {number} [fromIndex=0]
 * @returns {EventSource}
 */
export function openLogStream(buildId, fromIndex = 0) {
  const url = `${BASE}/builds/${encodeURIComponent(buildId)}/logs`;
  const es = new EventSource(url);
  return es;
}

// ---------------------------------------------------------------------------
// Build history
// ---------------------------------------------------------------------------

export async function fetchHistory(params = {}) {
  const qs = new URLSearchParams();
  if (params.page) qs.set("page", params.page);
  if (params.page_size) qs.set("page_size", params.page_size);
  if (params.model) qs.set("model", params.model);
  if (params.status) qs.set("status", params.status);
  if (params.date_from) qs.set("date_from", params.date_from);
  if (params.date_to) qs.set("date_to", params.date_to);
  const queryStr = qs.toString();
  return _json(`/history${queryStr ? "?" + queryStr : ""}`);
}

export async function fetchHistoryEntry(buildId) {
  return _json(`/history/${encodeURIComponent(buildId)}`);
}

export async function deleteHistoryEntry(buildId) {
  return _json(`/history/${encodeURIComponent(buildId)}`, { method: "DELETE" });
}

export async function clearHistory() {
  return _json("/history", { method: "DELETE" });
}

export function getHistoryLogUrl(buildId) {
  return `${BASE}/history/${encodeURIComponent(buildId)}/log`;
}

// ---------------------------------------------------------------------------
// Artifacts
// ---------------------------------------------------------------------------

export async function fetchArtifacts(modelKey) {
  return _json(`/artifacts/${encodeURIComponent(modelKey)}`);
}

export function getArtifactDownloadUrl(modelKey, filename) {
  return `${BASE}/artifacts/${encodeURIComponent(modelKey)}/${encodeURIComponent(filename)}`;
}

// ---------------------------------------------------------------------------
// Settings
// ---------------------------------------------------------------------------

export async function fetchSettings() {
  return _json("/settings");
}

export async function updateSettings(data) {
  return _json("/settings", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

// ---------------------------------------------------------------------------
// Health
// ---------------------------------------------------------------------------

export async function fetchHealth() {
  return _json("/health");
}
