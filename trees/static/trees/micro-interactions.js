document.addEventListener("DOMContentLoaded", () => {
  document.addEventListener("click", (event) => {
    const button = event.target.closest("button, .primary-action, .secondary-action");
    if (button && !button.disabled) {
      button.classList.remove("tap-feedback");
      void button.offsetWidth;
      button.classList.add("tap-feedback");
    }
  });

  const cards = document.querySelectorAll(".tree-card, .profile-post-tile, .discover-person");
  if ("IntersectionObserver" in window) {
    const observer = new IntersectionObserver(
      (entries) => entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        }
      }),
      { threshold: 0.08 },
    );
    cards.forEach((card) => observer.observe(card));
  } else {
    cards.forEach((card) => card.classList.add("is-visible"));
  }

  let deferredPrompt;
  const prompt = document.getElementById("install-app-prompt");
  const installButton = document.getElementById("install-app-button");
  const dismissButton = document.getElementById("dismiss-install-button");
  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    deferredPrompt = event;
    if (prompt && localStorage.getItem("install-prompt-dismissed") !== "true") {
      prompt.hidden = false;
    }
  });
  installButton?.addEventListener("click", async () => {
    if (!deferredPrompt) return;
    deferredPrompt.prompt();
    await deferredPrompt.userChoice;
    deferredPrompt = null;
    prompt.hidden = true;
  });
  dismissButton?.addEventListener("click", () => {
    prompt.hidden = true;
    localStorage.setItem("install-prompt-dismissed", "true");
  });

  document.querySelectorAll("[data-follow-url]").forEach((button) => {
    button.addEventListener("click", async () => {
      const csrfCookie = document.cookie.split("; ").find((item) => item.startsWith("csrftoken="));
      const csrf = csrfCookie?.split("=")[1] || document.querySelector('meta[name="csrf-token"]')?.content;
      button.disabled = true;
      try {
        const response = await fetch(button.dataset.followUrl, {
          method: "POST",
          headers: { "X-CSRFToken": csrf || "", "X-Requested-With": "XMLHttpRequest" },
        });
        const result = await response.json();
        if (!response.ok || !result.success) throw new Error(result.error || "Follow update failed.");
        button.dataset.following = String(result.following);
        button.classList.toggle("is-following", result.following);
        button.textContent = result.following ? "Following ✓" : "Follow";
        const count = document.getElementById("follower-count");
        if (count) count.textContent = result.follower_count;
        showCommunityToast(result.following ? "You’re now following this gardener." : "You unfollowed this gardener.");
      } catch (error) {
        showCommunityToast(error.message || "We couldn’t update your follow. Please try again.");
      } finally {
        button.disabled = false;
      }
    });
  });

  document.querySelectorAll(".tree-card, .discover-person").forEach((card) => {
    card.addEventListener("touchstart", () => card.classList.add("is-touching"), { passive: true });
    ["touchend", "touchcancel"].forEach((name) => card.addEventListener(name, () => card.classList.remove("is-touching"), { passive: true }));
  });
});

function showCommunityToast(message) {
  let toast = document.getElementById("community-toast");
  if (!toast) {
    toast = document.createElement("div");
    toast.id = "community-toast";
    toast.className = "community-toast";
    toast.setAttribute("role", "status");
    toast.setAttribute("aria-live", "polite");
    document.body.append(toast);
  }
  toast.textContent = message;
  toast.classList.add("is-visible");
  window.clearTimeout(toast.hideTimer);
  toast.hideTimer = window.setTimeout(() => toast.classList.remove("is-visible"), 2600);
}
