const { app, BrowserWindow, ipcMain } = require("electron");
const path = require("path");
const fs = require("fs/promises");

const pagesDir = path.join(__dirname, "pages");
const interfacesDir = path.join(__dirname, "interfaces");
const allowedPages = new Set(["home", "chat", "commands", "workspace", "ai", "settings"]);

ipcMain.handle("load-page", async (_event, page, interfaceName = "classic") => {
  if (!allowedPages.has(page)) throw new Error("Unknown page");

  const safeInterfaceName = String(interfaceName).match(/^[a-z0-9_-]+$/i)?.[0];
  if (safeInterfaceName && safeInterfaceName !== "classic") {
    const customRoot = path.resolve(interfacesDir, safeInterfaceName, "pages");
    const customPage = path.resolve(customRoot, page + ".html");
    if (customPage.startsWith(customRoot + path.sep)) {
      try {
        return await fs.readFile(customPage, "utf8");
      } catch (error) {
        if (error.code !== "ENOENT") throw error;
      }
    }
  }

  return fs.readFile(path.join(pagesDir, page + ".html"), "utf8");
});

ipcMain.handle("restart-app", () => {
  app.relaunch();
  app.exit(0);
});

function createWindow() {
  const win = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1100,
    minHeight: 700,
    backgroundColor: "#111210",
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false
    }
  });

  win.loadFile(path.join(__dirname, "index.html"));
}

app.whenReady().then(() => {
  createWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});
