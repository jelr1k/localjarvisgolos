(() => {
  const pages = [
    ["home", "Главная", "◉"],
    ["chat", "Разговор", "◌"],
    ["commands", "Команды", "⌘"],
    ["workspace", "Workspace", "□"],
    ["ai", "Интеллект", "◇"]
  ];

  function go(page) {
    if (typeof window.go === "function") {
      window.go(page);
      return;
    }
    const target = document.querySelector(`.nav-item[data-page="${page}"]`);
    target?.click();
  }

  function installShell() {
    if (document.querySelector(".jx-header")) return;

    const header = document.createElement("header");
    header.className = "jx-header";
    header.innerHTML = `
      <div class="jx-brand">
        <span class="jx-brand-mark">J</span>
        <span class="jx-brand-name">JARVIS</span>
      </div>
      <nav class="jx-nav" aria-label="Навигация">
        ${pages.map(([id, label, icon]) => `<button type="button" data-jx-page="${id}" title="${label}">${icon} <span>${label}</span></button>`).join("")}
      </nav>
      <button class="jx-header-action" type="button" data-jx-page="settings" title="Настройки">⚙</button>
    `;

    const dock = document.createElement("div");
    dock.className = "jx-dock";
    dock.innerHTML = `
      <button class="jx-dock-command" type="button" data-jx-focus>
        <span>⌕</span><span>Что делаем?</span>
      </button>
      <button type="button" data-jx-page="chat" title="Разговор">◌</button>
      <button type="button" data-jx-page="commands" title="Команды">⌘</button>
      <button type="button" data-jx-page="settings" title="Настройки">⚙</button>
    `;

    const status = document.createElement("div");
    status.className = "jx-status";
    status.innerHTML = "<i></i><span>LOCAL / READY</span>";

    document.body.append(header, dock, status);

    document.querySelectorAll("[data-jx-page]").forEach((button) => {
      button.addEventListener("click", () => go(button.dataset.jxPage));
    });

    document.querySelector("[data-jx-focus]")?.addEventListener("click", () => {
      const input = document.querySelector("#chatInput, #jarvisCommandInput");
      if (input) input.focus();
      else go("chat");
    });
  }

  function sync(page) {
    document.querySelectorAll(".jx-nav button").forEach((button) => {
      button.classList.toggle("active", button.dataset.jxPage === page);
    });
  }

  document.addEventListener("click", (event) => {
    const pageButton = event.target.closest("[data-jx-page]");
    if (pageButton) {
      // Navigation is handled by the shell listener. This branch intentionally
      // does not duplicate it.
    }
  });

  installShell();
  window.JarvisCustomInterface = Object.freeze({ go, sync });
  window.dispatchEvent(new CustomEvent("jarvis-custom-interface-ready"));
})();