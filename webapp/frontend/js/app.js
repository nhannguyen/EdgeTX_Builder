/**
 * app.js — SPA router and global state.
 *
 * Pages are loaded as ES modules on demand. Navigation updates the active
 * nav item and renders the current page into #main-content.
 */

import * as api from "./api.js";
import { showToast } from "./components/toast.js";

// ---------------------------------------------------------------------------
// Page registry
// ---------------------------------------------------------------------------

const PAGES = {
  models:   () => import("./pages/models.js"),
  build:    () => import("./pages/build.js"),
  history:  () => import("./pages/history.js"),
  settings: () => import("./pages/settings.js"),
};

let _currentPage = null;

// ---------------------------------------------------------------------------
// Router
// ---------------------------------------------------------------------------

async function navigate(page) {
  if (!PAGES[page]) page = "models";

  // Update nav state
  document.querySelectorAll(".nav-item").forEach((el) => {
    el.classList.toggle("active", el.dataset.page === page);
  });

  _currentPage = page;

  const content = document.getElementById("main-content");
  if (!content) return;

  // Reset content styles — the build page takes full height
  content.style.overflow = page === "build" ? "hidden" : "auto";
  content.style.padding = page === "build" ? "0" : "var(--space-6)";
  content.innerHTML = ""; // Clear previous page

  try {
    const module = await PAGES[page]();
    await module.render(content);
  } catch (err) {
    content.innerHTML = `<div class="alert-error">Failed to load page: ${err.message}</div>`;
    console.error("Page load error:", err);
  }
}

// ---------------------------------------------------------------------------
// Health indicator
// ---------------------------------------------------------------------------

export async function updateHealth() {
  const dot = document.getElementById("health-dot");
  const text = document.getElementById("health-text");
  if (!dot || !text) return;

  try {
    const report = await api.fetchHealth();
    dot.className = `health-dot ${report.status}`;
    text.className = `health-text ${report.status}`;

    switch (report.status) {
      case "ok":
        text.textContent = "Ready";
        break;
      case "degraded":
        text.textContent = "Toolchain missing";
        break;
      case "error":
        text.textContent = "Config error";
        break;
      default:
        text.textContent = report.status;
    }
  } catch (_) {
    dot.className = "health-dot error";
    text.className = "health-text error";
    text.textContent = "Unreachable";
  }
}

// ---------------------------------------------------------------------------
// Sidebar firmware version
// ---------------------------------------------------------------------------

async function updateFirmwareVersion() {
  try {
    const config = await api.fetchConfig();
    const el = document.getElementById("sidebar-fw-version");
    if (el) el.textContent = config.firmware_version || "—";
  } catch (_) {}
}

// ---------------------------------------------------------------------------
// Initialisation
// ---------------------------------------------------------------------------

function init() {
  // Bind nav clicks
  document.querySelectorAll(".nav-item").forEach((el) => {
    el.addEventListener("click", () => navigate(el.dataset.page));
  });

  // Header settings button
  document.getElementById("header-settings-btn")?.addEventListener("click", () => {
    navigate("settings");
  });

  // Health indicator click — navigate to settings
  document.getElementById("health-indicator")?.addEventListener("click", () => {
    navigate("settings");
  });

  // Initial health check and firmware version
  updateHealth();
  updateFirmwareVersion();

  // Navigate to models page on load
  navigate("models");
}

// Boot
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
