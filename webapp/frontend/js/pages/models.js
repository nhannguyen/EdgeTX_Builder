/**
 * models.js — Radio Models page.
 *
 * Renders the models table with search/filter, inline toggle,
 * and Add/Edit/Delete modals.
 */

import * as api from "../api.js";
import { showToast } from "../components/toast.js";
import { showConfirm } from "../components/confirm.js";

// Icons
const EDIT_ICON = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L10.582 16.07a4.5 4.5 0 0 1-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 0 1 1.13-1.897l8.932-8.931Zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0 1 15.75 21H5.25A2.25 2.25 0 0 1 3 18.75V8.25A2.25 2.25 0 0 1 5.25 6H10"/></svg>`;
const DELETE_ICON = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0"/></svg>`;
const DOWNLOAD_ICON = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 12 12 16.5m0 0L7.5 12m4.5 4.5V3"/></svg>`;
const UPLOAD_ICON = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5m-13.5-9L12 3m0 0 4.5 4.5M12 3v13.5"/></svg>`;
const SEARCH_ICON = `<svg class="search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607Z"/></svg>`;
const BOX_ICON = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="m21 7.5-9-5.25L3 7.5m18 0-9 5.25m9-5.25v9l-9 5.25M3 7.5l9 5.25M3 7.5v9l9 5.25m0-9v9"/></svg>`;

let _allModels = {};
let _firmwareVersion = "";
let _filter = "all"; // all | enabled | disabled
let _search = "";
let _checkedKeys = new Set();

export async function render(container) {
  container.innerHTML = _buildShell();
  _bindStaticEvents(container);
  await _loadModels(container);
}

function _buildShell() {
  return `
    <div class="page-header">
      <h1 class="page-title">Radio Models</h1>
      <div class="flex items-center gap-3">
        <div class="search-input-wrapper">
          ${SEARCH_ICON}
          <input type="text" class="search-input" id="models-search" placeholder="Search models..." aria-label="Search models" />
        </div>
        <button class="btn btn-success" id="add-model-btn">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15"/></svg>
          Add Model
        </button>
      </div>
    </div>

    <div class="filter-bar">
      <div class="filter-chips">
        <button class="filter-chip active" data-filter="all" id="filter-all">All (<span id="count-all">0</span>)</button>
        <button class="filter-chip" data-filter="enabled" id="filter-enabled">Enabled (<span id="count-enabled">0</span>)</button>
        <button class="filter-chip" data-filter="disabled" id="filter-disabled">Disabled (<span id="count-disabled">0</span>)</button>
      </div>
      <div class="flex gap-2">
        <a class="btn btn-secondary" id="export-config-btn" href="${api.getExportUrl()}" download="targets.json">
          ${DOWNLOAD_ICON} Export Config
        </a>
        <button class="btn btn-secondary" id="import-config-btn">
          ${UPLOAD_ICON} Import Config
        </button>
        <input type="file" id="import-file-input" accept=".json,application/json" class="hidden" />
      </div>
    </div>

    <div id="models-error" class="hidden"></div>

    <div class="data-table-wrapper" id="models-table-wrapper">
      <table class="data-table" id="models-table" aria-label="Radio models">
        <thead>
          <tr>
            <th class="col-checkbox"><input type="checkbox" id="select-all-cb" aria-label="Select all models" /></th>
            <th class="col-key">Model Key</th>
            <th class="col-pcb">PCB Type</th>
            <th class="col-pcbrev">PCB Revision</th>
            <th class="col-enabled">Enabled</th>
            <th class="col-flags">Extra Flags</th>
            <th class="col-actions">Actions</th>
          </tr>
        </thead>
        <tbody id="models-tbody">
          ${_skeletonRows(8)}
        </tbody>
      </table>
    </div>
  `;
}

function _skeletonRows(count) {
  return Array.from({ length: count }, () => `
    <tr class="skeleton-row">
      <td><div class="skeleton-cell" style="width:16px;height:16px;border-radius:3px"></div></td>
      <td><div class="skeleton-cell" style="width:80%"></div></td>
      <td><div class="skeleton-cell" style="width:60%"></div></td>
      <td><div class="skeleton-cell" style="width:50%"></div></td>
      <td><div class="skeleton-cell" style="width:36px;height:20px;border-radius:10px"></div></td>
      <td><div class="skeleton-cell" style="width:70%"></div></td>
      <td></td>
    </tr>
  `).join("");
}

function _bindStaticEvents(container) {
  // Search
  container.querySelector("#models-search").addEventListener("input", (e) => {
    _search = e.target.value.toLowerCase();
    _renderTable(container);
  });

  // Filter chips
  container.querySelectorAll(".filter-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      _filter = chip.dataset.filter;
      container.querySelectorAll(".filter-chip").forEach((c) => c.classList.remove("active"));
      chip.classList.add("active");
      _renderTable(container);
    });
  });

  // Select all
  container.querySelector("#select-all-cb").addEventListener("change", (e) => {
    const visible = _visibleModels();
    if (e.target.checked) {
      visible.forEach((m) => _checkedKeys.add(m.key));
    } else {
      visible.forEach((m) => _checkedKeys.delete(m.key));
    }
    _renderTable(container);
  });

  // Add model
  container.querySelector("#add-model-btn").addEventListener("click", () => {
    _openModelModal(container, null);
  });

  // Import config
  container.querySelector("#import-config-btn").addEventListener("click", () => {
    container.querySelector("#import-file-input").click();
  });

  container.querySelector("#import-file-input").addEventListener("change", async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    e.target.value = ""; // reset

    // Preview before importing
    await _handleImport(container, file);
  });
}

async function _loadModels(container) {
  try {
    const data = await api.fetchModels();
    _allModels = data.targets || {};
    _firmwareVersion = data.firmware_version || "";
    // Update sidebar firmware version
    const versionEl = document.getElementById("sidebar-fw-version");
    if (versionEl) versionEl.textContent = _firmwareVersion || "—";
    _renderTable(container);
  } catch (err) {
    _showError(container, `Failed to load models. ${err.message} <button class="btn btn-secondary" onclick="location.reload()">Retry</button>`);
  }
}

function _visibleModels() {
  return Object.values(_allModels).filter((m) => {
    if (_filter === "enabled" && !m.enabled) return false;
    if (_filter === "disabled" && m.enabled) return false;
    if (_search && !m.key.toLowerCase().includes(_search)) return false;
    return true;
  });
}

function _renderTable(container) {
  const tbody = container.querySelector("#models-tbody");
  if (!tbody) return;

  // Update counts
  const all = Object.values(_allModels);
  const enabled = all.filter((m) => m.enabled);
  const disabled = all.filter((m) => !m.enabled);
  container.querySelector("#count-all").textContent = all.length;
  container.querySelector("#count-enabled").textContent = enabled.length;
  container.querySelector("#count-disabled").textContent = disabled.length;

  const visible = _visibleModels();

  if (all.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="7">
          <div class="empty-state">
            ${BOX_ICON}
            <div class="empty-state-title">No models configured</div>
            <div class="empty-state-sub">Add your first radio model to get started.</div>
            <button class="btn btn-success" id="empty-add-btn">Add Model</button>
          </div>
        </td>
      </tr>`;
    tbody.querySelector("#empty-add-btn")?.addEventListener("click", () => _openModelModal(container, null));
    return;
  }

  if (visible.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="7">
          <div class="empty-state">
            ${BOX_ICON}
            <div class="empty-state-title">No models match your search</div>
            <button class="btn btn-secondary" id="clear-search-btn">Clear search</button>
          </div>
        </td>
      </tr>`;
    tbody.querySelector("#clear-search-btn")?.addEventListener("click", () => {
      container.querySelector("#models-search").value = "";
      _search = "";
      _renderTable(container);
    });
    return;
  }

  tbody.innerHTML = visible.map((m) => _modelRow(m)).join("");

  // Bind row events
  tbody.querySelectorAll("[data-toggle-key]").forEach((el) => {
    el.addEventListener("change", (e) => {
      e.stopPropagation();
      _toggleModel(container, el.dataset.toggleKey, e.target.checked);
    });
  });

  tbody.querySelectorAll("[data-edit-key]").forEach((el) => {
    el.addEventListener("click", (e) => {
      e.stopPropagation();
      _openModelModal(container, el.dataset.editKey);
    });
  });

  tbody.querySelectorAll("[data-delete-key]").forEach((el) => {
    el.addEventListener("click", (e) => {
      e.stopPropagation();
      _deleteModel(container, el.dataset.deleteKey);
    });
  });

  tbody.querySelectorAll("[data-row-key]").forEach((row) => {
    row.addEventListener("click", (e) => {
      if (e.target.closest(".actions-cell") || e.target.closest(".toggle-switch") || e.target.type === "checkbox") return;
      _openModelModal(container, row.dataset.rowKey);
    });
  });

  tbody.querySelectorAll("[data-check-key]").forEach((cb) => {
    cb.addEventListener("change", (e) => {
      e.stopPropagation();
      if (e.target.checked) {
        _checkedKeys.add(cb.dataset.checkKey);
      } else {
        _checkedKeys.delete(cb.dataset.checkKey);
      }
    });
  });
}

function _modelRow(m) {
  const disabledClass = m.enabled ? "" : "disabled-row";
  const checked = _checkedKeys.has(m.key) ? "checked" : "";
  const flags = m.extra_flags || [];
  const flagsHtml = flags.slice(0, 3).map((f) => `<span class="flag-chip">${_esc(f)}</span>`).join(" ");
  const moreHtml = flags.length > 3 ? `<span class="text-muted text-xs">+${flags.length - 3} more</span>` : "";
  const pcbrev = m.pcbrev ? _esc(m.pcbrev) : `<span class="td-muted">—</span>`;

  return `
    <tr class="${disabledClass}" data-row-key="${_esc(m.key)}">
      <td><input type="checkbox" data-check-key="${_esc(m.key)}" ${checked} aria-label="Select ${_esc(m.key)}" /></td>
      <td class="td-mono">${_esc(m.key)}</td>
      <td>${_esc(m.pcb)}</td>
      <td>${pcbrev}</td>
      <td>
        <label class="toggle-switch" title="${m.enabled ? "Enabled" : "Disabled"}" aria-label="Toggle ${_esc(m.key)}">
          <input type="checkbox" data-toggle-key="${_esc(m.key)}" ${m.enabled ? "checked" : ""} />
          <span class="toggle-track"></span>
        </label>
      </td>
      <td class="flags-cell">${flagsHtml} ${moreHtml}</td>
      <td>
        <div class="actions-cell">
          <button class="btn-icon" data-edit-key="${_esc(m.key)}" title="Edit ${_esc(m.key)}" aria-label="Edit model ${_esc(m.key)}">${EDIT_ICON}</button>
          <button class="btn-icon danger" data-delete-key="${_esc(m.key)}" title="Delete ${_esc(m.key)}" aria-label="Delete model ${_esc(m.key)}">${DELETE_ICON}</button>
        </div>
      </td>
    </tr>`;
}

async function _toggleModel(container, key, enabled) {
  // Optimistic update
  if (_allModels[key]) _allModels[key].enabled = enabled;
  _renderTable(container);
  try {
    await api.updateModel(key, { enabled });
  } catch (err) {
    // Revert
    if (_allModels[key]) _allModels[key].enabled = !enabled;
    _renderTable(container);
    showToast("error", "Failed to update model", err.message);
  }
}

async function _deleteModel(container, key) {
  const confirmed = await showConfirm({
    title: "Delete Model?",
    body: `This will permanently remove <code class="font-mono text-primary">${_esc(key)}</code> from the configuration. This action cannot be undone.`,
    confirmText: "Delete",
    confirmClass: "btn-danger",
  });
  if (!confirmed) return;

  try {
    await api.deleteModel(key);
    delete _allModels[key];
    _checkedKeys.delete(key);
    _renderTable(container);
    showToast("success", "Model deleted", `${key} was removed.`);
  } catch (err) {
    showToast("error", "Failed to delete model", err.message);
  }
}

async function _handleImport(container, file) {
  try {
    const text = await file.text();
    const parsed = JSON.parse(text);
    if (!parsed.firmware_version || !parsed.targets) {
      showToast("error", "Invalid JSON structure", "Expected: {firmware_version, targets}");
      return;
    }
    const modelCount = Object.keys(parsed.targets).length;
    const currentCount = Object.keys(_allModels).length;

    const confirmed = await showConfirm({
      title: "Import Configuration",
      body: `This will replace all ${currentCount} current model(s) with ${modelCount} imported model(s). This cannot be undone.`,
      confirmText: "Import and Replace",
      confirmClass: "btn-danger",
    });
    if (!confirmed) return;

    await api.importConfig(file);
    await _loadModels(container);
    showToast("success", "Configuration imported", `${modelCount} models loaded.`);
  } catch (err) {
    showToast("error", "Import failed", err.message);
  }
}

// ---------------------------------------------------------------------------
// Add/Edit modal
// ---------------------------------------------------------------------------

function _openModelModal(container, key) {
  const isEdit = key !== null;
  const model = isEdit ? _allModels[key] : null;

  const backdrop = document.createElement("div");
  backdrop.className = "modal-backdrop";
  backdrop.setAttribute("role", "dialog");
  backdrop.setAttribute("aria-modal", "true");

  const flags = model ? (model.extra_flags || []) : [];

  backdrop.innerHTML = `
    <div class="modal modal-md">
      <div class="modal-header">
        <h2 class="modal-title">
          ${isEdit
            ? `Edit Model &mdash; <span class="font-mono">${_esc(key)}</span>`
            : "Add Radio Model"}
        </h2>
        <button class="modal-close" id="modal-close-btn" aria-label="Close">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18 18 6M6 6l12 12"/></svg>
        </button>
      </div>
      <div class="modal-body">
        <div class="form-stack">
          ${isEdit
            ? `<div class="form-group">
                <label class="form-label">Model Key</label>
                <div class="flex items-center gap-2">
                  <input type="text" class="form-input" value="${_esc(key)}" disabled readonly />
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="16" height="16" style="color:var(--text-muted)"><path stroke-linecap="round" stroke-linejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 1 0-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 0 0 2.25-2.25v-6.75a2.25 2.25 0 0 0-2.25-2.25H6.75a2.25 2.25 0 0 0-2.25 2.25v6.75a2.25 2.25 0 0 0 2.25 2.25Z"/></svg>
                </div>
                <span class="form-help">Model key cannot be changed.</span>
               </div>`
            : `<div class="form-group">
                <label class="form-label" for="f-key">Model Key <span style="color:var(--accent-red)">*</span></label>
                <input type="text" class="form-input" id="f-key" placeholder="e.g., tx15" autocomplete="off" />
                <span class="form-error hidden" id="err-key"></span>
               </div>`}

          <div class="form-group">
            <label class="form-label" for="f-pcb">PCB Type <span style="color:var(--accent-red)">*</span></label>
            <input type="text" class="form-input" id="f-pcb" value="${model ? _esc(model.pcb) : ""}" placeholder="e.g., TX15" autocomplete="off" />
            <span class="form-error hidden" id="err-pcb"></span>
          </div>

          <div class="form-group">
            <label class="form-label" for="f-pcbrev">PCB Revision <span class="text-secondary">(optional)</span></label>
            <input type="text" class="form-input" id="f-pcbrev" value="${model && model.pcbrev ? _esc(model.pcbrev) : ""}" placeholder="e.g., EL18" autocomplete="off" />
          </div>

          <div class="form-group">
            <label class="form-label">Enabled by default</label>
            <label class="toggle-switch">
              <input type="checkbox" id="f-enabled" ${model && model.enabled ? "checked" : ""} />
              <span class="toggle-track"></span>
            </label>
          </div>

          <div class="form-group">
            <label class="form-label" for="tag-text-input-el">Extra CMake Flags</label>
            <div class="tag-input-container" id="tag-container">
              ${flags.map((f) => _tagChip(f)).join("")}
              <input type="text" class="tag-text-input" id="tag-text-input-el" placeholder="-DFLAG=VALUE" autocomplete="off" aria-label="Add CMake flag" />
            </div>
            <span class="form-error hidden" id="err-flags"></span>
            <span class="form-help">Each flag must start with -D and contain =. Press Enter to add. Example: -DCROSSFIRE=YES</span>
          </div>
        </div>
      </div>
      <div class="modal-footer">
        <button class="btn btn-secondary" id="modal-cancel-btn">Cancel</button>
        <button class="btn ${isEdit ? "btn-primary" : "btn-success"}" id="modal-submit-btn" ${isEdit ? "" : "disabled"}>
          ${isEdit ? "Save Changes" : "Add Model"}
        </button>
      </div>
    </div>`;

  const close = () => document.body.removeChild(backdrop);

  backdrop.querySelector("#modal-close-btn").addEventListener("click", close);
  backdrop.querySelector("#modal-cancel-btn").addEventListener("click", close);
  backdrop.addEventListener("click", (e) => { if (e.target === backdrop) close(); });
  document.addEventListener("keydown", function escHandler(e) {
    if (e.key === "Escape") { document.removeEventListener("keydown", escHandler); close(); }
  });

  // Tag input handling
  const tagContainer = backdrop.querySelector("#tag-container");
  const tagInput = backdrop.querySelector("#tag-text-input-el");
  const submitBtn = backdrop.querySelector("#modal-submit-btn");
  let isDirty = isEdit ? false : true;

  const currentFlags = () =>
    Array.from(tagContainer.querySelectorAll(".tag-chip")).map((c) => c.dataset.value);

  const addTag = (value) => {
    value = value.trim();
    if (!value) return;
    const valid = /^-D[A-Z0-9_]+=\S+$/.test(value);
    if (!valid) {
      _setFieldError(backdrop, "flags", "Format: -DFLAG_NAME=VALUE");
      return;
    }
    _clearFieldError(backdrop, "flags");
    const chip = document.createElement("span");
    chip.className = "tag-chip";
    chip.dataset.value = value;
    chip.innerHTML = `${_esc(value)}<button type="button" class="remove" aria-label="Remove flag ${_esc(value)}">&times;</button>`;
    chip.querySelector(".remove").addEventListener("click", () => {
      chip.remove();
      isDirty = true;
      _updateSubmitState();
    });
    tagContainer.insertBefore(chip, tagInput);
    tagInput.value = "";
    isDirty = true;
    _updateSubmitState();
  };

  tagInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      addTag(tagInput.value);
    } else if (e.key === "Backspace" && !tagInput.value) {
      const chips = tagContainer.querySelectorAll(".tag-chip");
      if (chips.length) chips[chips.length - 1].remove();
      isDirty = true;
      _updateSubmitState();
    }
  });

  tagInput.addEventListener("blur", () => { if (tagInput.value) addTag(tagInput.value); });
  tagContainer.addEventListener("click", () => tagInput.focus());

  // Add remove listeners to pre-existing chips (edit mode)
  tagContainer.querySelectorAll(".tag-chip .remove").forEach((btn) => {
    btn.addEventListener("click", () => {
      btn.closest(".tag-chip").remove();
      isDirty = true;
      _updateSubmitState();
    });
  });

  // Change detection for edit mode
  if (isEdit) {
    const origPcb = model.pcb;
    const origPcbrev = model.pcbrev || "";
    const origEnabled = model.enabled;
    const checkDirty = () => {
      const pcb = backdrop.querySelector("#f-pcb").value.trim();
      const pcbrev = backdrop.querySelector("#f-pcbrev").value.trim();
      const enabled = backdrop.querySelector("#f-enabled").checked;
      const newFlags = currentFlags();
      const origFlags = model.extra_flags || [];
      isDirty =
        pcb !== origPcb ||
        pcbrev !== origPcbrev ||
        enabled !== origEnabled ||
        JSON.stringify(newFlags) !== JSON.stringify(origFlags);
      _updateSubmitState();
    };
    backdrop.querySelector("#f-pcb").addEventListener("input", checkDirty);
    backdrop.querySelector("#f-pcbrev").addEventListener("input", checkDirty);
    backdrop.querySelector("#f-enabled").addEventListener("change", checkDirty);
  } else {
    // Add mode: enable button when required fields are filled
    const checkAdd = () => {
      const k = backdrop.querySelector("#f-key")?.value.trim() || "";
      const p = backdrop.querySelector("#f-pcb").value.trim();
      submitBtn.disabled = !k || !p;
    };
    backdrop.querySelector("#f-key")?.addEventListener("input", checkAdd);
    backdrop.querySelector("#f-pcb").addEventListener("input", checkAdd);
  }

  const _updateSubmitState = () => { submitBtn.disabled = !isDirty; };

  // Submit
  backdrop.querySelector("#modal-submit-btn").addEventListener("click", async () => {
    _clearAllErrors(backdrop);
    const pcb = backdrop.querySelector("#f-pcb").value.trim();
    const pcbrev = backdrop.querySelector("#f-pcbrev").value.trim() || null;
    const enabled = backdrop.querySelector("#f-enabled").checked;
    const extra_flags = currentFlags();

    let hasError = false;

    if (!pcb) {
      _setFieldError(backdrop, "pcb", "PCB type is required.");
      hasError = true;
    }

    if (!isEdit) {
      const k = backdrop.querySelector("#f-key").value.trim();
      if (!k) {
        _setFieldError(backdrop, "key", "Model name is required.");
        hasError = true;
      } else if (!/^[a-z0-9][a-z0-9_-]{0,63}$/.test(k)) {
        _setFieldError(backdrop, "key", "Must be lowercase alphanumeric with optional - or _");
        hasError = true;
      } else if (_allModels[k]) {
        _setFieldError(backdrop, "key", "A model with this key already exists.");
        hasError = true;
      }
    }

    if (hasError) return;

    submitBtn.disabled = true;
    submitBtn.innerHTML = `<span class="btn-spinner"></span>`;

    try {
      if (isEdit) {
        const updated = await api.updateModel(key, { pcb, pcbrev, enabled, extra_flags });
        _allModels[key] = { ...updated, key };
        showToast("success", "Model saved", `${key} was updated.`);
      } else {
        const newKey = backdrop.querySelector("#f-key").value.trim();
        const created = await api.createModel({ key: newKey, pcb, pcbrev, enabled, extra_flags });
        _allModels[newKey] = { ...created, key: newKey };
        showToast("success", "Model added", `${newKey} was added.`);
      }
      close();
      _renderTable(container);
    } catch (err) {
      submitBtn.disabled = false;
      submitBtn.textContent = isEdit ? "Save Changes" : "Add Model";
      showToast("error", "Save failed", err.message);
    }
  });

  document.body.appendChild(backdrop);
  const firstInput = backdrop.querySelector("input:not([disabled]):not([type=checkbox])");
  if (firstInput) firstInput.focus();
}

function _tagChip(value) {
  return `<span class="tag-chip" data-value="${_esc(value)}">${_esc(value)}<button type="button" class="remove" aria-label="Remove flag ${_esc(value)}">&times;</button></span>`;
}

function _setFieldError(container, field, msg) {
  const input = container.querySelector(`#f-${field}`);
  const err = container.querySelector(`#err-${field}`);
  if (input) input.classList.add("error");
  if (err) { err.textContent = msg; err.classList.remove("hidden"); }
}

function _clearFieldError(container, field) {
  const input = container.querySelector(`#f-${field}`);
  const err = container.querySelector(`#err-${field}`);
  if (input) input.classList.remove("error");
  if (err) { err.textContent = ""; err.classList.add("hidden"); }
}

function _clearAllErrors(container) {
  container.querySelectorAll(".form-error").forEach((el) => { el.textContent = ""; el.classList.add("hidden"); });
  container.querySelectorAll(".form-input.error").forEach((el) => el.classList.remove("error"));
}

function _showError(container, html) {
  const el = container.querySelector("#models-error");
  if (!el) return;
  el.className = "alert-error";
  el.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="width:16px;height:16px;flex-shrink:0"><path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m9-.75a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9 3.75h.008v.008H12v-.008Z"/></svg> ${html}`;
}

function _esc(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
