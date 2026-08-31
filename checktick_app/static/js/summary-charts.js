/**
 * Summary report client-side behaviour.
 *
 * Per docs/reporting-planning.md §4.3 and §4.4:
 *   - Copy-data buttons serialise a chart's underlying data to CSV/TSV (or
 *     JSON for the numeric card) via navigator.clipboard.writeText. No library.
 *   - Word cloud is rendered client-side from a JSON payload shipped in a
 *     data attribute. No LLM.
 *   - "Summarise themes" buttons POST to the themes endpoint and render the
 *     sanitised markdown response into a placeholder. Per-question, opt-in.
 *
 * The module is wrapped in an IIFE so it does not pollute the global scope.
 */
(function () {
  "use strict";

  // Show a toast if available; fall back to a no-op so this module never
  // crashes the page if toast.js failed to load.
  function toast(message, type) {
    try {
      if (typeof window.showToast === "function") {
        window.showToast(message, type || "info");
      }
    } catch (e) {}
  }

  // ----- Copy-data buttons -------------------------------------------------

  function serialiseChartToCSV(options) {
    // options is a list of {label, count, percent} — already JSON-parsed.
    if (!Array.isArray(options)) return "";
    var rows = [["Label", "Count", "Percent"].join(",")];
    options.forEach(function (opt) {
      // Quote labels that contain a comma or a quote.
      var label = String(opt.label || "");
      if (label.indexOf(",") !== -1 || label.indexOf('"') !== -1) {
        label = '"' + label.replace(/"/g, '""') + '"';
      }
      rows.push([label, opt.count, opt.percent].join(","));
    });
    return rows.join("\n");
  }

  function serialiseJSON(payload) {
    // Pretty-print JSON for the numeric summary card.
    try {
      return JSON.stringify(payload, null, 2);
    } catch (e) {
      return "";
    }
  }

  async function copyToClipboard(text) {
    if (
      typeof navigator !== "undefined" &&
      navigator.clipboard &&
      typeof navigator.clipboard.writeText === "function"
    ) {
      await navigator.clipboard.writeText(text);
      return true;
    }
    // Legacy fallback: hidden textarea + execCommand. Kept for browsers that
    // gate the async clipboard API behind a secure context.
    try {
      var ta = document.createElement("textarea");
      ta.value = text;
      ta.setAttribute("readonly", "");
      ta.style.position = "absolute";
      ta.style.left = "-9999px";
      document.body.appendChild(ta);
      ta.select();
      var ok = document.execCommand("copy");
      document.body.removeChild(ta);
      return ok;
    } catch (e) {
      return false;
    }
  }

  function wireCopyButtons() {
    var buttons = document.querySelectorAll(".copy-chart-data-btn");
    buttons.forEach(function (btn) {
      if (btn.dataset.wired === "1") return;
      btn.dataset.wired = "1";
      btn.addEventListener("click", async function () {
        var raw = btn.getAttribute("data-chart-data") || "";
        var format = btn.getAttribute("data-copy-format") || "csv";
        var payload;
        try {
          payload = JSON.parse(raw);
        } catch (e) {
          // Fallback: copy the raw attribute as-is.
          payload = raw;
        }
        var text = "";
        if (format === "json") {
          text = serialiseJSON(payload);
        } else {
          text = serialiseChartToCSV(payload);
        }
        if (!text) {
          toast("No data to copy", "warning");
          return;
        }
        var ok = await copyToClipboard(text);
        if (ok) {
          toast("Chart data copied to clipboard", "success");
        } else {
          toast("Could not copy to clipboard. Select the data manually.", "warning");
        }
      });
    });
  }

  // ----- Word cloud --------------------------------------------------------

  function renderWordCloud(container) {
    var raw = container.getAttribute("data-word-cloud") || "[]";
    var entries;
    try {
      entries = JSON.parse(raw);
    } catch (e) {
      entries = [];
    }
    if (!Array.isArray(entries) || entries.length === 0) {
      container.innerHTML =
        '<p class="text-xs text-base-content/60">No words to display.</p>';
      return;
    }
    // Compute a font-size scale from the max count.
    var max = 0;
    entries.forEach(function (e) {
      if (e.count > max) max = e.count;
    });
    if (max <= 0) max = 1;
    var minFont = 0.85; // rem
    var maxFont = 2.0; // rem
    var frag = document.createDocumentFragment();
    entries.forEach(function (entry) {
      var span = document.createElement("span");
      span.textContent = entry.term;
      // Scale font size by the square root of the count to tame outliers.
      var scaled = Math.sqrt(entry.count / max);
      var size = (minFont + (maxFont - minFont) * scaled).toFixed(2);
      span.style.fontSize = size + "rem";
      // Opacity fades smaller terms toward the muted colour.
      span.style.opacity = (0.55 + 0.45 * scaled).toFixed(2);
      span.className =
        "px-2 py-1 rounded bg-base-200 text-base-content hover:bg-base-300 transition-colors";
      span.title = entry.term + " (" + entry.count + ")";
      frag.appendChild(span);
    });
    container.innerHTML = "";
    container.appendChild(frag);
  }

  function wireWordClouds() {
    var containers = document.querySelectorAll(".word-cloud-container");
    containers.forEach(renderWordCloud);
  }

  // ----- Theme analysis (LLM, per question) -------------------------------

  function wireThemeButtons() {
    var buttons = document.querySelectorAll(".summarise-themes-btn");
    buttons.forEach(function (btn) {
      if (btn.dataset.wired === "1") return;
      btn.dataset.wired = "1";
      btn.addEventListener("click", async function () {
        var url = btn.getAttribute("data-themes-url");
        var questionId = btn.getAttribute("data-question-id");
        var resultContainer = document.querySelector(
          '.theme-summary-result[data-question-id="' + questionId + '"]'
        );
        if (!url || !questionId) return;
        // Idempotency guard: disable the button while the request is in flight.
        if (btn.disabled) return;
        btn.disabled = true;
        btn.classList.add("loading");
        if (resultContainer) {
          resultContainer.innerHTML =
            '<p class="text-sm text-base-content/70">Summarising…</p>';
        }
        try {
          var formData = new FormData();
          formData.append("question_id", questionId);
          // Preserve any active date-range filter so the theme summary covers
          // the same responses as the on-screen summary.
          var fromEl = document.getElementById("id_from");
          var toEl = document.getElementById("id_to");
          if (fromEl && fromEl.value) formData.append("from", fromEl.value);
          if (toEl && toEl.value) formData.append("to", toEl.value);
          var resp = await fetch(url, {
            method: "POST",
            body: formData,
            headers: {
              "X-CSRFToken": getCSRFToken(),
            },
          });
          var body = await resp.json().catch(function () {
            return { error: "Invalid response from server.", success: false };
          });
          if (resultContainer) {
            if (body.success && body.summary) {
              // The server already sanitised the markdown; render it as
              // text-safe HTML via a minimal markdown-to-HTML conversion.
              // We intentionally do NOT use innerHTML with the raw markdown —
              // render it as preformatted text to avoid any HTML injection
              // surface even after sanitisation.
              var pre = document.createElement("pre");
              pre.className =
                "bg-base-200 text-base-content rounded p-3 text-sm whitespace-pre-wrap";
              pre.textContent = body.summary;
              resultContainer.innerHTML = "";
              resultContainer.appendChild(pre);
              toast("Theme summary ready", "success");
            } else {
              var msg = body.error || "Could not generate a theme summary.";
              resultContainer.innerHTML =
                '<p class="text-sm text-base-content/70">' +
                escapeHTML(msg) +
                "</p>";
              toast(msg, "warning");
            }
          }
        } catch (e) {
          if (resultContainer) {
            resultContainer.innerHTML =
              '<p class="text-sm text-base-content/70">Network error — please try again.</p>';
          }
          toast("Network error", "error");
        } finally {
          btn.disabled = false;
          btn.classList.remove("loading");
        }
      });
    });
  }

  function getCSRFToken() {
    // Prefer the cookie set by Django's CsrfViewMiddleware.
    var match = document.cookie.match(/csrftoken=([^;]+)/);
    if (match) return decodeURIComponent(match[1]);
    // Fall back to a hidden form input.
    var el = document.querySelector(
      'input[name="csrfmiddlewaretoken"]'
    );
    return el ? el.value : "";
  }

  function escapeHTML(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  // ----- Init --------------------------------------------------------------

  function init() {
    wireCopyButtons();
    wireWordClouds();
    wireThemeButtons();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
