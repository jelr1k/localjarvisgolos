(() => {
  const pages = [
    ["home", "Обзор", "◈"],
    ["chat", "Чат", "◌"],
    ["commands", "Команды", "⌘"],
    ["workspace", "Workspace", "◎"],
    ["ai", "ИИ", "◇"]
  ];

  const NODE_DEFS = [
    { id: "core", title: "WORKSPACE CORE", tag: "CORE", description: "Центральный слой пространства. Связывает возможности Jarvis между собой.", x: 0, y: 0, state: "core", page: "workspace" },
    { id: "voice", title: "VOICE", tag: "01", description: "Запись, тишина, Whisper и голосовой контур.", x: -390, y: -250, state: "active", page: "settings" },
    { id: "wake", title: "WAKE WORD", tag: "02", description: "Vosk и фраза пробуждения Jarvis.", x: -620, y: -480, state: "active", page: "settings" },
    { id: "model", title: "MODEL", tag: "03", description: "Локальная модель и параметры генерации.", x: 390, y: -250, state: "active", page: "ai" },
    { id: "stats", title: "AI STATS", tag: "04", description: "Метрики модели, CPU, RAM, VRAM и времени обработки.", x: 680, y: 0, state: "active", page: "ai" },
    { id: "files", title: "FILES", tag: "05", description: "Файловые ресурсы и объекты Workspace.", x: -400, y: 280, state: "active", page: "workspace" },
    { id: "aliases", title: "ALIASES", tag: "06", description: "Связанные имена и пользовательские объекты.", x: -680, y: 500, state: "active", page: "workspace" },
    { id: "tools", title: "TOOLS", tag: "07", description: "Инструменты и разрешения, доступные Jarvis.", x: -100, y: 510, state: "active", page: "commands" },
    { id: "chat", title: "CHAT", tag: "08", description: "Текстовый канал взаимодействия с локальной моделью.", x: 400, y: 310, state: "active", page: "chat" }
  ];

  const LINK_DEFS = [
    ["core", "voice"], ["voice", "wake"],
    ["core", "model"], ["model", "stats"],
    ["core", "files"], ["files", "aliases"], ["files", "tools"],
    ["core", "chat"], ["model", "chat"]
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

  function go(page) {
    if (typeof window.go === "function") window.go(page);
  }

  function installShell() {
    if (document.querySelector(".nx-shell")) return;

    const shell = document.createElement("header");
    shell.className = "nx-shell";
    shell.innerHTML = `
      <div class="nx-brand">
        <span class="nx-logo">N</span>
        <div><b>NEXUS</b><small>JARVIS WORKSPACE</small></div>
      </div>
      <nav class="nx-nav">
        ${pages.map(([id, label, icon]) =>
          `<button type="button" data-nx-page="${id}"><i>${icon}</i>${label}</button>`
        ).join("")}
      </nav>
      <button class="nx-shell-action" type="button" data-nx-page="settings" title="Настройки">⚙</button>
    `;

    document.body.appendChild(shell);

    shell.querySelectorAll("[data-nx-page]").forEach(button => {
      button.addEventListener("click", () => go(button.dataset.nxPage));
    });
  }

  function sync(page) {
    document.querySelectorAll("[data-nx-page]").forEach(button => {
      button.classList.toggle("active", button.dataset.nxPage === page);
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
      if (!entry) return;

      entry.def.state = entry.def.state === "off" ? "active" : "off";
      entry.element.dataset.state = entry.def.state;
      updateInspector();
      renderLinks();
    });

    document.querySelector("[data-nx-open]").addEventListener("click", () => {
      if (!state.selected) return;
      const entry = state.nodes.get(state.selected);
      if (entry) go(entry.def.page);
    });

    resetView();
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

  function updateInspector() {
    const inspector = document.querySelector("[data-nx-inspector]");
    const toggle = document.querySelector("[data-nx-toggle]");
    const open = document.querySelector("[data-nx-open]");

    if (!inspector || !toggle || !open) return;

    if (!state.selected) {
      inspector.innerHTML = `
        <span class="nx-label">NO SELECTION</span>
        <strong>Выбери узел</strong>
        <p>Кликни объект в пространстве. Его связи и состояние появятся здесь.</p>
      `;
      toggle.disabled = true;
      open.disabled = true;
      return;
    }

    const entry = state.nodes.get(state.selected);
    if (!entry) return;

    const { def } = entry;
    const stateLabel = def.state === "off" ? "ОТКЛЮЧЁН" : def.state === "core" ? "CORE" : "АКТИВЕН";

    inspector.innerHTML = `
      <span class="nx-label">${def.tag} / ${stateLabel}</span>
      <strong>${def.title}</strong>
      <p>${def.description}</p>
    `;

    toggle.disabled = def.state === "core";
    toggle.textContent = def.state === "off" ? "Включить" : "Отключить";
    open.disabled = false;
  }

  function renderLinks() {
    const world = document.querySelector(".nx-world");
    if (!world) return;

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

    state.scale = 1;
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

    const form = document.querySelector("#nxChatForm");
    const input = document.querySelector("#nxChatInput");
    const messages = document.querySelector("#nxMessages");

    if (form && input && messages && !form.dataset.bound) {
      form.dataset.bound = "true";
      form.addEventListener("submit", event => {
        event.preventDefault();
        const value = input.value.trim();
        if (!value) return;

        const item = document.createElement("div");
        item.className = "nx-msg user";
        item.innerHTML = "<label>ВЫ</label><p></p>";
        item.querySelector("p").textContent = value;
        messages.appendChild(item);
        messages.scrollTop = messages.scrollHeight;
        input.value = "";
      });
    }
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

  window.NexusInterface = Object.freeze({ go, sync, resetView });
  window.addEventListener("resize", () => {
    if (document.querySelector(".nx-viewport")) render();
  });

  bindDynamicPage();
  window.dispatchEvent(new CustomEvent("nexus-interface-ready"));
})();