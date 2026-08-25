# AGENTS.md

This file is the operating contract for agents and contributors working in Offline Explorer. Read it before planning or changing files. A more specific `AGENTS.md` may add rules for a subtree.

## Mission

Build a private, local explorer for compatible `.genome` bundles.

The product promise is:

> Search and understand your downloaded genome privately, without uploading it or requiring AI.

Offline Explorer is a viewer and query engine for information already recorded in a bundle. It is not a diagnostic service and must not create new health interpretations from raw genomic data.

## Product boundaries

- The runtime must work without AI, an account, an API key, telemetry, or a network connection.
- Do not add automatic outbound requests, remote fonts, analytics, crash reporting, update checks, or external APIs.
- A public citation may open in the system browser only after an explicit user action.
- The desktop application must own the helper process and stop it when the application closes.
- The local server must bind only to authenticated loopback and must not be exposed to the local network.
- The original bundle is read-only and must never be modified.
- Extract only the files needed by Explorer into its ignored local workspace.
- The documented `.genome` format remains independent of this application.

## Scientific and medical boundaries

- Display only findings and explanations traceable to bundle fields or an approved, versioned offline reference.
- Never infer a diagnosis, risk estimate, treatment recommendation, carrier status, ancestry result, physical trait, or medication recommendation from arbitrary variants.
- Keep person-specific bundle records visibly distinct from general research or reference context.
- Keep clinical findings, pharmacogenomics, polygenic scores, research associations, and raw variant records distinct.
- A gene annotation does not mean that a person uniquely "has" that gene. Describe the records or variants annotated to it.
- Variant counts and density are navigation aids, not measures of biological importance or risk.
- Distinguish "analysis not included," "no matching result," "not callable," and "not recorded." Do not collapse them into a negative result.
- Treat site-level callability separately from interval coverage. Never calculate a coverage percentage from isolated callable sites.
- Scientific wording, aliases, evidence grouping, and deterministic explanation templates require biotech review.

## Genomic data safety

Never commit, upload, paste, log, screenshot, or attach real genomic data.

This includes VCF, gVCF, CRAM, BAM, Parquet rows, genome bundles, manifests carrying person-specific metadata, search histories, saved results, and exports. Removing a name does not make genomic data safe.

Use only purpose-built synthetic fixtures in tests, screenshots, documentation, issues, and pull requests. Large performance fixtures must be generated locally and kept out of Git history.

Do not inspect a real bundle unless the user explicitly places it in scope. When inspection is authorized, prefer schemas, aggregate sizes, and structural metadata. Do not print person-specific rows.

## Bundle compatibility and validation

- Treat the public Genome Spec as the format authority.
- Preserve supported legacy `.genome/1.x` behavior when adding current-format features.
- Optional files and fields must produce explicit unavailable states rather than crashes or invented values.
- Validate archive structure, manifest entries, file sizes, and recorded hashes before querying a newly opened bundle.
- Defend archive extraction against unsafe paths, links, special files, duplicate members, malformed headers, excessive expansion, and resource exhaustion.
- Reuse cached validation only when the source archive identity and retained files still match the recorded receipt.
- Workspace cleanup may target only directories created and positively identified by Offline Explorer.

## Architecture

- `electron/main.ts` owns the desktop window, native dialogs, local engine lifecycle, and saved-result file export.
- `electron/preload.ts` exposes the narrow sandboxed desktop bridge.
- `prototype/selective_reader/` contains validation, bundle storage, deterministic DuckDB queries, saved results, topics, the Region browser, and the loopback server.
- `prototype/selective_reader/web.py` contains the bundled local interface. Keep it dependency-free and offline.
- The everyday interface contains search, personal results, medications, conditions, traits, and saved results.
- Region browser is an advanced tool. Coverage and quality belong with Bundle details.
- The CLI and Electron application must share the same Python validation and query core.

## User-interface standard

- Lead with the person's recorded result and its source, not raw identifiers or generic research context.
- Prefer compact rows and tables over large repeated cards.
- Keep technical fields collapsed until requested.
- Avoid repetitive labels, warnings, eyebrows, and explanatory copy.
- Make the full visible row clickable when it represents one action.
- Provide deterministic source links when the bundle records a resolvable identifier.
- Do not make empty research context look like a personal finding.
- Test desktop and narrow layouts visually. Treat obvious alignment, hierarchy, overflow, and click-target problems as defects.

## Development

Install dependencies and start the development application with:

```sh
npm install
npm run dev
```

Run the standard checks with:

```sh
npm test
```

Run Electron end-to-end tests with synthetic fixtures:

```sh
OFFLINE_EXPLORER_TEST_BUNDLE=/absolute/path/to/sample.genome.tar.gz npm run test:e2e
```

`OFFLINE_EXPLORER_CURRENT_TEST_BUNDLE` and `OFFLINE_EXPLORER_CLINICAL_TEST_BUNDLE` enable the current-format and clinical fixture scenarios when those synthetic bundles are available.

The development launcher installs DuckDB from a prebuilt Python wheel. Do not compile DuckDB from source. Do not run `npm run package`, `npm run dist`, or the PyInstaller build merely to test ordinary source changes.

## Engineering workflow

- Work on one bounded change at a time.
- Start bug fixes by reproducing the end-user behavior in Electron as closely as possible.
- Prefer quality, simplicity, robustness, scalability, and long-term maintainability over short-term development cost.
- Preserve compatibility and make the smallest coherent change.
- Add deterministic tests for behavior, privacy boundaries, errors, and retries where applicable.
- Run the most relevant focused test during development, then `npm test` before handoff.
- Run relevant Electron end-to-end coverage for user-facing changes.
- Review the complete diff for genomic data, secrets, local absolute paths, and unrelated files before committing.
- Do not manually edit generated artifacts or changelogs marked as generated.
- Do not commit `.offline-explorer/`, `.electron-dist/`, `dist/`, `release/`, Playwright output, or dependency directories.
- Never add an agent as a commit co-author.
- Never use the em dash character in authored content.

## Public contribution standard

The project must remain understandable and maintainable without Codex. Repository instructions, scripts, synthetic fixtures, and tests are the shared interface for humans and agents.

If a change cannot be verified from a clean checkout using documented commands, it is not ready to merge.
