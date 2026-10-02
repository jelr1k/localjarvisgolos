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
  {
    "id": "core",
    "title": "SETTINGS CORE",
    "tag": "CORE",
    "description": "Центр настроек NEXUS. Здесь собрана вся карта параметров.",
    "x": 0,
    "y": 0,
    "state": "core",
    "kind": "core"
  },
  {
    "id": "interface",
    "title": "INTERFACE",
    "tag": "01",
    "description": "Оболочка и визуальная структура Jarvis.",
    "x": -720,
    "y": -500,
    "state": "active",
    "kind": "interface"
  },
  {
    "id": "interface-classic",
    "title": "Классический",
    "tag": "01.1",
    "description": "Sidebar и карточки",
    "x": -950,
    "y": -690,
    "state": "active",
    "kind": "interface-item",
    "setting": "classic",
    "parent": "interface"
  },
  {
    "id": "interface-minimal",
    "title": "Минималистичный",
    "tag": "01.2",
    "description": "Узкая навигация",
    "x": -720,
    "y": -690,
    "state": "active",
    "kind": "interface-item",
    "setting": "minimal",
    "parent": "interface"
  },
  {
    "id": "interface-dashboard",
    "title": "Dashboard",
    "tag": "01.3",
    "description": "Верхняя навигация",
    "x": -490,
    "y": -690,
    "state": "active",
    "kind": "interface-item",
    "setting": "dashboard",
    "parent": "interface"
  },
  {
    "id": "interface-atlas",
    "title": "Atlas",
    "tag": "01.4",
    "description": "Плотный командный центр",
    "x": -950,
    "y": -500,
    "state": "active",
    "kind": "interface-item",
    "setting": "atlas",
    "parent": "interface"
  },
  {
    "id": "interface-journal",
    "title": "Journal",
    "tag": "01.5",
    "description": "Редакционный журнал",
    "x": -720,
    "y": -500,
    "state": "active",
    "kind": "interface-item",
    "setting": "journal",
    "parent": "interface"
  },
  {
    "id": "interface-commandroom",
    "title": "Command Room",
    "tag": "01.6",
    "description": "Тёмная консоль",
    "x": -490,
    "y": -500,
    "state": "active",
    "kind": "interface-item",
    "setting": "commandroom",
    "parent": "interface"
  },
  {
    "id": "interface-wave",
    "title": "Wave",
    "tag": "01.7",
    "description": "Анимированные волны",
    "x": -950,
    "y": -310,
    "state": "active",
    "kind": "interface-item",
    "setting": "wave",
    "parent": "interface"
  },
  {
    "id": "interface-jarvis",
    "title": "JARVIS",
    "tag": "01.8",
    "description": "Отдельный интерфейс",
    "x": -720,
    "y": -310,
    "state": "active",
    "kind": "interface-item",
    "setting": "jarvis",
    "parent": "interface"
  },
  {
    "id": "interface-nexus",
    "title": "NEXUS",
    "tag": "01.9",
    "description": "Интерактивные настройки",
    "x": -490,
    "y": -310,
    "state": "active",
    "kind": "interface-item",
    "setting": "nexus",
    "parent": "interface"
  },
  {
    "id": "theme",
    "title": "THEME",
    "tag": "02",
    "description": "Каждая тема теперь отдельный узел.",
    "x": 0,
    "y": -700,
    "state": "active",
    "kind": "theme"
  },
  {
    "id": "theme-dark",
    "title": "Тёмная",
    "tag": "02.1",
    "description": "Базовая",
    "x": -260,
    "y": -1140,
    "state": "active",
    "kind": "theme-item",
    "setting": "dark",
    "parent": "theme"
  },
  {
    "id": "theme-light",
    "title": "Светлая",
    "tag": "02.2",
    "description": "Светлый интерфейс",
    "x": 0,
    "y": -1140,
    "state": "active",
    "kind": "theme-item",
    "setting": "light",
    "parent": "theme"
  },
  {
    "id": "theme-gradient-amber",
    "title": "Янтарный",
    "tag": "02.3",
    "description": "Тёплый градиент",
    "x": 260,
    "y": -1140,
    "state": "active",
    "kind": "theme-item",
    "setting": "gradient-amber",
    "parent": "theme"
  },
  {
    "id": "theme-gradient-blue",
    "title": "Синий",
    "tag": "02.4",
    "description": "Холодный градиент",
    "x": -260,
    "y": -920,
    "state": "active",
    "kind": "theme-item",
    "setting": "gradient-blue",
    "parent": "theme"
  },
  {
    "id": "theme-gradient-purple",
    "title": "Фиолетовый",
    "tag": "02.5",
    "description": "Тёмный градиент",
    "x": 0,
    "y": -920,
    "state": "active",
    "kind": "theme-item",
    "setting": "gradient-purple",
    "parent": "theme"
  },
  {
    "id": "theme-mono-slate",
    "title": "Сланец",
    "tag": "02.6",
    "description": "Монохромный",
    "x": 260,
    "y": -920,
    "state": "active",
    "kind": "theme-item",
    "setting": "mono-slate",
    "parent": "theme"
  },
  {
    "id": "theme-mono-graphite",
    "title": "Графит",
    "tag": "02.7",
    "description": "Монохромный",
    "x": -260,
    "y": -700,
    "state": "active",
    "kind": "theme-item",
    "setting": "mono-graphite",
    "parent": "theme"
  },
  {
    "id": "theme-mono-silver",
    "title": "Серебро",
    "tag": "02.8",
    "description": "Монохромный",
    "x": 0,
    "y": -700,
    "state": "active",
    "kind": "theme-item",
    "setting": "mono-silver",
    "parent": "theme"
  },
  {
    "id": "theme-mono-cream",
    "title": "Кремовый",
    "tag": "02.9",
    "description": "Монохромный",
    "x": 260,
    "y": -700,
    "state": "active",
    "kind": "theme-item",
    "setting": "mono-cream",
    "parent": "theme"
  },
  {
    "id": "theme-gradient-cyan",
    "title": "Циан",
    "tag": "02.10",
    "description": "Градиент",
    "x": -260,
    "y": -480,
    "state": "active",
    "kind": "theme-item",
    "setting": "gradient-cyan",
    "parent": "theme"
  },
  {
    "id": "theme-gradient-green",
    "title": "Изумруд",
    "tag": "02.11",
    "description": "Градиент",
    "x": 0,
    "y": -480,
    "state": "active",
    "kind": "theme-item",
    "setting": "gradient-green",
    "parent": "theme"
  },
  {
    "id": "theme-gradient-red",
    "title": "Красный",
    "tag": "02.12",
    "description": "Градиент",
    "x": 260,
    "y": -480,
    "state": "active",
    "kind": "theme-item",
    "setting": "gradient-red",
    "parent": "theme"
  },
  {
    "id": "theme-gradient-sunset",
    "title": "Закат",
    "tag": "02.13",
    "description": "Градиент",
    "x": -260,
    "y": -260,
    "state": "active",
    "kind": "theme-item",
    "setting": "gradient-sunset",
    "parent": "theme"
  },
  {
    "id": "navigation",
    "title": "NAVIGATION",
    "tag": "03",
    "description": "Отдельный узел для каждой верхней вкладки.",
    "x": 720,
    "y": -500,
    "state": "active",
    "kind": "navigation"
  },
  {
    "id": "navigation-home",
    "title": "Главная",
    "tag": "03.1",
    "description": "Верхняя вкладка",
    "x": 605,
    "y": -595,
    "state": "active",
    "kind": "navigation-item",
    "setting": "home",
    "parent": "navigation"
  },
  {
    "id": "navigation-chat",
    "title": "Чат",
    "tag": "03.2",
    "description": "Верхняя вкладка",
    "x": 835,
    "y": -595,
    "state": "active",
    "kind": "navigation-item",
    "setting": "chat",
    "parent": "navigation"
  },
  {
    "id": "navigation-commands",
    "title": "Команды",
    "tag": "03.3",
    "description": "Верхняя вкладка",
    "x": 605,
    "y": -405,
    "state": "active",
    "kind": "navigation-item",
    "setting": "commands",
    "parent": "navigation"
  },
  {
    "id": "navigation-ai",
    "title": "ИИ",
    "tag": "03.4",
    "description": "Верхняя вкладка",
    "x": 835,
    "y": -405,
    "state": "active",
    "kind": "navigation-item",
    "setting": "ai",
    "parent": "navigation"
  },
  {
    "id": "application",
    "title": "APPLICATION",
    "tag": "04",
    "description": "Параметры самого приложения.",
    "x": -720,
    "y": 300,
    "state": "active",
    "kind": "application"
  },
  {
    "id": "application-app-name",
    "title": "Название приложения",
    "tag": "04.1",
    "description": "JARVIS",
    "x": -835,
    "y": 205,
    "state": "active",
    "kind": "application-item",
    "setting": "app-name",
    "parent": "application"
  },
  {
    "id": "application-assistant-name",
    "title": "Имя ассистента",
    "tag": "04.2",
    "description": "Jarvis",
    "x": -605,
    "y": 205,
    "state": "active",
    "kind": "application-item",
    "setting": "assistant-name",
    "parent": "application"
  },
  {
    "id": "application-testing",
    "title": "Режим тестирования",
    "tag": "04.3",
    "description": "Command Router без ИИ",
    "x": -835,
    "y": 395,
    "state": "active",
    "kind": "application-item",
    "setting": "testing",
    "parent": "application"
  },
  {
    "id": "voice",
    "title": "VOICE",
    "tag": "05",
    "description": "Параметры голосового контура.",
    "x": 0,
    "y": 650,
    "state": "active",
    "kind": "voice"
  },
  {
    "id": "voice-wake-word",
    "title": "Wake word",
    "tag": "05.1",
    "description": "Jarvis",
    "x": -115,
    "y": 555,
    "state": "active",
    "kind": "voice-item",
    "setting": "wake-word",
    "parent": "voice"
  },
  {
    "id": "voice-microphone",
    "title": "Микрофон",
    "tag": "05.2",
    "description": "Системный",
    "x": 115,
    "y": 555,
    "state": "active",
    "kind": "voice-item",
    "setting": "microphone",
    "parent": "voice"
  },
  {
    "id": "voice-silence",
    "title": "Тишина до автоотправки",
    "tag": "05.3",
    "description": "1.2 с",
    "x": -115,
    "y": 745,
    "state": "active",
    "kind": "voice-item",
    "setting": "silence",
    "parent": "voice"
  },
  {
    "id": "workspace",
    "title": "WORKSPACE",
    "tag": "06",
    "description": "Рабочая область и алиасы.",
    "x": 720,
    "y": 300,
    "state": "active",
    "kind": "workspace"
  },
  {
    "id": "workspace-workspace-scope",
    "title": "Рабочая область",
    "tag": "06.1",
    "description": "Только Workspace",
    "x": 605,
    "y": 300,
    "state": "active",
    "kind": "workspace-item",
    "setting": "workspace-scope",
    "parent": "workspace"
  },
  {
    "id": "workspace-aliases",
    "title": "Алиасы",
    "tag": "06.2",
    "description": "Файлы, папки и приложения",
    "x": 835,
    "y": 300,
    "state": "active",
    "kind": "workspace-item",
    "setting": "aliases",
    "parent": "workspace"
  },
  {
    "id": "system",
    "title": "SYSTEM",
    "tag": "07",
    "description": "Системные параметры.",
    "x": 1200,
    "y": 700,
    "state": "active",
    "kind": "system"
  },
  {
    "id": "system-language",
    "title": "Язык",
    "tag": "07.1",
    "description": "Русский",
    "x": 1085,
    "y": 700,
    "state": "active",
    "kind": "system-item",
    "setting": "language",
    "parent": "system"
  },
  {
    "id": "system-interface-id",
    "title": "Текущий интерфейс",
    "tag": "07.2",
    "description": "NEXUS",
    "x": 1315,
    "y": 700,
    "state": "active",
    "kind": "system-item",
    "setting": "interface-id",
    "parent": "system"
  }
];

  const LINK_DEFS = [
  [
    "core",
    "interface"
  ],
  [
    "interface",
    "interface-classic"
  ],
  [
    "interface",
    "interface-minimal"
  ],
  [
    "interface",
    "interface-dashboard"
  ],
  [
    "interface",
    "interface-atlas"
  ],
  [
    "interface",
    "interface-journal"
  ],
  [
    "interface",
    "interface-commandroom"
  ],
  [
    "interface",
    "interface-wave"
  ],
  [
    "interface",
    "interface-jarvis"
  ],
  [
    "interface",
    "interface-nexus"
  ],
  [
    "core",
    "theme"
  ],
  [
    "theme",
    "theme-dark"
  ],
  [
    "theme",
    "theme-light"
  ],
  [
    "theme",
    "theme-gradient-amber"
  ],
  [
    "theme",
    "theme-gradient-blue"
  ],
  [
    "theme",
    "theme-gradient-purple"
  ],
  [
    "theme",
    "theme-mono-slate"
  ],
  [
    "theme",
    "theme-mono-graphite"
  ],
  [
    "theme",
    "theme-mono-silver"
  ],
  [
    "theme",
    "theme-mono-cream"
  ],
  [
    "theme",
    "theme-gradient-cyan"
  ],
  [
    "theme",
    "theme-gradient-green"
  ],
  [
    "theme",
    "theme-gradient-red"
  ],
  [
    "theme",
    "theme-gradient-sunset"
  ],
  [
    "core",
    "navigation"
  ],
  [
    "navigation",
    "navigation-home"
  ],
  [
    "navigation",
    "navigation-chat"
  ],
  [
    "navigation",
    "navigation-commands"
  ],
  [
    "navigation",
    "navigation-ai"
  ],
  [
    "core",
    "application"
  ],
  [
    "application",
    "application-app-name"
  ],
  [
    "application",
    "application-assistant-name"
  ],
  [
    "application",
    "application-testing"
  ],
  [
    "core",
    "voice"
  ],
  [
    "voice",
    "voice-wake-word"
  ],
  [
    "voice",
    "voice-microphone"
  ],
  [
    "voice",
    "voice-silence"
  ],
  [
    "core",
    "workspace"
  ],
  [
    "workspace",
    "workspace-workspace-scope"
  ],
  [
    "workspace",
    "workspace-aliases"
  ],
  [
    "core",
    "system"
  ],
  [
    "system",
    "system-language"
  ],
  [
    "system",
    "system-interface-id"
  ]
];

  const state = {
    x: 0,
    y: 0,
    scale: 1,
    selected: null,
    pan: false,
    pointerX: 0,
    pointerY: 0,
    nodes: new Map(),
    map: "root",
    mapStack: []
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
    updatePageState();
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

  function getMapDefs() {
    if (state.map === "root") return NODE_DEFS.filter(def => def.kind === "core" || !def.parent);
    return NODE_DEFS.filter(def => def.id === state.map || def.parent === state.map);
  }

  function getMapLinks() {
    const visible = new Set(getMapDefs().map(def => def.id));
    return LINK_DEFS.filter(([from, to]) => visible.has(from) && visible.has(to));
  }

  function openSettingsMap(id) {
    const def = NODE_DEFS.find(item => item.id === id);
    if (!def || !["interface","theme","navigation","application","voice","workspace","system"].includes(def.kind)) return;
    state.mapStack.push(state.map);
    state.map = id;
    state.selected = null;
    const viewport = document.querySelector(".nx-viewport");
    if (viewport) delete viewport.dataset.bound;
    bindWorkspace();
  }

  function updateMapChrome() {
    const viewport = document.querySelector(".nx-viewport");
    if (!viewport) return;
    let head = viewport.querySelector(".nx-map-head");
    if (!head) { head = document.createElement("div"); head.className = "nx-map-head"; viewport.appendChild(head); }
    if (state.map === "root") {
      head.innerHTML = '<span class="nx-label">SETTINGS / ROOT MAP</span><strong>Основные настройки</strong>';
    } else {
      const parent = NODE_DEFS.find(def => def.id === state.map);
      head.innerHTML = '<span class="nx-label">SETTINGS / NODE MAP</span><strong>' + (parent?.title || "Настройки") + '</strong><button type="button" data-nx-back>← Назад</button>';
      head.querySelector("[data-nx-back]").addEventListener("click", () => {
        state.map = state.mapStack.pop() || "root";
        state.selected = null;
        const viewport = document.querySelector(".nx-viewport");
        if (viewport) delete viewport.dataset.bound;
        bindWorkspace();
      });
    }
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

    const visibleDefs = getMapDefs();

    visibleDefs.forEach(def => {
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
        let moved = false;

        const move = moveEvent => {
          moved = true;
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
          if (!moved && ["interface","theme","navigation","application","voice","workspace","system"].includes(def.kind)) openSettingsMap(def.id);
        };

        node.classList.add("dragging");
        node.addEventListener("pointermove", move);
        node.addEventListener("pointerup", up);
      });

      nodesRoot.appendChild(node);
      state.nodes.set(def.id, { def, element: node });
    });

    getMapLinks().forEach(([from, to]) => {
      const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
      line.dataset.from = from;
      line.dataset.to = to;
      linksRoot.appendChild(line);
    });

    document.querySelector("[data-nx-node-count]").textContent = visibleDefs.length;
    document.querySelector("[data-nx-link-count]").textContent = getMapLinks().length;
    updateMapChrome();

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
      if (!entry) return;
      if (["interface","theme","navigation","application","voice","workspace","system"].includes(entry.def.kind)) openSettingsMap(entry.def.id);
      else focusSettingsNode(entry.def.id);
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
      const related = getMapLinks().some(([a, b]) =>
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
        <p>Каждая настройка представлена отдельным узлом. Категории соединены с конкретными параметрами.</p>
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
      content += `<div class="nx-control-block"><span class="nx-control-title">Категория интерфейса</span><p class="nx-note">Выбери конкретный дочерний узел ниже, чтобы изменить одну оболочку.</p></div>`;
    }

    if (def.kind === "interface-item") {
      content += `<div class="nx-control-block"><span class="nx-control-title">Оболочка</span><button type="button" class="nx-wide-action" data-nx-interface="${def.setting}">Выбрать ${def.title}</button><small class="nx-note">${def.setting === "nexus" || def.setting === "jarvis" ? "Требует перезапуска." : "Применяется сразу."}</small></div>`;
    }

    if (def.kind === "theme") {
      content += `<div class="nx-control-block"><span class="nx-control-title">Темы</span><p class="nx-note">13 вариантов вынесены в отдельные узлы. Связи показывают принадлежность к THEME.</p></div>`;
    }

    if (def.kind === "theme-item") {
      content += `<div class="nx-control-block"><span class="nx-control-title">Тема</span><button type="button" class="nx-wide-action" data-nx-theme="${def.setting}">Применить «${def.title}»</button></div>`;
    }

    if (def.kind === "navigation") {
      content += `<div class="nx-control-block"><span class="nx-control-title">Вкладки</span><p class="nx-note">Каждая вкладка имеет собственный узел. Выбери его для управления видимостью.</p></div>`;
    }

    if (def.kind === "navigation-item") {
      const hidden = new Set(getHiddenNav());
      content += `<div class="nx-control-block"><span class="nx-control-title">Верхняя вкладка</span><label class="nx-setting-row"><span><b>Показывать «${def.title}»</b><small>Настройка сохраняется локально</small></span><input type="checkbox" data-nx-nav="${def.setting}" ${hidden.has(def.setting) ? "" : "checked"}></label></div>`;
    }

    if (def.kind === "application") {
      content += `<div class="nx-control-block"><span class="nx-control-title">Параметры приложения</span><p class="nx-note">Каждый параметр вынесен в отдельный узел.</p></div>`;
    }

    if (def.kind === "application-item") {
      if (def.setting === "app-name") {
        content += `<div class="nx-control-block"><div class="nx-readonly"><span>Название приложения</span><b>JARVIS</b></div></div>`;
      }
      if (def.setting === "assistant-name") {
        content += `<div class="nx-control-block"><label class="nx-field"><span>Имя ассистента</span><input data-nx-setting="assistant-name" value="${getSetting("jarvis-assistant-name", "Jarvis")}"></label></div>`;
      }
      if (def.setting === "testing") {
        content += `<div class="nx-control-block"><label class="nx-setting-row"><span><b>Режим тестирования</b><small>Command Router без вызова ИИ</small></span><input type="checkbox" data-nx-setting="testing" ${getSetting("jarvis-testing-mode","false") === "true" ? "checked" : ""}></label></div>`;
      }
    }

    if (def.kind === "voice") {
      content += `<div class="nx-control-block"><span class="nx-control-title">Голосовые параметры</span><p class="nx-note">Каждый параметр имеет отдельный узел.</p></div>`;
    }

    if (def.kind === "voice-item") {
      if (def.setting === "wake-word") content += `<div class="nx-control-block"><div class="nx-readonly"><span>Wake word</span><b>Jarvis</b></div></div>`;
      if (def.setting === "microphone") content += `<div class="nx-control-block"><div class="nx-readonly"><span>Микрофон</span><b>Системный</b></div></div>`;
      if (def.setting === "silence") content += `<div class="nx-control-block"><label class="nx-field"><span>Тишина до автоотправки</span><input type="number" min="0.2" max="10" step="0.1" data-nx-setting="silence" value="${getSetting("jarvis-silence-threshold","1.2")}"><small>сек.</small></label></div>`;
    }

    if (def.kind === "workspace") {
      content += `<div class="nx-control-block"><span class="nx-control-title">Workspace</span><p class="nx-note">Рабочая область и алиасы разделены на отдельные узлы.</p></div>`;
    }

    if (def.kind === "workspace-item") {
      if (def.setting === "workspace-scope") content += `<div class="nx-control-block"><div class="nx-readonly"><span>Рабочая область</span><b>Только Workspace</b></div></div>`;
      if (def.setting === "aliases") content += `<div class="nx-control-block"><button type="button" class="nx-wide-action" data-nx-action="aliases">Открыть алиасы</button></div>`;
    }

    if (def.kind === "system") {
      content += `<div class="nx-control-block"><span class="nx-control-title">Система</span><p class="nx-note">Системные параметры разделены на отдельные узлы.</p></div>`;
    }

    if (def.kind === "system-item") {
      if (def.setting === "language") {
        content += `<div class="nx-control-block"><label class="nx-field"><span>Язык</span><select data-nx-setting="language"><option value="ru">Русский</option><option value="en">English</option></select></label></div>`;
      }
      if (def.setting === "interface-id") content += `<div class="nx-control-block"><div class="nx-readonly"><span>Интерфейс</span><b>NEXUS</b></div></div>`;
    }

    inspector.innerHTML = content;

    const language = inspector.querySelector('[data-nx-setting="language"]');
    if (language) language.value = getSetting("jarvis-language", "ru");

    toggle.disabled = def.kind === "core";
    toggle.textContent = def.state === "off" ? "Включить узел" : "Отключить узел";
    open.disabled = def.kind === "core";
    open.textContent = ["interface","theme","navigation","application","voice","workspace","system"].includes(def.kind) ? "Открыть настройки" : "Центрировать";
  }

  function handleInspectorClick(event) {
    const interfaceButton = event.target.closest("[data-nx-interface]");
    if (interfaceButton) {
      const name = interfaceButton.dataset.nxInterface;
      const choices = interfaceButton.closest(".nx-choice-grid");
      if (choices) choices.querySelectorAll(".nx-choice").forEach(item => item.classList.remove("selected"));
      if (interfaceButton.classList.contains("nx-choice")) interfaceButton.classList.add("selected");

      if (window.JarvisInterfaceManager) {
        const bridgeOption = document.createElement("button");
        bridgeOption.type = "button";
        bridgeOption.dataset.interface = name;
        bridgeOption.hidden = true;
        document.body.appendChild(bridgeOption);
        bridgeOption.click();

        const save = document.createElement("button");
        save.id = "saveAllButton";
        save.hidden = true;
        document.body.appendChild(save);
        save.click();
        bridgeOption.remove();
        save.remove();
      } else {
        localStorage.setItem("jarvis-interface", name);
        if (typeof window.setInterfaceClass === "function") window.setInterfaceClass(name);
        location.reload();
      }
      return;
    }

    const themeButton = event.target.closest("[data-nx-theme]");
    if (themeButton) {
      const theme = themeButton.dataset.nxTheme;
      if (typeof window.applyTheme === "function") window.applyTheme(theme);
      else localStorage.setItem("jarvis-theme", theme);
      return;
    }

    const action = event.target.closest("[data-nx-action]");
    if (action?.dataset.nxAction === "aliases") go("commands");
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

      const ax = parseFloat(from.element.style.left || "0") + from.element.offsetWidth / 2;
      const ay = parseFloat(from.element.style.top || "0") + from.element.offsetHeight / 2;
      const bx = parseFloat(to.element.style.left || "0") + to.element.offsetWidth / 2;
      const by = parseFloat(to.element.style.top || "0") + to.element.offsetHeight / 2;

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


  function showNexusToast(message) {
    let toast = document.querySelector(".nx-toast");
    if (!toast) {
      toast = document.createElement("div");
      toast.className = "nx-toast";
      document.body.appendChild(toast);
    }
    toast.textContent = message;
    toast.classList.add("show");
    clearTimeout(toast._timer);
    toast._timer = setTimeout(() => toast.classList.remove("show"), 1800);
  }

  function bindPageInteractions() {
    const container = document.querySelector("#pageContainer");
    if (!container || container.dataset.nexusPageBound === "true") return;
    container.dataset.nexusPageBound = "true";

    container.addEventListener("click", event => {
      const nav = event.target.closest("[data-go]");
      if (nav) {
        event.preventDefault();
        go(nav.dataset.go);
        return;
      }

      const command = event.target.closest(".command-item");
      if (command) {
        const phrase = command.querySelector("span")?.textContent?.replace(/[«»]/g, "").split(",")[0].trim();
        if (phrase) {
          go("chat");
          setTimeout(() => {
            const input = document.querySelector("#chatInput");
            if (input) {
              input.value = phrase;
              input.focus();
              showNexusToast("Команда перенесена в чат");
            }
          }, 40);
        }
        return;
      }

      const saveButton = event.target.closest(".primary");
      if (saveButton && saveButton.id !== "saveAllButton" && saveButton.closest("#workspace")) {
        showNexusToast("Добавление ресурсов требует подключения Workspace");
        return;
      }

      if (event.target.closest("#interfaceButton")) {
        go("workspace");
        return;
      }

      if (event.target.closest(".theme-switcher")) {
        const dropdown = document.querySelector("#themeDropdown");
        if (dropdown) dropdown.hidden = !dropdown.hidden;
        return;
      }

      const theme = event.target.closest("[data-theme]");
      if (theme && typeof window.applyTheme === "function") {
        window.applyTheme(theme.dataset.theme);
        setSetting("jarvis-theme", theme.dataset.theme);
        showNexusToast("Тема применена");
      }
    });

    container.addEventListener("submit", event => {
      const form = event.target.closest("#chatForm");
      if (!form) return;
      event.preventDefault();
      const input = form.querySelector("#chatInput");
      const text = input?.value.trim();
      if (!text) return;

      const messages = document.querySelector("#messages");
      if (messages) {
        const item = document.createElement("div");
        item.className = "message user";
        item.innerHTML = "<span>ВЫ</span><p></p>";
        item.querySelector("p").textContent = text;
        messages.appendChild(item);
        messages.scrollTop = messages.scrollHeight;
      }
      input.value = "";
      showNexusToast("Команда добавлена в локальный журнал. Backend пока не подключён.");
    });

    container.addEventListener("change", event => {
      const think = event.target.closest("#thinkingToggle");
      if (think) {
        const stateEl = document.querySelector("#thinkingState");
        if (stateEl) stateEl.textContent = think.checked ? "размышления вкл." : "размышления выкл.";
      }

      const language = event.target.closest("#languageSelect");
      if (language) {
        setSetting("jarvis-language", language.value);
        if (typeof window.applyLanguage === "function") window.applyLanguage(language.value);
        showNexusToast("Язык сохранён");
      }
    });

    applyNavVisibility();
  }

  function updatePageState() {
    applyNavVisibility();
    const hidden = new Set(getHiddenNav());
    const current = document.querySelector(".nx-nav button.active")?.dataset.nxPage;
    if (current && hidden.has(current)) go("home");
  }

  function bindDynamicPage() {
    if (document.querySelector(".nx-viewport")) bindWorkspace();
    bindPageInteractions();
    applyNavVisibility();
  }

  installShell();
  bindPageInteractions();

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