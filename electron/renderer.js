const pageNames = {
  home: "Главная",
  chat: "Чат",
  commands: "Команды",
  workspace: "Рабочая область",
  ai: "ИИ",
  settings: "Настройки"
};

const pageContainer = document.querySelector("#pageContainer");
const themeClasses = ["theme-light", "theme-gradient-amber", "theme-gradient-blue", "theme-gradient-purple"];
const interfaceClasses = ["interface-minimal", "interface-dashboard"];

function setThemeClass(theme) {
  document.body.classList.remove(...themeClasses);
  if (theme === "light") document.body.classList.add("theme-light");
  if (theme === "gradient-amber") document.body.classList.add("theme-gradient-amber");
  if (theme === "gradient-blue") document.body.classList.add("theme-gradient-blue");
  if (theme === "gradient-purple") document.body.classList.add("theme-gradient-purple");
}

function applyTheme(theme) {
  setThemeClass(theme);
  localStorage.setItem("jarvis-theme", theme);
}

function setInterfaceClass(name) {
  document.body.classList.remove(...interfaceClasses);
  if (name === "minimal") document.body.classList.add("interface-minimal");
  if (name === "dashboard") document.body.classList.add("interface-dashboard");
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
    bindPageEvents();
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
  const interfaceButton = document.querySelector("#interfaceButton");
  const interfacePicker = document.querySelector("#interfacePicker");

  if (profileButton && profileMenu) {
    profileButton.addEventListener("click", (event) => {
      event.stopPropagation();
      const isOpen = !profileMenu.hidden;
      profileMenu.hidden = isOpen;
      profileButton.setAttribute("aria-expanded", String(!isOpen));
    });

    document.addEventListener("click", () => {
      profileMenu.hidden = true;
      profileButton.setAttribute("aria-expanded", "false");
    }, { once: true });
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
      option.addEventListener("mouseenter", () => setThemeClass(option.dataset.theme));
      option.addEventListener("mouseleave", () => setThemeClass(localStorage.getItem("jarvis-theme") || "dark"));
      option.addEventListener("click", () => {
        applyTheme(option.dataset.theme);
        themePicker.querySelectorAll("[data-theme]").forEach((item) => {
          item.classList.toggle("selected", item === option);
        });
      });
    });
  }

  if (interfaceButton) {
    interfaceButton.addEventListener("click", () => {
      interfacePicker?.scrollIntoView({ behavior: "smooth", block: "center" });
    });
  }

  if (interfacePicker) {
    const savedInterface = localStorage.getItem("jarvis-interface") || "classic";
    setInterfaceClass(savedInterface);

    interfacePicker.querySelectorAll("[data-interface]").forEach((option) => {
      option.classList.toggle("selected", option.dataset.interface === savedInterface);
      option.addEventListener("mouseenter", () => setInterfaceClass(option.dataset.interface));
      option.addEventListener("mouseleave", () => {
        setInterfaceClass(localStorage.getItem("jarvis-interface") || "classic");
      });
      option.addEventListener("click", () => {
        applyInterface(option.dataset.interface);
        interfacePicker.querySelectorAll("[data-interface]").forEach((item) => {
          item.classList.toggle("selected", item === option);
        });
      });
    });
  }

  if (languageSelect) {
    languageSelect.value = localStorage.getItem("jarvis-language") || "ru";
    languageSelect.addEventListener("change", () => applyLanguage(languageSelect.value));
  }

  if (profileSettings) {
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
go("home");
