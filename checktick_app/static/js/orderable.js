(function () {
  if (!window.Sortable) return;

  document.querySelectorAll(".orderable-list").forEach(function (listEl) {
    // Initialize SortableJS for drag-and-drop
    new Sortable(listEl, {
      animation: 150,
      handle: ".drag-handle",
      forceFallback: true,
      onStart: function () {
        document.body.classList.add("select-none");
      },
      onEnd: function () {
        document.body.classList.remove("select-none");
      },
    });

    // Add keyboard navigation for accessibility
    const items = listEl.querySelectorAll('[role="option"]');

    items.forEach(function (item, index) {
      // Make items focusable
      item.setAttribute("tabindex", index === 0 ? "0" : "-1");

      item.addEventListener("keydown", function (e) {
        const currentIndex = Array.from(items).indexOf(document.activeElement);
        let targetIndex = -1;
        let shouldMove = false;

        switch (e.key) {
          case "ArrowUp":
            e.preventDefault();
            if (e.altKey || e.metaKey) {
              // Alt/Cmd + Arrow = move item up
              if (currentIndex > 0) {
                targetIndex = currentIndex - 1;
                shouldMove = true;
              }
            } else {
              // Just Arrow = navigate focus up
              if (currentIndex > 0) {
                items[currentIndex].setAttribute("tabindex", "-1");
                items[currentIndex - 1].setAttribute("tabindex", "0");
                items[currentIndex - 1].focus();
              }
            }
            break;

          case "ArrowDown":
            e.preventDefault();
            if (e.altKey || e.metaKey) {
              // Alt/Cmd + Arrow = move item down
              if (currentIndex < items.length - 1) {
                targetIndex = currentIndex + 1;
                shouldMove = true;
              }
            } else {
              // Just Arrow = navigate focus down
              if (currentIndex < items.length - 1) {
                items[currentIndex].setAttribute("tabindex", "-1");
                items[currentIndex + 1].setAttribute("tabindex", "0");
                items[currentIndex + 1].focus();
              }
            }
            break;

          case "Home":
            e.preventDefault();
            items[currentIndex].setAttribute("tabindex", "-1");
            items[0].setAttribute("tabindex", "0");
            items[0].focus();
            break;

          case "End":
            e.preventDefault();
            items[currentIndex].setAttribute("tabindex", "-1");
            items[items.length - 1].setAttribute("tabindex", "0");
            items[items.length - 1].focus();
            break;

          case " ":
          case "Enter":
            // Toggle "grabbed" state for move mode
            e.preventDefault();
            if (item.getAttribute("aria-grabbed") === "true") {
              item.setAttribute("aria-grabbed", "false");
              item.classList.remove("ring-2", "ring-primary");
              announceToScreenReader("Item released");
            } else {
              item.setAttribute("aria-grabbed", "true");
              item.classList.add("ring-2", "ring-primary");
              announceToScreenReader(
                "Item grabbed. Use arrow keys to move, Enter or Space to release."
              );
            }
            break;
        }

        // Move the item if in "grabbed" state and arrow pressed
        if (
          item.getAttribute("aria-grabbed") === "true" &&
          (e.key === "ArrowUp" || e.key === "ArrowDown")
        ) {
          e.preventDefault();
          if (e.key === "ArrowUp" && currentIndex > 0) {
            targetIndex = currentIndex - 1;
            shouldMove = true;
          } else if (e.key === "ArrowDown" && currentIndex < items.length - 1) {
            targetIndex = currentIndex + 1;
            shouldMove = true;
          }
        }

        if (shouldMove && targetIndex >= 0) {
          moveItem(listEl, currentIndex, targetIndex, item);
        }
      });
    });
  });

  function moveItem(listEl, fromIndex, toIndex, item) {
    const items = Array.from(listEl.querySelectorAll('[role="option"]'));
    const targetItem = items[toIndex];

    if (fromIndex < toIndex) {
      // Moving down - insert after target
      targetItem.parentNode.insertBefore(item, targetItem.nextSibling);
    } else {
      // Moving up - insert before target
      targetItem.parentNode.insertBefore(item, targetItem);
    }

    // Maintain focus on moved item
    item.focus();

    // Announce position change
    const newPosition = toIndex + 1;
    const total = items.length;
    announceToScreenReader(`Moved to position ${newPosition} of ${total}`);
  }

  function announceToScreenReader(message) {
    // Create or reuse live region
    let liveRegion = document.getElementById("orderable-live-region");
    if (!liveRegion) {
      liveRegion = document.createElement("div");
      liveRegion.id = "orderable-live-region";
      liveRegion.setAttribute("role", "status");
      liveRegion.setAttribute("aria-live", "polite");
      liveRegion.setAttribute("aria-atomic", "true");
      liveRegion.className = "sr-only";
      document.body.appendChild(liveRegion);
    }

    // Clear and set message (triggers announcement)
    liveRegion.textContent = "";
    setTimeout(function () {
      liveRegion.textContent = message;
    }, 50);
  }
})();
