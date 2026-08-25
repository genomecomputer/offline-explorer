import assert from "node:assert/strict";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { mkdtemp, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import { migrateLegacyUserData } from "./user-data-migration";

test("moves app-owned data from the Genome Explorer user-data directory", async () => {
  const appData = await mkdtemp(path.join(os.tmpdir(), "offline-explorer-migration-"));
  try {
    const legacy = path.join(appData, "Genome Explorer");
    const current = path.join(appData, "Offline Explorer");
    mkdirSync(path.join(legacy, "workspaces", "bundle-1"), { recursive: true });
    writeFileSync(path.join(legacy, "bundle-library.json"), "legacy library");
    writeFileSync(path.join(legacy, "saved-results.json"), "legacy results");
    writeFileSync(path.join(legacy, "workspaces", "bundle-1", "schema.json"), "schema");
    writeFileSync(path.join(legacy, "Cache"), "browser cache", { flag: "w" });

    const migrated = migrateLegacyUserData(current);

    assert.deepEqual(migrated.sort(), [
      "bundle-library.json",
      "saved-results.json",
      "workspaces",
    ]);
    assert.equal(readFileSync(path.join(current, "bundle-library.json"), "utf8"), "legacy library");
    assert.equal(readFileSync(path.join(current, "saved-results.json"), "utf8"), "legacy results");
    assert.equal(readFileSync(path.join(current, "workspaces", "bundle-1", "schema.json"), "utf8"), "schema");
    assert.equal(readFileSync(path.join(legacy, "Cache"), "utf8"), "browser cache");
  } finally {
    await rm(appData, { recursive: true, force: true });
  }
});

test("does not overwrite data already created by Offline Explorer", async () => {
  const appData = await mkdtemp(path.join(os.tmpdir(), "offline-explorer-conflict-"));
  try {
    const legacy = path.join(appData, "Genome Explorer");
    const current = path.join(appData, "Offline Explorer");
    mkdirSync(legacy, { recursive: true });
    mkdirSync(current, { recursive: true });
    writeFileSync(path.join(legacy, "saved-results.json"), "legacy results");
    writeFileSync(path.join(current, "saved-results.json"), "current results");

    const migrated = migrateLegacyUserData(current);

    assert.deepEqual(migrated, []);
    assert.equal(readFileSync(path.join(current, "saved-results.json"), "utf8"), "current results");
    assert.equal(readFileSync(path.join(legacy, "saved-results.json"), "utf8"), "legacy results");
  } finally {
    await rm(appData, { recursive: true, force: true });
  }
});
