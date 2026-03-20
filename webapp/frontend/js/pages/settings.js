/**
 * settings.js — Settings page.
 */

import * as api from "../api.js";
import { showToast } from "../components/toast.js";

export async function render(container) {
  container.innerHTML = _shell();
  await _loadSettings(container);
  _bindEvents(container);
}

function _shell() {
  return `
    <h1 class="page-title" style="margin-bottom:var(--space-8)">Settings</h1>
    <div class="settings-content" id="settings-content">
      <div class="empty-state">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="width:24px;height:24px;animation:spin-build 1s linear infinite"><path stroke-linecap="round" stroke-linejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182m0-4.991v4.99"/></svg>
        <span class="text-secondary text-sm">Loading settings...</span>
      </div>
    </div>`;
}

async function _loadSettings(container) {
  try {
    const [settings, config] = await Promise.all([api.fetchSettings(), api.fetchConfig()]);
    const fwVersion = config.firmware_version || "";
    _renderSettings(container, settings, fwVersion);
  } catch (err) {
    container.querySelector("#settings-content").innerHTML =
      `<div class="alert-error">Failed to load settings: ${_esc(err.message)}</div>`;
  }
}

function _renderSettings(container, settings, fwVersion) {
  const sc = container.querySelector("#settings-content");
  sc.innerHTML = `
    <!-- Card 1: Toolchain -->
    <div class="settings-card">
      <h2 class="settings-card-title">Toolchain</h2>
      <div class="settings-fields">
        <div class="form-group">
          <label class="form-label" for="s-toolchain">ARM Toolchain Path</label>
          <div class="toolchain-input-row">
            <input type="text" class="form-input" id="s-toolchain"
              value="${_esc(settings.toolchain_path || "")}"
              placeholder="/Applications/ArmGNUToolchain/14.2.rel1/arm-none-eabi/bin" />
            <button class="btn btn-secondary" id="validate-toolchain-btn">Validate</button>
          </div>
          <div class="toolchain-status" id="toolchain-status"></div>
          <span class="form-help">Path to the directory containing arm-none-eabi-gcc</span>
        </div>
      </div>
    </div>

    <!-- Card 2: Build Defaults -->
    <div class="settings-card">
      <h2 class="settings-card-title">Build Defaults</h2>
      <div class="settings-fields">
        <div class="form-group">
          <label class="form-label" for="s-fw-ver">Default Firmware Version</label>
          <input type="text" class="form-input font-mono" id="s-fw-ver"
            value="${_esc(fwVersion)}" placeholder="e.g., 2.12" />
          <span class="form-help">Branch or tag name in the EdgeTX repository</span>
        </div>
        <div class="form-group">
          <label class="form-label" for="s-dist-dir">Build Output Directory</label>
          <input type="text" class="form-input font-mono" id="s-dist-dir"
            value="${_esc(settings.build_output_directory || "./dist")}" />
        </div>
        <div class="form-group">
          <label class="form-label" for="s-logs-dir">Logs Directory</label>
          <input type="text" class="form-input font-mono" id="s-logs-dir"
            value="${_esc(settings.logs_directory || "./logs")}" />
        </div>
      </div>
    </div>

    <!-- Card 3: Configuration Management -->
    <div class="settings-card">
      <h2 class="settings-card-title">Configuration Management</h2>
      <div class="flex gap-3">
        <a class="btn btn-secondary" href="${api.getExportUrl()}" download="targets.json">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 12 12 16.5m0 0L7.5 12m4.5 4.5V3"/></svg>
          Export Configuration
        </a>
        <button class="btn btn-secondary" id="import-cfg-btn">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5m-13.5-9L12 3m0 0 4.5 4.5M12 3v13.5"/></svg>
          Import Configuration
        </button>
        <input type="file" id="settings-import-file" accept=".json,application/json" class="hidden" />
      </div>
    </div>

    <!-- Card 4: Build History -->
    <div class="settings-card">
      <h2 class="settings-card-title">Build History</h2>
      <div class="settings-fields">
        <label class="form-check">
          <input type="checkbox" id="s-auto-clean" ${settings.auto_clean_old_builds ? "checked" : ""} />
          <span class="form-check-label">Automatically remove old build history</span>
        </label>
        <div class="form-group">
          <label class="form-label" for="s-retention">Retain history for N days (0 = forever)</label>
          <input type="number" class="form-input" id="s-retention"
            value="${_esc(String(settings.build_history_retention_days || 0))}"
            min="0" step="1" style="max-width:200px" />
        </div>
        <button class="btn btn-danger-outline" id="clear-history-settings-btn">Clear Build History</button>
      </div>
    </div>

    <div class="settings-save-bar">
      <button class="btn btn-primary" id="save-settings-btn">Save Settings</button>
    </div>`;
}

function _bindEvents(container) {
  // Validate toolchain
  container.addEventListener("click", async (e) => {
    if (e.target.id === "validate-toolchain-btn") {
      const path = container.querySelector("#s-toolchain")?.value.trim() || "";
      const statusEl = container.querySelector("#toolchain-status");
      if (!statusEl) return;
      statusEl.innerHTML = `<span class="text-secondary">Checking...</span>`;
      try {
        const health = await api.fetchHealth();
        const toolchain = health.checks?.toolchain;
        if (toolchain?.ok) {
          statusEl.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14" style="color:var(--accent-green)"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z"/></svg><span style="color:var(--accent-green)">arm-none-eabi-gcc found</span>`;
        } else {
          statusEl.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14" style="color:var(--accent-red)"><path stroke-linecap="round" stroke-linejoin="round" d="m9.75 9.75 4.5 4.5m0-4.5-4.5 4.5M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z"/></svg><span style="color:var(--accent-red)">${_esc(toolchain?.message || "Toolchain not found")}</span>`;
        }
      } catch (err) {
        statusEl.innerHTML = `<span style="color:var(--accent-red)">${_esc(err.message)}</span>`;
      }
    }

    if (e.target.id === "save-settings-btn") {
      await _saveSettings(container, e.target);
    }

    if (e.target.id === "import-cfg-btn") {
      container.querySelector("#settings-import-file")?.click();
    }

    if (e.target.id === "clear-history-settings-btn") {
      const { showConfirm } = await import("../components/confirm.js");
      const ok = await showConfirm({
        title: "Clear Build History?",
        body: "This will permanently delete all build history and log files.",
        confirmText: "Clear History",
        confirmClass: "btn-danger",
      });
      if (ok) {
        try {
          await api.clearHistory();
          showToast("success", "History cleared");
        } catch (err) {
          showToast("error", "Failed to clear history", err.message);
        }
      }
    }
  });

  container.addEventListener("change", async (e) => {
    if (e.target.id === "settings-import-file") {
      const file = e.target.files[0];
      if (!file) return;
      e.target.value = "";
      try {
        const result = await api.importConfig(file);
        showToast("success", "Configuration imported", `${result.model_count} models loaded.`);
      } catch (err) {
        showToast("error", "Import failed", err.message);
      }
    }
  });
}

async function _saveSettings(container, btn) {
  const toolchain = container.querySelector("#s-toolchain")?.value.trim() || "";
  const distDir = container.querySelector("#s-dist-dir")?.value.trim() || "./dist";
  const logsDir = container.querySelector("#s-logs-dir")?.value.trim() || "./logs";
  const autoClean = container.querySelector("#s-auto-clean")?.checked || false;
  const retention = parseInt(container.querySelector("#s-retention")?.value, 10) || 0;
  const fwVer = container.querySelector("#s-fw-ver")?.value.trim() || "";

  btn.disabled = true;
  btn.innerHTML = `<span class="btn-spinner"></span>`;

  try {
    // Save app settings
    await api.updateSettings({
      toolchain_path: toolchain,
      build_output_directory: distDir,
      logs_directory: logsDir,
      auto_clean_old_builds: autoClean,
      build_history_retention_days: retention,
    });

    // Save firmware version to config
    if (fwVer) {
      try {
        const currentConfig = await api.fetchConfig();
        if (currentConfig.firmware_version !== fwVer) {
          const form = new FormData();
          const updated = { ...currentConfig, firmware_version: fwVer };
          form.append("file", new Blob([JSON.stringify(updated, null, 2)], { type: "application/json" }), "targets.json");
          await api.importConfig(new File([JSON.stringify(updated, null, 2)], "targets.json", { type: "application/json" }));
        }
      } catch (_) {}
    }

    // Update sidebar firmware version
    const versionEl = document.getElementById("sidebar-fw-version");
    if (versionEl && fwVer) versionEl.textContent = fwVer;

    btn.disabled = false;
    btn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z"/></svg> Saved`;
    setTimeout(() => {
      if (btn) btn.innerHTML = "Save Settings";
    }, 2000);

    showToast("success", "Settings saved");

    // Refresh health
    const { updateHealth } = await import("../app.js");
    updateHealth();
  } catch (err) {
    btn.disabled = false;
    btn.innerHTML = "Save Settings";
    showToast("error", "Save failed", err.message);
  }
}

function _esc(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
