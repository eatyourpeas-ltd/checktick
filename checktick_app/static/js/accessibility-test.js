/**
 * Accessibility Test Module
 *
 * Uses axe-core to run WCAG 2.1 AA accessibility checks on survey styles.
 * This script loads axe-core dynamically and runs tests against the survey preview.
 */

(function () {
  "use strict";

  /**
   * Load axe-core library dynamically from local static files
   * SRI hash verified by GitHub Actions workflow
   */
  function loadAxeCore() {
    return new Promise((resolve, reject) => {
      if (window.axe) {
        resolve(window.axe);
        return;
      }

      // Get the base URL from existing static file references
      const existingScript = document.querySelector(
        'script[src*="/static/js/"]'
      );
      let basePath = "/static/js/";
      if (existingScript) {
        const match = existingScript.src.match(/(.+\/static\/js\/)/);
        if (match) basePath = match[1];
      }

      const script = document.createElement("script");
      script.src = basePath + "axe-core.min.js";
      script.onload = () => resolve(window.axe);
      script.onerror = () => reject(new Error("Failed to load axe-core"));
      document.head.appendChild(script);
    });
  }

  /**
   * Create an iframe to load the survey preview for testing
   */
  function createTestFrame(previewUrl) {
    return new Promise((resolve, reject) => {
      const iframe = document.createElement("iframe");
      iframe.id = "accessibility-test-frame";
      iframe.src = previewUrl;
      iframe.style.cssText =
        "position: absolute; left: -9999px; width: 1024px; height: 768px; border: none;";
      iframe.setAttribute("aria-hidden", "true");

      iframe.onload = () => {
        // Wait a bit for styles to fully apply
        setTimeout(() => resolve(iframe), 500);
      };

      iframe.onerror = () => reject(new Error("Failed to load survey preview"));

      document.body.appendChild(iframe);
    });
  }

  /**
   * Run axe-core accessibility tests
   */
  async function runAccessibilityTest(iframe) {
    const axe = window.axe;
    const frameDoc = iframe.contentDocument || iframe.contentWindow.document;

    // Configure axe to focus on WCAG 2.1 AA
    const config = {
      runOnly: {
        type: "tag",
        values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"],
      },
      rules: {
        // Focus on color contrast and form accessibility
        "color-contrast": { enabled: true },
        label: { enabled: true },
        "aria-required-attr": { enabled: true },
        "aria-valid-attr": { enabled: true },
        "button-name": { enabled: true },
        "form-field-multiple-labels": { enabled: true },
        "input-image-alt": { enabled: true },
        "link-name": { enabled: true },
        "select-name": { enabled: true },
      },
    };

    try {
      const results = await axe.run(frameDoc, config);
      return results;
    } catch (error) {
      throw new Error("Accessibility test failed: " + error.message);
    }
  }

  /**
   * Format test results for display
   */
  function formatResults(results) {
    const violations = results.violations || [];
    const passes = results.passes || [];
    const incomplete = results.incomplete || [];

    let html = "";

    // Summary
    const totalIssues = violations.reduce((sum, v) => sum + v.nodes.length, 0);
    const passCount = passes.length;

    if (totalIssues === 0) {
      html += `
        <div class="alert alert-success mb-4">
          <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <div>
            <h3 class="font-bold">All accessibility checks passed!</h3>
            <p class="text-sm">${passCount} WCAG 2.1 AA rules checked. Your survey style meets accessibility standards.</p>
          </div>
        </div>
      `;
    } else {
      html += `
        <div class="alert alert-warning mb-4">
          <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <div>
            <h3 class="font-bold">${totalIssues} accessibility issue${
        totalIssues !== 1 ? "s" : ""
      } found</h3>
            <p class="text-sm">Please review the issues below to improve accessibility.</p>
          </div>
        </div>
      `;

      // Violations
      violations.forEach((violation) => {
        const impactClass =
          {
            critical: "text-error",
            serious: "text-warning",
            moderate: "text-info",
            minor: "text-base-content/70",
          }[violation.impact] || "text-base-content";

        html += `
          <div class="collapse collapse-arrow bg-base-100 border border-base-300 mb-2">
            <input type="checkbox" />
            <div class="collapse-title font-medium">
              <span class="badge badge-sm ${
                violation.impact === "critical"
                  ? "badge-error"
                  : violation.impact === "serious"
                  ? "badge-warning"
                  : "badge-info"
              } mr-2">${violation.impact}</span>
              ${escapeHtml(violation.help)}
              <span class="text-sm opacity-70 ml-2">(${
                violation.nodes.length
              } instance${violation.nodes.length !== 1 ? "s" : ""})</span>
            </div>
            <div class="collapse-content">
              <p class="text-sm mb-2">${escapeHtml(violation.description)}</p>
              <p class="text-sm mb-2"><a href="${
                violation.helpUrl
              }" target="_blank" rel="noopener" class="link link-primary">Learn more about this issue</a></p>
              <div class="text-xs font-mono bg-base-200 p-2 rounded overflow-x-auto">
                ${violation.nodes
                  .map(
                    (node) =>
                      `<div class="mb-1">${escapeHtml(
                        node.html.substring(0, 200)
                      )}${node.html.length > 200 ? "..." : ""}</div>`
                  )
                  .join("")}
              </div>
            </div>
          </div>
        `;
      });
    }

    // Incomplete/needs review (if any)
    if (incomplete.length > 0) {
      const incompleteCount = incomplete.reduce(
        (sum, i) => sum + i.nodes.length,
        0
      );
      html += `
        <div class="mt-4">
          <h5 class="font-semibold text-sm mb-2">${incompleteCount} item${
        incompleteCount !== 1 ? "s" : ""
      } need manual review:</h5>
          <ul class="text-sm list-disc list-inside opacity-70">
            ${incomplete
              .map((item) => `<li>${escapeHtml(item.help)}</li>`)
              .join("")}
          </ul>
        </div>
      `;
    }

    // Summary stats
    html += `
      <div class="mt-4 text-xs opacity-60">
        <p>Tested against WCAG 2.1 AA standards using axe-core ${
          window.axe ? window.axe.version : "N/A"
        }</p>
        <p>${passCount} rules passed • ${
      violations.length
    } rules with issues • ${incomplete.length} rules need review</p>
      </div>
    `;

    return html;
  }

  /**
   * Escape HTML to prevent XSS
   */
  function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  /**
   * Show loading state
   */
  function showLoading(resultsContainer) {
    resultsContainer.classList.remove("hidden");
    document.getElementById("accessibility-results-content").innerHTML = `
      <div class="flex items-center gap-2">
        <span class="loading loading-spinner loading-sm"></span>
        <span>Running accessibility tests...</span>
      </div>
    `;
  }

  /**
   * Show error state
   */
  function showError(message) {
    document.getElementById("accessibility-results-content").innerHTML = `
      <div class="alert alert-error">
        <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <div>
          <h3 class="font-bold">Test failed</h3>
          <p class="text-sm">${escapeHtml(message)}</p>
        </div>
      </div>
    `;
  }

  /**
   * Clean up test resources
   */
  function cleanup() {
    const iframe = document.getElementById("accessibility-test-frame");
    if (iframe) {
      iframe.remove();
    }
  }

  /**
   * Main test runner
   */
  async function runTest(previewUrl) {
    const resultsContainer = document.getElementById("accessibility-results");
    if (!resultsContainer) return;

    showLoading(resultsContainer);
    cleanup();

    try {
      // Load axe-core
      await loadAxeCore();

      // Create test iframe
      const iframe = await createTestFrame(previewUrl);

      // Run tests
      const results = await runAccessibilityTest(iframe);

      // Display results
      document.getElementById("accessibility-results-content").innerHTML =
        formatResults(results);

      // Cleanup
      cleanup();
    } catch (error) {
      showError(error.message);
      cleanup();
    }
  }

  // Initialize
  document.addEventListener("DOMContentLoaded", function () {
    const testButton = document.getElementById("run-accessibility-test");
    if (testButton) {
      testButton.addEventListener("click", function (e) {
        e.preventDefault();
        const previewUrl = this.dataset.surveyPreviewUrl;
        if (previewUrl) {
          runTest(previewUrl);
        }
      });
    }
  });
})();
