(() => {
  const INTERFACES = {
    classic: { mode: "shared", requiresRestart: false },
    minimal: { mode: "shared", requiresRestart: false },
    dashboard: { mode: "shared", requiresRestart: false },
    atlas: { mode: "shared", requiresRestart: false },
    journal: { mode: "shared", requiresRestart: false },
    commandroom: { mode: "shared", requiresRestart: false },
    wave: { mode: "shared", requiresRestart: false },
    jarvis: {
      mode: "custom",
      requiresRestart: true,
      css: "interfaces/jarvis/interface.css",
      js: "interfaces/jarvis/interface.js"
    },
    nexus: {
      mode: "custom",
      requiresRestart: true,
      css: "interfaces/nexus/interface.css",
      js: "interfaces/nexus/interface.js"
    }
  };

  let pendingInterface = localStorage.getItem("jarvis-interface") || "classic";
  let loadedCustomStyles = new Set();

  function currentInterface() {
    return localStorage.getItem("jarvis-interface") || "classic";
  }

  function requiresInterfaceRestart(name) {
    const current = currentInterface();
    if (current === name) return false;
    const currentConfig = getInterfaceConfig(current);
    const nextConfig = getInterfaceConfig(name);
    return currentConfig.mode === "custom" || nextConfig.mode === "custom";
  }

  function getInterfaceConfig(name) {
    return INTERFACES[name] || { mode: "shared", requiresRestart: false };
  }

  function loadCustomAssets(name) {
    const config = getInterfaceConfig(name);
    document.querySelectorAll("link[data-jarvis-interface-css]").forEach((link) => link.remove());
    loadedCustomStyles.clear();
    if (config.mode !== "custom" || !config.css) return;
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = config.css;
    link.dataset.jarvisInterfaceCss = name;
    document.head.appendChild(link);
    loadedCustomStyles.add(name);
  }

  function loadCustomScript(name) {
    const config = getInterfaceConfig(name);
    if (!config.js) return;
    if (document.querySelector(`script[data-jarvis-interface-js="${name}"]`)) return;
    const script = document.createElement("script");
    script.src = config.js;
    script.dataset.jarvisInterfaceJs = name;
    document.body.appendChild(script);
  }

  function applyInterface(name) {
    const config = getInterfaceConfig(name);
    if (typeof window.setInterfaceClass === "function") window.setInterfaceClass(name);
    localStorage.setItem("jarvis-interface", name);
    loadCustomAssets(name);
    loadCustomScript(name);
  }

  function createRestartModal() {
    let modal = document.querySelector("#interfaceRestartModal");
    if (modal) return modal;

    modal = document.createElement("div");
    modal.id = "interfaceRestartModal";
    modal.hidden = true;
    modal.innerHTML = `
      <div class="interface-restart-dialog" role="dialog" aria-modal="true" aria-labelledby="interfaceRestartTitle">
        <h3 id="interfaceRestartTitle">Нужен перезапуск</h3>
        <p id="interfaceRestartText">Этот интерфейс меняет структуру приложения и будет применён после перезапуска Jarvis.</p>
        <div class="interface-restart-actions">
          <button type="button" id="interfaceRestartLater">Позже</button>
          <button type="button" id="interfaceRestartNow" class="primary">Перезапустить</button>
        </div>
      </div>
    `;

    document.body.appendChild(modal);
    modal.querySelector("#interfaceRestartLater").addEventListener("click", () => modal.hidden = true);
    modal.querySelector("#interfaceRestartNow").addEventListener("click", () => {
      applyInterface(pendingInterface);
      modal.hidden = true;
      window.jarvis.restartApp();
    });
    modal.addEventListener("click", (event) => {
      if (event.target === modal) modal.hidden = true;
    });
    return modal;
  }

  function saveInterface(button) {
    const config = getInterfaceConfig(pendingInterface);
    if (!requiresInterfaceRestart(pendingInterface) && !config.requiresRestart) {
      applyInterface(pendingInterface);
      if (button) {
        button.textContent = "Сохранено";
        setTimeout(() => {
          if (button.isConnected) button.textContent = "Сохранить всё";
        }, 1200);
      }
      return;
    }

    const modal = createRestartModal();
    modal.querySelector("#interfaceRestartTitle").textContent =
      `Интерфейс «${pendingInterface}» требует перезапуска`;
    modal.querySelector("#interfaceRestartText").textContent =
      "Настройка будет сохранена, а новый интерфейс применится после перезапуска Jarvis.";
    modal.hidden = false;
  }

  document.addEventListener("click", (event) => {
    const interfaceOption = event.target.closest("[data-interface]");
    if (interfaceOption) pendingInterface = interfaceOption.dataset.interface;

    const saveButton = event.target.closest("#saveAllButton");
    if (!saveButton) return;

    event.preventDefault();
    event.stopImmediatePropagation();
    saveInterface(saveButton);
  }, true);

  window.JarvisInterfaceManager = Object.freeze({
    interfaces: INTERFACES,
    get: getInterfaceConfig,
    register(name, config) {
      if (!name || !config) return;
      INTERFACES[name] = Object.freeze({
        mode: config.mode || "shared",
        requiresRestart: Boolean(config.requiresRestart),
        css: config.css || null,
        js: config.js || null
      });
    }
  });

  loadCustomAssets(pendingInterface);
  loadCustomScript(pendingInterface);
})();
