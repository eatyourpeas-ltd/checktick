/**
 * Documentation Navigation - Collapsible Categories
 *
 * Provides collapsible category navigation with localStorage persistence.
 * Active category is always expanded.
 */

(function () {
  "use strict";

  const STORAGE_KEY = "docs-collapsed-categories";

  /**
   * Get collapsed categories from localStorage
   * @returns {Array<string>} Array of collapsed category slugs
   */
  function getCollapsedCategories() {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      return stored ? JSON.parse(stored) : [];
    } catch (e) {
      return [];
    }
  }

  /**
   * Save collapsed categories to localStorage
   * @param {Array<string>} collapsed - Array of collapsed category slugs
   */
  function saveCollapsedCategories(collapsed) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(collapsed));
    } catch (e) {
      // Ignore localStorage errors (e.g., privacy mode)
    }
  }

  /**
   * Find which category contains the active page
   * @returns {string|null} Category slug or null
   */
  function getActiveCategorySlug() {
    const activeLink = document.querySelector(".docs-category-items a.active");
    if (activeLink) {
      const category = activeLink.closest(".docs-category");
      return category ? category.dataset.category : null;
    }
    return null;
  }

  /**
   * Initialize collapsible categories
   */
  function initCollapsibleCategories() {
    const categories = document.querySelectorAll(".docs-category");
    const collapsedCategories = getCollapsedCategories();
    const activeCategorySlug = getActiveCategorySlug();

    categories.forEach(function (category) {
      const toggle = category.querySelector(".docs-category-toggle");
      const items = category.querySelector(".docs-category-items");
      const chevron = toggle.querySelector(".docs-chevron");
      const categorySlug = category.dataset.category;

      // Collapse all categories by default, except the one containing active page
      const shouldCollapse = categorySlug !== activeCategorySlug;

      if (shouldCollapse) {
        items.style.display = "none";
        toggle.setAttribute("aria-expanded", "false");
        chevron.style.transform = "rotate(-90deg)";
      }

      // Toggle category on click
      toggle.addEventListener("click", function () {
        const isExpanded = toggle.getAttribute("aria-expanded") === "true";

        if (isExpanded) {
          // Collapse
          items.style.display = "none";
          toggle.setAttribute("aria-expanded", "false");
          chevron.style.transform = "rotate(-90deg)";

          // Add to collapsed list
          if (!collapsedCategories.includes(categorySlug)) {
            collapsedCategories.push(categorySlug);
            saveCollapsedCategories(collapsedCategories);
          }
        } else {
          // Expand
          items.style.display = "block";
          toggle.setAttribute("aria-expanded", "true");
          chevron.style.transform = "rotate(0deg)";

          // Remove from collapsed list
          const index = collapsedCategories.indexOf(categorySlug);
          if (index > -1) {
            collapsedCategories.splice(index, 1);
            saveCollapsedCategories(collapsedCategories);
          }
        }
      });
    });
  }

  // Initialize on DOMContentLoaded
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initCollapsibleCategories);
  } else {
    initCollapsibleCategories();
  }
})();
