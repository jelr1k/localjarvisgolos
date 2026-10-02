const pageNames = {
  home: "Главная",
  chat: "Чат",
  commands: "Команды",
  workspace: "Рабочая область",
  ai: "ИИ",
  settings: "Настройки"
};

const pageContainer = document.querySelector("#pageContainer");
const themeClasses = ["theme-light", "theme-mono-slate", "theme-mono-graphite", "theme-mono-silver", "theme-mono-cream", "theme-gradient-amber", "theme-gradient-blue", "theme-gradient-purple", "theme-gradient-cyan", "theme-gradient-green", "theme-gradient-red", "theme-gradient-sunset"];
const interfaceClasses = ["interface-minimal", "interface-dashboard", "interface-atlas", "interface-journal", "interface-commandroom", "interface-orbit"];
const densityClasses = ["interface-density-comfortable", "interface-density-compact", "interface-density-dense"];
const cornerClasses = ["interface-corners-sharp", "interface-corners-soft", "interface-corners-round"];
const motionClasses = ["interface-motion-full", "interface-motion-reduced", "interface-motion-off"];
let pendingInterface = localStorage.getItem("jarvis-interface") || "classic";

function setThemeClass(theme) {
  document.body.classList.remove(...themeClasses);
  if (theme === "light") document.body.classList.add("theme-light");
  if (theme === "gradient-amber") document.body.classList.add("theme-gradient-amber");
  if (theme === "gradient-blue") document.body.classList.add("theme-gradient-blue");
  if (theme === "gradient-purple") document.body.classList.add("theme-gradient-purple");
  if (theme === "gradient-cyan") document.body.classList.add("theme-gradient-cyan");
  if (theme === "gradient-green") document.body.classList.add("theme-gradient-green");
  if (theme === "gradient-red") document.body.classList.add("theme-gradient-red");
  if (theme === "gradient-sunset") document.body.classList.add("theme-gradient-sunset");
  if (theme === "mono-slate") document.body.classList.add("theme-mono-slate");
  if (theme === "mono-graphite") document.body.classList.add("theme-mono-graphite");
  if (theme === "mono-silver") document.body.classList.add("theme-mono-silver");
  if (theme === "mono-cream") document.body.classList.add("theme-mono-cream");
}

function applyTheme(theme) {
  setThemeClass(theme);
  localStorage.setItem("jarvis-theme", theme);
}

function setInterfaceClass(name) {
  document.body.classList.remove(...interfaceClasses);
  if (name === "minimal") document.body.classList.add("interface-minimal");
  if (name === "dashboard") document.body.classList.add("interface-dashboard");
  if (name === "atlas") document.body.classList.add("interface-atlas");
  if (name === "journal") document.body.classList.add("interface-journal");
  if (name === "commandroom") document.body.classList.add("interface-commandroom");
  if (name === "orbit") document.body.classList.add("interface-orbit");
}

function applyInterface(name) {
  setInterfaceClass(name);
  localStorage.setItem("jarvis-interface", name);
}

function applyLanguage(language) {
  localStorage.setItem("jarvis-language", language);
}

async function go(page) {
  try {
    pageContainer.innerHTML = await window.jarvis.loadPage(page);
    document.querySelectorAll(".nav-item").forEach((el) => {
      el.classList.toggle("active", el.dataset.page === page);
    });
    document.querySelector("#pageName").textContent = pageNames[page] || pageNames.home;
    document.body.classList.toggle("page-settings", page === "settings");
    const settingsSaveButton = document.querySelector("#saveAllButton");
    const topbar = document.querySelector(".topbar");
    if (page === "settings" && settingsSaveButton && topbar) {
      settingsSaveButton.classList.add("settings-save-button");
      topbar.appendChild(settingsSaveButton);
    }
    bindPageEvents();
    requestAnimationFrame(() => initBlackHole());
  } catch (error) {
    pageContainer.innerHTML = '<section class="page active"><div class="panel" style="padding:24px">Не удалось загрузить страницу.</div></section>';
    console.error("Jarvis page load error:", error);
  }
}

function bindPageEvents() {
  const profileButton = document.querySelector("#profileButton");
  const profileMenu = document.querySelector("#profileMenu");
  const profileSettings = document.querySelector("#profileSettings");
  const themeSelect = document.querySelector("#themeSelect");
  const languageSelect = document.querySelector("#languageSelect");
  const themePicker = document.querySelector("#themePicker");
  const themeSwitcher = document.querySelector("#themeSwitcher");
  const themeDropdown = document.querySelector("#themeDropdown");
  const interfaceButton = document.querySelector("#interfaceButton");
  const interfacePicker = document.querySelector("#interfacePicker");
  const saveAllButton = document.querySelector("#saveAllButton");
  const interfaceDensity = document.querySelector("#interfaceDensity");
  const interfaceCorners = document.querySelector("#interfaceCorners");
  const interfaceMotion = document.querySelector("#interfaceMotion");
  const homeHelp = document.querySelector("#homeHelp");
  const homeHelpPopover = document.querySelector("#homeHelpPopover");

  if (profileButton && profileMenu && profileButton.dataset.bound !== "true") {
    profileButton.dataset.bound = "true";

    profileButton.addEventListener("click", (event) => {
      event.stopPropagation();
      const isOpen = profileMenu.hidden;
      profileMenu.hidden = !isOpen;
      profileButton.setAttribute("aria-expanded", String(isOpen));
    });

    profileMenu.addEventListener("click", (event) => {
      event.stopPropagation();
    });

    document.addEventListener("click", () => {
      profileMenu.hidden = true;
      profileButton.setAttribute("aria-expanded", "false");
    });
  }

  if (themeSelect) {
    themeSelect.value = localStorage.getItem("jarvis-theme") || "dark";
    themeSelect.addEventListener("change", () => applyTheme(themeSelect.value));
  }

  if (themePicker) {
    const savedTheme = localStorage.getItem("jarvis-theme") || "dark";
    setThemeClass(savedTheme);
    themePicker.querySelectorAll("[data-theme]").forEach((option) => {
      option.classList.toggle("selected", option.dataset.theme === savedTheme);
      option.addEventListener("click", () => {
        applyTheme(option.dataset.theme);
        themePicker.querySelectorAll("[data-theme]").forEach((item) => {
          item.classList.toggle("selected", item === option);
        });
      });
    });
  }

  if (themeSwitcher && themeDropdown) {
    themeSwitcher.addEventListener("click", (event) => {
      event.stopPropagation();
      const isOpen = themeDropdown.hidden;
      themeDropdown.hidden = !isOpen;
      themeSwitcher.setAttribute("aria-expanded", String(isOpen));
    });

    themeDropdown.addEventListener("click", (event) => event.stopPropagation());

    document.addEventListener("click", () => {
      if (!themeDropdown.hidden) {
        themeDropdown.hidden = true;
        themeSwitcher.setAttribute("aria-expanded", "false");
      }
    });
  }

  if (homeHelp && homeHelpPopover) {
    homeHelp.addEventListener("click", (event) => {
      event.stopPropagation();
      const isOpen = homeHelpPopover.hidden;
      homeHelpPopover.hidden = !isOpen;
      homeHelp.setAttribute("aria-expanded", String(isOpen));
    });
    homeHelpPopover.addEventListener("click", (event) => event.stopPropagation());
    document.addEventListener("click", () => {
      if (!homeHelpPopover.hidden) {
        homeHelpPopover.hidden = true;
        homeHelp.setAttribute("aria-expanded", "false");
      }
    });
  }

  if (interfaceButton) {
    interfaceButton.addEventListener("click", () => {
      interfacePicker?.scrollIntoView({ behavior: "smooth", block: "center" });
    });
  }

  if (interfacePicker) {
    pendingInterface = localStorage.getItem("jarvis-interface") || "classic";

    interfacePicker.querySelectorAll("[data-interface]").forEach((option) => {
      option.classList.toggle("selected", option.dataset.interface === pendingInterface);
      option.addEventListener("click", () => {
        pendingInterface = option.dataset.interface;
        interfacePicker.querySelectorAll("[data-interface]").forEach((item) => {
          item.classList.toggle("selected", item.dataset.interface === pendingInterface);
        });
      });
    });
  }

  if (saveAllButton) {
    saveAllButton.addEventListener("click", () => {
      applyInterface(pendingInterface);
      saveAllButton.textContent = "Сохранено";
      setTimeout(() => {
        if (saveAllButton.isConnected) saveAllButton.textContent = "Сохранить всё";
      }, 1200);
    });
  }

  if (languageSelect) {
    languageSelect.value = localStorage.getItem("jarvis-language") || "ru";
    languageSelect.addEventListener("change", () => applyLanguage(languageSelect.value));
  }

  if (profileSettings && profileSettings.dataset.bound !== "true") {
    profileSettings.dataset.bound = "true";
    profileSettings.addEventListener("click", () => {
      if (profileMenu) profileMenu.hidden = true;
      if (profileButton) profileButton.setAttribute("aria-expanded", "false");
      go("settings");
    });
  }

  document.querySelectorAll("[data-go]").forEach((button) => {
    button.addEventListener("click", () => go(button.dataset.go));
  });

  const form = document.querySelector("#chatForm");
  const input = document.querySelector("#chatInput");
  const messages = document.querySelector("#messages");
  const thinkingToggle = document.querySelector("#thinkingToggle");
  const thinkingState = document.querySelector("#thinkingState");
  const micButton = document.querySelector("#micButton");

  if (thinkingToggle && thinkingState) {
    thinkingToggle.addEventListener("change", () => {
      thinkingState.textContent = thinkingToggle.checked ? "размышления вкл." : "размышления выкл.";
    });
  }

  if (micButton) {
    micButton.addEventListener("click", () => {
      micButton.classList.toggle("active");
      micButton.textContent = "●";
    });
  }

  if (!form || !input || !messages) return;

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const value = input.value.trim();
    if (!value) return;

    const item = document.createElement("div");
    item.className = "message user";
    item.innerHTML = "<span>ВЫ</span><p></p>";
    item.querySelector("p").textContent = value;
    messages.appendChild(item);
    messages.scrollTop = messages.scrollHeight;
    input.value = "";
  });
}

document.querySelectorAll("[data-page]").forEach((button) => {
  button.addEventListener("click", () => go(button.dataset.page));
});

applyTheme(localStorage.getItem("jarvis-theme") || "dark");
setInterfaceClass(localStorage.getItem("jarvis-interface") || "classic");
pendingInterface = localStorage.getItem("jarvis-interface") || "classic";
go("home");
