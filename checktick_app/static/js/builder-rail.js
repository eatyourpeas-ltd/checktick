(function () {
  "use strict";

  function $(sel, root) {
    return (root || document).querySelector(sel);
  }

  function init() {
    var rail = $("#builder-rail");
    if (!rail) return;

    var surveySlug = rail.dataset.surveySlug || "";

    // --- Rename modal ---
    var renameModal = $("#rename-section-modal");
    var renameForm = $("#rename-section-form");
    var renameGid = $("#rename-section-gid");
    var renameName = $("#rename-section-name");
    var renameDesc = $("#rename-section-description");
    var renameCancelBtn = $("#rename-section-cancel-btn");

    document.addEventListener("click", function (e) {
      var renameBtn = e.target.closest(".rename-section-btn");
      if (!renameBtn) return;

      e.preventDefault();
      e.stopPropagation();

      if (renameGid) renameGid.value = renameBtn.dataset.gid;
      if (renameName) renameName.value = renameBtn.dataset.name || "";
      if (renameDesc) renameDesc.value = renameBtn.dataset.description || "";

      // Set the form action dynamically based on the section's gid
      if (renameForm) {
        renameForm.action =
          "/surveys/" + surveySlug + "/groups/" + renameBtn.dataset.gid + "/edit";
      }

      if (renameModal && renameModal.showModal) renameModal.showModal();
    });

    if (renameCancelBtn && renameModal) {
      renameCancelBtn.addEventListener("click", function () {
        renameModal.close();
      });
    }

    // --- Delete confirmation modal ---
    var deleteModal = $("#delete-section-modal");
    var deleteForm = $("#delete-section-form");
    var deleteNameDisplay = $("#delete-section-name-display");
    var deleteCancelBtn = $("#delete-section-cancel-btn");

    document.addEventListener("click", function (e) {
      var deleteBtn = e.target.closest(".delete-section-btn");
      if (!deleteBtn) return;

      e.preventDefault();
      e.stopPropagation();

      if (deleteNameDisplay) {
        deleteNameDisplay.textContent = deleteBtn.dataset.name || "";
      }

      if (deleteForm) {
        deleteForm.action = deleteBtn.dataset.deleteUrl;
      }

      if (deleteModal && deleteModal.showModal) deleteModal.showModal();
    });

    if (deleteCancelBtn && deleteModal) {
      deleteCancelBtn.addEventListener("click", function () {
        deleteModal.close();
      });
    }

    // Re-init after HTMX swaps that replace the rail
    document.body.addEventListener("htmx:afterSwap", function (evt) {
      var target = (evt.detail && evt.detail.target) || evt.target;
      if (
        target.id === "builder-rail" ||
        (target.closest && target.closest("#builder-rail"))
      ) {
        // The rail was swapped — re-bind modal references since the DOM changed.
        renameModal = $("#rename-section-modal");
        renameForm = $("#rename-section-form");
        renameGid = $("#rename-section-gid");
        renameName = $("#rename-section-name");
        renameDesc = $("#rename-section-description");
        renameCancelBtn = $("#rename-section-cancel-btn");
        deleteModal = $("#delete-section-modal");
        deleteForm = $("#delete-section-form");
        deleteNameDisplay = $("#delete-section-name-display");
        deleteCancelBtn = $("#delete-section-cancel-btn");
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
