(() => {
  "use strict";

  const form = document.querySelector("form[data-invitation-registration]");
  const tokenInput = document.querySelector('input[name="token"]');
  const error = document.querySelector("[data-invitation-error]");

  if (!(form instanceof HTMLFormElement) || !(tokenInput instanceof HTMLInputElement)) {
    return;
  }

  const fragment = new URLSearchParams(window.location.hash.slice(1));
  const fragmentToken = fragment.get("token");

  if (fragmentToken) {
    tokenInput.value = fragmentToken;
    window.history.replaceState(null, "", window.location.pathname);
  }

  if (!tokenInput.value) {
    form.hidden = true;
    if (error) {
      error.textContent = "This invitation link is missing its credential.";
    }
  }
})();
