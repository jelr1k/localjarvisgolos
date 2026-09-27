const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("jarvis", {
  version: "0.1.0",
  ready: true,
  loadPage: (page) => ipcRenderer.invoke("load-page", page)
});
