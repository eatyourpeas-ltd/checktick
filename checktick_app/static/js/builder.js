(function () {
  let currentEditingRow = null;
  let currentEditingCard = null;
  let currentEditButton = null;
  let builderEditorCard = null;
  let editButtonsDelegated = false;

  function csrfToken() {
    const name = "csrftoken";
    const m = document.cookie.match(new RegExp("(^| )" + name + "=([^;]+)"));
    return m ? m[2] : "";
  }

  function scheduleDismissals(root) {
    const scope = root || document;
    const alerts = scope.querySelectorAll("#questions-list .alert");
    alerts.forEach((el) => {
      if (el.dataset.autodismissBound) return;
      el.dataset.autodismissBound = "1";
      setTimeout(() => {
        el.classList.add("transition-opacity", "duration-700");
        el.classList.add("opacity-0");
        setTimeout(() => {
          if (el && el.parentElement) el.remove();
        }, 800);
      }, 1500);
    });
  }

  function initSortable(container) {
    bindEditButtons();
    const el = container.querySelector("#questions-draggable");
    if (!el || el.dataset.sortableBound) return;
    el.dataset.sortableBound = "1";
    new Sortable(el, {
      handle: "[data-drag-handle]",
      filter: "[data-drag-ignore]",
      preventOnFilter: false,
      animation: 150,
      forceFallback: true,
      onEnd: function () {
        const ids = Array.from(el.querySelectorAll("[data-qid]")).map(
          (li) => li.dataset.qid
        );
        const body = new URLSearchParams({ order: ids.join(",") });
        fetch(
          el.dataset.reorderUrl ||
            window.location.pathname.replace(/\/$/, "") + "/questions/reorder",
          {
            method: "POST",
            headers: {
              "Content-Type": "application/x-www-form-urlencoded",
              "X-CSRFToken": csrfToken(),
              "X-Requested-With": "XMLHttpRequest",
            },
            body,
          }
        )
          .then((resp) => {
            if (!resp.ok) {
              console.error("Failed to persist question order", resp.status);
              return;
            }
            renumberQuestions(el);
            if (typeof window.showToast === "function") {
              window.showToast("Order saved", "success");
            }
          })
          .catch((err) => {
            console.error("Error persisting question order", err);
          });
        bindEditButtons(document);
      },
    });
  }

  function renumberQuestions(scope) {
    const root = scope || document;
    const items = root.querySelectorAll("#questions-draggable > li[data-qid]");
    let i = 1;
    items.forEach((li) => {
      const badge = li.querySelector(".q-number");
      if (badge) {
        badge.textContent = String(i);
      }
      i += 1;
    });
  }

  function initConditionForms(scope) {
    const root = scope || document;
    const forms = root.querySelectorAll("[data-condition-form]");
    forms.forEach((form) => {
      if (form.dataset.conditionBound) return;
      form.dataset.conditionBound = "1";

      const operatorSelect = form.querySelector("[data-condition-operator]");
      const valueWrapper = form.querySelector("[data-condition-value]");
      const valueInput = form.querySelector('input[name="value"]');
      const actionSelect = form.querySelector('select[name="action"]');
      const targetFieldset = form.querySelector("[data-target-fieldset]");
      const questionSelect = form.querySelector(
        '[data-target-select="question"]'
      );

      const toggleValueField = () => {
        if (!operatorSelect) return;
        const option = operatorSelect.options[operatorSelect.selectedIndex];
        const requiresValue = option
          ? option.getAttribute("data-requires-value") !== "0"
          : true;
        if (valueWrapper) {
          valueWrapper.classList.toggle("hidden", !requiresValue);
        }
        if (valueInput) {
          valueInput.disabled = !requiresValue;
        }
      };

      const toggleTargetFields = () => {
        // Check if END_SURVEY is selected - hide target field
        const isEndSurvey = actionSelect && actionSelect.value === "end_survey";

        if (targetFieldset) {
          targetFieldset.classList.toggle("hidden", isEndSurvey);
        }

        if (questionSelect) {
          questionSelect.disabled = isEndSurvey;
        }
      };

      if (operatorSelect) {
        operatorSelect.addEventListener("change", toggleValueField);
      }
      if (actionSelect) {
        actionSelect.addEventListener("change", toggleTargetFields);
      }

      toggleValueField();
      toggleTargetFields();
    });
  }

  function updateFormModeUI(form, mode) {
    const isEdit = mode === "edit";
    form.dataset.mode = mode;
    const toggleHidden = (selector, hidden) => {
      form.querySelectorAll(selector).forEach((el) => {
        el.classList.toggle("hidden", hidden);
      });
    };
    toggleHidden('[data-editor-label="headline-add"]', isEdit);
    toggleHidden('[data-editor-label="headline-edit"]', !isEdit);
    toggleHidden('[data-editor-label="submit-add"]', isEdit);
    toggleHidden('[data-editor-label="submit-edit"]', !isEdit);
    toggleHidden('[data-editor-label="edit-hint"]', !isEdit);
    const cancelBtn = form.querySelector('[data-action="cancel-edit"]');
    if (cancelBtn) cancelBtn.classList.toggle("hidden", !isEdit);
  }

  function focusFirstField(form) {
    const firstField = form.querySelector(
      "input:not([type=hidden]):not([disabled]), textarea, select"
    );
    if (firstField && firstField.focus) {
      firstField.focus();
    }
  }

  function exitEditMode(form, options) {
    if (!form) return;
    const opts = Object.assign({ reset: false, focus: false }, options || {});
    const createUrl =
      form.dataset.createUrl ||
      form.getAttribute("data-create-url") ||
      form.getAttribute("hx-post");
    if (createUrl) {
      form.setAttribute("hx-post", createUrl);
    }
    const createTarget =
      form.dataset.createTarget ||
      form.getAttribute("data-create-target") ||
      form.getAttribute("hx-target") ||
      "";
    if (createTarget) {
      form.setAttribute("hx-target", createTarget);
    } else {
      form.removeAttribute("hx-target");
    }
    const createSwap =
      form.dataset.createSwap ||
      form.getAttribute("data-create-swap") ||
      form.getAttribute("hx-swap") ||
      "";
    if (createSwap) {
      form.setAttribute("hx-swap", createSwap);
    } else {
      form.removeAttribute("hx-swap");
    }
    delete form.dataset.editingQuestionId;
    delete form.dataset.currentEditUrl;
    if (currentEditingCard) {
      currentEditingCard.classList.remove("is-active");
    }
    if (builderEditorCard) {
      builderEditorCard.classList.remove("is-active");
    }
    if (currentEditingRow && currentEditingRow.parentElement) {
      currentEditingRow.classList.remove("is-editing");
    }
    if (currentEditButton) {
      currentEditButton.classList.remove("is-active");
    }
    currentEditingRow = null;
    currentEditingCard = null;
    currentEditButton = null;
    updateFormModeUI(form, "add");
    if (opts.reset) {
      form.reset();
      if (typeof form._refreshCreateToggles === "function") {
        form._refreshCreateToggles();
      } else {
        const evtChange = new Event("change", { bubbles: true });
        const checkedType = form.querySelector('input[name="type"]:checked');
        if (checkedType) checkedType.dispatchEvent(evtChange);
      }
    }
    if (opts.focus) {
      focusFirstField(form);
    }
  }

  function populateFormForPayload(form, payload) {
    if (!form || !payload) return;
    const textInput = form.querySelector('input[name="text"]');
    if (textInput) {
      textInput.value = payload.text || "";
    }

    const typeInput = payload.type
      ? form.querySelector(`input[name="type"][value="${payload.type}"]`)
      : null;
    if (typeInput) {
      typeInput.checked = true;
      typeInput.dispatchEvent(new Event("change", { bubbles: true }));
    } else if (typeof form._refreshCreateToggles === "function") {
      form._refreshCreateToggles();
    }

    const requiredInput = form.querySelector('input[name="required"]');
    if (requiredInput) {
      requiredInput.checked = Boolean(payload.required);
    }

    const optionsField = form.querySelector('textarea[name="options"]');
    if (optionsField) {
      if (Array.isArray(payload.options)) {
        optionsField.value = payload.options.join("\n");
      } else if (typeof payload.options === "string") {
        optionsField.value = payload.options;
      } else {
        optionsField.value = "";
      }
    }

    // Restore prefilled dataset selection if present
    if (payload.type === "dropdown" && payload.prefilled_dataset) {
      const prefilledCheckbox = form.querySelector(
        'input[name="use_prefilled_options"]'
      );
      const prefilledDataset = form.querySelector(
        'select[name="prefilled_dataset"]'
      );

      if (prefilledCheckbox && prefilledDataset) {
        prefilledCheckbox.checked = true;
        prefilledCheckbox.dispatchEvent(new Event("change", { bubbles: true }));

        // Set the dataset value
        prefilledDataset.value = payload.prefilled_dataset;

        // Store the dataset key on the textarea for later save
        if (optionsField) {
          optionsField.dataset.prefilledDataset = payload.prefilled_dataset;
        }
      }
    }

    if (payload.type === "text") {
      const fmt = payload.text_format || payload.textFormat || "free";
      const fmtInput = form.querySelector(
        `input[name="text_format"][value="${fmt}"]`
      );
      if (fmtInput) fmtInput.checked = true;
    }

    if (payload.type === "likert") {
      const likertMode =
        payload.likert_mode || payload.likertMode || "categories";
      const likertRadio = form.querySelector(
        `input[name="likert_mode"][value="${likertMode}"]`
      );
      if (likertRadio) {
        likertRadio.checked = true;
        likertRadio.dispatchEvent(new Event("change", { bubbles: true }));
      }
      if (likertMode === "number") {
        const minField = form.querySelector('input[name="likert_min"]');
        const maxField = form.querySelector('input[name="likert_max"]');
        const leftField = form.querySelector('input[name="likert_left_label"]');
        const rightField = form.querySelector(
          'input[name="likert_right_label"]'
        );
        if (minField)
          minField.value =
            payload.likert_min !== undefined && payload.likert_min !== null
              ? payload.likert_min
              : "1";
        if (maxField)
          maxField.value =
            payload.likert_max !== undefined && payload.likert_max !== null
              ? payload.likert_max
              : "5";
        if (leftField) leftField.value = payload.likert_left_label || "";
        if (rightField) rightField.value = payload.likert_right_label || "";
      } else {
        const catsField = form.querySelector(
          'textarea[name="likert_categories"]'
        );
        if (catsField) {
          if (Array.isArray(payload.likert_categories)) {
            catsField.value = payload.likert_categories.join("\n");
          } else if (typeof payload.likert_categories === "string") {
            catsField.value = payload.likert_categories;
          } else {
            catsField.value = "";
          }
        }
      }
    }

    // Restore follow-up configuration for MC/Dropdown/Orderable questions
    if (
      payload.type === "mc_single" ||
      payload.type === "mc_multi" ||
      payload.type === "dropdown" ||
      payload.type === "orderable"
    ) {
      if (
        typeof form._populateFollowupOptions === "function" &&
        payload.followup_config
      ) {
        // Convert followup_config object to expected format
        const followupConfig = {};
        for (const [key, value] of Object.entries(payload.followup_config)) {
          followupConfig[parseInt(key)] = value;
        }
        form._populateFollowupOptions(optionsField.value, followupConfig);
      } else if (typeof form._populateFollowupOptions === "function") {
        form._populateFollowupOptions(optionsField.value, null);
      }
    }

    // Restore follow-up configuration for Yes/No questions
    if (payload.type === "yesno" && payload.yesno_followup_config) {
      const config = payload.yesno_followup_config;

      // Yes followup
      const yesCheckbox = form.querySelector(
        'input[name="yesno_yes_followup"]'
      );
      const yesLabel = form.querySelector(
        'input[name="yesno_yes_followup_label"]'
      );
      if (yesCheckbox && config.yes) {
        yesCheckbox.checked = config.yes.enabled || false;
      }
      if (yesLabel && config.yes) {
        yesLabel.value = config.yes.label || "";
      }

      // No followup
      const noCheckbox = form.querySelector('input[name="yesno_no_followup"]');
      const noLabel = form.querySelector(
        'input[name="yesno_no_followup_label"]'
      );
      if (noCheckbox && config.no) {
        noCheckbox.checked = config.no.enabled || false;
      }
      if (noLabel && config.no) {
        noLabel.value = config.no.label || "";
      }
    }

    // Restore image upload UI for image choice questions
    if (payload.type === "image") {
      if (typeof form._showImageUploadUI === "function" && payload.id) {
        form._showImageUploadUI(
          payload.id,
          payload.group_id || null,
          payload.survey_slug || null,
          payload.images || []
        );
      }
    } else {
      if (typeof form._hideImageUploadUI === "function") {
        form._hideImageUploadUI();
      }
    }

    const groupSelect = form.querySelector('select[name="group_id"]');
    if (groupSelect) {
      if (payload.group_id) {
        groupSelect.value = String(payload.group_id);
      } else {
        groupSelect.value = "";
      }
    }

    if (textInput && textInput.focus) {
      textInput.focus();
    }
  }

  function enterEditMode(form, payload, button, editUrl) {
    if (!form || !payload) return;
    if (!form.dataset.createUrl) {
      form.dataset.createUrl =
        form.getAttribute("data-create-url") ||
        form.getAttribute("hx-post") ||
        "";
    }
    if (!form.dataset.createTarget) {
      form.dataset.createTarget =
        form.getAttribute("data-create-target") ||
        form.getAttribute("hx-target") ||
        "";
    }
    if (!form.dataset.createSwap) {
      form.dataset.createSwap =
        form.getAttribute("data-create-swap") ||
        form.getAttribute("hx-swap") ||
        "outerHTML";
    }
    const destination = editUrl;
    if (destination) {
      form.setAttribute("hx-post", destination);
      form.dataset.currentEditUrl = destination;
    } else {
      delete form.dataset.currentEditUrl;
    }
    form.dataset.editingQuestionId =
      payload.id != null ? String(payload.id) : "";

    if (payload.id != null) {
      form.setAttribute("hx-target", `#question-row-${payload.id}`);
      form.setAttribute("hx-swap", "outerHTML");
    }

    const nextRow = button.closest("li");
    const nextCard = nextRow
      ? nextRow.querySelector("[data-question-card]")
      : null;

    if (!builderEditorCard) {
      builderEditorCard = form.closest("[data-builder-editor-card]") || null;
    }

    if (currentEditButton && currentEditButton !== button) {
      currentEditButton.classList.remove("is-active");
    }
    currentEditButton = button;
    if (currentEditButton) {
      currentEditButton.classList.add("is-active");
    }

    if (currentEditingCard && currentEditingCard !== nextCard) {
      currentEditingCard.classList.remove("is-active");
    }
    if (currentEditingRow && currentEditingRow !== nextRow) {
      currentEditingRow.classList.remove("is-editing");
    }

    currentEditingRow = nextRow;
    currentEditingCard = nextCard;
    if (currentEditingRow) {
      currentEditingRow.classList.add("is-editing");
    }
    if (currentEditingCard) {
      currentEditingCard.classList.add("is-active");
    }
    if (builderEditorCard) {
      builderEditorCard.classList.add("is-active");
    }

    updateFormModeUI(form, "edit");
    form.reset();
    if (typeof form._refreshCreateToggles === "function") {
      form._refreshCreateToggles();
    }
    populateFormForPayload(form, payload);
    form.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function handleEditButtonClick(btn) {
    const form = document.getElementById("create-question-form");
    if (!form || !document.body.contains(btn)) return;

    if (currentEditButton === btn && btn.classList.contains("is-active")) {
      exitEditMode(form, { reset: true, focus: true });
      return;
    }

    const payloadId = btn.dataset.payloadId;
    if (!payloadId) return;
    const scriptEl = document.getElementById(payloadId);
    if (!scriptEl) return;
    const raw = (scriptEl.textContent || "").trim();
    if (!raw) {
      console.error("Question payload was empty", scriptEl);
      return;
    }
    let payload;
    try {
      payload = JSON.parse(raw);
      if (typeof payload === "string") {
        payload = JSON.parse(payload);
      }
    } catch (err) {
      console.error("Failed to parse question payload", err);
      return;
    }

    const base = form.dataset.editUrlBase || "";
    const explicitUrl = btn.dataset.editUrl;
    const questionId =
      payload && payload.id != null ? String(payload.id) : null;
    let editUrl = explicitUrl || null;
    if (!editUrl && base && questionId) {
      editUrl = base.replace(/\/$/, "") + "/" + questionId + "/edit";
    }
    if (!editUrl) {
      console.error("Could not determine edit URL for question", payload);
      return;
    }

    enterEditMode(form, payload, btn, editUrl);
  }

  function bindEditButtons() {
    if (editButtonsDelegated) return;
    editButtonsDelegated = true;
    document.addEventListener("click", function (evt) {
      const btn = evt.target.closest('button[data-action="edit-question"]');
      if (!btn) return;
      evt.preventDefault();
      handleEditButtonClick(btn);
    });
  }

  function bindCancelButton(form) {
    if (!form) return;
    const cancelBtn = form.querySelector('[data-action="cancel-edit"]');
    if (!cancelBtn || cancelBtn.dataset.bound) return;
    cancelBtn.dataset.bound = "1";
    cancelBtn.addEventListener("click", function () {
      exitEditMode(form, { reset: true, focus: true });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    initSortable(document);
    scheduleDismissals(document);
    initCreateFormToggles();
    renumberQuestions(document);
    bindEditButtons();
    bindCancelButton(document.getElementById("create-question-form"));
    initConditionForms(document);
  });

  // Add CSRF header to all HTMX requests and coerce edit submissions to the correct endpoint
  document.body.addEventListener("htmx:configRequest", function (evt) {
    const detail = evt.detail || {};
    const headers = detail.headers || (detail.headers = {});
    headers["X-CSRFToken"] = csrfToken();

    const src = detail.elt || null;
    if (!src) return;
    const form =
      src.id === "create-question-form"
        ? src
        : src.closest && src.closest("#create-question-form");
    if (!form) return;

    const editingId = form.dataset.editingQuestionId || "";
    if (!editingId) return;

    const explicitUrl = form.dataset.currentEditUrl || "";
    const base = form.dataset.editUrlBase || "";
    let editUrl = explicitUrl;
    if (!editUrl && base) {
      editUrl = base.replace(/\/$/, "") + "/" + editingId + "/edit";
    }
    if (editUrl) {
      detail.path = editUrl;
      headers["HX-Request-Path"] = editUrl;
    }
    const targetSelector = `#question-row-${editingId}`;
    headers["HX-Target"] = targetSelector;
    if (!detail.target) {
      const explicitTarget = document.querySelector(targetSelector);
      if (explicitTarget) {
        detail.target = explicitTarget;
      }
    }
  });

  // Disable the Add button while submitting to avoid double posts
  document.body.addEventListener("htmx:beforeRequest", function (evt) {
    const src = evt.detail && evt.detail.elt ? evt.detail.elt : null;
    const form = document.getElementById("create-question-form");
    if (
      src &&
      form &&
      (src === form || (src.closest && src.closest("#create-question-form")))
    ) {
      const btn = form.querySelector('button[type="submit"]');
      if (btn) btn.disabled = true;
    }
  });
  // Re-init Sortable after swaps that touch the questions list
  document.body.addEventListener("htmx:afterSwap", function (evt) {
    const target = (evt.detail && evt.detail.target) || evt.target;
    if (!target) return;
    if (
      target.id === "questions-list" ||
      (target.closest && target.closest("#questions-list"))
    ) {
      initSortable(document);
      scheduleDismissals(document);
      renumberQuestions(document);
      initConditionForms(document);
      // If this swap was triggered by the create-question form submission, reset the form
      const src = evt.detail && evt.detail.elt ? evt.detail.elt : null;
      const form = document.getElementById("create-question-form");
      if (
        src &&
        form &&
        (src === form || (src.closest && src.closest("#create-question-form")))
      ) {
        exitEditMode(form, { reset: true, focus: true });
      }
    }
    // Re-bind toggles for the create form if present
    if (document.getElementById("create-question-form")) {
      initCreateFormToggles();
      bindCancelButton(document.getElementById("create-question-form"));
    }
    bindEditButtons();
    initConditionForms(target);
  });

  // Also reset form after the request completes successfully, even if no swap occurred
  document.body.addEventListener("htmx:afterRequest", function (evt) {
    const src = evt.detail && evt.detail.elt ? evt.detail.elt : null;
    if (
      !src ||
      !(
        src.id === "create-question-form" ||
        (src.closest && src.closest("#create-question-form"))
      )
    )
      return;
    const xhr = evt.detail && evt.detail.xhr ? evt.detail.xhr : null;
    if (xhr && xhr.status >= 200 && xhr.status < 300) {
      const form = document.getElementById("create-question-form") || src;
      if (!form) return;
      exitEditMode(form, { reset: true, focus: true });
    }
    // Always re-enable submit button after request completes
    const form = document.getElementById("create-question-form") || src;
    if (form) {
      const btn = form.querySelector('button[type="submit"]');
      if (btn) btn.disabled = false;
    }
  });

  document.addEventListener("pointerdown", function (evt) {
    const form = document.getElementById("create-question-form");
    if (!form || !form.dataset.editingQuestionId) return;
    const target = evt.target;
    if (!target) return;
    const activeCard = currentEditingCard;
    const editorCard =
      builderEditorCard || form.closest("[data-builder-editor-card]") || null;
    if (
      (activeCard && (activeCard === target || activeCard.contains(target))) ||
      (editorCard && (editorCard === target || editorCard.contains(target))) ||
      (currentEditButton &&
        (currentEditButton === target || currentEditButton.contains(target)))
    ) {
      return;
    }
    exitEditMode(form, { reset: true, focus: false });
  });

  function initCreateFormToggles() {
    const form = document.getElementById("create-question-form");
    if (!form || form.dataset.togglesBound) return;
    form.dataset.togglesBound = "1";

    const textSection = form.querySelector('[data-section="text-options"]');
    const optsSection = form.querySelector('[data-section="options"]');
    const likertSection = form.querySelector('[data-section="likert"]');
    const yesnoFollowupSection = form.querySelector(
      '[data-section="yesno-followup"]'
    );
    const imageOptionsSection = form.querySelector(
      '[data-section="image-options"]'
    );
    const likertCat = likertSection
      ? likertSection.querySelector('[data-likert="categories"]')
      : null;
    const likertNum = likertSection
      ? likertSection.querySelector('[data-likert="number"]')
      : null;

    // Prefilled dataset controls
    const prefilledToggle = form.querySelector("[data-prefilled-toggle]");
    const prefilledSection = form.querySelector("[data-prefilled-section]");
    const prefilledContainer = form.querySelector("[data-prefilled-container]");
    const prefilledDataset = form.querySelector("[data-prefilled-dataset]");
    const loadDatasetBtn = form.querySelector("[data-load-dataset]");
    const optionsTextarea = form.querySelector('textarea[name="options"]');

    // Image upload controls
    const imageUploadContainer = form.querySelector(
      "[data-image-upload-container]"
    );
    const imageUploadPlaceholder = form.querySelector(
      "[data-image-upload-placeholder]"
    );
    const imageList = form.querySelector("[data-image-list]");
    const imageUploadInput = form.querySelector("[data-image-upload-input]");
    const imageLabelInput = form.querySelector("[data-image-label-input]");
    const uploadImageBtn = form.querySelector("[data-upload-image-btn]");

    // Follow-up controls
    const followupContainer = form.querySelector(
      "[data-options-followup-container]"
    );
    const followupList = form.querySelector("[data-followup-options-list]");
    const refreshFollowupBtn = form.querySelector(
      "[data-refresh-followup-options]"
    );

    function refresh() {
      const checked = form.querySelector('input[name="type"]:checked');
      const type = checked ? checked.value : null;
      if (!type) return;
      const isText = type === "text";
      const isImage = type === "image";
      const isMC =
        type === "mc_single" ||
        type === "mc_multi" ||
        type === "dropdown" ||
        type === "orderable";
      const isDropdown = type === "dropdown";
      const isLikert = type === "likert";
      const isYesNo = type === "yesno";

      // Show/hide follow-up for mc/dropdown/orderable (not image or likert)
      const showFollowup =
        type === "mc_single" ||
        type === "mc_multi" ||
        type === "dropdown" ||
        type === "orderable";

      if (textSection) textSection.classList.toggle("hidden", !isText);
      if (optsSection) optsSection.classList.toggle("hidden", !isMC);
      if (likertSection) likertSection.classList.toggle("hidden", !isLikert);
      if (yesnoFollowupSection)
        yesnoFollowupSection.classList.toggle("hidden", !isYesNo);
      if (imageOptionsSection)
        imageOptionsSection.classList.toggle("hidden", !isImage);

      // Show/hide follow-up container within options section
      if (followupContainer) {
        followupContainer.classList.toggle("hidden", !showFollowup);
      }

      // Only show prefilled options for dropdown type
      if (prefilledContainer) {
        prefilledContainer.classList.toggle("hidden", !isDropdown);
      }
      // Reset prefilled checkbox if switching away from dropdown
      if (!isDropdown && prefilledToggle && prefilledToggle.checked) {
        prefilledToggle.checked = false;
        if (prefilledSection) {
          prefilledSection.classList.add("hidden");
        }
        if (prefilledDataset) {
          prefilledDataset.value = "";
        }
      }

      if (isLikert && likertSection) {
        const modeChecked = form.querySelector(
          'input[name="likert_mode"]:checked'
        );
        const mode = modeChecked ? modeChecked.value : "categories";
        if (likertCat)
          likertCat.classList.toggle("hidden", mode !== "categories");
        if (likertNum) likertNum.classList.toggle("hidden", mode !== "number");
      }
    }

    // Function to populate follow-up options based on textarea content
    function populateFollowupOptions(optionsText, followupConfig) {
      if (!followupList) return;

      const lines = (optionsText || "")
        .split("\n")
        .map((s) => s.trim())
        .filter((s) => s);
      if (lines.length === 0) {
        followupList.innerHTML =
          '<p class="text-xs opacity-60">Enter options above first</p>';
        return;
      }

      const html = lines
        .map((line, idx) => {
          const isEnabled =
            followupConfig &&
            followupConfig[idx] &&
            followupConfig[idx].enabled;
          const label =
            followupConfig && followupConfig[idx]
              ? followupConfig[idx].label
              : "Please elaborate";

          return `
          <div class="flex items-start gap-2 p-2 bg-base-100 rounded border border-base-300">
            <input type="checkbox" class="checkbox checkbox-sm mt-1" name="option_${idx}_followup" id="option-${idx}-followup" ${
            isEnabled ? "checked" : ""
          } />
            <div class="flex-1 min-w-0">
              <label for="option-${idx}-followup" class="text-sm font-medium cursor-pointer block truncate" title="${line}">${line}</label>
              <input type="text" name="option_${idx}_followup_label" class="input input-xs input-bordered w-full mt-1" placeholder="Follow-up label..." value="${label}" />
            </div>
          </div>
        `;
        })
        .join("");

      followupList.innerHTML = html;
    }

    // Refresh follow-up options button
    if (refreshFollowupBtn && optionsTextarea) {
      refreshFollowupBtn.addEventListener("click", function () {
        populateFollowupOptions(optionsTextarea.value, null);
      });
    }

    // Prefilled dataset toggle handler
    if (prefilledToggle && prefilledSection) {
      prefilledToggle.addEventListener("change", function () {
        const isChecked = prefilledToggle.checked;
        prefilledSection.classList.toggle("hidden", !isChecked);
        if (!isChecked && prefilledDataset) {
          prefilledDataset.value = "";
        }
      });
    }

    // Load dataset button handler
    if (loadDatasetBtn && prefilledDataset && optionsTextarea) {
      loadDatasetBtn.addEventListener("click", async function () {
        const datasetKey = prefilledDataset.value;
        if (!datasetKey) {
          if (typeof window.showToast === "function") {
            window.showToast("Please select a dataset first", "error");
          } else {
            alert("Please select a dataset first");
          }
          return;
        }

        // Show loading state with spinner
        loadDatasetBtn.disabled = true;
        const originalContent = loadDatasetBtn.innerHTML;
        loadDatasetBtn.innerHTML =
          '<span class="loading loading-spinner loading-xs"></span> Loading...';

        try {
          const response = await fetch(`/api/datasets/${datasetKey}/`, {
            method: "GET",
            headers: {
              "Content-Type": "application/json",
              "X-CSRFToken": csrfToken(),
            },
            credentials: "same-origin",
          });

          if (!response.ok) {
            throw new Error(`Failed to load dataset: ${response.statusText}`);
          }

          const data = await response.json();
          if (data.options && Array.isArray(data.options)) {
            optionsTextarea.value = data.options.join("\n");
            // Store the dataset key as a data attribute for later retrieval
            optionsTextarea.dataset.prefilledDataset = datasetKey;
            // Also refresh follow-up options
            populateFollowupOptions(optionsTextarea.value, null);
            if (typeof window.showToast === "function") {
              window.showToast(
                `Loaded ${data.options.length} options`,
                "success"
              );
            }
          } else {
            throw new Error("Invalid response format");
          }
        } catch (error) {
          console.error("Error loading dataset:", error);
          if (typeof window.showToast === "function") {
            window.showToast("Failed to load dataset options", "error");
          } else {
            alert("Failed to load dataset options: " + error.message);
          }
        } finally {
          // Restore button state
          loadDatasetBtn.disabled = false;
          loadDatasetBtn.innerHTML = originalContent;
        }
      });
    }

    // Expose refresh and populate functions so we can call them externally
    form._refreshCreateToggles = refresh;
    form._populateFollowupOptions = populateFollowupOptions;

    // Image upload handling functions
    let currentQuestionId = null;
    let currentGroupId = null;
    let currentSurveySlug = null;

    function getImageUploadUrl() {
      if (!currentSurveySlug || !currentQuestionId) return null;
      if (currentGroupId) {
        return `/surveys/${currentSurveySlug}/builder/groups/${currentGroupId}/questions/${currentQuestionId}/images/upload`;
      }
      return `/surveys/${currentSurveySlug}/builder/questions/${currentQuestionId}/images/upload`;
    }

    function getImageDeleteUrl(imageId) {
      if (!currentSurveySlug || !currentQuestionId) return null;
      if (currentGroupId) {
        return `/surveys/${currentSurveySlug}/builder/groups/${currentGroupId}/questions/${currentQuestionId}/images/${imageId}/delete`;
      }
      return `/surveys/${currentSurveySlug}/builder/questions/${currentQuestionId}/images/${imageId}/delete`;
    }

    function renderImage(img) {
      return `
        <div class="relative group w-16 h-16" data-image-id="${
          img.id
        }" title="${img.label || "Image option"}">
          <img src="${img.url}" alt="${
        img.label || ""
      }" class="w-16 h-16 object-cover rounded border border-base-300" />
          <div class="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity rounded flex items-center justify-center">
            <button type="button" class="btn btn-circle btn-error btn-xs" data-delete-image="${
              img.id
            }" title="Delete image">
              <svg xmlns="http://www.w3.org/2000/svg" class="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>
      `;
    }

    function refreshImageList(images) {
      if (!imageList) return;
      if (images && images.length > 0) {
        imageList.innerHTML = images.map(renderImage).join("");
      } else {
        imageList.innerHTML =
          '<p class="text-xs opacity-60">No images uploaded yet.</p>';
      }
    }

    function showImageUploadUI(questionId, groupId, surveySlug, images) {
      currentQuestionId = questionId;
      currentGroupId = groupId;
      currentSurveySlug = surveySlug;

      if (imageUploadContainer) {
        imageUploadContainer.classList.remove("hidden");
      }
      if (imageUploadPlaceholder) {
        imageUploadPlaceholder.classList.add("hidden");
      }

      refreshImageList(images || []);
    }

    function hideImageUploadUI() {
      currentQuestionId = null;
      currentGroupId = null;
      currentSurveySlug = null;

      if (imageUploadContainer) {
        imageUploadContainer.classList.add("hidden");
      }
      if (imageUploadPlaceholder) {
        imageUploadPlaceholder.classList.remove("hidden");
      }
      if (imageList) {
        imageList.innerHTML = "";
      }
      if (imageUploadInput) {
        imageUploadInput.value = "";
      }
      if (imageLabelInput) {
        imageLabelInput.value = "";
      }
    }

    // Handle image upload button click
    if (uploadImageBtn && imageUploadInput) {
      uploadImageBtn.addEventListener("click", async function () {
        const file = imageUploadInput.files && imageUploadInput.files[0];
        if (!file) {
          if (typeof window.showToast === "function") {
            window.showToast("Please select an image file", "error");
          }
          return;
        }

        const uploadUrl = getImageUploadUrl();
        if (!uploadUrl) {
          if (typeof window.showToast === "function") {
            window.showToast(
              "Save the question first before uploading images",
              "error"
            );
          }
          return;
        }

        // Show loading state
        uploadImageBtn.disabled = true;
        const originalContent = uploadImageBtn.innerHTML;
        uploadImageBtn.innerHTML =
          '<span class="loading loading-spinner loading-xs"></span>';

        const formData = new FormData();
        formData.append("image", file);
        formData.append("label", imageLabelInput ? imageLabelInput.value : "");

        try {
          const response = await fetch(uploadUrl, {
            method: "POST",
            headers: {
              "X-CSRFToken": csrfToken(),
            },
            credentials: "same-origin",
            body: formData,
          });

          const data = await response.json();

          if (!response.ok || !data.success) {
            throw new Error(data.error || "Upload failed");
          }

          // Add the new image to the list
          const existingImages = imageList.querySelectorAll("[data-image-id]");
          const currentImages = Array.from(existingImages).map((el) => {
            const id = el.dataset.imageId;
            const img = el.querySelector("img");
            const label = el.querySelector("p");
            return {
              id: parseInt(id),
              url: img ? img.src : "",
              label: label ? label.textContent : "",
            };
          });
          currentImages.push(data.image);
          refreshImageList(currentImages);

          // Clear inputs
          if (imageUploadInput) imageUploadInput.value = "";
          if (imageLabelInput) imageLabelInput.value = "";

          if (typeof window.showToast === "function") {
            window.showToast("Image uploaded successfully", "success");
          }
        } catch (error) {
          console.error("Image upload error:", error);
          if (typeof window.showToast === "function") {
            window.showToast(
              error.message || "Failed to upload image",
              "error"
            );
          }
        } finally {
          uploadImageBtn.disabled = false;
          uploadImageBtn.innerHTML = originalContent;
        }
      });
    }

    // Handle image delete (using event delegation on imageList)
    if (imageList) {
      imageList.addEventListener("click", async function (e) {
        const deleteBtn = e.target.closest("[data-delete-image]");
        if (!deleteBtn) return;

        const imageId = deleteBtn.dataset.deleteImage;
        if (!imageId) return;

        const deleteUrl = getImageDeleteUrl(imageId);
        if (!deleteUrl) return;

        // Confirm deletion
        if (!confirm("Are you sure you want to delete this image?")) {
          return;
        }

        deleteBtn.disabled = true;

        try {
          const response = await fetch(deleteUrl, {
            method: "POST",
            headers: {
              "X-CSRFToken": csrfToken(),
              "Content-Type": "application/json",
            },
            credentials: "same-origin",
          });

          const data = await response.json();

          if (!response.ok || !data.success) {
            throw new Error(data.error || "Delete failed");
          }

          // Remove the image from the list
          const imageEl = imageList.querySelector(
            `[data-image-id="${imageId}"]`
          );
          if (imageEl) {
            imageEl.remove();
          }

          // Check if there are any images left
          if (!imageList.querySelector("[data-image-id]")) {
            imageList.innerHTML =
              '<p class="text-xs opacity-60 col-span-3">No images uploaded yet.</p>';
          }

          if (typeof window.showToast === "function") {
            window.showToast("Image deleted successfully", "success");
          }
        } catch (error) {
          console.error("Image delete error:", error);
          if (typeof window.showToast === "function") {
            window.showToast(
              error.message || "Failed to delete image",
              "error"
            );
          }
          deleteBtn.disabled = false;
        }
      });
    }

    // Expose image handling functions for edit mode
    form._showImageUploadUI = showImageUploadUI;
    form._hideImageUploadUI = hideImageUploadUI;

    form.addEventListener("change", function (e) {
      if (
        e.target &&
        (e.target.name === "type" || e.target.name === "likert_mode")
      ) {
        refresh();
        // Reset image upload UI when changing question type
        if (e.target.name === "type" && e.target.value !== "image") {
          hideImageUploadUI();
        }
      }
    });

    // Initial state
    refresh();
  }

  // Template functionality for Special Templates tab
  function initTemplateHandling() {
    const form = document.getElementById("create-question-form");
    if (!form) return;

    const templateRadios = document.querySelectorAll('input[name="template"]');
    const questionTypeRadios = document.querySelectorAll('input[name="type"]');
    const addButton = form.querySelector('button[type="submit"]');
    const addButtonText = form.querySelector(
      '[data-editor-label="submit-add"]'
    );
    const tabRadios = document.querySelectorAll(
      'input[name="add_question_tabs"]'
    );
    if (
      !templateRadios.length ||
      !addButton ||
      !tabRadios.length ||
      !addButtonText
    )
      return;

    function getCurrentTab() {
      const activeTab = Array.from(tabRadios).find((tab) => tab.checked);
      return activeTab ? activeTab.getAttribute("aria-label") : null;
    }

    function updateFormAction() {
      const currentTab = getCurrentTab();
      const isTemplateTab = currentTab === "Special Templates";
      const isQuestionTab = currentTab === "Build question";
      const textInput = form.querySelector('input[name="text"]');

      if (isTemplateTab) {
        // Special Templates tab
        const isTemplateSelected = Array.from(templateRadios).some(
          (radio) => radio.checked
        );

        addButtonText.textContent = "Add Template";
        addButton.disabled = !isTemplateSelected;

        // Update button styling based on disabled state
        if (!isTemplateSelected) {
          addButton.classList.add("btn-disabled");
          addButton.setAttribute("aria-disabled", "true");
        } else {
          addButton.classList.remove("btn-disabled");
          addButton.removeAttribute("aria-disabled");
        }

        if (isTemplateSelected) {
          const templateUrl = form.dataset.templateUrl;
          form.setAttribute("hx-post", templateUrl);
        } else {
          // Don't set form action if no template selected
          form.removeAttribute("hx-post");
        }

        // Remove required attribute from text input when using templates
        if (textInput) {
          textInput.removeAttribute("required");
        }
      } else if (isQuestionTab) {
        // Build question tab
        const isQuestionTypeSelected = Array.from(questionTypeRadios).some(
          (radio) => radio.checked
        );
        const hasQuestionText = textInput && textInput.value.trim() !== "";
        const isFormValid = isQuestionTypeSelected && hasQuestionText;

        addButtonText.textContent = "Add Question";
        addButton.disabled = !isFormValid;

        // Update button styling based on disabled state
        if (!isFormValid) {
          addButton.classList.add("btn-disabled");
          addButton.setAttribute("aria-disabled", "true");
        } else {
          addButton.classList.remove("btn-disabled");
          addButton.removeAttribute("aria-disabled");
        }

        if (isFormValid) {
          const createUrl = form.dataset.createUrl;
          form.setAttribute("hx-post", createUrl);
        } else {
          // Don't set form action if requirements not met
          form.removeAttribute("hx-post");
        }

        // Add required attribute back to text input for regular questions
        if (textInput) {
          textInput.setAttribute("required", "");
        }
      } else {
        // Fallback state
        addButtonText.textContent = "Add";
        addButton.disabled = true;
        addButton.classList.add("btn-disabled");
        addButton.setAttribute("aria-disabled", "true");
        form.removeAttribute("hx-post");
      }

      // Reinitialize htmx for the form only if it has an action
      if (window.htmx && form.hasAttribute("hx-post")) {
        window.htmx.process(form);
      }
    }

    // Prevent form submission when button is disabled
    form.addEventListener("submit", function (e) {
      if (addButton.disabled) {
        e.preventDefault();
        e.stopPropagation();
        return false;
      }
    });

    // Listen for template radio changes
    templateRadios.forEach((radio) => {
      radio.addEventListener("change", updateFormAction);
    });

    // Listen for question type radio changes
    questionTypeRadios.forEach((radio) => {
      radio.addEventListener("change", updateFormAction);
    });

    // Listen for text input changes
    const textInput = form.querySelector('input[name="text"]');
    if (textInput) {
      textInput.addEventListener("input", updateFormAction);
    }

    // Listen for tab changes
    tabRadios.forEach((tab) => {
      tab.addEventListener("change", function () {
        // Clear selections when switching tabs for cleaner UX
        if (this.getAttribute("aria-label") === "Build question") {
          templateRadios.forEach((radio) => {
            radio.checked = false;
          });
        } else if (this.getAttribute("aria-label") === "Special Templates") {
          // Don't clear question selections as user might switch back
        }

        // Small delay to ensure tab content is visible before checking
        setTimeout(updateFormAction, 10);
      });
    });

    // Initial check
    updateFormAction();
  }

  // Initialize template handling when DOM is ready
  document.addEventListener("DOMContentLoaded", function () {
    initTemplateHandling();
  });
})();
