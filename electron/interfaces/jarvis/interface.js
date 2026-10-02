(() => {
  const root = document.documentElement;
  const updateClock = () => {
    const target = document.querySelector("[data-jarvis-clock]");
    if (target) {
      target.textContent = new Intl.DateTimeFormat("ru-RU", {
        hour: "2-digit",
        minute: "2-digit"
      }).format(new Date());
    }
  };

  document.addEventListener("click", (event) => {
    const action = event.target.closest("[data-jarvis-action]");
    if (!action) return;

    const type = action.dataset.jarvisAction;
    if (type === "focus-command") {
      const input = document.querySelector("#jarvisCommandInput");
      input?.focus();
    }
  });

  updateClock();
  setInterval(updateClock, 30000);

  root.dataset.jarvisInterface = "jarvis";
})();
