export interface BackendReady {
  url: string;
  desktopToken: string;
}

interface BackendReadyPayload {
  url?: unknown;
  desktop_token?: unknown;
}

export const BACKEND_READY_PREFIX = "OFFLINE_EXPLORER_READY ";

export function parseBackendReady(line: string): BackendReady | null {
  if (!line.startsWith(BACKEND_READY_PREFIX)) return null;

  let payload: BackendReadyPayload;
  try {
    payload = JSON.parse(line.slice(BACKEND_READY_PREFIX.length)) as BackendReadyPayload;
  } catch {
    throw new Error("The genome engine returned an invalid startup message.");
  }

  if (typeof payload.url !== "string" || typeof payload.desktop_token !== "string") {
    throw new Error("The genome engine returned an incomplete startup message.");
  }

  const url = new URL(payload.url);
  if (
    url.protocol !== "http:" ||
    url.hostname !== "127.0.0.1" ||
    url.username ||
    url.password ||
    !/^\/[A-Za-z0-9_-]+\/$/.test(url.pathname) ||
    url.search ||
    url.hash
  ) {
    throw new Error("The genome engine did not start on a private local address.");
  }
  if (payload.desktop_token.length < 32) {
    throw new Error("The genome engine returned an invalid desktop token.");
  }

  return { url: url.toString(), desktopToken: payload.desktop_token };
}

export function isTrustedBackendUrl(candidate: string, backendUrl: string): boolean {
  try {
    const candidateUrl = new URL(candidate);
    const backend = new URL(backendUrl);
    return (
      candidateUrl.origin === backend.origin &&
      candidateUrl.pathname.startsWith(backend.pathname)
    );
  } catch {
    return false;
  }
}
