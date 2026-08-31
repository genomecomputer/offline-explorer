<p align="center">
  <img src="assets/app-icon.png" width="128" alt="Offline Explorer app icon">
</p>

<h1 align="center">Offline Explorer</h1>

<p align="center">
  <strong>Private, local exploration for <code>.genome</code> bundles.</strong>
</p>

<p align="center">
  <a href="https://github.com/genomecomputer/offline-explorer/releases"><img alt="GitHub release" src="https://img.shields.io/github/v/release/genomecomputer/offline-explorer?include_prereleases&label=release"></a>
  <a href="LICENSE"><img alt="Apache 2.0 license" src="https://img.shields.io/badge/license-Apache%202.0-blue.svg"></a>
  <img alt="macOS on Apple silicon" src="https://img.shields.io/badge/macOS-Apple%20silicon-black.svg">
</p>

<p align="center">
  <a href="https://github.com/genomecomputer/offline-explorer/releases">Download</a>
  ·
  <a href="https://github.com/genome-computer/genome-spec"><code>.genome</code> specification</a>
  ·
  <a href="AGENTS.md">Contributing</a>
</p>

Offline Explorer is an open-source desktop application for browsing compatible `.genome` bundles. It makes the information in a bundle accessible through deterministic local queries without uploading genomic data or requiring an account, API key, AI service, telemetry, or network connection.

## Features

- Search genes, rsIDs, genomic coordinates, medications, conditions, traits, and reviewed topics.
- Browse personal results, clinical findings, pharmacogenomics, polygenic scores, research associations, and raw variants.
- Distinguish recorded findings from missing matches, unavailable analyses, and non-callable positions.
- Explore genomic regions with variant tracks, callability context, coverage information, and bounded pagination.
- Save bundle-specific results and export them as JSON or CSV.

## Download

Preview builds for macOS on Apple silicon are available from [GitHub Releases](https://github.com/genomecomputer/offline-explorer/releases). New preview releases include a SHA-256 checksum and a GitHub build-provenance attestation.

These previews are ad-hoc signed but not yet notarized with Apple. macOS will identify the developer as unverified. To open a preview, Control-click the app in Finder, choose **Open**, then confirm **Open**. Never disable Gatekeeper globally.

## The `.genome` bundle

Offline Explorer reads [`.genome` bundles](https://github.com/genome-computer/genome-spec), the open, self-describing format developed by [Genome Computer](https://genome.computer) for structured, queryable genomic data. A bundle brings variants, annotations, evidence, provenance, and coverage information together so the data is accessible to compatible tools.

## Contributing

Contributor setup, development commands, architecture guidance, and genomic-data safety requirements are documented in [AGENTS.md](AGENTS.md).

## License

Offline Explorer is available under the [Apache License 2.0](LICENSE).

The Genome Computer name, logo, and sunflower mark are not licensed under Apache 2.0. See [TRADEMARKS.md](TRADEMARKS.md) for permitted use.

<p align="center">
  <a href="https://genome.computer">
    <img src="assets/genome-computer-sunflower.png" width="48" alt="Genome Computer sunflower">
  </a>
</p>

<p align="center">
  An open-source project from <a href="https://genome.computer"><strong>Genome Computer</strong></a>.
</p>
