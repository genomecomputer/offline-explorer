import assert from "node:assert/strict";
import test from "node:test";

import { isGenomeBundlePath } from "./bundle-path";

test("accepts compressed and uncompressed genome tar paths", () => {
  assert.equal(isGenomeBundlePath("sample.genome.tar.gz"), true);
  assert.equal(isGenomeBundlePath("sample.genome.tar"), true);
  assert.equal(isGenomeBundlePath("SAMPLE.GENOME.TAR"), true);
});

test("rejects generic tar and gzip paths", () => {
  assert.equal(isGenomeBundlePath("sample.tar"), false);
  assert.equal(isGenomeBundlePath("sample.tar.gz"), false);
  assert.equal(isGenomeBundlePath("sample.genome.gz"), false);
});
