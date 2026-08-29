(function () {
  "use strict";

  function $(sel, root) {
    return (root || document).querySelector(sel);
  }

  function csrfToken() {
    var name = "csrftoken";
    var m = document.cookie.match(new RegExp("(^| )" + name + "=([^;]+)"));
    return m ? m[2] : "";
  }

  // --- Section rail drag-reorder ---
  // Reuses the same SortableJS + auto-save pattern as the Organise page
  // (static/js/groups.js): handle ".drag-handle", animation 150, forceFallback,
  // and on drop POST `order=ids.join(",")` to data-reorder-url with the CSRF
  // header. The endpoint (survey_groups_reorder) is shared with the Organise
  // page, so no new view is needed.
  //
  // The Sortable instance is stored so it can be destroyed before re-creating
  // one after an HTMX OOB swap replaces the rail DOM. Without destroy(), the
  // old instance's document-level fallback listeners (from forceFallback)
  // linger and interfere with the new instance — causing the "can only drag
  // once" bug.
  var railSortable = null;

  function initRailSortable() {
    var el = $("#builder-rail-list");
    if (!el) return;
    // Destroy the previous instance so its event listeners don't stack up.
    if (railSortable) {
      railSortable.destroy();
      railSortable = null;
    }
    var canEdit = (el.getAttribute("data-can-edit") || "false") === "true";
    if (!window.Sortable || !canEdit) return;
    railSortable = new Sortable(el, {
      handle: ".drag-handle",
      animation: 150,
      forceFallback: true,
      onEnd: function () {
        submitRailOrder(el);
      },
    });
  }

  function submitRailOrder(el) {
    var ids = Array.from(el.querySelectorAll("[data-gid]")).map(function (li) {
      return li.dataset.gid;
    });
    var url = el.getAttribute("data-reorder-url");
    if (!url) return;
    var body = new URLSearchParams({ order: ids.join(",") });
    return fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        "X-CSRFToken": csrfToken(),
        "X-Requested-With": "XMLHttpRequest",
      },
      body: body,
    })
      .then(function (resp) {
        if (resp.ok) {
          if (typeof window.showToast === "function") {
            window.showToast("Order saved", "success");
          }
          // Notify any listeners (e.g. a visualizer) that groups were reordered.
          document.dispatchEvent(new CustomEvent("groupsReordered"));
          return true;
        } else {
          console.error("Failed to save section order");
          return false;
        }
      })
      .catch(function (err) {
        console.error(err);
        return false;
      });
  }

  function init() {
    var rail = $("#builder-rail");
    if (!rail) return;

    var surveySlug = rail.dataset.surveySlug || "";

    initRailSortable();

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

    // --- Repeat create modal ---
    var repeatCreateModal = $("#repeat-create-modal");
    var repeatCreateForm = $("#repeat-create-form");
    var repeatCreateGid = $("#repeat-create-gid");
    var repeatCreateName = $("#repeat-create-name");
    var repeatCreateSectionName = $("#repeat-create-section-name");
    var repeatCreateCancelBtn = $("#repeat-create-cancel-btn");

    document.addEventListener("click", function (e) {
      var createBtn = e.target.closest(".create-repeat-btn");
      if (!createBtn) return;

      e.preventDefault();
      e.stopPropagation();

      if (repeatCreateGid) repeatCreateGid.value = createBtn.dataset.gid;
      // Default the repeat name to the section name.
      var gname = createBtn.dataset.gname || "";
      if (repeatCreateName) repeatCreateName.value = gname;
      if (repeatCreateSectionName)
        repeatCreateSectionName.textContent = gname;
      if (repeatCreateForm)
        repeatCreateForm.action =
          "/surveys/" + surveySlug + "/groups/repeat/create";

      if (repeatCreateModal && repeatCreateModal.showModal)
        repeatCreateModal.showModal();
    });

    if (repeatCreateCancelBtn && repeatCreateModal) {
      repeatCreateCancelBtn.addEventListener("click", function () {
        repeatCreateModal.close();
      });
    }

    // --- Repeat edit modal ---
    var repeatEditModal = $("#repeat-edit-modal");
    var repeatEditForm = $("#repeat-edit-form");
    var repeatEditCollectionId = $("#repeat-edit-collection-id");
    var repeatEditName = $("#repeat-edit-name");
    var repeatEditMin = $("#repeat-edit-min");
    var repeatEditMax = $("#repeat-edit-max");
    var repeatEditCancelBtn = $("#repeat-edit-cancel-btn");

    document.addEventListener("click", function (e) {
      var editBtn = e.target.closest(".edit-repeat-btn");
      if (!editBtn) return;

      e.preventDefault();
      e.stopPropagation();

      if (repeatEditCollectionId)
        repeatEditCollectionId.value = editBtn.dataset.collectionId;
      if (repeatEditName) repeatEditName.value = editBtn.dataset.collectionName || "";
      if (repeatEditMin) repeatEditMin.value = editBtn.dataset.minCount || "0";
      if (repeatEditMax) repeatEditMax.value = editBtn.dataset.maxCount || "";
      if (repeatEditForm)
        repeatEditForm.action =
          "/surveys/" + surveySlug + "/groups/repeat/edit";

      if (repeatEditModal && repeatEditModal.showModal)
        repeatEditModal.showModal();
    });

    if (repeatEditCancelBtn && repeatEditModal) {
      repeatEditCancelBtn.addEventListener("click", function () {
        repeatEditModal.close();
      });
    }

    // --- Repeat remove modal ---
    var repeatRemoveModal = $("#repeat-remove-modal");
    var repeatRemoveForm = $("#repeat-remove-form");
    var repeatRemoveCancelBtn = $("#repeat-remove-cancel-btn");

    // The edit-repeat-btn also has data-gid; we add a separate remove button
    // inside the edit modal instead. For now, removing is done via the edit
    // modal's "Remove" action — but to keep it simple, we expose a remove
    // button on the edit modal.
    // (The remove form action is set dynamically when the edit modal opens.)
    if (repeatRemoveCancelBtn && repeatRemoveModal) {
      repeatRemoveCancelBtn.addEventListener("click", function () {
        repeatRemoveModal.close();
      });
    }

    // Wire the edit-repeat-btn to also set the remove form action.
    document.addEventListener("click", function (e) {
      var editBtn = e.target.closest(".edit-repeat-btn");
      if (!editBtn) return;
      if (repeatRemoveForm) {
        repeatRemoveForm.action =
          "/surveys/" +
          surveySlug +
          "/groups/" +
          editBtn.dataset.gid +
          "/repeat/remove";
      }
    });

    // Re-init after HTMX swaps. The rail is OOB-swapped when the user clicks
    // a section (the primary swap target is #builder-main, not #builder-rail),
    // so we can't rely on target matching. Instead, after any HTMX settle, if
    // the rail list is in the DOM, (re-)init Sortable on it. initRailSortable
    // is idempotent: it destroys the old instance before creating a new one.
    document.body.addEventListener("htmx:afterSettle", function () {
      if ($("#builder-rail-list")) {
        // Re-bind modal references since the rail DOM may have changed.
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
        repeatCreateModal = $("#repeat-create-modal");
        repeatCreateForm = $("#repeat-create-form");
        repeatCreateGid = $("#repeat-create-gid");
        repeatCreateName = $("#repeat-create-name");
        repeatCreateSectionName = $("#repeat-create-section-name");
        repeatCreateCancelBtn = $("#repeat-create-cancel-btn");
        repeatEditModal = $("#repeat-edit-modal");
        repeatEditForm = $("#repeat-edit-form");
        repeatEditCollectionId = $("#repeat-edit-collection-id");
        repeatEditName = $("#repeat-edit-name");
        repeatEditMin = $("#repeat-edit-min");
        repeatEditMax = $("#repeat-edit-max");
        repeatEditCancelBtn = $("#repeat-edit-cancel-btn");
        repeatRemoveModal = $("#repeat-remove-modal");
        repeatRemoveForm = $("#repeat-remove-form");
        repeatRemoveCancelBtn = $("#repeat-remove-cancel-btn");
        initRailSortable();
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
