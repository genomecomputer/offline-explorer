import { createRequire } from "node:module";
import { copyFile, mkdir, mkdtemp, rm } from "node:fs/promises";
import { existsSync } from "node:fs";
import os from "node:os";
import path from "node:path";

const require = createRequire(import.meta.url);
const { downloadArtifact } = require("@electron/get");
const { extract } = require("@electron-internal/extract-zip");
const electronPackage = require("electron/package.json");
const electronChecksums = require("electron/checksums.json");

const outputDirectory = path.resolve("dist/electron-licenses");
const installedDirectory = path.resolve("node_modules/electron/dist");
const requiredFiles = ["LICENSE", "LICENSES.chromium.html"];

async function copyLicenses(sourceDirectory) {
  await mkdir(outputDirectory, { recursive: true });
  await Promise.all(
    requiredFiles.map((fileName) =>
      copyFile(
        path.join(sourceDirectory, fileName),
        path.join(outputDirectory, fileName),
      ),
    ),
  );
}

async function main() {
  if (
    requiredFiles.every((fileName) =>
      existsSync(path.join(installedDirectory, fileName)),
    )
  ) {
    await copyLicenses(installedDirectory);
    console.log(`Collected Electron ${electronPackage.version} license files.`);
    return;
  }

  const archivePath = await downloadArtifact({
    version: electronPackage.version,
    artifactName: "electron",
    platform: process.env.ELECTRON_INSTALL_PLATFORM ?? process.platform,
    arch: process.env.ELECTRON_INSTALL_ARCH ?? process.arch,
    checksums: electronChecksums,
  });
  const extractionDirectory = await mkdtemp(
    path.join(os.tmpdir(), "offline-explorer-electron-licenses-"),
  );

  try {
    await extract(archivePath, { dir: extractionDirectory });
    await copyLicenses(extractionDirectory);
  } finally {
    await rm(extractionDirectory, { recursive: true, force: true });
  }

  console.log(`Collected Electron ${electronPackage.version} license files.`);
}

await main();
