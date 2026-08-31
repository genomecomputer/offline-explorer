import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import process from "node:process";

const require = createRequire(import.meta.url);
const { listPackage } = require("@electron/asar");
const { FuseV1Options, getCurrentFuseWire } = require("@electron/fuses");

function run(command, args) {
  const result = spawnSync(command, args, { encoding: "utf8" });
  if (result.status !== 0) {
    throw new Error(
      `${command} ${args.join(" ")} failed:\n${result.stderr || result.stdout}`,
    );
  }
  return result.stdout.trim();
}

function requireFile(filePath) {
  assert.ok(existsSync(filePath), `Required packaged file is missing: ${filePath}`);
}

async function main() {
  assert.equal(process.platform, "darwin", "macOS preview verification requires macOS.");
  const appPath = process.argv[2];
  assert.ok(appPath, "usage: npm run verify:mac-preview -- /path/to/Offline Explorer.app");
  const resolvedAppPath = path.resolve(appPath);
  requireFile(resolvedAppPath);

  run("codesign", ["--verify", "--deep", "--strict", "--verbose=2", resolvedAppPath]);
  const executablePath = path.join(
    resolvedAppPath,
    "Contents",
    "MacOS",
    "Offline Explorer",
  );
  assert.equal(run("lipo", ["-archs", executablePath]), "arm64");

  const infoPlist = path.join(resolvedAppPath, "Contents", "Info.plist");
  assert.equal(
    run("plutil", ["-extract", "CFBundleIdentifier", "raw", "-o", "-", infoPlist]),
    "org.genomecomputer.offline-explorer",
  );
  run("plutil", ["-extract", "ElectronAsarIntegrity", "xml1", "-o", "-", infoPlist]);

  const fuses = await getCurrentFuseWire(resolvedAppPath);
  const disabled = "0".charCodeAt(0);
  const enabled = "1".charCodeAt(0);
  const expectedFuses = new Map([
    [FuseV1Options.RunAsNode, disabled],
    [FuseV1Options.EnableNodeOptionsEnvironmentVariable, disabled],
    [FuseV1Options.EnableNodeCliInspectArguments, disabled],
    [FuseV1Options.EnableEmbeddedAsarIntegrityValidation, enabled],
    [FuseV1Options.OnlyLoadAppFromAsar, enabled],
    [FuseV1Options.LoadBrowserProcessSpecificV8Snapshot, disabled],
    [FuseV1Options.GrantFileProtocolExtraPrivileges, disabled],
  ]);
  for (const [fuse, expectedState] of expectedFuses) {
    assert.equal(
      fuses[fuse],
      expectedState,
      `${FuseV1Options[fuse]} has an unexpected packaged state.`,
    );
  }

  const resources = path.join(resolvedAppPath, "Contents", "Resources");
  const asarFiles = listPackage(path.join(resources, "app.asar"), {});
  assert.equal(
    asarFiles.some((file) => file.endsWith(".test.js")),
    false,
    "Compiled tests must not be included in app.asar.",
  );
  for (const relativePath of [
    "licenses/OFFLINE-EXPLORER-LICENSE.txt",
    "licenses/ELECTRON-LICENSE.txt",
    "licenses/ELECTRON-THIRD-PARTY-NOTICES.html",
    "engine/licenses/DUCKDB-LICENSE.txt",
    "engine/licenses/PYINSTALLER-LICENSE.txt",
    "engine/licenses/PYTHON-LICENSE.txt",
  ]) {
    requireFile(path.join(resources, relativePath));
  }

  console.log("Verified unsigned macOS ARM preview package.");
}

await main();
