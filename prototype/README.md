# Selective reader prototype

This throwaway prototype answers one question: can Offline Explorer fully
validate a compressed `.genome` bundle while storing only the JSON and Parquet
files needed for deterministic local search?

Run it with:

```sh
./prototype/run /path/to/sample.genome.tar.gz
```

Open the optional local browser interface from the CLI with:

```sh
./prototype/run /path/to/sample.genome.tar.gz --serve
```

Run the desktop application for development with:

```sh
npm install
npm run dev
```

The Electron application opens a welcome screen in its own window. Add genome
bundle opens a native file picker, then the same window shows local validation
and the private explorer. Closing the application also stops its bundled local
engine. The source archive is never modified or uploaded.

Create an unpacked desktop build with:

```sh
npm run package
```

The build includes its own Python genome engine and DuckDB dependency. Release
users do not need Python, Node.js, DuckDB, a terminal, an account, or an API key.

The interface leads with everyday medication, trait, and condition searches.
It restates only fields recorded in the bundle and keeps genomic identifiers,
coordinates, alleles, and other raw fields inside collapsed technical details.

Build a standalone command-line executable separately with:

```sh
./prototype/build cli
./dist/offline-explorer /path/to/sample.genome.tar.gz --serve
```

The prototype creates an ignored `.offline-explorer/` workspace. It never
modifies the source archive and does not make network requests after the first
prebuilt DuckDB package download.

The first open performs full manifest and hash validation and writes a local
validation receipt. Later opens reuse that workspace only while the archive's
path, size, modification time, device, and inode still match and retained file
sizes remain intact. Pass `--verify` to force full validation again.
