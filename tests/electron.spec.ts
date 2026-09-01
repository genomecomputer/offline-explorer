import {
  _electron as electron,
  chromium,
  expect,
  test,
  type Browser,
  type Page,
} from "@playwright/test";
import { spawn, type ChildProcess } from "node:child_process";
import {
  existsSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  rmSync,
  statSync,
} from "node:fs";
import os from "node:os";
import path from "node:path";
import { createServer } from "node:net";

const repositoryRoot = path.resolve(__dirname, "..");
const sampleBundle = process.env.OFFLINE_EXPLORER_TEST_BUNDLE;

if (!sampleBundle || !existsSync(sampleBundle)) {
  throw new Error("The tracked E2E runner did not generate its synthetic bundle.");
}
if (process.env.OFFLINE_EXPLORER_TEST_HEADLESS !== "1") {
  throw new Error("Electron E2E tests must run headlessly.");
}

function processIsAlive(pid: number): boolean {
  try {
    process.kill(pid, 0);
    return true;
  } catch {
    return false;
  }
}

async function waitForProcessExit(pid: number): Promise<void> {
  await expect.poll(() => processIsAlive(pid), { timeout: 10_000 }).toBe(false);
}

async function runSearch(window: Page, query: string): Promise<void> {
  await window.getByRole("button", { name: /Genome search/ }).click();
  await window
    .getByRole("searchbox", { name: "Search your genome bundle" })
    .fill(query);
  const response = window.waitForResponse((candidate) =>
    candidate.url().endsWith("/api/search"),
  );
  await window.getByRole("button", { name: "Search", exact: true }).click();
  expect((await response).ok()).toBe(true);
}

type TestApp = {
  firstWindow(): Promise<Page>;
  close(): Promise<void>;
};

async function reserveLoopbackPort(): Promise<number> {
  const server = createServer();
  await new Promise<void>((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", resolve);
  });
  const address = server.address();
  const port = typeof address === "object" && address ? address.port : 0;
  await new Promise<void>((resolve, reject) =>
    server.close((error) => error ? reject(error) : resolve()),
  );
  if (!port) throw new Error("Could not reserve a loopback debugging port");
  return port;
}

async function waitForChildExit(child: ChildProcess): Promise<void> {
  if (child.exitCode !== null || child.signalCode !== null) return;
  await Promise.race([
    new Promise<void>((resolve) => child.once("exit", () => resolve())),
    new Promise<never>((_resolve, reject) =>
      setTimeout(() => reject(new Error("Electron did not stop")), 10_000),
    ),
  ]);
}

async function launchPackagedApp(
  executablePath: string,
  environment: NodeJS.ProcessEnv,
): Promise<TestApp> {
  const port = await reserveLoopbackPort();
  const child = spawn(
    executablePath,
    [
      `--remote-debugging-port=${port}`,
      "--remote-debugging-address=127.0.0.1",
    ],
    {
      cwd: repositoryRoot,
      env: environment,
      stdio: "ignore",
    },
  );
  let browser: Browser | undefined;
  try {
    await expect.poll(async () => {
      if (child.exitCode !== null) {
        throw new Error(`Packaged Electron exited during startup (${child.exitCode})`);
      }
      try {
        const response = await fetch(`http://127.0.0.1:${port}/json/version`);
        return response.ok;
      } catch {
        return false;
      }
    }, { timeout: 30_000 }).toBe(true);
    browser = await chromium.connectOverCDP(`http://127.0.0.1:${port}`);
  } catch (error) {
    child.kill();
    await waitForChildExit(child).catch(() => undefined);
    throw error;
  }
  if (!browser) throw new Error("Could not connect to packaged Electron");
  const connectedBrowser = browser;

  return {
    async firstWindow() {
      await expect.poll(
        () => connectedBrowser.contexts().flatMap((context) => context.pages()).length,
        { timeout: 30_000 },
      ).toBeGreaterThan(0);
      const page = connectedBrowser.contexts().flatMap((context) => context.pages())[0];
      if (!page) throw new Error("Packaged Electron did not create a page");
      return page;
    },
    async close() {
      await connectedBrowser.close().catch(() => undefined);
      if (child.exitCode === null && child.signalCode === null) child.kill();
      await waitForChildExit(child);
    },
  };
}

async function launchApp(
  executablePath: string | undefined,
  environment: NodeJS.ProcessEnv,
): Promise<TestApp> {
  if (executablePath) return launchPackagedApp(executablePath, environment);
  return electron.launch({
    args: [repositoryRoot],
    cwd: repositoryRoot,
    env: environment,
  });
}

test("runs the review flow against the exact Electron executable", async () => {
  const progress = (stage: string) => console.log(`[electron-e2e] ${stage}`);
  const userData = mkdtempSync(path.join(os.tmpdir(), "offline-explorer-electron-"));
  const pidFile = path.join(userData, "engine.pid");
  const exportDirectory = path.join(userData, "exports");
  mkdirSync(exportDirectory);
  const environment = {
    ...process.env,
    OFFLINE_EXPLORER_TEST_BUNDLE: sampleBundle,
    OFFLINE_EXPLORER_TEST_PID_FILE: pidFile,
    OFFLINE_EXPLORER_USER_DATA: userData,
    OFFLINE_EXPLORER_TEST_EXPORT_DIR: exportDirectory,
    OFFLINE_EXPLORER_TEST_HEADLESS: "1",
  };
  const executablePath = process.env.OFFLINE_EXPLORER_EXECUTABLE;

  let firstApp: TestApp | undefined;
  let secondApp: TestApp | undefined;
  try {
    firstApp = await launchApp(executablePath, environment);
    const window = await firstApp.firstWindow();
    progress("first window ready");
    await expect(
      window.getByRole("heading", { name: "Explore your genome bundle privately." }),
    ).toBeAttached();

    await window.getByRole("button", { name: "Add genome bundle" }).click();
    await expect(window.locator("#explorer")).toBeAttached({ timeout: 60_000 });
    await expect(window.locator("#validation")).toHaveText("Verified");
    await expect(window.locator("#spec-version")).toHaveText("v1.1.0");
    await expect(window.locator("#build")).toHaveText("GRCh38");
    progress("bundle verified");

    await window.getByRole("button", { name: /Region browser/ }).click();
    await window
      .getByRole("searchbox", { name: "Find a genomic region" })
      .fill("CYP2C19");
    const regionResponse = window.waitForResponse((candidate) =>
      candidate.url().endsWith("/api/region-browser"),
    );
    await window.getByRole("button", { name: "Open region" }).click();
    expect((await regionResponse).ok()).toBe(true);
    await expect(window.locator("#region-target-title")).toHaveText("CYP2C19");
    await expect(window.locator("#region-coordinate")).toContainText("chr10:");
    progress("region browser verified");

    await window.getByRole("button", { name: /Coverage & quality/ }).click();
    await expect(window.locator("#map-total")).toHaveText("3 recorded variants");
    await expect(window.locator("#map-callability")).toContainText("site records");
    await expect(window.locator("#map-table-body tr")).toHaveCount(25);
    progress("coverage map verified");

    await runSearch(window, "1:100:A:G");
    await expect(window.locator("#results-title")).toHaveText("Personal records found");
    await expect(
      window.locator(".section-variants .record-row").filter({ hasText: "rs100" }),
    ).toBeAttached();

    await runSearch(window, "Synthetic condition");
    const clinical = window.locator(".section-clinical_findings .card").first();
    await expect(clinical).toContainText("Synthetic condition");
    await expect(clinical).toContainText("Likely pathogenic");
    await expect(clinical).toContainText("reviewed by expert panel");
    progress("clinical search verified");

    await runSearch(window, "Synthetic trait");
    const score = window.locator(".section-polygenic_scores .card").first();
    await expect(score).toContainText("Synthetic trait");
    await expect(score).toContainText("2026-08-14");
    progress("polygenic score search verified");

    await runSearch(window, "synthetic-drug");
    const pharmacogenomics = window.locator(".section-pharmacogenomics .card").first();
    await expect(pharmacogenomics).toContainText("CYP2C19");
    await pharmacogenomics.getByRole("button", { name: /Save CYP2C19/ }).click();
    await expect(
      pharmacogenomics.getByRole("button", { name: /Saved CYP2C19/ }),
    ).toBeAttached();

    await window.getByRole("button", { name: /Saved results/ }).click();
    await expect(window.locator(".saved-result-row")).toHaveCount(1);
    await window.getByRole("button", { name: "Export JSON" }).click();
    const exportPath = path.join(
      exportDirectory,
      "synthetic-review-saved-results.json",
    );
    await expect.poll(() => existsSync(exportPath)).toBe(true);
    const exported = JSON.parse(readFileSync(exportPath, "utf8"));
    expect(exported.results[0].record.gene_symbol).toBe("CYP2C19");
    expect(statSync(exportPath).mode & 0o777).toBe(0o600);
    progress("saved result export verified");

    await runSearch(window, "chr1:200:A:T");
    await expect(window.locator("#results")).toHaveAttribute(
      "data-answerability-state",
      "callable_no_matching_alternate",
    );
    await runSearch(window, "chr1:300");
    await expect(window.locator("#results")).toHaveAttribute(
      "data-answerability-state",
      "not_callable",
    );

    await window.route("**/api/search", async (route) => {
      const payload = route.request().postDataJSON() as { query: string };
      if (!payload.query.startsWith("race-")) {
        await route.continue();
        return;
      }
      if (payload.query === "race-old") {
        await new Promise((resolve) => setTimeout(resolve, 300));
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          query: payload.query,
          query_kind: "term",
          answerability: {
            state: payload.query === "race-new"
              ? "analysis_not_included"
              : "not_callable",
            scope: "term",
            basis: "synthetic_race",
            reason: payload.query === "race-new"
              ? "site_callability_not_included"
              : "position_not_reliably_callable",
          },
          hits: [],
          elapsed_seconds: 0,
        }),
      });
    });
    await window.getByRole("button", { name: /Genome search/ }).click();
    const input = window.getByRole("searchbox", { name: "Search your genome bundle" });
    await input.fill("race-old");
    await window.locator("#search-form").evaluate((form) =>
      form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true })),
    );
    await window.locator("#search-form").evaluate((form) => {
      const searchInput = form.querySelector<HTMLInputElement>("#search-input");
      if (!searchInput) throw new Error("Search input is missing");
      searchInput.value = "race-new";
      form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    });
    await expect(window.locator("#result-meta")).toHaveText("Search: race-new");
    await expect(window.locator("#results")).toHaveAttribute(
      "data-answerability-state",
      "analysis_not_included",
    );
    await new Promise((resolve) => setTimeout(resolve, 400));
    await expect(window.locator("#result-meta")).toHaveText("Search: race-new");
    await window.unroute("**/api/search");
    progress("overlapping search verified");

    const firstEnginePid = Number.parseInt(readFileSync(pidFile, "utf8"), 10);
    progress("closing first app");
    await firstApp.close();
    firstApp = undefined;
    await waitForProcessExit(firstEnginePid);
    progress("first engine stopped");

    secondApp = await launchApp(executablePath, environment);
    const secondWindow = await secondApp.firstWindow();
    progress("second window ready");
    await expect(
      secondWindow.getByRole("heading", { name: "Choose a genome bundle." }),
    ).toBeAttached();
    await expect(secondWindow.locator(".bundle-item")).toHaveCount(1);
    await secondWindow.locator(".bundle-open").click();
    await expect(secondWindow.locator("#validation")).toHaveText("Previously verified");
    await secondWindow.getByRole("button", { name: /Saved results/ }).click();
    await expect(secondWindow.locator(".saved-result-row")).toHaveCount(1);
    progress("cached bundle and saved result verified");

    await secondWindow.getByRole("button", { name: "Manage bundles" }).click();
    await secondWindow.locator(".bundle-remove").click();
    const confirmation = secondWindow.getByRole("alertdialog", {
      name: "Remove synthetic review from Offline Explorer",
    });
    await confirmation.getByRole("button", { name: "Remove bundle" }).click();
    await expect(secondWindow.locator(".bundle-item")).toHaveCount(0);
    expect(existsSync(sampleBundle)).toBe(true);
    progress("bundle removal verified");

    const secondEnginePid = Number.parseInt(readFileSync(pidFile, "utf8"), 10);
    progress("closing second app");
    await secondApp.close();
    secondApp = undefined;
    await waitForProcessExit(secondEnginePid);
    progress("second engine stopped");
  } finally {
    if (secondApp) await secondApp.close().catch(() => undefined);
    if (firstApp) await firstApp.close().catch(() => undefined);
    rmSync(userData, { recursive: true, force: true });
  }
});
