# Genome Explorer

Genome Explorer is a private desktop application for browsing compatible `.genome` bundles. It runs deterministic local queries without uploading genomic data or requiring an account, API key, or AI service.

The application presents information already recorded in a bundle. It is a viewer and query engine, not a diagnostic or interpretation service.

Genome Explorer is developed by [Genome Computer](https://genome.computer), a company focused on making whole-genome data accessible and privately explorable. It reads `.genome` bundles, an open, self-describing format that packages variants, annotations, evidence, provenance, and coverage information into structured, queryable files. The public [`.genome` specification](https://github.com/genome-computer/genome-spec) defines the format and includes its schema, reference tools, and synthetic examples.

## What it includes

- A native Electron desktop application with bundle selection and local engine lifecycle management.
- A reusable local bundle library with validation, cached workspaces, friendly names, and recent-bundle handling.
- Search across genes, rsIDs, genomic coordinates, medications, conditions, traits, and reviewed topic terms.
- Clear result states for recorded findings, missing matches, analyses not included in the bundle, unavailable data, and non-callable positions.
- Dedicated views for personal results, medications, conditions, traits, clinical findings, pharmacogenomics, polygenic scores, research associations, and raw variants.
- An advanced region browser with genomic tracks, callability context, coverage information, and bounded pagination.
- Bundle-scoped saved results with notes and JSON or CSV export.

Contributor setup, verification commands, fixture requirements, architecture rules, and genomic-data safety guidance are documented in [AGENTS.md](AGENTS.md).
