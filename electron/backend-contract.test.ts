import assert from "node:assert/strict";
import test from "node:test";

import { isTrustedBackendUrl, parseBackendReady } from "./backend-contract";

test("accepts a private authenticated backend address", () => {
  assert.deepEqual(
    parseBackendReady(
      'OFFLINE_EXPLORER_READY {"url":"http://127.0.0.1:43123/session_token/","desktop_token":"abcdefghijklmnopqrstuvwxyz1234567890"}',
    ),
    {
      url: "http://127.0.0.1:43123/session_token/",
      desktopToken: "abcdefghijklmnopqrstuvwxyz1234567890",
    },
  );
});

test("rejects non-loopback and malformed backend addresses", () => {
  assert.throws(() =>
    parseBackendReady(
      'OFFLINE_EXPLORER_READY {"url":"https://example.com/session/","desktop_token":"abcdefghijklmnopqrstuvwxyz1234567890"}',
    ),
  );
  assert.throws(() =>
    parseBackendReady(
      'OFFLINE_EXPLORER_READY {"url":"http://localhost:43123/session/","desktop_token":"abcdefghijklmnopqrstuvwxyz1234567890"}',
    ),
  );
});

test("trusts only routes beneath the authenticated backend path", () => {
  const backend = "http://127.0.0.1:43123/session/";
  assert.equal(isTrustedBackendUrl(`${backend}api/status`, backend), true);
  assert.equal(isTrustedBackendUrl("http://127.0.0.1:43123/other/", backend), false);
  assert.equal(isTrustedBackendUrl("https://example.com/", backend), false);
});
