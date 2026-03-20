/**
 * toast.js — Toast notification system.
 *
 * Usage:
 *   import { showToast } from './components/toast.js';
 *   showToast('success', 'Model saved', 'The model was updated successfully.');
 */

const DURATIONS = {
  success: 3000,
  info: 3000,
  warning: 5000,
  error: null, // manual dismiss only
};

const ICONS = {
  success: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z"/></svg>`,
  error:   `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="m9.75 9.75 4.5 4.5m0-4.5-4.5 4.5M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z"/></svg>`,
  warning: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z"/></svg>`,
  info:    `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="m11.25 11.25.041-.02a.75.75 0 0 1 1.063.852l-.708 2.836a.75.75 0 0 0 1.063.853l.041-.021M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9-3.75h.008v.008H12V8.25Z"/></svg>`,
};

const DISMISS_ICON = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18 18 6M6 6l12 12"/></svg>`;

/**
 * Show a toast notification.
 *
 * @param {'success'|'error'|'warning'|'info'} type
 * @param {string} title
 * @param {string} [message]
 */
export function showToast(type, title, message = "") {
  const container = document.getElementById("toast-container");
  if (!container) return;

  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.setAttribute("role", "alert");

  toast.innerHTML = `
    <span class="toast-icon">${ICONS[type] || ICONS.info}</span>
    <div class="toast-body">
      <div class="toast-title">${_escape(title)}</div>
      ${message ? `<div class="toast-message">${_escape(message)}</div>` : ""}
    </div>
    <button class="toast-dismiss" aria-label="Dismiss notification">${DISMISS_ICON}</button>
  `;

  const dismiss = toast.querySelector(".toast-dismiss");
  const remove = () => {
    toast.classList.add("fade-out");
    toast.addEventListener("animationend", () => toast.remove(), { once: true });
    // Fallback in case animationend doesn't fire
    setTimeout(() => toast.remove(), 300);
  };
  dismiss.addEventListener("click", remove);

  container.appendChild(toast);

  const duration = DURATIONS[type];
  if (duration !== null) {
    setTimeout(remove, duration);
  }
}

function _escape(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
