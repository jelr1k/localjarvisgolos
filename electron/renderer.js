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

function applyTheme(theme) {
  document.body.classList.remove(...themeClasses);
  if (theme === "light") document.body.classList.add("theme-light");
  if (theme === "gradient-amber") document.body.classList.add("theme-gradient-amber");
  if (theme === "gradient-blue") document.body.classList.add("theme-gradient-blue");
  if (theme === "gradient-purple") document.body.classList.add("theme-gradient-purple");
  localStorage.setItem("jarvis-theme", theme);
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
    console.error(error);
  }
}

function bindPageEvents() {
  const profileButton = document.querySelector("#profileButton");
  const profileMenu = document.querySelector("#profileMenu");
  const profileSettings = document.querySelector("#profileSettings");
  const themeSelect = document.querySelector("#themeSelect");
  const languageSelect = document.querySelector("#languageSelect");

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
      micButton.textContent = micButton.classList.contains("active") ? "●" : "●";
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
go("home");
