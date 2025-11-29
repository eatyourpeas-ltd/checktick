/**
 * Subscription portal interactions
 */

document.addEventListener("DOMContentLoaded", function () {
  // Handle cancel subscription confirmation
  const cancelForm = document.querySelector(
    'form[action*="cancel"]#cancel-subscription-form'
  );

  if (cancelForm) {
    cancelForm.addEventListener("submit", function (e) {
      const confirmMessage = cancelForm.dataset.confirmMessage;
      if (confirmMessage && !confirm(confirmMessage)) {
        e.preventDefault();
        return false;
      }
    });
  }
});
