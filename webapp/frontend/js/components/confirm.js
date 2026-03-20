/**
 * confirm.js — Reusable confirmation dialog.
 *
 * Usage:
 *   import { showConfirm } from './components/confirm.js';
 *   const confirmed = await showConfirm({
 *     title: 'Delete Model?',
 *     body: 'This will remove <strong>tx15</strong> from the configuration. This action cannot be undone.',
 *     confirmText: 'Delete',
 *     confirmClass: 'btn-danger',
 *   });
 *   if (confirmed) { ... }
 */

/**
 * @param {object} opts
 * @param {string} opts.title
 * @param {string} opts.body   - may contain safe HTML
 * @param {string} [opts.confirmText='Confirm']
 * @param {string} [opts.confirmClass='btn-primary']
 * @param {string} [opts.cancelText='Cancel']
 * @returns {Promise<boolean>}
 */
export function showConfirm({
  title,
  body,
  confirmText = "Confirm",
  confirmClass = "btn-primary",
  cancelText = "Cancel",
}) {
  return new Promise((resolve) => {
    const backdrop = document.createElement("div");
    backdrop.className = "modal-backdrop";
    backdrop.setAttribute("role", "dialog");
    backdrop.setAttribute("aria-modal", "true");
    backdrop.setAttribute("aria-labelledby", "confirm-dialog-title");

    backdrop.innerHTML = `
      <div class="modal modal-sm">
        <div class="delete-confirm-content">
          <svg class="delete-confirm-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round"
              d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
          </svg>
          <div class="delete-confirm-title" id="confirm-dialog-title">${_escape(title)}</div>
          <div class="delete-confirm-body">${body}</div>
          <div class="delete-confirm-footer">
            <button class="btn btn-secondary min-w-100" id="confirm-cancel">${_escape(cancelText)}</button>
            <button class="btn ${confirmClass} min-w-100" id="confirm-ok">${_escape(confirmText)}</button>
          </div>
        </div>
      </div>
    `;

    const close = (result) => {
      document.body.removeChild(backdrop);
      resolve(result);
    };

    backdrop.querySelector("#confirm-cancel").addEventListener("click", () => close(false));
    backdrop.querySelector("#confirm-ok").addEventListener("click", async () => {
      const btn = backdrop.querySelector("#confirm-ok");
      const cancelBtn = backdrop.querySelector("#confirm-cancel");
      btn.disabled = true;
      cancelBtn.disabled = true;
      btn.innerHTML = `<span class="btn-spinner"></span>`;
      close(true);
    });

    // Click outside to cancel
    backdrop.addEventListener("click", (e) => {
      if (e.target === backdrop) close(false);
    });

    // Escape key
    const keyHandler = (e) => {
      if (e.key === "Escape") {
        document.removeEventListener("keydown", keyHandler);
        close(false);
      }
    };
    document.addEventListener("keydown", keyHandler);

    document.body.appendChild(backdrop);
    backdrop.querySelector("#confirm-cancel").focus();
  });
}

function _escape(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
