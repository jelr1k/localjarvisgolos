const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("jarvis", Object.freeze({
  version: "0.2.0-ui",
  mode: "ui-prototype",
  restartApp: () => ipcRenderer.invoke("restart-app")
}));
