/**
 * Professional Fields Auto-Complete
 *
 * Automatically loads dataset options for professional detail fields
 * that have associated RCPCH API endpoints (trusts, health boards, etc.)
 */

document.addEventListener("DOMContentLoaded", function () {
  const datasetFields = document.querySelectorAll("[data-dataset-field]");

  console.log(
    `[Professional Fields] Found ${datasetFields.length} fields with dataset mapping`
  );

  datasetFields.forEach(async function (select) {
    const datasetKey = select.dataset.datasetKey;
    const fieldKey = select.dataset.datasetField;

    console.log(
      `[Professional Fields] Processing field: ${fieldKey}, dataset: ${datasetKey}`
    );

    if (!datasetKey) {
      console.warn(`No dataset key for field: ${fieldKey}`);
      return;
    }

    try {
      // Fetch dataset options from API
      console.log(
        `[Professional Fields] Fetching /api/datasets/${datasetKey}/`
      );
      const response = await fetch(`/api/datasets/${datasetKey}/`, {
        credentials: "same-origin",
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();

      // Clear loading option
      select.innerHTML = "";

      // Add default "select" option
      const defaultOption = document.createElement("option");
      defaultOption.value = "";
      defaultOption.textContent = `-- Select ${
        select.closest("[data-professional-field]")?.dataset
          .professionalField || "option"
      } --`;
      select.appendChild(defaultOption);

      // Add fetched options (all datasets use dict format: code -> name)
      if (data.options && typeof data.options === "object") {
        let optionCount = 0;

        Object.entries(data.options).forEach(function ([code, name]) {
          const option = document.createElement("option");
          option.value = code;
          option.textContent = `${code}: ${name}`;
          select.appendChild(option);
          optionCount++;
        });

        console.log(
          `Loaded ${optionCount} options for ${fieldKey} from ${datasetKey}`
        );
      } else {
        console.warn(`No options returned for ${datasetKey}`);
      }
    } catch (error) {
      console.error(
        `Failed to load dataset ${datasetKey} for field ${fieldKey}:`,
        error
      );

      // Show error state
      select.innerHTML = "";
      const errorOption = document.createElement("option");
      errorOption.value = "";
      errorOption.textContent = `Error loading options - please refresh`;
      errorOption.disabled = true;
      errorOption.selected = true;
      select.appendChild(errorOption);

      // Add manual entry option as fallback
      const manualOption = document.createElement("option");
      manualOption.value = "__manual__";
      manualOption.textContent = "Enter manually...";
      select.appendChild(manualOption);
    }
  });

  // Handle manual entry option
  document.addEventListener("change", function (e) {
    const select = e.target;
    if (
      select.matches("[data-dataset-field]") &&
      select.value === "__manual__"
    ) {
      const field = select.dataset.datasetField;
      const label =
        select
          .closest("[data-professional-field]")
          ?.querySelector(".label-text")?.textContent || "Value";

      // Replace select with text input
      const input = document.createElement("input");
      input.type = "text";
      input.name = `prof_${field}`;
      input.placeholder = `Enter ${label}`;
      input.className = "input input-bordered input-sm w-full";

      const wrapper = select.closest("label") || select.parentElement;
      wrapper.replaceChild(input, select);
      input.focus();
    }
  });
});
