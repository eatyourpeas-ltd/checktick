/**
 * Paddle.js Checkout Integration
 *
 * Handles Paddle checkout initialization and payment flow for CheckTick subscriptions.
 * Requires Paddle.js SDK to be loaded in the page.
 */

// Initialize Paddle when DOM is ready
document.addEventListener("DOMContentLoaded", function () {
  // Get environment from template context
  const paddleEnvironment =
    document.body.dataset.paddleEnvironment || "sandbox";
  const paddleToken = document.body.dataset.paddleToken;

  if (!paddleToken) {
    console.warn("Paddle client token not found. Checkout will not work.");
    return;
  }

  // Initialize Paddle
  try {
    if (typeof Paddle !== "undefined") {
      Paddle.Environment.set(paddleEnvironment);
      Paddle.Initialize({
        token: paddleToken,
        eventCallback: function (data) {
          console.log("Paddle event:", data);

          // Handle checkout completion
          if (data.name === "checkout.completed") {
            handleCheckoutCompleted(data);
          }

          // Handle checkout closure (user cancelled)
          if (data.name === "checkout.closed") {
            console.log("Checkout closed by user");
          }
        },
      });
      console.log(`Paddle initialized in ${paddleEnvironment} mode`);
    } else {
      console.error("Paddle SDK not loaded");
    }
  } catch (error) {
    console.error("Error initializing Paddle:", error);
  }

  // Add click event listeners to all Paddle checkout buttons
  document.querySelectorAll(".paddle-checkout-btn").forEach((button) => {
    button.addEventListener("click", function () {
      const tier = this.dataset.tier;
      const priceId = this.dataset.priceId;
      openPaddleCheckout(tier, priceId);
    });
  });
});

/**
 * Open Paddle checkout for a specific tier
 * @param {string} tier - The tier name (pro, team_small, etc.)
 * @param {string} priceId - The Paddle price ID (pri_*)
 */
function openPaddleCheckout(tier, priceId) {
  if (typeof Paddle === "undefined") {
    showToast("Payment system not loaded. Please refresh the page.", "error");
    return;
  }

  if (!priceId) {
    showToast(
      "Invalid pricing configuration. Please contact support.",
      "error"
    );
    return;
  }

  try {
    // Detect current theme (light/dark)
    const isDarkMode =
      document.documentElement.getAttribute("data-theme") === "dark";

    // Open Paddle checkout overlay with theme customization
    Paddle.Checkout.open({
      settings: {
        displayMode: "overlay",
        theme: isDarkMode ? "dark" : "light",
        locale: "en",
        allowLogout: false,
        // Paddle allows some style customization via CSS variables
        // These will be applied if Paddle supports them in their overlay
        variant: "multi-page", // or "one-page" for single-page checkout
      },
      items: [
        {
          priceId: priceId,
          quantity: 1,
        },
      ],
      customData: {
        tier: tier,
        userId: document.body.dataset.userId || "",
      },
      customer: getCustomerInfo(),
      // URLs for checkout flow
      successUrl: window.location.origin + "/billing/success/?tier=" + tier,
      closeUrl: window.location.origin + "/pricing/",
    });
  } catch (error) {
    console.error("Error opening Paddle checkout:", error);
    showToast("Unable to open checkout. Please try again.", "error");
  }
}

/**
 * Get customer info for pre-filling checkout
 */
function getCustomerInfo() {
  const customerId = document.body.dataset.paddleCustomerId;
  const userEmail = document.body.dataset.userEmail;

  if (customerId) {
    return { id: customerId };
  } else if (userEmail) {
    return { email: userEmail };
  }

  return undefined;
}

/**
 * Handle successful checkout completion
 */
function handleCheckoutCompleted(data) {
  console.log("Checkout completed:", data);

  // Show success message
  showToast("Payment successful! Your account is being upgraded...", "success");

  // Redirect will happen via successUrl, but we can also handle it here
  const tier = data.data?.customData?.tier;
  if (tier) {
    // Give webhook time to process (1 second delay)
    setTimeout(() => {
      window.location.href = "/billing/success/?tier=" + tier;
    }, 1000);
  }
}

/**
 * Show toast notification
 * Uses the global toast.js system if available
 */
function showToast(message, type = "info") {
  if (typeof window.showToast === "function") {
    window.showToast(message, type);
  } else {
    // Fallback to console if toast system not available
    console.log(`[${type.toUpperCase()}] ${message}`);
    alert(message);
  }
}
