import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync, rmSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { test } from "node:test";

function processIsAlive(pid) {
  try {
    process.kill(pid, 0);
    return true;
  } catch {
    return false;
  }
}

function childHasExited(child) {
  return child.exitCode !== null || child.signalCode !== null;
}

async function waitFor(description, predicate, timeoutMilliseconds = 90_000) {
  const deadline = Date.now() + timeoutMilliseconds;
  while (Date.now() < deadline) {
    if (predicate()) return;
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error(`Timed out waiting for ${description}.`);
}

test("packaged app stops its engine after a main-process crash", async () => {
  assert.equal(process.platform, "darwin", "The packaged macOS smoke test requires macOS.");
  const executablePath = process.env.OFFLINE_EXPLORER_EXECUTABLE;
  assert.ok(executablePath, "Set OFFLINE_EXPLORER_EXECUTABLE to the packaged app executable.");
  assert.ok(existsSync(executablePath), `Packaged executable does not exist: ${executablePath}`);

  const testDirectory = mkdtempSync(path.join(os.tmpdir(), "offline-explorer-package-"));
  const pidFile = path.join(testDirectory, "engine.pid");
  const readyFile = path.join(testDirectory, "ready");
  const appProcess = spawn(executablePath, [], {
    cwd: path.dirname(executablePath),
    env: {
      ...process.env,
      OFFLINE_EXPLORER_TEST_HEADLESS: "1",
      OFFLINE_EXPLORER_TEST_PID_FILE: pidFile,
      OFFLINE_EXPLORER_TEST_READY_FILE: readyFile,
      OFFLINE_EXPLORER_USER_DATA: path.join(testDirectory, "user-data"),
    },
    stdio: "ignore",
  });

  try {
    await waitFor("the packaged app to become ready", () => existsSync(readyFile));
    assert.equal(childHasExited(appProcess), false, "The packaged app exited during startup.");
    const enginePid = Number.parseInt(readFileSync(pidFile, "utf8").trim(), 10);
    assert.ok(Number.isSafeInteger(enginePid) && enginePid > 0, "The engine PID was invalid.");
    assert.equal(processIsAlive(enginePid), true, "The packaged engine was not running.");

    appProcess.kill("SIGKILL");
    await waitFor("the Electron main process to exit", () => childHasExited(appProcess), 10_000);
    await waitFor("the packaged engine to stop after its parent crashed", () => !processIsAlive(enginePid), 10_000);
  } finally {
    if (!childHasExited(appProcess)) appProcess.kill("SIGKILL");
    rmSync(testDirectory, { recursive: true, force: true });
  }
});
