const { contextBridge } = require("electron");

contextBridge.exposeInMainWorld("jarvis", {
  version: "0.1.0",
  ready: true
});
