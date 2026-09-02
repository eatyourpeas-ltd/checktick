/**
 * CSP-safe replacements for inline event-handler attributes.
 *
 * The site's Content-Security-Policy forbids 'unsafe-inline' for scripts and
 * per-request nonces do not cover inline handler attributes (onclick=, etc.),
 * so inline handlers are blocked by the browser. Templates must instead use
 * these declarative data attributes:
 *
 *   data-confirm="..."            Ask for confirmation before submitting.
 *                                 Attach to a <form> or to a submit <button>
 *                                 (button-level only gates its own submitter).
 *   data-open-modal="id"          Show the <dialog> with that id (falls back
 *                                 to the closest ancestor dialog).
 *   data-close-modal="id"         Close the <dialog> with that id (falls back
 *                                 to the closest ancestor dialog).
 *   data-copy-value="text"        Copy text to the clipboard with toast
 *                                 feedback.
 *   data-select-on-click          Select the element's text on click
 *                                 (readonly textareas showing URLs/keys).
 *   data-stop-propagation         Stop click event propagation.
 *   data-print                    Call window.print().
 *
 * All behaviour is delegated from document level, so it works for elements
 * rendered after initial load (e.g. HTMX swaps).
 */
(function () {
  "use strict";

  function resolveDialog(el, attr) {
    var id = el.getAttribute(attr);
    if (id) {
      return document.getElementById(id);
    }
    return el.closest("dialog");
  }

  // Confirmation gating for form submissions.
  document.addEventListener("submit", function (e) {
    var form = e.target;
    if (!(form instanceof HTMLFormElement)) return;
    var source = null;
    if (form.hasAttribute("data-confirm")) {
      source = form;
    } else if (
      e.submitter &&
      e.submitter instanceof Element &&
      e.submitter.hasAttribute("data-confirm")
    ) {
      source = e.submitter;
    }
    if (source && !window.confirm(source.getAttribute("data-confirm"))) {
      e.preventDefault();
    }
  });

  document.addEventListener("click", function (e) {
    var el;

    el = e.target.closest("[data-stop-propagation]");
    if (el) {
      e.stopPropagation();
    }

    el = e.target.closest("[data-open-modal]");
    if (el) {
      var dialog = resolveDialog(el, "data-open-modal");
      if (dialog && typeof dialog.showModal === "function") {
        dialog.showModal();
      }
      return;
    }

    el = e.target.closest("[data-close-modal]");
    if (el) {
      var dialogToClose = resolveDialog(el, "data-close-modal");
      if (dialogToClose && typeof dialogToClose.close === "function") {
        dialogToClose.close();
      }
      return;
    }

    el = e.target.closest("[data-copy-value]");
    if (el) {
      var value = el.getAttribute("data-copy-value") || "";
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(value).then(
          function () {
            if (typeof window.showToast === "function") {
              window.showToast("Copied to clipboard", "success");
            }
          },
          function () {
            if (typeof window.showToast === "function") {
              window.showToast("Could not copy to clipboard", "warning");
            }
          }
        );
      }
      return;
    }

    el = e.target.closest("[data-select-on-click]");
    if (el && typeof el.select === "function") {
      el.select();
      return;
    }

    el = e.target.closest("[data-print]");
    if (el) {
      window.print();
    }
  });
})();
