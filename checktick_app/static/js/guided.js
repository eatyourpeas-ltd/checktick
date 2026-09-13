/**
 * Guided layout — one question per screen with Next/Back navigation.
 *
 * This is a rendering layer on top of the existing survey pipeline. All
 * questions still render in the DOM (so branching, repeats, follow-ups,
 * and autosave all work unchanged); this module shows one step at a time
 * by toggling data attributes that the scoped CSS in detail.html reacts
 * to. It is deliberately layout-agnostic: it operates on whatever
 * [data-question-id] / [data-guided-extra] elements the pipeline
 * produced, so a future Delphi round allocator can reuse it without
 * changes (see docs/survey-layouts-technical.md §Guided layout).
 *
 * Visibility contract with branching.js:
 *  - branching.js sets inline `style.display` on [data-question-id]
 *    ("" = visible, "none" = hidden by a condition).
 *  - This module uses data attributes + stylesheet rules, never inline
 *    display, so the two never fight. A question hidden by branching
 *    stays hidden (inline none beats CSS); a question shown by branching
 *    but not current is hidden by the CSS rule (inline "" removes the
 *    inline style so the stylesheet display:none applies). The guided
 *    nav skips branching-hidden questions so the participant never
 *    lands on one.
 */

(function () {
  "use strict";

  const form = document.querySelector("form[data-guided]");
  if (!form) return;

  const navBar = form.querySelector("[data-guided-nav]");
  if (!navBar) return;

  const backBtn = navBar.querySelector("[data-guided-back]");
  const nextBtn = navBar.querySelector("[data-guided-next]");
  const submitBtn = navBar.querySelector("[data-guided-submit]");
  const indicator = navBar.querySelector("[data-guided-step-indicator]");

  let currentIdx = 0;

  /**
   * Collect every guided step in DOM order. A step is either a rendered
   * question ([data-question-id]) or an extra section ([data-guided-extra],
   * e.g. patient/professional details). Repeat clones add new
   * [data-question-id] elements; re-collect runs after DOM mutations.
   */
  function collectSteps() {
    const selectors = "[data-question-id], [data-guided-extra]";
    return Array.from(form.querySelectorAll(selectors));
  }

  /**
   * A step is "reachable" if branching has not hidden it. branching.js
   * hides questions by setting inline display:none; questions with a
   * SHOW condition start with inline display:none in the template and
   * are revealed by branching.js (inline ""). We treat any step whose
   * computed display is none as unreachable and skip it.
   *
   * [data-guided-extra] sections are never branching-controlled, so they
   * are always reachable.
   */
  function isReachable(step) {
    if (step.hasAttribute("data-guided-extra")) return true;
    return step.style.display !== "none";
  }

  function reachableSteps() {
    return collectSteps().filter(isReachable);
  }

  /**
   * Show a single step: mark it current, mark its ancestor group fieldset
   * and repeat instance as current, and clear the current markers from
   * everything else. The scoped CSS hides anything not marked current.
   */
  function showStep(step) {
    // Clear previous current markers.
    form
      .querySelectorAll("[data-guided-current]")
      .forEach((el) => el.removeAttribute("data-guided-current"));
    form
      .querySelectorAll("[data-guided-current-group]")
      .forEach((el) => el.removeAttribute("data-guided-current-group"));
    form
      .querySelectorAll("[data-guided-current-instance]")
      .forEach((el) => el.removeAttribute("data-guided-current-instance"));

    // Mark the step current.
    step.setAttribute("data-guided-current", "");

    // Mark the ancestor group fieldset (so its header shows).
    const group = step.closest("fieldset[data-guided-group]");
    if (group) group.setAttribute("data-guided-current-group", "");

    // Mark the ancestor repeat instance (so siblings are hidden).
    const instance = step.closest("[data-repeat-instance]");
    if (instance) instance.setAttribute("data-guided-current-instance", "");
  }

  function updateNav() {
    const steps = reachableSteps();
    if (steps.length === 0) return;
    if (currentIdx >= steps.length) currentIdx = steps.length - 1;
    if (currentIdx < 0) currentIdx = 0;

    showStep(steps[currentIdx]);

    // Step indicator: "Question X of Y" for question steps; extra sections
    // are counted in the total but labelled as a section.
    const total = steps.length;
    const isExtra = steps[currentIdx].hasAttribute("data-guided-extra");
    if (isExtra) {
      indicator.textContent = "";
    } else {
      // Count only question steps up to and including the current one for
      // the "X" number, so extra sections don't inflate the question count.
      let questionNo = 0;
      for (let i = 0; i <= currentIdx; i++) {
        if (!steps[i].hasAttribute("data-guided-extra")) questionNo++;
      }
      const totalQuestions = steps.filter(
        (s) => !s.hasAttribute("data-guided-extra")
      ).length;
      indicator.textContent = questionNo + " / " + totalQuestions;
    }

    const atFirst = currentIdx === 0;
    const atLast = currentIdx === steps.length - 1;
    backBtn.disabled = atFirst;
    backBtn.setAttribute("aria-disabled", atFirst ? "true" : "false");
    nextBtn.classList.toggle("hidden", atLast);
    if (submitBtn) submitBtn.classList.toggle("hidden", !atLast);

    // Focus the step's heading for screen readers. Defer until the browser
    // has applied the CSS display change.
    window.requestAnimationFrame(function () {
      const heading = step.querySelector("h2, legend, .card-title");
      if (heading && typeof heading.focus === "function") {
        heading.setAttribute("tabindex", "-1");
        heading.focus({ preventScroll: false });
      }
    });
  }

  function goTo(idx) {
    const steps = reachableSteps();
    if (idx < 0 || idx >= steps.length) return;
    currentIdx = idx;
    updateNav();
  }

  function next() {
    goTo(currentIdx + 1);
  }

  function back() {
    goTo(currentIdx - 1);
  }

  backBtn.addEventListener("click", back);
  nextBtn.addEventListener("click", next);

  // Keyboard: Left/Right arrows navigate, but only when the focus is not
  // inside an input (so editing text isn't hijacked).
  form.addEventListener("keydown", function (e) {
    const tag = (e.target.tagName || "").toLowerCase();
    if (["input", "textarea", "select"].includes(tag)) return;
    if (e.key === "ArrowRight") {
      e.preventDefault();
      next();
    } else if (e.key === "ArrowLeft") {
      e.preventDefault();
      back();
    }
  });

  // Re-collect and re-render when branching changes visibility or a
  // repeat instance is added/removed. branching.js runs on input/change;
  // a microtask delay lets it finish before we re-collect.
  function refreshAfterMutation() {
    // If the current step became unreachable (branching hid it), clamp.
    const steps = reachableSteps();
    const currentEl = steps[currentIdx];
    if (!currentEl) {
      // Find the nearest still-reachable step.
      currentIdx = Math.min(currentIdx, steps.length - 1);
    }
    updateNav();
  }

  let debounce;
  function debouncedRefresh() {
    clearTimeout(debounce);
    debounce = setTimeout(refreshAfterMutation, 0);
  }

  // Observe DOM mutations (repeat add/remove) and re-collect.
  if (typeof MutationObserver !== "undefined") {
    const observer = new MutationObserver(debouncedRefresh);
    observer.observe(form, { childList: true, subtree: true });
  }

  // Re-evaluate after branching runs (input/change events bubble to form).
  form.addEventListener("input", debouncedRefresh);
  form.addEventListener("change", debouncedRefresh);

  // Initial render.
  updateNav();
})();
