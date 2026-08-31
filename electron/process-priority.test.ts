import assert from "node:assert/strict";
import { constants } from "node:os";
import test from "node:test";

import { lowerProcessPriority } from "./process-priority";

test("lowers the engine process priority", () => {
  let observed: [number, number] | undefined;

  const lowered = lowerProcessPriority(42, (pid, priority) => {
    observed = [pid, priority];
  });

  assert.equal(lowered, true);
  assert.deepEqual(observed, [42, constants.priority.PRIORITY_BELOW_NORMAL]);
});

test("does not interrupt startup when process priority cannot be changed", () => {
  const lowered = lowerProcessPriority(42, () => {
    throw new Error("permission denied");
  });

  assert.equal(lowered, false);
});
