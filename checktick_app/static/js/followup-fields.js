/**
 * Handle dynamic show/hide of follow-up text inputs based on user selections
 * for multiple choice, dropdown, and yes/no questions
 */
(function () {
  function initFollowupFields() {
    // Handle radio and checkbox inputs (mc_single, mc_multi)
    const triggers = document.querySelectorAll("[data-followup-trigger]");
    triggers.forEach((trigger) => {
      const targetId = trigger.dataset.followupTrigger;
      const followupField = document.querySelector(
        `[data-followup-field="${targetId}"]`
      );

      if (!followupField) return;

      const inputName = trigger.getAttribute("name");
      const inputType = trigger.getAttribute("type");

      if (inputType === "radio") {
        // For radio buttons, listen to all radios with the same name
        const allRadios = document.querySelectorAll(
          `input[name="${inputName}"]`
        );
        allRadios.forEach((radio) => {
          radio.addEventListener("change", function () {
            // Hide all follow-up fields for this question
            const questionId = inputName; // e.g., "q_123"
            const allFollowups = document.querySelectorAll(
              `[data-followup-field^="${questionId}_"]`
            );
            allFollowups.forEach((field) => {
              field.classList.add("hidden");
              // Clear the input value when hiding
              const input = field.querySelector("input");
              if (input) input.value = "";
            });

            // Show the selected option's follow-up field if it exists
            if (this.checked) {
              const selectedTargetId = this.dataset.followupTrigger;
              const selectedFollowup = document.querySelector(
                `[data-followup-field="${selectedTargetId}"]`
              );
              if (selectedFollowup) {
                selectedFollowup.classList.remove("hidden");
              }
            }
          });
        });
      } else if (inputType === "checkbox") {
        // For checkboxes, toggle independently
        trigger.addEventListener("change", function () {
          if (this.checked) {
            followupField.classList.remove("hidden");
          } else {
            followupField.classList.add("hidden");
            // Clear the input value when hiding
            const input = followupField.querySelector("input");
            if (input) input.value = "";
          }
        });
      }
    });

    // Handle dropdown selects (dropdown, yesno)
    const selects = document.querySelectorAll(
      "[data-followup-select], [data-yesno-select]"
    );
    selects.forEach((select) => {
      select.addEventListener("change", function () {
        const selectedOption = this.options[this.selectedIndex];
        const targetId = selectedOption
          ? selectedOption.dataset.followupTarget
          : null;

        // Get the base question ID to find all related follow-up fields
        const selectId =
          this.dataset.followupSelect || this.dataset.yesnoSelect;

        // Hide all follow-up fields for this select
        const allFollowups = document.querySelectorAll(
          `[data-followup-field^="${selectId}_"]`
        );
        allFollowups.forEach((field) => {
          field.classList.add("hidden");
          // Clear the input value when hiding
          const input = field.querySelector("input");
          if (input) input.value = "";
        });

        // Show the selected option's follow-up field if it exists
        if (targetId) {
          const followupField = document.querySelector(
            `[data-followup-field="${targetId}"]`
          );
          if (followupField) {
            followupField.classList.remove("hidden");
          }
        }
      });
    });
    // Handle question-level follow-up: a single text box offered after all
    // options (used for dataset-backed option lists). Shown whenever any
    // selection is made for the question, hidden and cleared otherwise.
    const anyFields = document.querySelectorAll("[data-followup-any]");
    anyFields.forEach((field) => {
      const questionId = field.dataset.followupAny; // e.g. "q_123"
      const controls = document.querySelectorAll(`[name="${questionId}"]`);
      if (controls.length === 0) return;

      const first = controls[0];

      const showIfSelected = () => {
        const hasSelection = Array.from(controls).some(
          (el) =>
            (el.type === "checkbox" || el.type === "radio")
              ? el.checked
              : el.value !== ""
        );
        if (hasSelection) {
          field.classList.remove("hidden");
        } else {
          field.classList.add("hidden");
          const input = field.querySelector("input");
          if (input) input.value = "";
        }
      };

      if (first.tagName === "SELECT") {
        first.addEventListener("change", showIfSelected);
      } else {
        controls.forEach((el) => el.addEventListener("change", showIfSelected));
      }
    });
    // Dependent dropdowns (grouped single-choice, ``cascading`` mode): the
    // level-1 select (named q_<id>_group) reveals the selected group's
    // level-2 select (named q_<id> — the stored answer). Hidden level-2
    // selects are disabled so they never submit a stale value; a panel
    // whose select has a single option (a group with no sub-options) is
    // auto-answered when its group is chosen.
    document.querySelectorAll("[data-cascading-dropdown]").forEach((root) => {
      const qid = root.dataset.cascadingDropdown; // e.g. "q_123"
      const groupSelect = root.querySelector("[data-group-select]");
      if (!groupSelect) return;
      const panels = root.querySelectorAll("[data-group-panel]");
      const resetPanel = (panel) => {
        const select = panel.querySelector("select");
        if (select) {
          select.disabled = true;
          select.value = "";
        }
        panel
          .querySelectorAll(`[data-followup-field^="${qid}_"]`)
          .forEach((field) => {
            field.classList.add("hidden");
            const input = field.querySelector("input");
            if (input) input.value = "";
          });
      };
      groupSelect.addEventListener("change", function () {
        const chosen = this.options[this.selectedIndex];
        const panelId = chosen ? chosen.dataset.groupTarget : null;
        panels.forEach(resetPanel);
        if (!panelId) return;
        const panel = root.querySelector(`[data-group-panel="${panelId}"]`);
        if (!panel) return;
        panel.classList.remove("hidden");
        const select = panel.querySelector("select");
        if (select) {
          select.disabled = false;
          // A single-option select means the group has no sub-options —
          // selecting the group is itself the answer.
          if (select.options.length === 1) select.value = select.options[0].value;
        }
      });
    });

    // Cascading grouped single-choice (``cascading_radios`` mode): level-1
    // group radios (named q_<id>_group) reveal the selected group's
    // sub-option panel. The stored answer is the leaf radio (named q_<id>)
    // — the group pick is transient UI state. A panel with exactly one
    // radio (a group with no sub-options) is auto-selected so every group
    // yields an answer.
    document.querySelectorAll("[data-cascading]").forEach((root) => {
      const qid = root.dataset.cascading; // e.g. "q_123"
      const panels = root.querySelectorAll("[data-group-panel]");
      const clearLeaves = () => {
        root.querySelectorAll(`input[name="${qid}"]`).forEach((leaf) => {
          if (leaf.type === "radio") leaf.checked = false;
        });
        // Clear any visible follow-up inputs too.
        root
          .querySelectorAll(`[data-followup-field^="${qid}_"]`)
          .forEach((field) => {
            field.classList.add("hidden");
            const input = field.querySelector("input");
            if (input) input.value = "";
          });
      };
      root.querySelectorAll("[data-group-trigger]").forEach((trigger) => {
        trigger.addEventListener("change", function () {
          if (!this.checked) return;
          const panelId = this.dataset.groupTrigger;
          panels.forEach((panel) => panel.classList.add("hidden"));
          clearLeaves();
          const panel = root.querySelector(`[data-group-panel="${panelId}"]`);
          if (!panel) return;
          panel.classList.remove("hidden");
          const radios = panel.querySelectorAll('input[type="radio"]');
          if (radios.length === 1) radios[0].checked = true;
        });
      });
    });
  }

  // Initialize on page load
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initFollowupFields);
  } else {
    initFollowupFields();
  }
})();
