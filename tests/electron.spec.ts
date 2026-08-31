import { _electron as electron, expect, test } from "@playwright/test";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync } from "node:fs";
import os from "node:os";
import path from "node:path";

const repositoryRoot = path.resolve(__dirname, "..");
const sampleBundle = process.env.OFFLINE_EXPLORER_TEST_BUNDLE;
const clinicalBundle = process.env.OFFLINE_EXPLORER_CLINICAL_TEST_BUNDLE;
const currentBundle = process.env.OFFLINE_EXPLORER_CURRENT_TEST_BUNDLE;

if (!sampleBundle || !existsSync(sampleBundle)) {
  throw new Error("Set OFFLINE_EXPLORER_TEST_BUNDLE to a purpose-built synthetic bundle.");
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
  const deadline = Date.now() + 10_000;
  while (Date.now() < deadline) {
    if (!processIsAlive(pid)) return;
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error(`Genome engine process ${pid} remained alive after the app closed.`);
}

test("opens, searches, reuses a bundle, and owns engine shutdown", async () => {
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
  };
  const executablePath = process.env.OFFLINE_EXPLORER_EXECUTABLE;
  const launchOptions = executablePath
    ? { executablePath, args: [] as string[], cwd: repositoryRoot, env: environment }
    : { args: [repositoryRoot], cwd: repositoryRoot, env: environment };

  let firstApp: Awaited<ReturnType<typeof electron.launch>> | undefined;
  let secondApp: Awaited<ReturnType<typeof electron.launch>> | undefined;
  try {
    firstApp = await electron.launch(launchOptions);
    const firstWindow = await firstApp.firstWindow();
    await expect(firstWindow.getByRole("heading", { name: "Explore your genome bundle privately." })).toBeVisible();
    await expect(firstWindow.getByText("Stays on this computer", { exact: true })).toHaveCount(0);
    await expect(firstWindow.locator("#quit-button")).toBeHidden();
    await expect(firstWindow.locator("#sidebar-context")).toBeHidden();
    if (process.env.OFFLINE_EXPLORER_SCREENSHOT_DIR) {
      mkdirSync(process.env.OFFLINE_EXPLORER_SCREENSHOT_DIR, { recursive: true });
      await firstWindow.screenshot({
        path: path.join(process.env.OFFLINE_EXPLORER_SCREENSHOT_DIR, "welcome.png"),
      });
    }

    await firstWindow.getByRole("button", { name: "Add genome bundle" }).click();
    await expect(firstWindow.locator("#explorer")).toBeVisible({ timeout: 90_000 });
    await expect(firstWindow.locator("#validation")).toHaveText("Verified");
    await expect(firstWindow.locator("#spec-version")).toHaveText("v1.0.0");
    await expect(firstWindow.locator("#sidebar-context")).toBeVisible();
    await expect(firstWindow.locator("#sidebar-bundle-name")).toHaveText("sample");
    await expect(firstWindow.locator("#build")).toHaveText("GRCh38");
    await expect(firstWindow.locator("#view-search")).toBeVisible();
    await expect(firstWindow.locator("#view-library")).toBeHidden();
    await expect(firstWindow.locator("#results")).toBeHidden();
    await expect(firstWindow).toHaveURL(/#search$/);
    await firstWindow.getByRole("button", { name: /Region browser/ }).click();
    await expect(firstWindow.locator("#view-map")).toBeVisible();
    await expect(firstWindow.getByRole("heading", { name: "Region browser" })).toBeVisible();
    await expect(firstWindow.locator("#region-browser-status")).toContainText("Choose a locus");
    await firstWindow.getByRole("searchbox", { name: "Find a genomic region" }).fill("CYP2C19");
    const regionResponse = firstWindow.waitForResponse((response) => response.url().endsWith("/api/region-browser"));
    await firstWindow.getByRole("button", { name: "Open region" }).click();
    expect((await regionResponse).ok()).toBe(true);
    await expect(firstWindow.locator("#region-browser-workspace")).toBeVisible();
    await expect(firstWindow.locator("#region-target-title")).toHaveText("CYP2C19");
    await expect(firstWindow.locator("#region-coordinate")).toContainText("chr10:");
    await expect(firstWindow.locator("#region-gene-track").getByRole("button", { name: "CYP2C19" })).toBeVisible();
    await expect(firstWindow.locator("#region-variants-meta")).toContainText("recorded variants");
    await expect(firstWindow.locator("#region-records-content .record-row").first()).toBeVisible();
    if (process.env.OFFLINE_EXPLORER_SCREENSHOT_DIR) {
      await firstWindow.screenshot({
        path: path.join(process.env.OFFLINE_EXPLORER_SCREENSHOT_DIR, "region-browser.png"),
        fullPage: true,
      });
      const regionViewport = await firstWindow.evaluate(() => ({
        width: window.innerWidth,
        height: window.innerHeight,
      }));
      await firstWindow.setViewportSize({ width: 700, height: 900 });
      await firstWindow.screenshot({
        path: path.join(process.env.OFFLINE_EXPLORER_SCREENSHOT_DIR, "region-browser-narrow.png"),
        fullPage: true,
      });
      await firstWindow.setViewportSize(regionViewport);
    }
    const originalRegion = await firstWindow.locator("#region-coordinate").textContent();
    const zoomResponse = firstWindow.waitForResponse((response) => response.url().endsWith("/api/region-browser"));
    await firstWindow.getByRole("button", { name: "Zoom in" }).click();
    expect((await zoomResponse).ok()).toBe(true);
    await expect(firstWindow.locator("#region-coordinate")).not.toHaveText(originalRegion || "");
    await firstWindow.getByRole("button", { name: /Coverage & quality/ }).click();
    await expect(firstWindow.locator("#view-coverage")).toBeVisible();
    await expect(firstWindow.locator("#map-total")).toHaveText("5,159,392 recorded variants");
    await expect(firstWindow.locator("#map-callability")).toContainText("Not included in this bundle");
    await expect(firstWindow.locator("#map-table-body tr")).toHaveCount(25);
    await firstWindow.getByRole("tab", { name: /Personal results/ }).click();
    await expect(firstWindow.locator("#view-search")).toBeHidden();
    await expect(firstWindow.locator("#view-library")).toBeVisible();
    await expect(firstWindow.locator(".topic-browser")).toBeVisible();
    await expect(firstWindow.getByRole("tab", { name: /Personal results/ })).toHaveAttribute("aria-selected", "true");
    await expect(firstWindow.locator(".directory-row").first()).toBeVisible();
    await expect(firstWindow).toHaveURL(/#personal$/);
    if (process.env.OFFLINE_EXPLORER_SCREENSHOT_DIR) {
      await firstWindow.screenshot({
        path: path.join(process.env.OFFLINE_EXPLORER_SCREENSHOT_DIR, "topic-library.png"),
        fullPage: true,
      });
    }
    await firstWindow.getByRole("button", { name: /Genome search/ }).click();
    await expect(firstWindow.locator("#view-search")).toBeVisible();
    const popularSearches = firstWindow.locator(".featured-search");
    await expect(popularSearches).toHaveCount(6);
    const geneResponse = firstWindow.waitForResponse((response) => response.url().endsWith("/api/search"));
    await firstWindow.getByRole("button", { name: "MTHFR", exact: true }).click();
    expect((await geneResponse).ok()).toBe(true);
    await expect(firstWindow.locator("#results")).toBeVisible();
    await expect(firstWindow.locator("#view-search")).toBeHidden();
    await expect(firstWindow).toHaveURL(/#results$/);
    await expect(firstWindow.locator(".section-genes .card").first()).toBeVisible();
    await firstWindow.getByRole("tab", { name: /Conditions/ }).click();
    await expect(firstWindow.locator("#results")).toBeHidden();
    await expect(firstWindow.locator("#view-library")).toBeVisible();
    const pcosTopic = firstWindow.getByRole("button", { name: "Search this bundle for PCOS" });
    await expect(pcosTopic.locator(".topic-indicator-value")).toHaveText("85th percentile");
    await firstWindow.getByRole("tab", { name: /Traits/ }).click();
    const cholesterolTopic = firstWindow.getByRole("button", { name: "Search this bundle for Cholesterol levels" });
    await expect(cholesterolTopic.locator(".topic-indicator-value")).toHaveText("Related variants");
    const lactoseTopic = firstWindow.getByRole("button", { name: "Search this bundle for Lactose intolerance" });
    await expect(lactoseTopic.locator(".topic-indicator")).toHaveClass(/no-data/);
    await expect(lactoseTopic.locator(".topic-indicator-value")).toHaveText("No matching record");
    if (process.env.OFFLINE_EXPLORER_SCREENSHOT_DIR) {
      await firstWindow.screenshot({
        path: path.join(process.env.OFFLINE_EXPLORER_SCREENSHOT_DIR, "topic-answerability.png"),
        fullPage: true,
      });
    }
    await lactoseTopic.click();
    await expect(firstWindow.locator("#results-title")).toHaveText("No matching record");
    await expect(firstWindow.locator("#results")).toHaveAttribute(
      "data-answerability-state",
      "analysis_included_no_record",
    );
    await expect(firstWindow.locator("#result-notice-text")).toHaveText(
      "Relevant analysis is included, but this bundle does not record a personal result for this trait.",
    );
    await expect(firstWindow.locator(".section-gwas")).toHaveCount(0);
    await firstWindow.getByRole("button", { name: "← Back" }).click();
    await expect(firstWindow.locator("#view-library")).toBeVisible();
    await expect(firstWindow.locator("#results")).toBeHidden();
    await expect(firstWindow).toHaveURL(/#traits$/);
    await firstWindow.getByRole("button", { name: "Search this bundle for Cholesterol levels" }).click();
    await expect(firstWindow.getByText("Related variants", { exact: true }).last()).toBeVisible();
    await expect(firstWindow.getByText("High density lipoprotein cholesterol levels").first()).toBeVisible();
    const firstPersonalRecord = firstWindow.locator(".section-trait_variants .record-row").first();
    await expect(firstWindow.locator(".section-trait_variants .card")).toHaveCount(0);
    await expect(firstPersonalRecord.getByText("G / C")).toBeVisible();
    await firstPersonalRecord.locator(":scope > summary").click();
    const compactSave = firstPersonalRecord.locator(".save-result-button");
    await compactSave.click();
    await expect(compactSave).toHaveText("Saved");
    await expect(firstWindow.getByRole("button", { name: /Saved results/ })).toContainText("1");
    await compactSave.click();
    await expect(compactSave).toHaveText("Save");
    await expect(firstWindow.getByRole("button", { name: /Saved results/ })).toContainText("0");
    await expect(firstPersonalRecord.getByRole("link", { name: "PubMed 34887591" })).toHaveAttribute(
      "href",
      "https://pubmed.ncbi.nlm.nih.gov/34887591/",
    );
    const relatedPagination = firstWindow.locator(".section-trait_variants .result-pagination");
    await expect(relatedPagination.locator(".pagination-range")).toHaveText("1-10 of 25");
    await expect(firstWindow.locator(".section-trait_variants .record-row")).toHaveCount(10);
    await expect(firstWindow.getByText("Show more related records", { exact: true })).toHaveCount(0);
    const firstPageRecord = await firstWindow.locator(".section-trait_variants .record-row").first().textContent();
    await relatedPagination.getByRole("button", { name: "Next page of Related variants" }).click();
    await expect(relatedPagination.locator(".pagination-range")).toHaveText("11-20 of 25");
    const secondPageRecord = await firstWindow.locator(".section-trait_variants .record-row").first().textContent();
    expect(secondPageRecord).not.toBe(firstPageRecord);
    await relatedPagination.getByRole("button", { name: "Previous page of Related variants" }).click();
    await expect(relatedPagination.locator(".pagination-range")).toHaveText("1-10 of 25");
    await expect(firstWindow.getByText("Research sources")).toBeVisible();
    await expect(firstWindow.getByText(/has not been presented as a match/)).toHaveCount(0);
    if (process.env.OFFLINE_EXPLORER_SCREENSHOT_DIR) {
      await firstWindow.screenshot({
        path: path.join(process.env.OFFLINE_EXPLORER_SCREENSHOT_DIR, "person-linked-topic.png"),
        fullPage: true,
      });
      const desktopViewport = await firstWindow.evaluate(() => ({
        width: window.innerWidth,
        height: window.innerHeight,
      }));
      await firstWindow.setViewportSize({ width: 700, height: 900 });
      await expect(firstWindow.locator(".section-trait_variants .record-list-head")).toBeHidden();
      await firstWindow.screenshot({
        path: path.join(process.env.OFFLINE_EXPLORER_SCREENSHOT_DIR, "person-linked-topic-narrow.png"),
        fullPage: true,
      });
      await firstWindow.setViewportSize(desktopViewport);
      await expect(firstWindow.locator(".section-trait_variants .record-list-head")).toBeVisible();
    }
    const supportingResearch = firstWindow.locator(".section-gwas");
    await supportingResearch.locator(":scope > .result-disclosure > summary").click();
    await expect(supportingResearch.locator(".pagination-range")).toHaveText("1-10 of 25");
    await expect(supportingResearch.locator(".card")).toHaveCount(0);
    await expect(supportingResearch.getByText("GWAS Catalog").first()).toBeVisible();
    await supportingResearch.locator(".record-row").first().locator(":scope > summary").click();
    await expect(supportingResearch.getByRole("link", { name: /PubMed/ }).first()).toHaveAttribute(
      "href",
      /pubmed\.ncbi\.nlm\.nih\.gov\/\d+\/$/,
    );
    if (process.env.OFFLINE_EXPLORER_SCREENSHOT_DIR) {
      await firstWindow.screenshot({
        path: path.join(process.env.OFFLINE_EXPLORER_SCREENSHOT_DIR, "supporting-research.png"),
        fullPage: true,
      });
    }
    await firstWindow.getByRole("tab", { name: /Medications/ }).click();
    await expect(firstWindow.locator(".directory-row")).toHaveCount(15);

    await firstWindow.getByRole("button", { name: /Genome search/ }).click();
    await firstWindow.getByRole("searchbox", { name: "Search your genome bundle" }).fill("CYP2C9");
    await firstWindow.getByRole("button", { name: "Search", exact: true }).click();
    const cyp2c9Card = firstWindow.locator(".section-pharmacogenomics .card").first();
    const cyp2c9Save = cyp2c9Card.getByRole("button", { name: /Save CYP2C9/ });
    await cyp2c9Save.click();
    await expect(cyp2c9Card.getByRole("button", { name: /Saved CYP2C9/ })).toBeVisible();
    await firstWindow.getByRole("button", { name: /Saved results/ }).click();
    await expect(firstWindow.locator(".saved-result-row")).toHaveCount(1);
    const savedCyp2c9 = firstWindow.locator(".saved-result-row").first();
    await expect(savedCyp2c9).toContainText("CYP2C9");
    await savedCyp2c9.locator(":scope > summary").click();
    await savedCyp2c9.getByRole("button", { name: "Remove" }).click();
    await expect(firstWindow.locator(".saved-result-row")).toHaveCount(0);
    await firstWindow.getByRole("button", { name: /Genome search/ }).click();
    await firstWindow.getByRole("searchbox", { name: "Search your genome bundle" }).fill("CYP2C19");
    await firstWindow.getByRole("button", { name: "Search", exact: true }).click();
    await expect(firstWindow.locator("#results-title")).toHaveText("Personal records found");
    await expect(firstWindow.locator("#results")).toHaveAttribute("data-answerability-state", "recorded");
    await expect(firstWindow.locator("#result-meta")).toContainText("Search: CYP2C19");
    await expect(firstWindow.getByText("Person-specific data from this bundle").first()).toBeVisible();
    const pgxCard = firstWindow.locator(".section-pharmacogenomics .card").first();
    await pgxCard.getByRole("button", { name: /Save CYP2C19/ }).click();
    await expect(pgxCard.getByRole("button", { name: /Saved CYP2C19/ })).toBeVisible();
    if (process.env.OFFLINE_EXPLORER_SCREENSHOT_DIR) {
      await firstWindow.screenshot({
        path: path.join(process.env.OFFLINE_EXPLORER_SCREENSHOT_DIR, "search-results.png"),
        fullPage: true,
      });
    }
    await firstWindow.getByRole("button", { name: /Saved results/ }).click();
    await expect(firstWindow.locator("#view-saved")).toBeVisible();
    await expect(firstWindow.locator(".saved-result-row")).toHaveCount(1);
    await expect(firstWindow.locator(".saved-result-row").first()).toContainText("CYP2C19");
    await firstWindow.getByRole("button", { name: "Export JSON" }).click();
    await firstWindow.getByRole("button", { name: "Export CSV" }).click();
    const jsonExportPath = path.join(exportDirectory, "sample-saved-results.json");
    const csvExportPath = path.join(exportDirectory, "sample-saved-results.csv");
    await expect.poll(() => existsSync(jsonExportPath)).toBe(true);
    await expect.poll(() => existsSync(csvExportPath)).toBe(true);
    const jsonExport = JSON.parse(readFileSync(jsonExportPath, "utf8"));
    expect(jsonExport.bundle.nickname).toBe("sample");
    expect(jsonExport.bundle).not.toHaveProperty("bundle_id");
    expect(jsonExport).not.toHaveProperty("format");
    expect(jsonExport).not.toHaveProperty("version");
    expect(jsonExport.results).toHaveLength(1);
    expect(jsonExport.results[0].result_type).toBe("pharmacogenomics");
    expect(jsonExport.results[0]).not.toHaveProperty("saved_id");
    expect(jsonExport.results[0].record).not.toHaveProperty("section");
    expect(jsonExport.results[0].record.gene_symbol).toBe("CYP2C19");
    expect(readFileSync(csvExportPath, "utf8")).not.toContain("saved_id");
    expect(readFileSync(csvExportPath, "utf8")).toContain("gene_symbol");
    expect(readFileSync(csvExportPath, "utf8")).toContain("CYP2C19");
    if (process.env.OFFLINE_EXPLORER_SCREENSHOT_DIR) {
      await firstWindow.screenshot({
        path: path.join(process.env.OFFLINE_EXPLORER_SCREENSHOT_DIR, "saved-results.png"),
        fullPage: true,
      });
    }

    const answerabilityFixtures: Record<string, { state: string; reason: string }> = {
      "chr1:200:A:T": {
        state: "callable_no_matching_alternate",
        reason: "callable_position_without_matching_variant",
      },
      "chr1:300": {
        state: "not_callable",
        reason: "position_not_reliably_callable",
      },
      "chr1:400": {
        state: "analysis_not_included",
        reason: "site_callability_not_included",
      },
      "chr1:500": {
        state: "unsupported_bundle_version",
        reason: "site_callability_not_available_in_bundle_version",
      },
      rs999: {
        state: "insufficient_bundle_data",
        reason: "rsid_has_no_offline_coordinate_mapping",
      },
    };
    await firstWindow.route("**/api/search", async (route) => {
      const request = route.request();
      const payload = request.postDataJSON() as { query: string };
      const answerability = answerabilityFixtures[payload.query];
      if (!answerability) {
        await route.continue();
        return;
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          query: payload.query,
          query_kind: payload.query.startsWith("rs") ? "rsid" : "coordinate",
          answerability: {
            ...answerability,
            scope: payload.query.startsWith("rs") ? "rsid" : "coordinate",
            basis: "test_fixture",
          },
          hits: [],
          elapsed_seconds: 0,
        }),
      });
    });

    const answerabilityCases = [
      ["chr1:200:A:T", "callable_no_matching_alternate", "No matching alternate record"],
      ["chr1:300", "not_callable", "Position not reliably callable"],
      ["chr1:400", "analysis_not_included", "Callability not included"],
      ["chr1:500", "unsupported_bundle_version", "Bundle version cannot answer"],
      ["rs999", "insufficient_bundle_data", "Not enough bundle data"],
    ];
    for (const [query, state, title] of answerabilityCases) {
      await firstWindow.getByRole("button", { name: /Genome search/ }).click();
      await firstWindow.getByRole("searchbox", { name: "Search your genome bundle" }).fill(query);
      await firstWindow.getByRole("button", { name: "Search", exact: true }).click();
      await expect(firstWindow.locator("#results")).toHaveAttribute("data-answerability-state", state);
      await expect(firstWindow.locator("#results-title")).toHaveText(title);
    }
    await firstWindow.unroute("**/api/search");

    const firstEnginePid = Number.parseInt(readFileSync(pidFile, "utf8"), 10);
    await firstApp.close();
    firstApp = undefined;
    await waitForProcessExit(firstEnginePid);

    secondApp = await electron.launch(launchOptions);
    const secondWindow = await secondApp.firstWindow();
    await expect(secondWindow.getByRole("heading", { name: "Choose a genome bundle." })).toBeVisible();
    await expect(secondWindow.locator(".bundle-item")).toHaveCount(1);
    await expect(secondWindow.locator(".bundle-meta").first()).toContainText("Genome spec v1.0.0");
    if (process.env.OFFLINE_EXPLORER_SCREENSHOT_DIR) {
      await secondWindow.screenshot({
        path: path.join(process.env.OFFLINE_EXPLORER_SCREENSHOT_DIR, "bundle-library.png"),
        fullPage: true,
      });
    }
    await secondWindow.locator(".bundle-open").click();
    await expect(secondWindow.locator("#explorer")).toBeVisible();
    await expect(secondWindow.locator("#validation")).toHaveText("Previously verified");
    await secondWindow.getByRole("button", { name: /Saved results/ }).click();
    await expect(secondWindow.locator(".saved-result-row")).toHaveCount(1);
    const savedRow = secondWindow.locator(".saved-result-row").first();
    await savedRow.locator(":scope > summary").click();
    if (process.env.OFFLINE_EXPLORER_SCREENSHOT_DIR) {
      await secondWindow.screenshot({
        path: path.join(process.env.OFFLINE_EXPLORER_SCREENSHOT_DIR, "saved-results-expanded.png"),
        fullPage: true,
      });
    }
    await savedRow.getByRole("button", { name: "Remove" }).click();
    await expect(secondWindow.locator(".saved-result-row")).toHaveCount(0);
    await expect(secondWindow.getByRole("button", { name: /Saved results/ })).toContainText("0");

    const secondEnginePid = Number.parseInt(readFileSync(pidFile, "utf8"), 10);
    await secondApp.close();
    secondApp = undefined;
    await waitForProcessExit(secondEnginePid);
  } finally {
    if (secondApp) await secondApp.close().catch(() => undefined);
    if (firstApp) await firstApp.close().catch(() => undefined);
    rmSync(userData, { recursive: true, force: true });
  }
});

test("shows clinical-grade findings with person calls and ClinVar evidence", async () => {
  test.skip(!clinicalBundle || !existsSync(clinicalBundle), "Set OFFLINE_EXPLORER_CLINICAL_TEST_BUNDLE to a synthetic v1.1 bundle.");

  const userData = mkdtempSync(path.join(os.tmpdir(), "offline-explorer-clinical-"));
  const pidFile = path.join(userData, "engine.pid");
  const environment = {
    ...process.env,
    OFFLINE_EXPLORER_TEST_BUNDLE: clinicalBundle,
    OFFLINE_EXPLORER_TEST_PID_FILE: pidFile,
    OFFLINE_EXPLORER_USER_DATA: userData,
  };
  const executablePath = process.env.OFFLINE_EXPLORER_EXECUTABLE;
  const launchOptions = executablePath
    ? { executablePath, args: [] as string[], cwd: repositoryRoot, env: environment }
    : { args: [repositoryRoot], cwd: repositoryRoot, env: environment };

  let app: Awaited<ReturnType<typeof electron.launch>> | undefined;
  try {
    app = await electron.launch(launchOptions);
    const window = await app.firstWindow();
    await window.getByRole("button", { name: "Add genome bundle" }).click();
    await expect(window.locator("#explorer")).toBeVisible({ timeout: 30_000 });

    await window.getByRole("tab", { name: /Personal results/ }).click();
    const clinicalRow = window.getByRole("button", { name: "Search this bundle for Clinical findings" });
    await expect(clinicalRow.locator(".topic-indicator-value")).toHaveText("2 clinical findings");
    await clinicalRow.click();

    const section = window.locator(".section-clinical_findings");
    await expect(section.getByText("Clinical findings", { exact: true })).toBeVisible();
    const firstFinding = section.locator(".card").first();
    await expect(firstFinding.getByRole("heading", { name: "Dihydropyrimidine dehydrogenase deficiency" })).toBeVisible();
    await expect(firstFinding.locator(":scope > .simple-fields").getByText("Likely pathogenic", { exact: true })).toBeVisible();
    await expect(firstFinding.locator(":scope > .simple-fields").getByText("A / T", { exact: true })).toBeVisible();
    await expect(firstFinding.locator(":scope > .simple-fields").getByText("high", { exact: true })).toBeVisible();
    await expect(firstFinding.locator(":scope > .simple-fields").getByText("reviewed by expert panel", { exact: true })).toBeVisible();
    await expect(firstFinding.getByRole("link", { name: "ClinVar VCV000307730" })).toHaveAttribute(
      "href",
      "https://www.ncbi.nlm.nih.gov/clinvar/?term=VCV000307730",
    );
    await expect(section.getByText(/Conflicting ClinVar submissions/)).toBeVisible();

    if (process.env.OFFLINE_EXPLORER_SCREENSHOT_DIR) {
      mkdirSync(process.env.OFFLINE_EXPLORER_SCREENSHOT_DIR, { recursive: true });
      await window.screenshot({
        path: path.join(process.env.OFFLINE_EXPLORER_SCREENSHOT_DIR, "clinical-findings.png"),
        fullPage: true,
      });
    }

    const enginePid = Number.parseInt(readFileSync(pidFile, "utf8"), 10);
    await app.close();
    app = undefined;
    await waitForProcessExit(enginePid);
  } finally {
    if (app) await app.close().catch(() => undefined);
    rmSync(userData, { recursive: true, force: true });
  }
});

test("opens and searches a current v1.1 bundle", async () => {
  test.skip(!currentBundle || !existsSync(currentBundle), "Set OFFLINE_EXPLORER_CURRENT_TEST_BUNDLE to a synthetic v1.1 bundle.");

  const userData = mkdtempSync(path.join(os.tmpdir(), "offline-explorer-current-"));
  const pidFile = path.join(userData, "engine.pid");
  const environment = {
    ...process.env,
    OFFLINE_EXPLORER_TEST_BUNDLE: currentBundle,
    OFFLINE_EXPLORER_TEST_PID_FILE: pidFile,
    OFFLINE_EXPLORER_USER_DATA: userData,
  };
  const executablePath = process.env.OFFLINE_EXPLORER_EXECUTABLE;
  const launchOptions = executablePath
    ? { executablePath, args: [] as string[], cwd: repositoryRoot, env: environment }
    : { args: [repositoryRoot], cwd: repositoryRoot, env: environment };

  let app: Awaited<ReturnType<typeof electron.launch>> | undefined;
  try {
    app = await electron.launch(launchOptions);
    const window = await app.firstWindow();
    await window.getByRole("button", { name: "Add genome bundle" }).click();
    await expect(window.locator("#explorer")).toBeVisible({ timeout: 30_000 });
    await expect(window.locator("#validation")).toHaveText("Verified");
    await expect(window.locator("#spec-version")).toHaveText("v1.1.0");
    await window.getByRole("button", { name: /Coverage & quality/ }).click();
    await expect(window.locator("#map-callability")).toContainText("Included, no records");

    await window.getByRole("tab", { name: /Medications/ }).click();
    const clopidogrelTopic = window.getByRole("button", { name: "Search this bundle for Clopidogrel" });
    await expect(clopidogrelTopic.locator(".topic-indicator-value")).toHaveText("Analysis not included");
    if (process.env.OFFLINE_EXPLORER_SCREENSHOT_DIR) {
      await window.screenshot({
        path: path.join(process.env.OFFLINE_EXPLORER_SCREENSHOT_DIR, "topic-analysis-not-included.png"),
        fullPage: true,
      });
    }
    await clopidogrelTopic.click();
    await expect(window.locator("#results-title")).toHaveText("Analysis not included");
    await expect(window.locator("#results")).toHaveAttribute(
      "data-answerability-state",
      "analysis_not_included",
    );
    await expect(window.locator("#result-notice-text")).toHaveText(
      "This bundle does not include the analysis needed to answer this medication.",
    );

    await window.getByRole("button", { name: /Genome search/ }).click();
    await window.getByRole("searchbox", { name: "Search your genome bundle" }).fill("HFE");
    const searchResponse = window.waitForResponse((response) => response.url().endsWith("/api/search"));
    await window.getByRole("button", { name: "Search", exact: true }).click();
    expect((await searchResponse).ok()).toBe(true);
    await expect(window.locator("#results-title")).toHaveText("Personal records found");
    await expect(window.locator("#results")).toHaveAttribute("data-answerability-state", "recorded");
    await expect(window.locator(".section-variants .record-row").filter({ hasText: "rs1800562" })).toBeVisible();
    await expect(window.locator(".section-clinical_findings")).toHaveCount(0);

    await window.getByRole("button", { name: /Genome search/ }).click();
    await window.getByRole("searchbox", { name: "Search your genome bundle" }).fill("Hemoglobin");
    const researchResponse = window.waitForResponse((response) => response.url().endsWith("/api/search"));
    await window.getByRole("button", { name: "Search", exact: true }).click();
    expect((await researchResponse).ok()).toBe(true);
    const research = window.locator(".section-gwas");
    await expect(research.getByText("Research sources", { exact: true })).toBeVisible();
    await research.locator(":scope > .result-disclosure > summary").click();
    await research.locator(".record-row").first().locator(":scope > summary").click();
    await expect(research.getByRole("link", { name: /PubMed/ }).first()).toHaveAttribute(
      "href",
      /pubmed\.ncbi\.nlm\.nih\.gov\/\d+\/$/,
    );

    await window.getByRole("button", { name: /Genome search/ }).click();
    await window.getByRole("searchbox", { name: "Search your genome bundle" }).fill("chr6:1");
    const unresolvedResponse = window.waitForResponse((response) => response.url().endsWith("/api/search"));
    await window.getByRole("button", { name: "Search", exact: true }).click();
    const unresolvedPayload = await (await unresolvedResponse).json();
    expect(unresolvedPayload.answerability.state).toBe("insufficient_bundle_data");
    await expect(window.locator("#results-title")).toHaveText("Not enough bundle data");
    await expect(window.locator("#result-meta")).toHaveText("Search: chr6:1");
    await expect(window.locator("#result-notice-text")).toContainText("so it remains unresolved");
    if (process.env.OFFLINE_EXPLORER_SCREENSHOT_DIR) {
      await window.screenshot({
        path: path.join(process.env.OFFLINE_EXPLORER_SCREENSHOT_DIR, "answerability-unresolved.png"),
      });
    }

    const enginePid = Number.parseInt(readFileSync(pidFile, "utf8"), 10);
    await app.close();
    app = undefined;
    await waitForProcessExit(enginePid);
  } finally {
    if (app) await app.close().catch(() => undefined);
    rmSync(userData, { recursive: true, force: true });
  }
});
