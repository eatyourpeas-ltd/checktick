function updateHiddenFields() {
  const selectedTier = document.querySelector(
    'input[name="selected_tier"]:checked'
  );
  if (selectedTier) {
    // If team tier is selected, use the team size dropdown value
    if (selectedTier.id === "team-tier-radio") {
      const teamSizeSelect = document.getElementById("team-size-select");
      if (teamSizeSelect) {
        document.getElementById("selected-tier").value = teamSizeSelect.value;
        return;
      }
    }
    document.getElementById("selected-tier").value = selectedTier.value;
  }
}

function handleSSOSignup(provider) {
  const selectedTier = document.querySelector(
    'input[name="selected_tier"]:checked'
  );

  let tierValue = selectedTier ? selectedTier.value : "free";

  // If team tier is selected, use the team size dropdown value
  if (selectedTier && selectedTier.id === "team-tier-radio") {
    const teamSizeSelect = document.getElementById("team-size-select");
    if (teamSizeSelect) {
      tierValue = teamSizeSelect.value;
    }
  }

  // Store choices in sessionStorage for post-auth processing
  sessionStorage.setItem("signup_tier", tierValue);

  // Get the 'next' URL from current page's query params (e.g., from survey invite)
  const urlParams = new URLSearchParams(window.location.search);
  const nextUrl = urlParams.get("next");
  if (nextUrl) {
    sessionStorage.setItem("signup_next_url", nextUrl);
  }

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

  // Add event listener to team size dropdown
  const teamSizeSelect = document.getElementById("team-size-select");
  if (teamSizeSelect) {
    teamSizeSelect.addEventListener("change", function () {
      // Also check the team tier radio when changing team size
      const teamRadio = document.getElementById("team-tier-radio");
      if (teamRadio) {
        teamRadio.checked = true;
        teamRadio.value = this.value; // Update the radio value to match
      }
      updateHiddenFields();
    });

    // When clicking on the dropdown, ensure the team radio is selected
    teamSizeSelect.addEventListener("focus", function () {
      const teamRadio = document.getElementById("team-tier-radio");
      if (teamRadio) {
        teamRadio.checked = true;
      }
      updateHiddenFields();
    });
  }

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
