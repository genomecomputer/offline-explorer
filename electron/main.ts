import {
  app,
  BrowserWindow,
  dialog,
  ipcMain,
  Menu,
  type MenuItemConstructorOptions,
  type MessageBoxOptions,
  session,
  shell,
} from "electron";
import { spawn, type ChildProcess } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import readline from "node:readline";

import {
  isTrustedBackendUrl,
  parseBackendReady,
  type BackendReady,
} from "./backend-contract";

const repositoryRoot = path.resolve(__dirname, "..");
const startupTimeoutMilliseconds = 90_000;

let backendProcess: ChildProcess | null = null;
let backendReady: BackendReady | null = null;
let mainWindow: BrowserWindow | null = null;
let isQuitting = false;

app.setName("Offline Explorer");
if (process.env.OFFLINE_EXPLORER_USER_DATA) {
  app.setPath("userData", path.resolve(process.env.OFFLINE_EXPLORER_USER_DATA));
}

function backendExecutable(): { command: string; args: string[]; cwd: string } {
  if (app.isPackaged) {
    const executable = process.platform === "win32"
      ? "offline-explorer-engine.exe"
      : "offline-explorer-engine";
    return {
      command: path.join(process.resourcesPath, "engine", executable),
      args: [],
      cwd: process.resourcesPath,
    };
  }

  return {
    command: path.join(repositoryRoot, "prototype", "run"),
    args: [],
    cwd: repositoryRoot,
  };
}

function stopBackend(): void {
  const processToStop = backendProcess;
  backendProcess = null;
  backendReady = null;
  if (processToStop && processToStop.exitCode === null && !processToStop.killed) {
    processToStop.kill();
  }
}

function startBackend(): Promise<BackendReady> {
  const workspaceRoot = path.join(app.getPath("userData"), "workspaces");
  const executable = backendExecutable();
  const child = spawn(
    executable.command,
    [...executable.args, "--desktop-backend", "--workspace-root", workspaceRoot],
    {
      cwd: executable.cwd,
      env: { ...process.env, PYTHONDONTWRITEBYTECODE: "1" },
      stdio: ["ignore", "pipe", "pipe"],
      windowsHide: true,
    },
  );
  backendProcess = child;
  child.stderr.resume();

  if (process.env.OFFLINE_EXPLORER_TEST_PID_FILE) {
    writeFileSync(process.env.OFFLINE_EXPLORER_TEST_PID_FILE, `${child.pid}\n`, {
      encoding: "utf8",
      mode: 0o600,
    });
  }

  return new Promise((resolve, reject) => {
    let settled = false;
    const output = readline.createInterface({ input: child.stdout });
    const timer = setTimeout(() => {
      if (settled) return;
      settled = true;
      stopBackend();
      reject(new Error("The local genome engine did not start in time."));
    }, startupTimeoutMilliseconds);

    const fail = (error: Error) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      stopBackend();
      reject(error);
    };

    child.once("error", () => fail(new Error("The local genome engine could not be started.")));
    child.once("exit", (code) => {
      if (!settled) {
        fail(new Error(`The local genome engine stopped during startup (${code ?? "unknown"}).`));
      } else if (!isQuitting && backendProcess === child) {
        backendProcess = null;
        backendReady = null;
        void dialog.showMessageBox({
          type: "error",
          title: "Offline Explorer",
          message: "The local genome engine stopped unexpectedly.",
          detail: "Close and reopen Offline Explorer to continue.",
        });
      }
    });

    output.on("line", (line) => {
      if (settled) return;
      try {
        const ready = parseBackendReady(line);
        if (!ready) return;
        settled = true;
        clearTimeout(timer);
        backendReady = ready;
        resolve(ready);
      } catch (error) {
        fail(error instanceof Error ? error : new Error("The genome engine could not be verified."));
      }
    });
  });
}

async function backendRequest(
  route: string,
  options: { method?: "GET" | "POST"; payload?: Record<string, unknown>; desktop?: boolean } = {},
): Promise<Record<string, unknown>> {
  if (!backendReady) throw new Error("The local genome engine is not ready.");
  const endpoint = new URL(route.replace(/^\//, ""), backendReady.url);
  const origin = new URL(backendReady.url).origin;
  const headers: Record<string, string> = { Origin: origin };
  if (options.payload) headers["Content-Type"] = "application/json";
  if (options.desktop) headers["X-Offline-Explorer-Desktop"] = backendReady.desktopToken;
  const response = await fetch(endpoint, {
    method: options.method ?? "GET",
    headers,
    body: options.payload ? JSON.stringify(options.payload) : undefined,
  });
  const payload = await response.json() as Record<string, unknown>;
  if (!response.ok) {
    throw new Error(typeof payload.error === "string" ? payload.error : "The local request failed.");
  }
  return payload;
}

function assertTrustedSender(url: string): void {
  if (!backendReady || !isTrustedBackendUrl(url, backendReady.url)) {
    throw new Error("The desktop request did not come from Offline Explorer.");
  }
}

async function chooseBundle(): Promise<Record<string, unknown>> {
  if (!mainWindow) throw new Error("The Offline Explorer window is unavailable.");

  let archive: string | undefined;
  if (process.env.OFFLINE_EXPLORER_TEST_BUNDLE) {
    archive = path.resolve(process.env.OFFLINE_EXPLORER_TEST_BUNDLE);
  } else {
    const selection = await dialog.showOpenDialog(mainWindow, {
      title: "Add a genome bundle",
      buttonLabel: "Add bundle",
      properties: ["openFile"],
      filters: [
        { name: "Genome bundles", extensions: ["gz"] },
        { name: "All files", extensions: ["*"] },
      ],
    });
    if (!selection.canceled) archive = selection.filePaths[0];
  }

  if (!archive) return backendRequest("api/status");
  if (!archive.toLowerCase().endsWith(".genome.tar.gz")) {
    await dialog.showMessageBox(mainWindow, {
      type: "warning",
      title: "Choose a genome bundle",
      message: "That file is not a supported genome bundle.",
      detail: "Choose a file ending in .genome.tar.gz.",
    });
    return backendRequest("api/status");
  }

  return backendRequest("api/desktop/open", {
    method: "POST",
    payload: { archive },
    desktop: true,
  });
}

async function exportSavedResults(format: "json" | "csv"): Promise<Record<string, unknown>> {
  if (!mainWindow) throw new Error("The Offline Explorer window is unavailable.");
  const exported = await backendRequest("api/saved/export", {
    method: "POST",
    payload: { format },
    desktop: true,
  });
  const fileName = exported.file_name;
  const content = exported.content;
  if (
    typeof fileName !== "string" ||
    path.basename(fileName) !== fileName ||
    typeof content !== "string"
  ) {
    throw new Error("The saved results export is invalid.");
  }

  let filePath: string | undefined;
  if (process.env.OFFLINE_EXPLORER_TEST_EXPORT_DIR) {
    const exportDirectory = path.resolve(process.env.OFFLINE_EXPLORER_TEST_EXPORT_DIR);
    mkdirSync(exportDirectory, { recursive: true });
    filePath = path.join(exportDirectory, fileName);
  } else {
    const extension = format === "json" ? "json" : "csv";
    const selection = await dialog.showSaveDialog(mainWindow, {
      title: `Export saved results as ${extension.toUpperCase()}`,
      buttonLabel: "Export",
      defaultPath: path.join(app.getPath("documents"), fileName),
      filters: [
        {
          name: format === "json" ? "JSON files" : "CSV files",
          extensions: [extension],
        },
      ],
    });
    if (!selection.canceled) filePath = selection.filePath;
  }

  if (!filePath) return { saved: false };
  writeFileSync(filePath, content, { encoding: "utf8", mode: 0o600 });
  return { saved: true, file_name: path.basename(filePath) };
}

function installMenu(): void {
  const template: MenuItemConstructorOptions[] = [];
  if (process.platform === "darwin") {
    template.push({
      label: app.name,
      submenu: [
        { role: "about" },
        { type: "separator" },
        { role: "hide" },
        { role: "hideOthers" },
        { role: "unhide" },
        { type: "separator" },
        { role: "quit" },
      ],
    });
  }
  template.push(
    {
      label: "File",
      submenu: [
        {
          label: "Add Genome Bundle...",
          accelerator: "CmdOrCtrl+O",
          click: () => { mainWindow?.webContents.send("genome:choose-bundle-requested"); },
        },
        { type: "separator" },
        process.platform === "darwin" ? { role: "close" } : { role: "quit" },
      ],
    },
    {
      label: "Edit",
      submenu: [
        { role: "undo" }, { role: "redo" }, { type: "separator" },
        { role: "cut" }, { role: "copy" }, { role: "paste" }, { role: "selectAll" },
      ],
    },
    {
      label: "View",
      submenu: [
        { role: "resetZoom" }, { role: "zoomIn" }, { role: "zoomOut" },
        { type: "separator" }, { role: "togglefullscreen" },
      ],
    },
    { label: "Window", submenu: [{ role: "minimize" }, { role: "zoom" }] },
  );
  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

function loadingPage(message: string): string {
  return `data:text/html;charset=utf-8,${encodeURIComponent(`<!doctype html>
    <html><head><meta charset="utf-8"><meta name="color-scheme" content="light">
    <style>html,body{height:100%;margin:0}body{display:grid;place-items:center;background:#f6f8f5;color:#17211d;font:16px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.card{text-align:center}.mark{width:46px;height:46px;margin:0 auto 20px;border-radius:14px;background:#153d2f;color:white;display:grid;place-items:center;font-size:22px}.muted{color:#65716c}</style>
    </head><body><main class="card"><div class="mark">O</div><h1>Offline Explorer</h1><p class="muted">${message}</p></main></body></html>`)}`;
}

async function confirmExternalReference(url: string): Promise<void> {
  let parsed: URL;
  try {
    parsed = new URL(url);
  } catch {
    return;
  }
  if (parsed.protocol !== "https:" && parsed.protocol !== "http:") return;
  const options: MessageBoxOptions = {
    type: "info",
    buttons: ["Cancel", "Open in browser"],
    defaultId: 0,
    cancelId: 0,
    title: "Open external reference?",
    message: "Open this recorded public reference in your browser?",
    detail: `Your browser will receive this public URL:\n${parsed.toString()}`,
  };
  const result = mainWindow
    ? await dialog.showMessageBox(mainWindow, options)
    : await dialog.showMessageBox(options);
  if (result.response === 1) await shell.openExternal(parsed.toString());
}

async function createWindow(): Promise<void> {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 900,
    minWidth: 820,
    minHeight: 640,
    show: false,
    backgroundColor: "#f6f8f5",
    title: "Offline Explorer",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webSecurity: true,
      devTools: !app.isPackaged,
      backgroundThrottling: false,
    },
  });

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    void confirmExternalReference(url);
    return { action: "deny" };
  });
  mainWindow.webContents.on("will-navigate", (event, url) => {
    if (!backendReady || !isTrustedBackendUrl(url, backendReady.url)) event.preventDefault();
  });
  mainWindow.webContents.on("render-process-gone", () => app.quit());
  mainWindow.on("closed", () => {
    mainWindow = null;
    if (!isQuitting) app.quit();
  });

  await mainWindow.loadURL(loadingPage("Starting the private local engine..."));
  mainWindow.show();

  try {
    const ready = await startBackend();
    await mainWindow.loadURL(ready.url);
  } catch (error) {
    const message = error instanceof Error ? error.message : "The private local engine could not start.";
    await mainWindow.loadURL(loadingPage(message));
  }
}

const singleInstance = app.requestSingleInstanceLock();
if (!singleInstance) {
  app.quit();
} else {
  app.on("second-instance", () => {
    if (!mainWindow) return;
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.show();
    mainWindow.focus();
  });

  app.whenReady().then(async () => {
    session.defaultSession.setPermissionRequestHandler((_webContents, _permission, callback) => callback(false));
    session.defaultSession.webRequest.onBeforeRequest((details, callback) => {
      if (details.url.startsWith("data:text/html")) {
        callback({ cancel: false });
        return;
      }
      callback({ cancel: !backendReady || !isTrustedBackendUrl(details.url, backendReady.url) });
    });

    ipcMain.handle("genome:choose-bundle", async (event) => {
      assertTrustedSender(event.senderFrame?.url ?? "");
      return chooseBundle();
    });
    ipcMain.handle("genome:export-saved", async (event, format: unknown) => {
      assertTrustedSender(event.senderFrame?.url ?? "");
      if (format !== "json" && format !== "csv") {
        throw new Error("The export format is invalid.");
      }
      return exportSavedResults(format);
    });
    ipcMain.handle("app:quit", (event) => {
      assertTrustedSender(event.senderFrame?.url ?? "");
      app.quit();
    });

    installMenu();
    await createWindow();
  }).catch(async () => {
    await dialog.showMessageBox({
      type: "error",
      title: "Offline Explorer",
      message: "Offline Explorer could not start.",
    });
    app.quit();
  });
}

app.on("before-quit", () => {
  isQuitting = true;
  stopBackend();
});
app.on("window-all-closed", () => app.quit());
process.on("exit", stopBackend);
