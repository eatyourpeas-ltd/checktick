function updateHiddenFields() {
  const selectedTier = document.querySelector(
    'input[name="selected_tier"]:checked'
  );
  if (selectedTier) {
    document.getElementById("selected-tier").value = selectedTier.value;
  }
}

function handleSSOSignup(provider) {
  const selectedTier = document.querySelector(
    'input[name="selected_tier"]:checked'
  );

  // Store choices in sessionStorage for post-auth processing
  sessionStorage.setItem(
    "signup_tier",
    selectedTier ? selectedTier.value : "free"
  );

  // Redirect to OIDC with signup flag
  window.location.href = `/oidc/authenticate/?provider=${provider}&signup=true`;
}

// Set initial state when page loads
document.addEventListener("DOMContentLoaded", function () {
  // Add event listeners to tier selection radios
  const tierRadios = document.querySelectorAll('input[name="selected_tier"]');
  tierRadios.forEach((radio) => {
    radio.addEventListener("change", updateHiddenFields);
  });

  // Add event listeners to SSO buttons
  const googleBtn = document.getElementById("google-signup");
  const azureBtn = document.getElementById("azure-signup");

  if (googleBtn) {
    googleBtn.addEventListener("click", () => handleSSOSignup("google"));
  }

  if (azureBtn) {
    azureBtn.addEventListener("click", () => handleSSOSignup("azure"));
  }
});
