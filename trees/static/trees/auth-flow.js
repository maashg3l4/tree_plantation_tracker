document.addEventListener("DOMContentLoaded", () => {
  const username = document.querySelector("#id_username");
  const usernameStatus = document.querySelector("#username-status");
  let usernameTimer;

  if (username && usernameStatus) {
    username.addEventListener("input", () => {
      window.clearTimeout(usernameTimer);
      const value = username.value.trim().replace(/^@/, "");
      usernameStatus.textContent = "";
      usernameStatus.className = "username-status";
      if (value.length < 3) return;

      usernameTimer = window.setTimeout(async () => {
        const endpoint = new URL(usernameStatus.dataset.checkUrl, window.location.origin);
        endpoint.searchParams.set("username", value);
        try {
          const response = await fetch(endpoint, { headers: { Accept: "application/json" } });
          if (!response.ok) throw new Error("Availability check failed.");
          const result = await response.json();
          usernameStatus.textContent = result.available ? "That handle is available." : "That handle is already in use.";
          usernameStatus.classList.toggle("is-available", result.available);
          usernameStatus.classList.toggle("is-taken", !result.available);
        } catch (error) {
          usernameStatus.textContent = "We couldn't check that handle just now. You can still try it.";
          usernameStatus.classList.add("is-taken");
          console.warn("Username availability check failed.", error);
        }
      }, 300);
    });
  }

  document.querySelectorAll('input[type="password"]').forEach((input) => {
    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "password-visibility-toggle";
    toggle.textContent = "Show";
    toggle.setAttribute("aria-label", "Show password");
    toggle.addEventListener("click", () => {
      const show = input.type === "password";
      input.type = show ? "text" : "password";
      toggle.textContent = show ? "Hide" : "Show";
      toggle.setAttribute("aria-label", show ? "Hide password" : "Show password");
      input.focus();
    });
    input.insertAdjacentElement("afterend", toggle);
  });
});
