/**
 * log-viewer.js — SSE log streaming component.
 *
 * Manages an EventSource connection, renders log lines into a scrollable
 * container with color-coding and auto-scroll behaviour.
 */

const DOWN_ICON = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" d="M19.5 13.5 12 21m0 0-7.5-7.5M12 21V3"/></svg>`;
const COPY_ICON = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" d="M15.75 17.25v3.375c0 .621-.504 1.125-1.125 1.125h-9.75a1.125 1.125 0 0 1-1.125-1.125V7.875c0-.621.504-1.125 1.125-1.125H6.75a9.06 9.06 0 0 1 1.5.124m7.5 10.376h3.375c.621 0 1.125-.504 1.125-1.125V11.25c0-4.46-3.243-8.161-7.5-8.876a9.06 9.06 0 0 0-1.5-.124H9.375c-.621 0-1.125.504-1.125 1.125v3.5m7.5 10.375H9.375a1.125 1.125 0 0 1-1.125-1.125v-9.25m12 6.625v-1.875a3.375 3.375 0 0 0-3.375-3.375h-1.5a1.125 1.125 0 0 1-1.125-1.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H9.75"/></svg>`;

/**
 * Classify a log line for color-coding.
 * @param {string} line
 * @returns {string} CSS class suffix
 */
function classifyLine(line) {
  const lower = line.toLowerCase();
  if (
    line.startsWith("ERROR:") ||
    line.startsWith("error:") ||
    lower.includes("failed") ||
    lower.includes("error:")
  ) {
    return "error";
  }
  if (
    line.startsWith("WARNING:") ||
    line.startsWith("warning:") ||
    lower.includes("warning:")
  ) {
    return "warning";
  }
  if (line.startsWith("-- ")) {
    return "cmake";
  }
  return "";
}

export class LogViewer {
  /**
   * @param {HTMLElement} container - The scrollable log body element
   * @param {HTMLElement} [autoScrollToggle] - Checkbox element for auto-scroll toggle
   */
  constructor(container, autoScrollToggle = null) {
    this._container = container;
    this._autoScrollEl = autoScrollToggle;
    this._autoScroll = true;
    this._es = null;
    this._onDone = null;

    // Jump-to-bottom button
    this._jumpBtn = document.createElement("button");
    this._jumpBtn.className = "jump-to-bottom";
    this._jumpBtn.innerHTML = `${DOWN_ICON} Jump to bottom`;
    this._jumpBtn.addEventListener("click", () => {
      this._autoScroll = true;
      if (this._autoScrollEl) this._autoScrollEl.checked = true;
      this._scrollToBottom();
      this._jumpBtn.classList.remove("visible");
    });
    this._container.style.position = "relative";
    this._container.appendChild(this._jumpBtn);

    // Detect manual scroll
    this._container.addEventListener("scroll", () => {
      const atBottom =
        this._container.scrollHeight -
          this._container.scrollTop -
          this._container.clientHeight <
        40;
      if (!atBottom && this._autoScroll) {
        this._autoScroll = false;
        if (this._autoScrollEl) this._autoScrollEl.checked = false;
        this._jumpBtn.classList.add("visible");
      }
      if (atBottom) {
        this._jumpBtn.classList.remove("visible");
      }
    });

    if (this._autoScrollEl) {
      this._autoScrollEl.addEventListener("change", () => {
        this._autoScroll = this._autoScrollEl.checked;
        if (this._autoScroll) {
          this._scrollToBottom();
          this._jumpBtn.classList.remove("visible");
        }
      });
    }
  }

  /**
   * Start streaming logs for a build via SSE.
   *
   * @param {string} buildId
   * @param {function} [onDone] - Called with ({ status, exitCode }) on completion
   */
  start(buildId, onDone = null) {
    this.stop();
    this._onDone = onDone;
    this._es = new EventSource(`/api/builds/${encodeURIComponent(buildId)}/logs`);

    this._es.onmessage = (event) => {
      this._appendLine(event.data);
    };

    this._es.addEventListener("done", (event) => {
      try {
        const data = JSON.parse(event.data);
        if (this._onDone) this._onDone(data);
      } catch (_) {
        if (this._onDone) this._onDone({ status: "unknown" });
      }
      this.stop();
    });

    this._es.addEventListener("truncated", (event) => {
      this._appendLine(`⚠ ${event.data}`, "warning");
    });

    this._es.onerror = () => {
      // Connection error — SSE will auto-retry; show indicator
      this._appendLine("[Connection lost. Attempting to reconnect...]", "warning");
    };
  }

  /**
   * Stop the SSE connection.
   */
  stop() {
    if (this._es) {
      this._es.close();
      this._es = null;
    }
  }

  /**
   * Populate the log viewer from a plain text string (for history view).
   *
   * @param {string} text
   */
  loadText(text) {
    this.clear();
    const lines = text.split("\n");
    for (const line of lines) {
      this._appendLine(line);
    }
  }

  /**
   * Load an array of log lines.
   * @param {string[]} lines
   */
  loadLines(lines) {
    this.clear();
    for (const line of lines) {
      this._appendLine(line);
    }
    this._scrollToBottom();
  }

  clear() {
    // Remove all .log-line elements, keep the jump button
    const lines = this._container.querySelectorAll(".log-line");
    lines.forEach((l) => l.remove());
  }

  /**
   * Copy log content to clipboard.
   */
  async copyToClipboard() {
    const lines = this._container.querySelectorAll(".log-line");
    const text = Array.from(lines).map((l) => l.textContent).join("\n");
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch (_) {
      return false;
    }
  }

  // ------------------------------------------------------------------
  // Internal helpers
  // ------------------------------------------------------------------

  _appendLine(text, forceClass = "") {
    const lineClass = forceClass || classifyLine(text);
    const span = document.createElement("span");
    span.className = `log-line${lineClass ? " " + lineClass : ""}`;
    span.textContent = text;
    // Insert before the jump button
    this._container.insertBefore(span, this._jumpBtn);
    if (this._autoScroll) {
      this._scrollToBottom();
    }
  }

  _scrollToBottom() {
    this._container.scrollTop = this._container.scrollHeight;
  }
}
