/**
 * history.js — Build History page.
 */

import * as api from "../api.js";
import { showToast } from "../components/toast.js";
import { showConfirm } from "../components/confirm.js";

const LOGS_ICON = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z"/></svg>`;
const DOWNLOAD_ICON = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 12 12 16.5m0 0L7.5 12m4.5 4.5V3"/></svg>`;
const TRASH_ICON = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0"/></svg>`;
const CLOCK_ICON = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z"/></svg>`;

let _page = 1;
const _pageSize = 20;
let _filterStatus = "";
let _filterModel = "";
let _filterFrom = "";
let _filterTo = "";
let _total = 0;

export async function render(container) {
  container.innerHTML = _shell();
  _bindFilters(container);
  await _loadHistory(container);
}

function _shell() {
  return `
    <div class="page-header">
      <h1 class="page-title">Build History</h1>
      <div class="history-filters">
        <select class="form-select" id="hist-status-filter" style="height:32px;width:160px">
          <option value="">All Statuses</option>
          <option value="success">Success</option>
          <option value="failed">Failed</option>
          <option value="aborted">Aborted</option>
        </select>
        <input type="date" id="hist-from" title="From date" aria-label="From date" style="height:32px" />
        <input type="date" id="hist-to" title="To date" aria-label="To date" style="height:32px" />
        <input type="text" class="form-input" id="hist-model-filter" placeholder="Filter by model..." style="height:32px;width:180px" />
        <button class="btn btn-danger-outline" id="clear-history-btn">${TRASH_ICON} Clear History</button>
      </div>
    </div>

    <div id="history-error" class="hidden"></div>

    <div class="data-table-wrapper">
      <table class="data-table" aria-label="Build history">
        <thead>
          <tr>
            <th class="col-status">Status</th>
            <th class="col-build-id">Build ID</th>
            <th class="col-models">Models</th>
            <th class="col-fw-ver">Firmware</th>
            <th class="col-started">Started</th>
            <th class="col-duration">Duration</th>
            <th class="col-options">Options</th>
            <th class="col-hist-actions">Actions</th>
          </tr>
        </thead>
        <tbody id="history-tbody">
          ${_skeletonRows(5)}
        </tbody>
      </table>
    </div>

    <div id="history-pagination" class="flex items-center justify-between mt-4 hidden">
      <span class="text-sm text-secondary" id="pagination-info"></span>
      <div class="flex gap-2">
        <button class="btn btn-secondary" id="prev-page-btn" disabled>Previous</button>
        <button class="btn btn-secondary" id="next-page-btn" disabled>Next</button>
      </div>
    </div>`;
}

function _skeletonRows(count) {
  return Array.from({ length: count }, () => `
    <tr class="skeleton-row">
      <td><div class="skeleton-cell" style="width:70px;height:22px;border-radius:4px"></div></td>
      <td><div class="skeleton-cell" style="width:100px"></div></td>
      <td><div class="skeleton-cell" style="width:80%"></div></td>
      <td><div class="skeleton-cell" style="width:50px"></div></td>
      <td><div class="skeleton-cell" style="width:110px"></div></td>
      <td><div class="skeleton-cell" style="width:60px"></div></td>
      <td><div class="skeleton-cell" style="width:80px"></div></td>
      <td></td>
    </tr>`
  ).join("");
}

function _bindFilters(container) {
  const debounce = (fn, delay) => {
    let t;
    return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), delay); };
  };

  container.querySelector("#hist-status-filter").addEventListener("change", (e) => {
    _filterStatus = e.target.value;
    _page = 1;
    _loadHistory(container);
  });

  container.querySelector("#hist-model-filter").addEventListener("input",
    debounce((e) => {
      _filterModel = e.target.value.trim();
      _page = 1;
      _loadHistory(container);
    }, 400)
  );

  container.querySelector("#hist-from").addEventListener("change", (e) => {
    _filterFrom = e.target.value;
    _page = 1;
    _loadHistory(container);
  });

  container.querySelector("#hist-to").addEventListener("change", (e) => {
    _filterTo = e.target.value;
    _page = 1;
    _loadHistory(container);
  });

  container.querySelector("#clear-history-btn").addEventListener("click", async () => {
    const confirmed = await showConfirm({
      title: "Clear Build History?",
      body: "This will permanently delete all build history and log files. This action cannot be undone.",
      confirmText: "Clear History",
      confirmClass: "btn-danger",
    });
    if (!confirmed) return;
    try {
      await api.clearHistory();
      _page = 1;
      _loadHistory(container);
      showToast("success", "History cleared");
    } catch (err) {
      showToast("error", "Failed to clear history", err.message);
    }
  });
}

async function _loadHistory(container) {
  container.querySelector("#history-tbody").innerHTML = _skeletonRows(5);
  container.querySelector("#history-pagination").classList.add("hidden");

  try {
    const data = await api.fetchHistory({
      page: _page,
      page_size: _pageSize,
      status: _filterStatus || undefined,
      model: _filterModel || undefined,
      date_from: _filterFrom || undefined,
      date_to: _filterTo || undefined,
    });

    _total = data.total;
    _renderTable(container, data.items);
    _renderPagination(container, data);
  } catch (err) {
    _showError(container, `Failed to load history: ${err.message}`);
  }
}

function _renderTable(container, items) {
  const tbody = container.querySelector("#history-tbody");
  if (!items.length) {
    tbody.innerHTML = `
      <tr><td colspan="8">
        <div class="empty-state">
          ${CLOCK_ICON}
          <div class="empty-state-title">${_filterStatus || _filterModel ? "No builds match your filters." : "No build history yet"}</div>
          <div class="empty-state-sub">${_filterStatus || _filterModel ? "" : "Builds you run will appear here."}</div>
          ${_filterStatus || _filterModel ? `<button class="btn btn-secondary" id="clear-filters-btn">Clear filters</button>` : ""}
        </div>
      </td></tr>`;
    tbody.querySelector("#clear-filters-btn")?.addEventListener("click", () => {
      _filterStatus = "";
      _filterModel = "";
      _filterFrom = "";
      _filterTo = "";
      container.querySelector("#hist-status-filter").value = "";
      container.querySelector("#hist-model-filter").value = "";
      container.querySelector("#hist-from").value = "";
      container.querySelector("#hist-to").value = "";
      _loadHistory(container);
    });
    return;
  }

  tbody.innerHTML = items.map((entry) => _historyRow(entry)).join("");

  tbody.querySelectorAll("[data-view-log]").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      _openLogModal(btn.dataset.viewLog);
    });
  });

  tbody.querySelectorAll("[data-history-row]").forEach((row) => {
    row.addEventListener("click", (e) => {
      if (e.target.closest(".actions-cell")) return;
      _openLogModal(row.dataset.historyRow);
    });
  });
}

function _historyRow(entry) {
  const statusBadge = _statusBadge(entry.status);
  const shortId = entry.build_id.substring(0, 8);
  const models = (entry.models || []);
  const modelsHtml = models.slice(0, 3).map((k) => `<span class="flag-chip">${_esc(k)}</span>`).join(" ");
  const moreHtml = models.length > 3 ? `<span class="text-muted text-xs">+${models.length - 3} more</span>` : "";
  const started = entry.timestamp ? new Date(entry.timestamp).toLocaleString() : "—";
  const duration = entry.duration_ms ? _formatDuration(entry.duration_ms) : "—";
  const options = [
    entry.clean ? `<span class="flag-chip">Clean</span>` : "",
    `<span class="flag-chip">Jobs: ${entry.jobs}</span>`,
  ].filter(Boolean).join(" ");

  return `
    <tr data-history-row="${_esc(entry.build_id)}" style="cursor:pointer">
      <td>${statusBadge}</td>
      <td class="td-mono text-xs">${_esc(shortId)}...</td>
      <td>${modelsHtml} ${moreHtml}</td>
      <td class="td-mono text-xs">${_esc(entry.firmware_version || "—")}</td>
      <td title="${_esc(entry.timestamp)}">${_esc(started)}</td>
      <td>${_esc(duration)}</td>
      <td>${options}</td>
      <td>
        <div class="actions-cell">
          <button class="btn-icon" data-view-log="${_esc(entry.build_id)}" title="View logs" aria-label="View logs for ${_esc(shortId)}">${LOGS_ICON}</button>
        </div>
      </td>
    </tr>`;
}

function _statusBadge(status) {
  switch (status) {
    case "success": return `<span class="badge badge-success"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z"/></svg> Success</span>`;
    case "failed":  return `<span class="badge badge-failed"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" d="m9.75 9.75 4.5 4.5m0-4.5-4.5 4.5M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z"/></svg> Failed</span>`;
    case "aborted": return `<span class="badge badge-aborted"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" d="M18.364 18.364A9 9 0 0 0 5.636 5.636m12.728 12.728A9 9 0 0 1 5.636 5.636m12.728 12.728L5.636 5.636"/></svg> Aborted</span>`;
    case "running": return `<span class="badge badge-running">Running</span>`;
    default: return `<span class="badge">${_esc(status)}</span>`;
  }
}

function _renderPagination(container, data) {
  if (data.total <= _pageSize) return;

  const pag = container.querySelector("#history-pagination");
  pag.classList.remove("hidden");

  const info = container.querySelector("#pagination-info");
  const start = (_page - 1) * _pageSize + 1;
  const end = Math.min(_page * _pageSize, data.total);
  info.textContent = `Showing ${start}–${end} of ${data.total}`;

  const prevBtn = container.querySelector("#prev-page-btn");
  const nextBtn = container.querySelector("#next-page-btn");
  prevBtn.disabled = _page <= 1;
  nextBtn.disabled = end >= data.total;

  prevBtn.onclick = () => { _page--; _loadHistory(container); };
  nextBtn.onclick = () => { _page++; _loadHistory(container); };
}

async function _openLogModal(buildId) {
  // Show modal immediately, load log async
  const backdrop = document.createElement("div");
  backdrop.className = "modal-backdrop";
  backdrop.setAttribute("role", "dialog");
  backdrop.setAttribute("aria-modal", "true");

  backdrop.innerHTML = `
    <div class="modal modal-lg">
      <div class="modal-header">
        <div>
          <h2 class="modal-title">Build Log &mdash; <span class="font-mono text-sm">${_esc(buildId.substring(0, 8))}...</span></h2>
        </div>
        <button class="modal-close" id="log-modal-close" aria-label="Close">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18 18 6M6 6l12 12"/></svg>
        </button>
      </div>
      <div class="log-modal-body">
        <div class="log-meta-grid" id="log-meta-grid">
          <div class="skeleton-cell" style="height:40px;border-radius:4px"></div>
          <div class="skeleton-cell" style="height:40px;border-radius:4px"></div>
        </div>
        <div class="log-viewer-header">
          <span class="log-viewer-title">Log Output</span>
          <a class="btn btn-secondary" id="download-log-btn" href="${api.getHistoryLogUrl(buildId)}" download="build_${_esc(buildId)}.log">
            ${DOWNLOAD_ICON} Download Log
          </a>
        </div>
        <div class="log-body" id="modal-log-body" style="flex:1;margin-top:var(--space-2)">
          <span class="text-secondary">Loading...</span>
        </div>
      </div>
    </div>`;

  const close = () => document.body.removeChild(backdrop);
  backdrop.querySelector("#log-modal-close").addEventListener("click", close);
  backdrop.addEventListener("click", (e) => { if (e.target === backdrop) close(); });
  document.addEventListener("keydown", function esc(e) {
    if (e.key === "Escape") { document.removeEventListener("keydown", esc); close(); }
  });

  document.body.appendChild(backdrop);

  // Load history entry
  try {
    const entry = await api.fetchHistoryEntry(buildId);
    const metaGrid = backdrop.querySelector("#log-meta-grid");
    metaGrid.innerHTML = `
      <div class="log-meta-item"><div class="meta-label">Start Time</div><div class="meta-value">${_esc(new Date(entry.timestamp).toLocaleString())}</div></div>
      <div class="log-meta-item"><div class="meta-label">End Time</div><div class="meta-value">${_esc(entry.end_time ? new Date(entry.end_time).toLocaleString() : "—")}</div></div>
      <div class="log-meta-item"><div class="meta-label">Models</div><div class="meta-value font-mono text-sm">${_esc((entry.models || []).join(", "))}</div></div>
      <div class="log-meta-item"><div class="meta-label">Duration</div><div class="meta-value">${_esc(entry.duration_ms ? _formatDuration(entry.duration_ms) : "—")}</div></div>
      <div class="log-meta-item"><div class="meta-label">Firmware Version</div><div class="meta-value font-mono text-sm">${_esc(entry.firmware_version || "—")}</div></div>
      <div class="log-meta-item"><div class="meta-label">Status</div><div class="meta-value">${_statusBadge(entry.status)}</div></div>
      <div class="log-meta-item"><div class="meta-label">Options</div><div class="meta-value">${entry.clean ? "Clean build" : "Incremental"} · Jobs: ${entry.jobs} · ${entry.component}</div></div>`;

    // Load log text
    const logBody = backdrop.querySelector("#modal-log-body");
    try {
      const resp = await fetch(api.getHistoryLogUrl(buildId));
      if (resp.ok) {
        const text = await resp.text();
        logBody.innerHTML = "";
        const lines = text.split("\n");
        for (const line of lines) {
          const span = document.createElement("span");
          span.className = "log-line";
          span.textContent = line;
          logBody.appendChild(span);
        }
        logBody.scrollTop = logBody.scrollHeight;
      } else {
        logBody.innerHTML = `<span class="text-muted">Log file not available.</span>`;
      }
    } catch (_) {
      logBody.innerHTML = `<span class="text-muted">Log file not available.</span>`;
    }
  } catch (err) {
    backdrop.querySelector("#log-meta-grid").innerHTML =
      `<div class="alert-error">${_esc(err.message)}</div>`;
  }
}

function _formatDuration(ms) {
  const secs = Math.floor(ms / 1000);
  const m = Math.floor(secs / 60);
  const s = secs % 60;
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

function _showError(container, msg) {
  const el = container.querySelector("#history-error");
  if (!el) return;
  el.className = "alert-error";
  el.textContent = msg;
}

function _esc(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
