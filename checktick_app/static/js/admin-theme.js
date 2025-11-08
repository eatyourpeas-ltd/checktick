(function () {
  try {
    var storageKey = "checktick:admin-theme";
    var meta = document.querySelector('meta[name="checktick-theme"]');
    var defaultTheme =
      (meta && meta.getAttribute("content")) || "checktick-light";
    var theme = localStorage.getItem(storageKey) || defaultTheme;
    var statusNode = null;
    var toggleNode = null;

    // Get actual daisyUI preset names from meta tag
    var presetsMeta = document.querySelector('meta[name="theme-presets"]');
    var presets = presetsMeta
      ? presetsMeta.content.split(",")
      : ["wireframe", "business"];
    var LIGHT_PRESET = presets[0] || "wireframe";
    var DARK_PRESET = presets[1] || "business";

    function themeToPreset(t) {
      // Map logical theme names to actual daisyUI presets
      if (t === "checktick-dark") {
        return DARK_PRESET;
      }
      return LIGHT_PRESET; // checktick-light or default
    }

    function applyTheme(t) {
      var preset = themeToPreset(t);
      document.documentElement.setAttribute("data-theme", preset);
      try {
        localStorage.setItem(storageKey, t);
      } catch (e) {}
      // Update toggle aria state and announce
      if (toggleNode) {
        var isDark = t === "checktick-dark";
        toggleNode.setAttribute("aria-pressed", String(isDark));
        // Optional: reflect current mode in the control label
        var baseLabel =
          toggleNode.getAttribute("data-theme-toggle-label") || "Toggle theme";
        toggleNode.textContent = baseLabel;
      }
      if (statusNode) {
        var msg =
          t === "checktick-dark" ? "Dark theme enabled" : "Light theme enabled";
        statusNode.textContent = msg;
      }
    }

    // Apply at load
    applyTheme(theme);

    // Wire up toggle if present
    function nextTheme(current) {
      return current === "checktick-light"
        ? "checktick-dark"
        : "checktick-light";
    }

    document.addEventListener("DOMContentLoaded", function () {
      toggleNode = document.getElementById("admin-theme-toggle");
      statusNode = document.getElementById("admin-theme-status");
      if (toggleNode) {
        // Initialize aria-pressed according to current theme
        toggleNode.setAttribute(
          "aria-pressed",
          String(theme === "checktick-dark")
        );
        toggleNode.addEventListener(
          "click",
          function (e) {
            e.preventDefault();
            var current =
              document.documentElement.getAttribute("data-theme") ||
              defaultTheme;
            applyTheme(nextTheme(current));
          },
          true
        );
      }
    });
  } catch (e) {
    // noop
  }
})();
