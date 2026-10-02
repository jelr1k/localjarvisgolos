(() => {
  const pages = [
    ["home", "Главная", "◈"],
    ["chat", "Чат", "◌"],
    ["commands", "Команды", "⌘"],
    ["workspace", "Настройки", "⚙"],
    ["ai", "ИИ", "◇"]
  ];

  const NAV_SETTINGS = [
    ["home", "Главная"],
    ["chat", "Чат"],
    ["commands", "Команды"],
    ["ai", "ИИ"]
  ];

  const NODE_DEFS = [
    { id: "core", title: "SETTINGS CORE", tag: "CORE", description: "Центр настроек NEXUS. Все параметры находятся внутри этого пространства.", x: 0, y: 0, state: "core", kind: "core" },
    { id: "interface", title: "INTERFACE", tag: "01", description: "Выбор оболочки Jarvis. Custom-интерфейсы применяются после перезапуска.", x: -410, y: -310, state: "active", kind: "interface" },
    { id: "theme", title: "THEME", tag: "02", description: "Цветовая схема приложения. Применяется сразу.", x: 0, y: -410, state: "active", kind: "theme" },
    { id: "navigation", title: "NAVIGATION", tag: "03", description: "Управление вкладками верхней навигации. Скрытые вкладки не удаляются.", x: 430, y: -290, state: "active", kind: "navigation" },
    { id: "application", title: "APPLICATION", tag: "04", description: "Имя ассистента и режим тестирования команд.", x: -470, y: 260, state: "active", kind: "application" },
    { id: "voice", title: "VOICE", tag: "05", description: "Параметры голосового контура и текущие значения голосовых настроек.", x: 0, y: 390, state: "active", kind: "voice" },
    { id: "workspace", title: "WORKSPACE", tag: "06", description: "Рабочая область, алиасы и ограничения файловых операций.", x: 470, y: 240, state: "active", kind: "workspace" },
    { id: "system", title: "SYSTEM", tag: "07", description: "Системные параметры приложения и язык интерфейса.", x: 780, y: 500, state: "active", kind: "system" }
  ];

  const LINK_DEFS = [
    ["core", "interface"], ["core", "theme"], ["core", "navigation"],
    ["core", "application"], ["core", "voice"], ["core", "workspace"],
    ["core", "system"]
  ];

  const state = {
    x: 0,
    y: 0,
    scale: 1,
    selected: null,
    pan: false,
    pointerX: 0,
    pointerY: 0,
    nodes: new Map()
  };

  const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
  const getSetting = (key, fallback = "") => localStorage.getItem(key) ?? fallback;
  const setSetting = (key, value) => localStorage.setItem(key, String(value));

  function go(page) {
    if (typeof window.go === "function") window.go(page);
  }

  function getHiddenNav() {
    try {
      return JSON.parse(localStorage.getItem("nexus-hidden-nav") || "[]");
    } catch {
      return [];
    }
  }

  function setHiddenNav(list) {
    localStorage.setItem("nexus-hidden-nav", JSON.stringify(list));
    applyNavVisibility();
  }

  function applyNavVisibility() {
    const hidden = new Set(getHiddenNav());
    document.querySelectorAll(".nx-nav [data-nx-page]").forEach(button => {
      button.hidden = hidden.has(button.dataset.nxPage);
    });
  }

  function installShell() {
    if (document.querySelector(".nx-shell")) {
      applyNavVisibility();
      return;
    }

    const shell = document.createElement("header");
    shell.className = "nx-shell";
    shell.innerHTML = `
      <div class="nx-brand">
        <span class="nx-logo">N</span>
        <div><b>NEXUS</b><small>JARVIS SETTINGS</small></div>
      </div>
      <nav class="nx-nav">
        ${pages.map(([id, label, icon]) =>
          `<button type="button" data-nx-page="${id}"><i>${icon}</i>${label}</button>`
        ).join("")}
      </nav>
    `;

    document.body.appendChild(shell);

    shell.querySelectorAll("[data-nx-page]").forEach(button => {
      button.addEventListener("click", () => go(button.dataset.nxPage));
    });

    applyNavVisibility();
  }

  function sync(page) {
    const target = page === "settings" ? "workspace" : page;
    document.querySelectorAll("[data-nx-page]").forEach(button => {
      button.classList.toggle("active", button.dataset.nxPage === target);
    });
  }

  function bindWorkspace() {
    const viewport = document.querySelector(".nx-viewport");
    const world = document.querySelector(".nx-world");
    const nodesRoot = document.querySelector(".nx-nodes");
    const linksRoot = document.querySelector(".nx-links");

    if (!viewport || !world || !nodesRoot || !linksRoot || viewport.dataset.bound === "true") return;
    viewport.dataset.bound = "true";

    state.nodes.clear();
    state.selected = null;
    nodesRoot.innerHTML = "";
    linksRoot.innerHTML = "";

    NODE_DEFS.forEach(def => {
      const node = document.createElement("button");
      node.type = "button";
      node.className = "nx-node";
      node.dataset.nodeId = def.id;
      node.dataset.state = def.state;
      node.style.left = `${def.x}px`;
      node.style.top = `${def.y}px`;
      node.innerHTML = `
        <span class="nx-node-orbit"></span>
        <span class="nx-node-top"><strong>${def.title}</strong><em>${def.tag}</em></span>
        <small>${def.description}</small>
      `;

      node.addEventListener("pointerdown", event => {
        event.stopPropagation();
        node.setPointerCapture(event.pointerId);
        selectNode(def.id);

        const startX = event.clientX;
        const startY = event.clientY;
        const originX = def.x;
        const originY = def.y;

        const move = moveEvent => {
          def.x = originX + (moveEvent.clientX - startX) / state.scale;
          def.y = originY + (moveEvent.clientY - startY) / state.scale;
          node.style.left = `${def.x}px`;
          node.style.top = `${def.y}px`;
          renderLinks();
        };

        const up = upEvent => {
          node.releasePointerCapture(upEvent.pointerId);
          node.classList.remove("dragging");
          node.removeEventListener("pointermove", move);
          node.removeEventListener("pointerup", up);
        };

        node.classList.add("dragging");
        node.addEventListener("pointermove", move);
        node.addEventListener("pointerup", up);
      });

      nodesRoot.appendChild(node);
      state.nodes.set(def.id, { def, element: node });
    });

    LINK_DEFS.forEach(([from, to]) => {
      const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
      line.dataset.from = from;
      line.dataset.to = to;
      linksRoot.appendChild(line);
    });

    document.querySelector("[data-nx-node-count]").textContent = NODE_DEFS.length;
    document.querySelector("[data-nx-link-count]").textContent = LINK_DEFS.length;

    viewport.addEventListener("pointerdown", event => {
      if (event.target.closest(".nx-node") || event.target.closest(".nx-hud") || event.target.closest(".nx-zoom")) return;
      state.pan = true;
      state.pointerX = event.clientX;
      state.pointerY = event.clientY;
      viewport.classList.add("is-panning");
    });

    window.addEventListener("pointermove", event => {
      if (!state.pan) return;
      state.x += event.clientX - state.pointerX;
      state.y += event.clientY - state.pointerY;
      state.pointerX = event.clientX;
      state.pointerY = event.clientY;
      render();
    });

    window.addEventListener("pointerup", () => {
      state.pan = false;
      viewport.classList.remove("is-panning");
    });

    viewport.addEventListener("wheel", event => {
      event.preventDefault();
      zoomAt(event.deltaY < 0 ? 1.1 : 0.9, event.clientX, event.clientY);
    }, { passive: false });

    document.querySelector("[data-nx-plus]").addEventListener("click", () => zoomAt(1.15));
    document.querySelector("[data-nx-minus]").addEventListener("click", () => zoomAt(0.87));
    document.querySelector("[data-nx-reset]").addEventListener("click", resetView);

    document.querySelector("[data-nx-toggle]").addEventListener("click", () => {
      if (!state.selected) return;
      const entry = state.nodes.get(state.selected);
      if (!entry || entry.def.kind === "core") return;
      entry.def.state = entry.def.state === "off" ? "active" : "off";
      entry.element.dataset.state = entry.def.state;
      updateInspector();
    });

    document.querySelector("[data-nx-open]").addEventListener("click", () => {
      if (!state.selected) return;
      const entry = state.nodes.get(state.selected);
      if (entry) focusSettingsNode(entry.def.id);
    });

    document.querySelector("[data-nx-inspector]").addEventListener("click", handleInspectorClick);
    document.querySelector("[data-nx-inspector]").addEventListener("change", handleInspectorChange);

    resetView();
  }

  function focusSettingsNode(id) {
    const entry = state.nodes.get(id);
    if (!entry) return;

    const viewport = document.querySelector(".nx-viewport");
    if (!viewport) return;

    state.scale = 1;
    state.x = viewport.clientWidth / 2 - entry.def.x;
    state.y = viewport.clientHeight / 2 - entry.def.y;
    selectNode(id);
    render();
  }

  function selectNode(id) {
    state.selected = id;

    state.nodes.forEach(({ element, def }) => {
      const selected = def.id === id;
      const related = LINK_DEFS.some(([a, b]) =>
        (a === id && b === def.id) || (b === id && a === def.id)
      );

      element.classList.toggle("selected", selected);
      element.classList.toggle("related", !selected && related);
    });

    updateInspector();
    renderLinks();
  }

  function interfaceOptions() {
    const current = localStorage.getItem("jarvis-interface") || "classic";
    const names = {
      classic: "Классический",
      minimal: "Минималистичный",
      dashboard: "Dashboard",
      atlas: "Atlas",
      journal: "Journal",
      commandroom: "Command Room",
      wave: "Wave",
      jarvis: "JARVIS",
      nexus: "NEXUS"
    };

    return Object.entries(names).map(([id, label]) =>
      `<button type="button" class="nx-choice ${id === current ? "selected" : ""}" data-nx-interface="${id}">
        <b>${label}</b><small>${id === current ? "Текущий" : id === "nexus" || id === "jarvis" ? "Требует перезапуска" : "Применяется сразу"}</small>
      </button>`
    ).join("");
  }

  function themeOptions() {
    const current = localStorage.getItem("jarvis-theme") || "dark";
    const names = {
      dark: "Тёмная", light: "Светлая", "gradient-amber": "Янтарный",
      "gradient-blue": "Синий", "gradient-purple": "Фиолетовый",
      "mono-slate": "Сланец", "mono-graphite": "Графит", "mono-silver": "Серебро",
      "mono-cream": "Кремовый", "gradient-cyan": "Циан", "gradient-green": "Изумруд",
      "gradient-red": "Красный", "gradient-sunset": "Закат"
    };

    return Object.entries(names).map(([id, label]) =>
      `<button type="button" class="nx-choice ${id === current ? "selected" : ""}" data-nx-theme="${id}">${label}</button>`
    ).join("");
  }

  function navigationControls() {
    const hidden = new Set(getHiddenNav());

    return NAV_SETTINGS.map(([id, label]) => `
      <label class="nx-setting-row">
        <span><b>${label}</b><small>Верхняя вкладка</small></span>
        <input type="checkbox" data-nx-nav="${id}" ${hidden.has(id) ? "" : "checked"}>
      </label>
    `).join("");
  }

  function updateInspector() {
    const inspector = document.querySelector("[data-nx-inspector]");
    const toggle = document.querySelector("[data-nx-toggle]");
    const open = document.querySelector("[data-nx-open]");

    if (!inspector || !toggle || !open) return;

    if (!state.selected) {
      inspector.innerHTML = `
        <span class="nx-label">SETTINGS</span>
        <strong>Выбери узел</strong>
        <p>Здесь находятся все настройки приложения. Узлы можно таскать, а поле можно масштабировать и перемещать.</p>
      `;
      toggle.disabled = true;
      open.disabled = true;
      return;
    }

    const entry = state.nodes.get(state.selected);
    if (!entry) return;
    const { def } = entry;

    let content = `
      <span class="nx-label">${def.tag} / ${def.state === "off" ? "ОТКЛЮЧЁН" : "АКТИВЕН"}</span>
      <strong>${def.title}</strong>
      <p>${def.description}</p>
    `;

    if (def.kind === "interface") {
      content += `<div class="nx-control-block"><span class="nx-control-title">Оболочка</span><div class="nx-choice-grid">${interfaceOptions()}</div></div>`;
    }

    if (def.kind === "theme") {
      content += `<div class="nx-control-block"><span class="nx-control-title">Тема</span><div class="nx-choice-grid theme-grid-nx">${themeOptions()}</div></div>`;
    }

    if (def.kind === "navigation") {
      content += `<div class="nx-control-block"><span class="nx-control-title">Верхние вкладки</span>${navigationControls()}<small class="nx-note">Настройки остаются доступны всегда.</small></div>`;
    }

    if (def.kind === "application") {
      content += `
        <div class="nx-control-block">
          <label class="nx-field"><span>Имя ассистента</span><input data-nx-setting="assistant-name" value="${getSetting("jarvis-assistant-name", "Jarvis")}"></label>
          <label class="nx-setting-row"><span><b>Режим тестирования</b><small>Только Command Router, без вызова ИИ</small></span><input type="checkbox" data-nx-setting="testing" ${getSetting("jarvis-testing-mode","false") === "true" ? "checked" : ""}></label>
        </div>`;
    }

    if (def.kind === "voice") {
      content += `
        <div class="nx-control-block">
          <div class="nx-readonly"><span>Wake word</span><b>Jarvis</b></div>
          <div class="nx-readonly"><span>Микрофон</span><b>Системный</b></div>
          <label class="nx-field"><span>Тишина до автоотправки</span><input type="number" min="0.2" max="10" step="0.1" data-nx-setting="silence" value="${getSetting("jarvis-silence-threshold","1.2")}"><small>сек.</small></label>
        </div>`;
    }

    if (def.kind === "workspace") {
      content += `
        <div class="nx-control-block">
          <div class="nx-readonly"><span>Рабочая область</span><b>Только Workspace</b></div>
          <button type="button" class="nx-wide-action" data-nx-action="aliases">Открыть алиасы</button>
          <small class="nx-note">Функция алиасов открывает существующий раздел команд/ресурсов, не создавая отдельную страницу.</small>
        </div>`;
    }

    if (def.kind === "system") {
      content += `
        <div class="nx-control-block">
          <label class="nx-field"><span>Язык</span><select data-nx-setting="language"><option value="ru">Русский</option><option value="en">English</option></select></label>
          <div class="nx-readonly"><span>Интерфейс</span><b>NEXUS</b></div>
        </div>`;
    }

    inspector.innerHTML = content;

    const language = inspector.querySelector('[data-nx-setting="language"]');
    if (language) language.value = getSetting("jarvis-language", "ru");

    toggle.disabled = def.kind === "core";
    toggle.textContent = def.state === "off" ? "Включить узел" : "Отключить узел";
    open.disabled = def.kind === "core";
    open.textContent = "Центрировать";
  }

  function handleInspectorClick(event) {
    const interfaceButton = event.target.closest("[data-nx-interface]");
    if (interfaceButton) {
      const name = interfaceButton.dataset.nxInterface;
      localStorage.setItem("jarvis-interface", name);

      if (window.JarvisInterfaceManager) {
        const save = document.createElement("button");
        save.id = "saveAllButton";
        save.hidden = true;
        document.body.appendChild(save);
        interfaceButton.closest(".nx-choice-grid").querySelectorAll(".nx-choice").forEach(item => item.classList.remove("selected"));
        interfaceButton.classList.add("selected");
        save.click();
        save.remove();
      } else {
        setInterfaceClass(name);
        location.reload();
      }
      return;
    }

    const themeButton = event.target.closest("[data-nx-theme]");
    if (themeButton) {
      const theme = themeButton.dataset.nxTheme;
      if (typeof window.applyTheme === "function") window.applyTheme(theme);
      else {
        localStorage.setItem("jarvis-theme", theme);
        document.body.className = document.body.className.replace(/theme-[^ ]+/g, "");
      }
      themeButton.closest(".nx-choice-grid").querySelectorAll(".nx-choice").forEach(item => item.classList.remove("selected"));
      themeButton.classList.add("selected");
      return;
    }

    const action = event.target.closest("[data-nx-action]");
    if (action?.dataset.nxAction === "aliases") {
      go("commands");
    }
  }

  function handleInspectorChange(event) {
    const nav = event.target.closest("[data-nx-nav]");
    if (nav) {
      const id = nav.dataset.nxNav;
      const hidden = new Set(getHiddenNav());
      if (nav.checked) hidden.delete(id);
      else hidden.add(id);
      setHiddenNav([...hidden]);
      return;
    }

    const setting = event.target.closest("[data-nx-setting]");
    if (!setting) return;

    const key = setting.dataset.nxSetting;
    if (key === "assistant-name") setSetting("jarvis-assistant-name", setting.value);
    if (key === "testing") setSetting("jarvis-testing-mode", setting.checked);
    if (key === "silence") setSetting("jarvis-silence-threshold", setting.value);
    if (key === "language") {
      setSetting("jarvis-language", setting.value);
      if (typeof window.applyLanguage === "function") window.applyLanguage(setting.value);
    }
  }

  function renderLinks() {
    const lines = [...document.querySelectorAll(".nx-links line")];

    lines.forEach(line => {
      const from = state.nodes.get(line.dataset.from);
      const to = state.nodes.get(line.dataset.to);
      if (!from || !to) return;

      const ax = from.def.x + from.element.offsetWidth / 2;
      const ay = from.def.y + from.element.offsetHeight / 2;
      const bx = to.def.x + to.element.offsetWidth / 2;
      const by = to.def.y + to.element.offsetHeight / 2;

      line.setAttribute("x1", ax);
      line.setAttribute("y1", ay);
      line.setAttribute("x2", bx);
      line.setAttribute("y2", by);

      const active = state.selected &&
        (line.dataset.from === state.selected || line.dataset.to === state.selected);

      line.classList.toggle("active", Boolean(active));
    });
  }

  function render() {
    const world = document.querySelector(".nx-world");
    if (!world) return;

    world.style.transform = `translate3d(${state.x}px, ${state.y}px, 0) scale(${state.scale})`;
    const zoom = document.querySelector("[data-nx-zoom]");
    if (zoom) zoom.textContent = `${Math.round(state.scale * 100)}%`;
    renderLinks();
  }

  function resetView() {
    const viewport = document.querySelector(".nx-viewport");
    if (!viewport) return;
    state.scale = 0.92;
    state.x = viewport.clientWidth / 2;
    state.y = viewport.clientHeight / 2;
    render();
  }

  function zoomAt(multiplier, clientX = window.innerWidth / 2, clientY = window.innerHeight / 2) {
    const viewport = document.querySelector(".nx-viewport");
    if (!viewport) return;

    const rect = viewport.getBoundingClientRect();
    const localX = clientX - rect.left;
    const localY = clientY - rect.top;
    const oldScale = state.scale;
    const nextScale = clamp(oldScale * multiplier, 0.35, 2.5);
    if (nextScale === oldScale) return;

    const worldX = (localX - state.x) / oldScale;
    const worldY = (localY - state.y) / oldScale;

    state.scale = nextScale;
    state.x = localX - worldX * nextScale;
    state.y = localY - worldY * nextScale;
    render();
  }

  function bindDynamicPage() {
    if (document.querySelector(".nx-viewport")) bindWorkspace();
  }

  installShell();

  const pageContainer = document.querySelector("#pageContainer");
  new MutationObserver(bindDynamicPage).observe(pageContainer || document.body, {
    childList: true,
    subtree: true
  });

  document.addEventListener("click", event => {
    const button = event.target.closest("[data-nx-page]");
    if (button) sync(button.dataset.nxPage);
  });

  window.NexusInterface = Object.freeze({ go, sync, resetView, selectNode });
  window.addEventListener("resize", () => {
    if (document.querySelector(".nx-viewport")) render();
  });

  bindDynamicPage();
  window.dispatchEvent(new CustomEvent("nexus-interface-ready"));
})();