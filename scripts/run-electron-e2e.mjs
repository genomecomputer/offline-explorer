import { existsSync, mkdtempSync, rmSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const scriptDirectory = path.dirname(fileURLToPath(import.meta.url));
const repositoryRoot = path.resolve(scriptDirectory, "..");
const runtimeDirectory = path.join(repositoryRoot, ".offline-explorer", "prototype-venv");
const python = process.platform === "win32"
  ? path.join(runtimeDirectory, "Scripts", "python.exe")
  : path.join(runtimeDirectory, "bin", "python");
const playwright = process.platform === "win32"
  ? path.join(repositoryRoot, "node_modules", ".bin", "playwright.cmd")
  : path.join(repositoryRoot, "node_modules", ".bin", "playwright");

function run(command, args, environment = process.env) {
  const result = spawnSync(command, args, {
    cwd: repositoryRoot,
    env: { ...environment, PYTHONDONTWRITEBYTECODE: "1" },
    stdio: "inherit",
  });
  if (result.error) throw result.error;
  return result.status ?? 1;
}

const runtimeReady = existsSync(python)
  && spawnSync(python, ["-c", "import duckdb"], { stdio: "ignore" }).status === 0;
if (!runtimeReady) {
  if (run(process.execPath, [path.join(scriptDirectory, "run-python-tests.mjs")]) !== 0) {
    throw new Error("Could not prepare the Python runtime for Electron E2E tests.");
  }
}

const fixtures = mkdtempSync(path.join(os.tmpdir(), "offline-explorer-e2e-"));
try {
  if (run(python, [path.join(scriptDirectory, "generate-e2e-bundle.py"), fixtures]) !== 0) {
    throw new Error("Could not generate the synthetic Electron E2E bundle.");
  }
  const bundle = path.join(fixtures, "synthetic-review.genome.tar");
  process.exitCode = run(
    playwright,
    ["test"],
    {
      ...process.env,
      OFFLINE_EXPLORER_TEST_BUNDLE: bundle,
      OFFLINE_EXPLORER_TEST_HEADLESS: "1",
    },
  );
} finally {
  rmSync(fixtures, { recursive: true, force: true });
}
