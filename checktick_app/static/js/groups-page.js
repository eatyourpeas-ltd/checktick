(function () {
  function $(sel, root) {
    return (root || document).querySelector(sel);
  }
  function $all(sel, root) {
    return Array.from((root || document).querySelectorAll(sel));
  }

  function init() {
    var root = $("#groups-draggable");
    if (!root) return;
    var createBtn = $("#create-repeat-btn");
    var removeRepeatBtn = $("#remove-repeat-btn");
    var removeRepeatIds = $("#remove-repeat-group-ids");
    var modal = $("#repeat-modal");
    var inputIds = $("#repeat-group-ids");
    var selected = new Set();

    function getSelectedRepeatedGroups() {
      // Return group IDs that are both selected AND part of a repeat
      var repeatedIds = [];
      $all("li[data-gid]", root).forEach(function (li) {
        if (selected.has(li.dataset.gid) && li.dataset.repeat === "1") {
          repeatedIds.push(li.dataset.gid);
        }
      });
      return repeatedIds;
    }

    function getSelectedNonRepeatedGroups() {
      // Return group IDs that are selected but NOT part of a repeat
      var nonRepeatedIds = [];
      $all("li[data-gid]", root).forEach(function (li) {
        if (selected.has(li.dataset.gid) && li.dataset.repeat !== "1") {
          nonRepeatedIds.push(li.dataset.gid);
        }
      });
      return nonRepeatedIds;
    }

    function refresh() {
      // Enable create repeat only if at least one selected group is NOT already repeated
      var nonRepeatedSelected = getSelectedNonRepeatedGroups();
      if (createBtn) {
        createBtn.disabled = nonRepeatedSelected.length === 0;
        // Update button title to explain why it might be disabled
        if (selected.size > 0 && nonRepeatedSelected.length === 0) {
          createBtn.title =
            "All selected groups are already in repeats. Use 'Remove from repeat' first.";
        } else {
          createBtn.title = "";
        }
      }

      // Enable remove repeat button only if selected groups include repeated ones
      var repeatedSelected = getSelectedRepeatedGroups();
      if (removeRepeatBtn) {
        removeRepeatBtn.disabled = repeatedSelected.length === 0;
      }
      if (removeRepeatIds) {
        removeRepeatIds.value = repeatedSelected.join(",");
      }

      var bar = $("#selection-toolbar");
      var count = $("#selection-count");
      if (bar && count) {
        count.textContent = String(selected.size);
        bar.classList.toggle("hidden", selected.size === 0);
      }
    }

    function updateSelection(li, isChecked) {
      var icon = li.querySelector(".sel-repeat-icon");
      var tile = li.querySelector(".selectable-group");
      if (isChecked) {
        selected.add(li.dataset.gid);
        if (tile) {
          tile.dataset.selected = "1";
          tile.style.outline =
            "2px solid color-mix(in oklch, var(--p) 45%, transparent)";
          tile.style.backgroundColor =
            "color-mix(in oklch, var(--p) 12%, transparent)";
        }
        if (icon) icon.classList.remove("hidden");
      } else {
        selected.delete(li.dataset.gid);
        if (tile) {
          delete tile.dataset.selected;
          tile.style.outline = "";
          tile.style.backgroundColor = "";
        }
        if (icon) icon.classList.add("hidden");
      }
    }

    root.addEventListener("click", function (e) {
      var li = e.target.closest("li[data-gid]");
      if (!li) return;
      if (
        e.target.closest(".drag-handle") ||
        e.target.closest("form") ||
        e.target.closest(".select-checkbox")
      )
        return;
      // If the click is on a builder link, allow normal navigation
      var a = e.target.closest('a[href*="/builder/"]');
      if (a) return;
      var cb = li.querySelector(".select-checkbox");
      if (!cb) return;
      cb.checked = !cb.checked;
      updateSelection(li, cb.checked);
      refresh();
    });

    root.addEventListener("change", function (e) {
      if (!e.target.classList.contains("select-checkbox")) return;
      var li = e.target.closest("li[data-gid]");
      if (!li) return;
      updateSelection(li, e.target.checked);
      refresh();
    });

    var clearBtn = $("#clear-selection");
    if (clearBtn)
      clearBtn.addEventListener("click", function () {
        $all("li[data-gid]", root).forEach(function (li) {
          var cb = li.querySelector(".select-checkbox");
          if (!cb) return;
          cb.checked = false;
          updateSelection(li, false);
        });
        selected.clear();
        refresh();
      });

    if (createBtn)
      createBtn.addEventListener("click", function () {
        // Only include non-repeated groups in the new repeat
        var nonRepeatedIds = getSelectedNonRepeatedGroups();
        if (!nonRepeatedIds.length) return;
        if (inputIds) inputIds.value = nonRepeatedIds.join(",");
        if (modal && modal.showModal) modal.showModal();
      });

    var cancelBtn = $("#repeat-cancel-btn");
    if (cancelBtn && modal)
      cancelBtn.addEventListener("click", function () {
        modal.close();
      });

    // Edit repeat modal handling
    var editModal = $("#edit-repeat-modal");
    var editCollectionId = $("#edit-repeat-collection-id");
    var editName = $("#edit-repeat-name");
    var editMin = $("#edit-repeat-min");
    var editMax = $("#edit-repeat-max");
    var editCancelBtn = $("#edit-repeat-cancel-btn");

    // Handle click on repeat badges to open edit modal
    document.addEventListener("click", function (e) {
      var editBtn = e.target.closest(".edit-repeat-btn");
      if (!editBtn) return;

      e.preventDefault();
      e.stopPropagation();

      // Populate the edit modal with current values
      if (editCollectionId)
        editCollectionId.value = editBtn.dataset.collectionId;
      if (editName) editName.value = editBtn.dataset.collectionName;
      if (editMin) editMin.value = editBtn.dataset.minCount || "0";
      if (editMax) {
        var maxVal = editBtn.dataset.maxCount;
        editMax.value = maxVal || "";
      }

      if (editModal && editModal.showModal) editModal.showModal();
    });

    if (editCancelBtn && editModal)
      editCancelBtn.addEventListener("click", function () {
        editModal.close();
      });

    // Initialize from any pre-checked boxes
    $all("li[data-gid]", root).forEach(function (li) {
      var cb = li.querySelector(".select-checkbox");
      if (cb && cb.checked) {
        selected.add(li.dataset.gid);
        updateSelection(li, true);
      }
    });
    refresh();

    // Confirmation dialogs for destructive form actions (replaces inline onsubmit)
    document.addEventListener("submit", function (e) {
      var form = e.target.closest("form[data-confirm-submit]");
      if (!form) return;
      var msg = form.dataset.confirmSubmit;
      if (msg && !window.confirm(msg)) {
        e.preventDefault();
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
