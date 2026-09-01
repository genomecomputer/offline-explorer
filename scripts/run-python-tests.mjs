import { existsSync } from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const scriptDirectory = path.dirname(fileURLToPath(import.meta.url));
const repositoryRoot = path.resolve(scriptDirectory, "..");
const runtimeDirectory = path.join(repositoryRoot, ".offline-explorer", "prototype-venv");
const python = process.platform === "win32"
  ? path.join(runtimeDirectory, "Scripts", "python.exe")
  : path.join(runtimeDirectory, "bin", "python");

function run(command, args, stdio = "inherit") {
  const result = spawnSync(command, args, {
    cwd: repositoryRoot,
    env: { ...process.env, PYTHONDONTWRITEBYTECODE: "1" },
    stdio,
  });
  if (result.error) throw result.error;
  return result.status ?? 1;
}

if (!existsSync(python)) {
  const systemPython = process.platform === "win32" ? "python" : "python3";
  if (run(systemPython, ["-m", "venv", runtimeDirectory]) !== 0) {
    throw new Error("Python is required to run contributor tests.");
  }
}

if (run(python, ["-c", "import duckdb"], "ignore") !== 0) {
  const requirements = path.join(repositoryRoot, "prototype", "requirements.txt");
  if (run(python, ["-m", "pip", "install", "--only-binary=:all:", "-r", requirements]) !== 0) {
    throw new Error("Could not install the prebuilt Python test dependencies.");
  }
}

process.exit(run(python, ["-m", "unittest", "discover", "-s", "prototype/tests"]));
