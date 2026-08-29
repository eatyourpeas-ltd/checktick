/**
 * Repeating sections - allow participants to add/remove instances of a
 * repeatable group's questions, up to the configured maximum.
 *
 * Instance 0 is rendered server-side with the standard field names
 * (e.g. ``q_123``). Additional instances are cloned client-side and their
 * field names/ids are suffixed with ``__r{index}`` (e.g. ``q_123__r1``).
 * The backend collects all instances into a single ordered list per
 * repeatable question.
 */
(function () {
  "use strict";

  const form = document.querySelector("[data-survey-form]");
  if (!form) return;

  const REPEAT_SUFFIX = /__r\d+$/;

  function maxFor(container) {
    const m = container.dataset.repeatMax;
    if (m === undefined || m === "" || m === "null") return Infinity;
    const n = parseInt(m, 10);
    return isNaN(n) ? Infinity : n;
  }

  function minFor(container) {
    return Math.max(parseInt(container.dataset.repeatMin || "0", 10) || 0, 1);
  }

  function instancesOf(container) {
    return Array.from(container.querySelectorAll("[data-repeat-instance]"));
  }

  function isInstanceEmpty(instance) {
    const els = instance.querySelectorAll("input, select, textarea");
    for (const el of els) {
      if (el.type === "radio" || el.type === "checkbox") {
        if (el.checked) return false;
      } else if (el.tagName === "SELECT") {
        if (el.value) return false;
      } else if (el.value !== undefined && el.value !== "") {
        return false;
      }
    }
    return true;
  }

  function reindexToken(tok, suffix) {
    const base = String(tok).replace(REPEAT_SUFFIX, "");
    return base + suffix;
  }

  const REINDEX_ATTRS = [
    "name",
    "id",
    "aria-labelledby",
    "data-followup-trigger",
    "data-followup-field",
    "data-followup-target",
    "data-followup-select",
    "data-yesno-select",
    "data-name",
  ];

  function reindexInstance(instance, idx) {
    const suffix = idx > 0 ? "__r" + idx : "";
    const selector = REINDEX_ATTRS.map((a) => "[" + a + "]").join(",");
    instance.querySelectorAll(selector).forEach(function (el) {
      REINDEX_ATTRS.forEach(function (attr) {
        if (!el.hasAttribute(attr)) return;
        let val = el.getAttribute(attr);
        if (attr === "aria-labelledby") {
          val = val
            .split(/\s+/)
            .map(function (tok) {
              return reindexToken(tok, suffix);
            })
            .join(" ");
        } else {
          val = reindexToken(val, suffix);
        }
        el.setAttribute(attr, val);
      });
    });
    instance.dataset.repeatIndex = String(idx);
  }

  function clearInstance(instance) {
    instance.querySelectorAll("input, select, textarea").forEach(function (el) {
      if (el.type === "radio" || el.type === "checkbox") {
        el.checked = false;
      } else {
        el.value = "";
      }
    });
    // Hide any follow-up fields that were visible in the source instance
    instance.querySelectorAll("[data-followup-field]").forEach(function (el) {
      el.classList.add("hidden");
    });
  }

  function initInstanceWidgets(root) {
    // Likert range value display
    root.querySelectorAll('input[type="range"]').forEach(function (input) {
      const qid = input.id.replace("range_q_", "");
      const display = root.querySelector("#range_value_q_" + qid);
      if (display) {
        input.addEventListener("input", function () {
          display.textContent = input.value;
        });
      }
    });

    // Follow-up text inputs (mc_single / mc_multi)
    root.querySelectorAll("[data-followup-trigger]").forEach(function (trigger) {
      const inputName = trigger.getAttribute("name");
      const inputType = trigger.getAttribute("type");
      if (inputType === "radio") {
        const radios = root.querySelectorAll('input[name="' + inputName + '"]');
        radios.forEach(function (radio) {
          radio.addEventListener("change", function () {
            root
              .querySelectorAll('[data-followup-field^="' + inputName + '_"]')
              .forEach(function (f) {
                f.classList.add("hidden");
                const inp = f.querySelector("input");
                if (inp) inp.value = "";
              });
            if (this.checked) {
              const sel = this.dataset.followupTrigger;
              const sf = root.querySelector(
                '[data-followup-field="' + sel + '"]'
              );
              if (sf) sf.classList.remove("hidden");
            }
          });
        });
      } else if (inputType === "checkbox") {
        trigger.addEventListener("change", function () {
          const targetId = trigger.dataset.followupTrigger;
          const followup = root.querySelector(
            '[data-followup-field="' + targetId + '"]'
          );
          if (!followup) return;
          if (this.checked) followup.classList.remove("hidden");
          else {
            followup.classList.add("hidden");
            const inp = followup.querySelector("input");
            if (inp) inp.value = "";
          }
        });
      }
    });

    // Follow-up inputs for dropdown / yesno
    root
      .querySelectorAll("[data-followup-select], [data-yesno-select]")
      .forEach(function (select) {
        select.addEventListener("change", function () {
          const opt = this.options[this.selectedIndex];
          const targetId = opt ? opt.dataset.followupTarget : null;
          const selectId =
            this.dataset.followupSelect || this.dataset.yesnoSelect;
          root
            .querySelectorAll('[data-followup-field^="' + selectId + '_"]')
            .forEach(function (f) {
              f.classList.add("hidden");
              const inp = f.querySelector("input");
              if (inp) inp.value = "";
            });
          if (targetId) {
            const f = root.querySelector(
              '[data-followup-field="' + targetId + '"]'
            );
            if (f) f.classList.remove("hidden");
          }
        });
      });

    // Orderable lists
    if (window.Sortable) {
      root.querySelectorAll(".orderable-list").forEach(function (list) {
        new Sortable(list, {
          animation: 150,
          handle: ".drag-handle",
          forceFallback: true,
        });
      });
    }
  }

  function updateState(container) {
    const max = maxFor(container);
    const min = minFor(container);
    const instances = instancesOf(container);
    const addBtn = container.querySelector("[data-repeat-add]");
    const last = instances[instances.length - 1];
    const atMax = instances.length >= max;
    const lastEmpty = last ? isInstanceEmpty(last) : true;
    if (addBtn) {
      addBtn.disabled = atMax || lastEmpty;
    }
    instances.forEach(function (inst) {
      const rm = inst.querySelector("[data-repeat-remove]");
      if (rm) rm.style.display = instances.length <= min ? "none" : "";
    });
  }

  function addInstance(container) {
    const max = maxFor(container);
    const instances = instancesOf(container);
    if (instances.length >= max) return null;
    const last = instances[instances.length - 1];
    const clone = last.cloneNode(true);
    clearInstance(clone);
    const newIdx = instances.length;
    reindexInstance(clone, newIdx);
    const addBtn = container.querySelector("[data-repeat-add]");
    container.insertBefore(clone, addBtn ? addBtn.parentElement : null);
    initInstanceWidgets(clone);
    updateState(container);
    return clone;
  }

  function removeInstance(container, instance) {
    const min = minFor(container);
    const instances = instancesOf(container);
    if (instances.length <= min) return;
    instance.remove();
    instancesOf(container).forEach(function (inst, i) {
      reindexInstance(inst, i);
    });
    updateState(container);
  }

  function initContainer(container) {
    container.addEventListener("click", function (e) {
      const addBtn = e.target.closest("[data-repeat-add]");
      const rmBtn = e.target.closest("[data-repeat-remove]");
      if (addBtn && addBtn.disabled) return;
      if (addBtn) {
        e.preventDefault();
        addInstance(container);
      } else if (rmBtn) {
        e.preventDefault();
        removeInstance(container, rmBtn.closest("[data-repeat-instance]"));
      }
    });
    container.addEventListener("input", function () {
      updateState(container);
    });
    container.addEventListener("change", function () {
      updateState(container);
    });
    updateState(container);
  }

  document.querySelectorAll("[data-repeat-container]").forEach(initContainer);

  // Expose a small API for saved-answer restoration (see detail.html).
  window.SurveyRepeats = {
    addInstance: addInstance,
    findContainerForQuestion: function (questionId) {
      const qEl = document.querySelector(
        '[data-question-id="' + questionId + '"]'
      );
      return qEl ? qEl.closest("[data-repeat-container]") : null;
    },
  };
})();
