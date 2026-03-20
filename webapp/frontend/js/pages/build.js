/**
 * build.js — Build page.
 *
 * Split panel: left (model selection + options), right (log viewer / status).
 */

import * as api from "../api.js";
import { showToast } from "../components/toast.js";
import { LogViewer } from "../components/log-viewer.js";

const SPINNER_SVG = `<svg class="icon-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182m0-4.991v4.99"/></svg>`;
const PLAY_ICON = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" d="M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z"/><path stroke-linecap="round" stroke-linejoin="round" d="M15.91 11.672a.375.375 0 0 1 0 .656l-5.603 3.113a.375.375 0 0 1-.557-.328V8.887c0-.286.307-.466.557-.327l5.603 3.112Z"/></svg>`;
const CHECK_ICON = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z"/></svg>`;
const X_ICON = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" d="m9.75 9.75 4.5 4.5m0-4.5-4.5 4.5M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z"/></svg>`;
const CLOCK_ICON = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z"/></svg>`;
const COPY_ICON = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" d="M15.75 17.25v3.375c0 .621-.504 1.125-1.125 1.125h-9.75a1.125 1.125 0 0 1-1.125-1.125V7.875c0-.621.504-1.125 1.125-1.125H6.75a9.06 9.06 0 0 1 1.5.124m7.5 10.376h3.375c.621 0 1.125-.504 1.125-1.125V11.25c0-4.46-3.243-8.161-7.5-8.876a9.06 9.06 0 0 0-1.5-.124H9.375c-.621 0-1.125.504-1.125 1.125v3.5m7.5 10.375H9.375a1.125 1.125 0 0 1-1.125-1.125v-9.25m12 6.625v-1.875a3.375 3.375 0 0 0-3.375-3.375h-1.5a1.125 1.125 0 0 1-1.125-1.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H9.75"/></svg>`;
const DOWNLOAD_ICON = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 12 12 16.5m0 0L7.5 12m4.5 4.5V3"/></svg>`;

let _models = {};
let _firmwareVersion = "";
let _selectedKeys = new Set();
let _logViewer = null;
let _activeBuildId = null;
let _buildStartTime = null;

export async function render(container) {
  container.style.overflow = "hidden";
  container.style.padding = "0";
  container.innerHTML = await _buildShell();
  await _loadModels(container);
  await _checkActiveBuild(container);
}

async function _buildShell() {
  let cpuCount = 4;
  try {
    const settings = await api.fetchSettings();
    cpuCount = 4; // Default; backend uses os.cpu_count()
    _firmwareVersion = (await api.fetchConfig()).firmware_version || "2.12";
  } catch (_) {}

  return `
    <div class="build-page">
      <!-- Left panel -->
      <div class="build-left">
        <div class="build-section-header">Select Models to Build</div>
        <div class="build-toolbar">
          <button class="btn btn-secondary" id="select-all-enabled-btn" style="font-size:var(--text-sm)">Select All Enabled</button>
          <span class="text-secondary text-sm" id="selected-count">0 selected</span>
          <button class="btn" id="clear-selection-btn" style="background:none;border:none;color:var(--text-secondary);font-size:var(--text-sm);cursor:pointer;padding:0;" class="hidden">Clear Selection</button>
        </div>
        <div class="model-selection-list" id="model-select-list">
          <div class="empty-state">
            ${SPINNER_SVG}
            <span class="text-secondary text-sm">Loading models...</span>
          </div>
        </div>
        <div class="build-options-header">Build Options</div>
        <div class="build-options-fields">
          <div class="form-group">
            <label class="form-label secondary" for="opt-fw-ver">Firmware Version</label>
            <input type="text" class="form-input font-mono" id="opt-fw-ver" value="${_esc(_firmwareVersion)}" autocomplete="off" />
          </div>
          <div class="form-group">
            <label class="form-label secondary" for="opt-component">Component</label>
            <select class="form-select" id="opt-component">
              <option value="all">all</option>
              <option value="firmware">firmware</option>
              <option value="simulator">simulator</option>
            </select>
          </div>
          <label class="form-check">
            <input type="checkbox" id="opt-clean" />
            <span class="form-check-label">Force clean build (slower but avoids cache issues)</span>
          </label>
          <div class="form-group">
            <label class="form-label secondary" for="opt-jobs">Parallel Jobs</label>
            <input type="number" class="form-input" id="opt-jobs" value="${cpuCount}" min="1" max="32" step="1" />
          </div>
        </div>
        <div class="build-action-area">
          <button class="btn btn-success btn-lg btn-full" id="start-build-btn" disabled>Start Build</button>
          <div class="text-xs text-muted text-center mt-2" id="build-hint">Select at least one model to build</div>
        </div>
      </div>

      <!-- Right panel -->
      <div class="build-right" id="build-right">
        <div class="build-idle" id="build-idle">
          ${PLAY_ICON}
          <div class="build-idle-title">Ready to Build</div>
          <div class="build-idle-sub">Select models and options on the left, then click Start Build.</div>
        </div>
      </div>
    </div>`;
}

async function _loadModels(container) {
  try {
    const data = await api.fetchModels();
    _models = data.targets || {};
    _firmwareVersion = data.firmware_version || "";
    _renderModelList(container);
  } catch (err) {
    showToast("error", "Failed to load models", err.message);
  }
}

function _renderModelList(container) {
  const list = container.querySelector("#model-select-list");
  if (!list) return;

  const modelKeys = Object.keys(_models);
  if (!modelKeys.length) {
    list.innerHTML = `<div class="empty-state"><span class="text-secondary text-sm">No models configured. Add models first.</span></div>`;
    return;
  }

  list.innerHTML = modelKeys.map((key) => {
    const m = _models[key];
    const checked = _selectedKeys.has(key);
    const enabledBadge = m.enabled
      ? `<span class="status-dot enabled"></span><span class="text-xs text-green">Enabled</span>`
      : `<span class="status-dot disabled"></span><span class="text-xs text-muted">Disabled</span>`;
    return `
      <div class="model-select-row ${checked ? "checked" : ""}" data-key="${_esc(key)}">
        <input type="checkbox" ${checked ? "checked" : ""} aria-label="Select ${_esc(key)}" />
        <span class="font-mono text-sm text-primary">${_esc(key)}</span>
        <span class="pcb-badge">${_esc(m.pcb)}</span>
        <span style="flex:1"></span>
        <span class="flex items-center gap-2">${enabledBadge}</span>
      </div>`;
  }).join("");

  list.querySelectorAll(".model-select-row").forEach((row) => {
    row.addEventListener("click", (e) => {
      const key = row.dataset.key;
      const cb = row.querySelector("input[type=checkbox]");
      if (e.target === cb) return;
      cb.checked = !cb.checked;
      _toggleSelected(key, cb.checked, container);
    });
    row.querySelector("input[type=checkbox]").addEventListener("change", (e) => {
      _toggleSelected(row.dataset.key, e.target.checked, container);
    });
  });

  _updateSelectionUI(container);
}

function _toggleSelected(key, checked, container) {
  if (checked) _selectedKeys.add(key);
  else _selectedKeys.delete(key);

  // Update row class
  const row = container.querySelector(`.model-select-row[data-key="${CSS.escape(key)}"]`);
  if (row) {
    row.classList.toggle("checked", checked);
  }
  _updateSelectionUI(container);
}

function _updateSelectionUI(container) {
  const count = _selectedKeys.size;
  const countEl = container.querySelector("#selected-count");
  if (countEl) countEl.textContent = `${count} selected`;

  const clearBtn = container.querySelector("#clear-selection-btn");
  if (clearBtn) clearBtn.style.display = count > 0 ? "" : "none";

  const startBtn = container.querySelector("#start-build-btn");
  const hint = container.querySelector("#build-hint");
  if (startBtn) {
    const isRunning = _activeBuildId !== null;
    if (isRunning) {
      startBtn.disabled = false;
      startBtn.className = "btn btn-danger btn-lg btn-full";
      startBtn.textContent = "Abort Build";
      if (hint) hint.style.display = "none";
    } else {
      startBtn.disabled = count === 0;
      startBtn.className = "btn btn-success btn-lg btn-full";
      startBtn.textContent = "Start Build";
      if (hint) hint.style.display = count === 0 ? "" : "none";
    }
  }
}

async function _checkActiveBuild(container) {
  try {
    const activeBuild = await api.fetchActiveBuild();
    if (activeBuild) {
      _activeBuildId = activeBuild.build_id;
      _buildStartTime = activeBuild.timestamp;
      _showRunningPanel(container, activeBuild);
    }
  } catch (_) {}

  // Bind start/abort button
  const startBtn = container.querySelector("#start-build-btn");
  startBtn?.addEventListener("click", () => {
    if (_activeBuildId) {
      _abortBuild(container);
    } else {
      _startBuild(container);
    }
  });

  // Bind select all enabled
  container.querySelector("#select-all-enabled-btn")?.addEventListener("click", () => {
    Object.entries(_models).forEach(([key, m]) => {
      if (m.enabled) _selectedKeys.add(key);
    });
    _renderModelList(container);
    _updateSelectionUI(container);
  });

  // Bind clear selection
  container.querySelector("#clear-selection-btn")?.addEventListener("click", () => {
    _selectedKeys.clear();
    _renderModelList(container);
    _updateSelectionUI(container);
  });
}

async function _startBuild(container) {
  if (_selectedKeys.size === 0) {
    showToast("warning", "No models selected", "Select at least one model to build.");
    return;
  }

  const fwVer = container.querySelector("#opt-fw-ver").value.trim();
  const component = container.querySelector("#opt-component").value;
  const clean = container.querySelector("#opt-clean").checked;
  const jobs = parseInt(container.querySelector("#opt-jobs").value, 10) || 0;

  const startBtn = container.querySelector("#start-build-btn");
  startBtn.disabled = true;
  startBtn.innerHTML = `${SPINNER_SVG} Starting...`;

  try {
    const result = await api.startBuild({
      selected_models: Array.from(_selectedKeys),
      component,
      firmware_version: fwVer || null,
      clean,
      jobs,
    });
    _activeBuildId = result.build_id;
    _buildStartTime = result.timestamp;
    _showRunningPanel(container, result);
    _updateSelectionUI(container);
  } catch (err) {
    startBtn.disabled = _selectedKeys.size === 0;
    startBtn.className = "btn btn-success btn-lg btn-full";
    startBtn.textContent = "Start Build";
    showToast("error", "Build failed to start", err.message);
  }
}

async function _abortBuild(container) {
  if (!_activeBuildId) return;
  try {
    await api.abortBuild(_activeBuildId);
    showToast("info", "Abort requested", "The build is being terminated.");
  } catch (err) {
    showToast("error", "Abort failed", err.message);
  }
}

function _showRunningPanel(container, buildStatus) {
  const right = container.querySelector("#build-right");
  const models = buildStatus.selected_models || [];
  const ts = buildStatus.timestamp ? new Date(buildStatus.timestamp).toLocaleString() : "";

  right.innerHTML = `
    <div class="build-active-panel" id="build-active-panel">
      <div class="build-run-header">
        <div class="build-run-meta">
          <span class="build-id-label">${_esc(buildStatus.build_id)}</span>
          <span class="build-timestamp">Started ${_esc(ts)}</span>
        </div>
        <div class="build-running-badge">
          <div class="status-dot running"></div>
          <span>Building...</span>
        </div>
      </div>

      <div class="model-progress-list" id="model-progress-list">
        ${models.map((k, i) => _modelProgressItem(k, i === 0 ? "building" : "pending")).join("")}
      </div>

      <div class="progress-bar-container">
        <div class="progress-bar-fill" id="progress-bar" style="width:0%"></div>
      </div>

      <div class="log-viewer" id="log-viewer-area">
        <div class="log-viewer-header">
          <span class="log-viewer-title">Build Log</span>
          <div class="log-viewer-controls">
            <label class="form-check">
              <input type="checkbox" id="auto-scroll-cb" checked />
              <span class="form-check-label">Auto-scroll</span>
            </label>
            <button class="btn-icon" id="copy-log-btn" title="Copy log">${COPY_ICON}</button>
          </div>
        </div>
        <div class="log-body" id="log-body"></div>
      </div>
    </div>`;

  // Set up log viewer
  const logBody = right.querySelector("#log-body");
  const autoScrollCb = right.querySelector("#auto-scroll-cb");
  _logViewer = new LogViewer(logBody, autoScrollCb);

  // Copy button
  right.querySelector("#copy-log-btn")?.addEventListener("click", async () => {
    const ok = await _logViewer.copyToClipboard();
    showToast(ok ? "success" : "error", ok ? "Log copied" : "Copy failed");
  });

  _logViewer.start(buildStatus.build_id, (doneData) => {
    _onBuildComplete(container, doneData);
  });
}

function _modelProgressItem(key, state) {
  const icons = {
    pending: `<span style="color:var(--text-muted)">${CLOCK_ICON}</span>`,
    building: `<span style="color:var(--accent-orange)">${SPINNER_SVG}</span>`,
    success: `<span style="color:var(--accent-green)">${CHECK_ICON}</span>`,
    failed: `<span style="color:var(--accent-red)">${X_ICON}</span>`,
  };
  const badges = {
    pending: `<span class="badge badge-disabled">Pending</span>`,
    building: `<span class="badge badge-running">Building</span>`,
    success: `<span class="badge badge-success">Success</span>`,
    failed: `<span class="badge badge-failed">Failed</span>`,
  };
  return `
    <div class="model-progress-item" data-progress-key="${_esc(key)}">
      ${icons[state] || icons.pending}
      <span class="font-mono text-sm" style="flex:1">${_esc(key)}</span>
      ${badges[state] || badges.pending}
    </div>`;
}

async function _onBuildComplete(container, doneData) {
  _activeBuildId = null;
  const status = doneData.status;
  const exitCode = doneData.exit_code ?? 0;

  const right = container.querySelector("#build-right");
  const panel = right?.querySelector("#build-active-panel");
  if (!panel) return;

  // Update running badge
  const badge = panel.querySelector(".build-running-badge");
  if (badge) {
    badge.innerHTML = status === "success"
      ? `<span style="color:var(--accent-green)">${CHECK_ICON}</span><span style="color:var(--accent-green)">Complete</span>`
      : `<span style="color:var(--accent-red)">${X_ICON}</span><span style="color:var(--accent-red)">Failed</span>`;
  }

  // Show banner
  const progressList = panel.querySelector("#model-progress-list");
  const banner = document.createElement("div");

  if (status === "success") {
    const elapsed = _buildStartTime
      ? _formatDuration(Date.now() - new Date(_buildStartTime).getTime())
      : "";
    banner.className = "build-success-banner";
    banner.innerHTML = `
      <div class="banner-left" style="color:var(--accent-green)">${CHECK_ICON} Build completed successfully</div>
      <div class="banner-right">${elapsed ? `Completed in ${elapsed}` : ""}</div>`;
    progressList.insertAdjacentElement("afterend", banner);

    // Artifacts section
    try {
      const models = Array.from(_selectedKeys);
      let artifactHtml = `<div class="artifacts-section"><div class="artifacts-heading">Download Artifacts</div>`;
      for (const key of models) {
        const artifacts = await api.fetchArtifacts(key);
        artifactHtml += `<div class="artifact-row">
          <span class="font-mono text-sm text-primary" style="flex:1">${_esc(key)}</span>
          ${artifacts.files.length
            ? artifacts.files.map((f) =>
                `<a class="btn btn-secondary" href="${api.getArtifactDownloadUrl(key, f.filename)}" download="${_esc(key)}_${_esc(f.filename)}">${DOWNLOAD_ICON} ${_esc(f.filename)}</a>`
              ).join(" ")
            : `<span class="badge badge-running" style="color:var(--accent-yellow)">No output files found</span>`}
        </div>`;
      }
      artifactHtml += `</div>`;
      banner.insertAdjacentHTML("afterend", artifactHtml);
    } catch (_) {}
  } else {
    banner.className = "build-fail-banner";
    banner.innerHTML = `
      <div class="banner-left" style="color:var(--accent-red)">${X_ICON} Build failed</div>
      <div class="banner-right">Exit code: ${exitCode}</div>`;
    progressList.insertAdjacentElement("afterend", banner);
  }

  _updateSelectionUI(container);
}

function _formatDuration(ms) {
  const secs = Math.floor(ms / 1000);
  const m = Math.floor(secs / 60);
  const s = secs % 60;
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

function _esc(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
