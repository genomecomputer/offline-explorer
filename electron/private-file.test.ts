import assert from "node:assert/strict";
import { chmodSync, mkdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import { writePrivateTextFile } from "./private-file";

test("replaces an existing public file with a private file", async () => {
  const directory = path.join(
    os.tmpdir(),
    `offline-explorer-private-file-${process.pid}-${Date.now()}`,
  );
  try {
    mkdirSync(directory, { recursive: true });
    const filePath = path.join(directory, "saved-results.json");
    writeFileSync(filePath, "old");
    chmodSync(filePath, 0o644);

    writePrivateTextFile(filePath, "new");

    assert.equal(readFileSync(filePath, "utf8"), "new");
    assert.equal(statSync(filePath).mode & 0o777, 0o600);
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});
