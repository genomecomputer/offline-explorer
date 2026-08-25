import { contextBridge, ipcRenderer } from "electron";

contextBridge.exposeInMainWorld("offlineExplorer", {
  desktop: true,
  chooseBundle: () => ipcRenderer.invoke("genome:choose-bundle"),
  exportSaved: (format: "json" | "csv") => ipcRenderer.invoke("genome:export-saved", format),
  onChooseBundleRequested: (callback: () => void) => {
    ipcRenderer.on("genome:choose-bundle-requested", callback);
  },
  quit: () => ipcRenderer.invoke("app:quit"),
});
