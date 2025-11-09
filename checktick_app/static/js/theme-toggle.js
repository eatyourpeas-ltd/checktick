(function () {
  const KEY = "checktick-theme"; // values: 'system' | 'checktick-light' | 'checktick-dark'
  const htmlEl = document.documentElement;
  const select = document.getElementById("theme-select");
  const ddBtn = document.getElementById("theme-dropdown-btn");
  const ddLabel = document.getElementById("theme-current-label");
  const media = window.matchMedia("(prefers-color-scheme: dark)");

  // Get actual daisyUI preset names from meta tag
  const presetsMeta = document.querySelector('meta[name="theme-presets"]');
  const presets = presetsMeta
    ? presetsMeta.content.split(",")
    : ["nord", "business"];
  const LIGHT_PRESET = presets[0] || "nord";
  const DARK_PRESET = presets[1] || "business";

  function normalize(pref) {
    switch (pref) {
      case "checktick":
      case "light":
        return "checktick-light";
      case "dark":
        return "checktick-dark";
      case "system":
      case "checktick-light":
      case "checktick-dark":
        return pref;
      default:
        return null;
    }
  }

  function effectiveTheme(pref) {
    if (pref === "system") {
      return media.matches ? "checktick-dark" : "checktick-light";
    }
    return pref || "checktick-light";
  }

  function themeToPreset(theme) {
    // Map logical theme names to actual daisyUI presets
    if (theme === "checktick-dark") {
      return DARK_PRESET;
    }
    return LIGHT_PRESET; // checktick-light or default
  }

  function applyTheme(pref) {
    const theme = effectiveTheme(normalize(pref) || pref);
    const preset = themeToPreset(theme);
    htmlEl.setAttribute("data-theme", preset);
  }

  function readSaved() {
    try {
      const raw = localStorage.getItem(KEY);
      return normalize(raw) || raw;
    } catch (_) {
      return null;
    }
  }

  function persist(pref) {
    try {
      localStorage.setItem(KEY, pref);
    } catch (_) {}
  }

  function labelFor(pref) {
    switch (pref) {
      case "checktick-light":
        return "Light";
      case "checktick-dark":
        return "Dark";
      case "system":
      default:
        return "System";
    }
  }

  function hydrate() {
    const saved = readSaved();
    if (saved) {
      applyTheme(saved);
      if (select) select.value = normalize(saved) || saved;
      if (ddLabel) ddLabel.textContent = labelFor(saved);
      return saved;
    }
    // default to current server-set theme, but set select to 'system' if it matches OS
    const current =
      normalize(htmlEl.getAttribute("data-theme")) || "checktick-light";
    const systemTheme = effectiveTheme("system");
    if (select) {
      select.value = current === systemTheme ? "system" : current;
    }
    if (ddLabel) {
      ddLabel.textContent = labelFor(
        current === systemTheme ? "system" : current
      );
    }
    // apply current as-is (server default) without persisting
    applyTheme(current);
    return null;
  }

  function onMediaChange() {
    const saved = readSaved();
    if (saved === "system" || !saved) {
      applyTheme("system");
      if (select && select.value === "system") {
        // keep select as 'system'; visual theme changes automatically
      }
    }
  }

  function init() {
    hydrate();
    // watch OS changes
    if (typeof media.addEventListener === "function") {
      media.addEventListener("change", onMediaChange);
    } else if (typeof media.addListener === "function") {
      // Safari
      media.addListener(onMediaChange);
    }

    if (select) {
      select.addEventListener("change", () => {
        const pref = select.value; // 'system' | 'checktick-light' | 'checktick-dark'
        applyTheme(pref);
        persist(pref);
        if (ddLabel) ddLabel.textContent = labelFor(pref);
      });
    }

    // Dropdown menu handling (use event delegation and pointerdown for reliability)
    if (ddBtn) {
      const dd = ddBtn.closest(".dropdown");
      const menu = dd ? dd.querySelector(".dropdown-content") : null;

      function setTheme(pref) {
        applyTheme(pref);
        persist(pref);
        if (ddLabel) ddLabel.textContent = labelFor(pref);
        if (select) select.value = pref;
        // update active marker
        if (menu) {
          menu
            .querySelectorAll("li")
            .forEach((li) => li.classList.remove("active"));
          const targetBtn = menu.querySelector(`[data-theme-choice="${pref}"]`);
          if (targetBtn) {
            const li = targetBtn.closest("li");
            if (li) li.classList.add("active");
          }
        }
        // close dropdown by blurring the button (focus-based dropdown)
        ddBtn.blur();
      }

      // hydrate active marker
      const current =
        readSaved() ||
        normalize(htmlEl.getAttribute("data-theme")) ||
        "checktick-light";
      if (menu) {
        const systemTheme = effectiveTheme("system");
        const prefShown = current === systemTheme ? "system" : current;
        menu
          .querySelectorAll("li")
          .forEach((li) => li.classList.remove("active"));
        const activeBtn = menu.querySelector(
          `[data-theme-choice="${prefShown}"]`
        );
        if (activeBtn) {
          const li = activeBtn.closest("li");
          if (li) li.classList.add("active");
        }
      }

      if (menu) {
        // Use pointerdown so the handler runs even if focus changes immediately
        menu.addEventListener("pointerdown", (e) => {
          const target = e.target.closest("[data-theme-choice]");
          if (!target) return;
          e.preventDefault();
          const pref = target.getAttribute("data-theme-choice");
          setTheme(pref);
        });
        // Fallback for click (some devices)
        menu.addEventListener("click", (e) => {
          const target = e.target.closest("[data-theme-choice]");
          if (!target) return;
          e.preventDefault();
          const pref = target.getAttribute("data-theme-choice");
          setTheme(pref);
        });
      }
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
