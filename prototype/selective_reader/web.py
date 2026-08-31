import base64
import sys
from pathlib import Path


# The topic library is a compact directory. It separates person-specific bundle
# fields from research context and never derives a new health interpretation.
PAGE = r'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="dark">
  <link rel="icon" href="data:,">
  <title>Offline Explorer</title>
  <style nonce="__NONCE__">
    :root {
      color-scheme: dark;
      --ink: #faf8f5;
      --muted: #c9c2bb;
      --muted-subtle: #948e88;
      --line: #3d3d3d;
      --surface: #202020;
      --surface-raised: #262626;
      --soft: #292929;
      --accent: #8fc8ad;
      --accent-dark: #b8dccb;
      --accent-soft: #22352c;
      --blue-soft: #202d34;
      --button: #faf8f5;
      --button-ink: #171717;
      --shadow: 0 18px 60px rgba(0, 0, 0, .24);
    }
    * { box-sizing: border-box; }
    [hidden] { display: none !important; }
    body {
      margin: 0;
      min-height: 100vh;
      color: var(--ink);
      background:
        radial-gradient(circle at 8% 0%, rgba(232, 193, 72, .06), transparent 30rem),
        #171717;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      -webkit-font-smoothing: antialiased;
    }
    button, input { font: inherit; }
    button { color: inherit; }
    .shell { width: min(1040px, calc(100% - 40px)); margin: 0 auto; padding: 26px 0 72px; }
    header { display: flex; align-items: center; justify-content: space-between; gap: 20px; }
    .brand { display: flex; align-items: center; gap: 11px; font-weight: 760; letter-spacing: -.02em; }
    .mark {
      width: 25px; height: 38px; flex: 0 0 auto; object-fit: contain;
      filter: drop-shadow(0 4px 10px rgba(0, 0, 0, .25));
    }
    .brand-copy { display: grid; gap: 2px; }
    .brand-name { font-size: 14px; line-height: 1.05; }
    .brand-byline { color: var(--muted); font-size: 9px; font-weight: 620; letter-spacing: .015em; line-height: 1.1; }
    .header-actions { display: flex; align-items: center; gap: 9px; }
    .quit-button {
      padding: 8px 11px; color: var(--muted); background: var(--surface);
      border: 1px solid var(--line); border-radius: 999px; font-size: 13px; font-weight: 680; cursor: pointer;
    }
    .quit-button:hover { color: var(--ink); background: var(--surface); }
    .quit-button:disabled { cursor: wait; opacity: .7; }
    main { padding-top: 64px; }
    .eyebrow {
      display: flex; align-items: center; gap: 8px; margin: 0 0 13px; color: var(--muted);
      font-size: 12px; font-weight: 620; letter-spacing: -.005em;
    }
    .eyebrow::before { content: ""; width: 6px; height: 6px; flex: 0 0 auto; background: var(--accent); border-radius: 999px; }
    h1 { max-width: 790px; margin: 0; font-size: clamp(40px, 5.2vw, 62px); line-height: 1.02; letter-spacing: -.052em; }
    .lede { max-width: 690px; margin: 20px 0 0; color: var(--muted); font-size: 18px; line-height: 1.6; }
    .welcome { padding-top: 78px; }
    .welcome h1 { max-width: 720px; }
    .open-card {
      display: grid; grid-template-columns: auto 1fr auto; align-items: center; gap: 20px;
      margin-top: 36px; padding: 22px; background: var(--surface); border: 1px solid var(--line);
      border-radius: 18px; box-shadow: var(--shadow);
    }
    .open-icon {
      width: 52px; height: 52px; display: grid; place-items: center; color: var(--accent);
      background: var(--accent-soft); border-radius: 15px;
    }
    .open-icon svg { width: 25px; height: 25px; }
    .open-copy h2 { margin: 0; font-size: 18px; letter-spacing: -.02em; }
    .open-copy p { margin: 6px 0 0; color: var(--muted); font-size: 14px; line-height: 1.5; }
    .choose-button {
      min-height: 48px; padding: 0 19px; color: var(--button-ink); background: var(--button); border: 0;
      border-radius: 12px; font-weight: 750; cursor: pointer;
    }
    .choose-button:hover { background: #e2ded8; }
    .choose-button:disabled { cursor: wait; opacity: .72; }
    .bundle-library { margin-top: 36px; }
    .library-head { display: flex; align-items: end; justify-content: space-between; gap: 20px; margin-bottom: 13px; }
    .library-head h2 { margin: 0; font-size: 22px; letter-spacing: -.03em; }
    .library-head p { margin: 0; color: var(--muted); font-size: 13px; }
    .bundle-list { display: grid; gap: 10px; }
    .bundle-item {
      display: grid; grid-template-columns: auto minmax(0, 1fr) auto; align-items: center; gap: 15px;
      padding: 17px; background: var(--surface); border: 1px solid var(--line); border-radius: 15px;
      box-shadow: 0 5px 20px rgba(0,0,0,.12);
    }
    .bundle-avatar {
      width: 42px; height: 42px; display: grid; place-items: center; color: var(--accent-dark);
      background: var(--accent-soft); border-radius: 12px; font-size: 15px; font-weight: 820; text-transform: uppercase;
    }
    .bundle-name { margin: 0; font-size: 17px; letter-spacing: -.015em; }
    .bundle-meta { margin: 5px 0 0; color: var(--muted); font-size: 12px; line-height: 1.45; overflow-wrap: anywhere; }
    .bundle-unavailable { color: #f0aaa6; }
    .bundle-actions { display: flex; align-items: center; gap: 8px; }
    .secondary-button, .text-button {
      min-height: 38px; padding: 0 13px; border-radius: 10px; font-size: 13px; font-weight: 720; cursor: pointer;
    }
    .secondary-button { color: var(--button-ink); background: var(--button); border: 1px solid var(--button); }
    .secondary-button:hover { background: #e2ded8; border-color: #e2ded8; }
    .text-button { color: var(--accent-dark); background: transparent; border: 1px solid var(--line); }
    .text-button:hover { background: var(--soft); }
    .secondary-button:disabled, .text-button:disabled { cursor: not-allowed; opacity: .5; }
    .nickname-form { display: flex; align-items: center; gap: 8px; margin-top: 9px; }
    .nickname-input {
      width: min(320px, 100%); min-height: 38px; padding: 8px 10px; color: var(--ink); background: var(--surface-raised);
      border: 1px solid var(--line); border-radius: 9px; outline: none;
    }
    .nickname-input:focus { border-color: var(--accent); box-shadow: 0 0 0 3px rgba(23,107,77,.10); }
    .nickname-error { margin: 7px 0 0; color: #f0aaa6; font-size: 12px; }
    .bundle-library:not([hidden]) + .selection-status { margin-top: 13px; }
    .bundle-library:not([hidden]) ~ .open-card { margin-top: 18px; box-shadow: none; }
    .selection-status {
      display: flex; align-items: flex-start; gap: 10px; margin: 13px 0 0; padding: 13px 15px;
      color: #c2d9e4; background: var(--blue-soft); border: 1px solid #344854; border-radius: 12px;
      font-size: 13px; line-height: 1.5;
    }
    .selection-status.error { color: #f2b0ac; background: #351f20; border-color: #653537; }
    .status-spinner {
      flex: 0 0 auto; width: 15px; height: 15px; margin-top: 2px;
      border: 2px solid rgba(23,107,77,.2); border-top-color: var(--accent); border-radius: 50%; animation: spin .7s linear infinite;
    }
    .trust-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin-top: 22px; }
    .trust-item { padding: 17px; background: var(--surface); border: 1px solid var(--line); border-radius: 13px; }
    .trust-item strong { display: block; font-size: 14px; }
    .trust-item span { display: block; margin-top: 5px; color: var(--muted); font-size: 12px; line-height: 1.45; }
    .search-panel {
      margin-top: 30px; padding: 10px; background: var(--surface); border: 1px solid var(--line);
      border-radius: 18px; box-shadow: var(--shadow); backdrop-filter: blur(14px);
    }
    form { display: flex; gap: 8px; }
    input[type="search"] {
      width: 100%; min-width: 0; padding: 17px 18px; color: var(--ink); background: transparent;
      border: 0; outline: none; font-size: 17px;
    }
    input[type="search"]::placeholder { color: var(--muted-subtle); }
    .search-button {
      flex: 0 0 auto; padding: 0 23px; color: var(--button-ink); background: var(--button); border: 0;
      border-radius: 12px; font-weight: 750; cursor: pointer; transition: background .15s, transform .15s;
    }
    .search-button:hover { background: #e2ded8; }
    .search-button:active { transform: translateY(1px); }
    .search-button:disabled { cursor: wait; opacity: .7; }
    .featured-searches { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; margin-top: 14px; }
    .featured-searches > span { margin-right: 2px; color: var(--muted); font-size: 13px; }
    .featured-search {
      padding: 8px 11px; color: var(--muted); background: var(--surface); border: 1px solid var(--line);
      border-radius: 999px; font-size: 13px; cursor: pointer;
    }
    .featured-search:hover { color: var(--accent-dark); border-color: #567665; background: var(--accent-soft); }
    .examples { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; margin-top: 14px; }
    .examples > span { margin-right: 2px; color: var(--muted); font-size: 13px; }
    .example {
      padding: 8px 11px; color: var(--muted); background: var(--surface); border: 1px solid var(--line);
      border-radius: 999px; font-size: 13px; cursor: pointer;
    }
    .example:hover { color: var(--accent-dark); border-color: #567665; background: var(--accent-soft); }
    .topic-library { margin-top: 58px; }
    .topic-library h2, .results h2 { margin: 0; font-size: 25px; letter-spacing: -.03em; }
    .topic-library-head { display: flex; align-items: end; justify-content: space-between; gap: 24px; }
    .topic-summary { flex: 0 0 auto; padding-bottom: 3px; color: var(--muted); font-size: 13px; }
    .topic-catalog { margin-top: 20px; }
    .topic-indicator { min-width: 0; text-align: right; }
    .topic-indicator-value { display: block; color: var(--accent-dark); font-size: 12px; font-weight: 780; }
    .topic-indicator.related .topic-indicator-value { color: #9cc6d9; }
    .topic-indicator.no-data .topic-indicator-value { color: var(--muted); font-weight: 680; }
    .topic-browser {
      display: grid; grid-template-columns: 210px minmax(0, 1fr); overflow: hidden;
      background: var(--surface); border: 1px solid var(--line); border-radius: 16px;
      box-shadow: 0 7px 26px rgba(0,0,0,.12);
    }
    .directory-main { min-width: 0; padding: 20px; }
    .directory-toolbar { display: grid; grid-template-columns: minmax(0, 1fr) minmax(190px, 260px); align-items: end; gap: 18px; margin-bottom: 20px; }
    .directory-title { margin: 0; font-size: 19px; letter-spacing: -.025em; }
    input.directory-filter {
      min-height: 43px; padding: 10px 13px; color: var(--ink); background: var(--surface-raised); border: 1px solid var(--line);
      border-radius: 11px; outline: none;
    }
    input.directory-filter:focus { border-color: var(--accent); box-shadow: 0 0 0 3px rgba(23,107,77,.1); }
    .directory-groups { display: grid; gap: 20px; }
    .directory-group-head { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin: 0 2px 8px; }
    .directory-group-head h4 { margin: 0; color: var(--muted); font-size: 11px; font-weight: 800; letter-spacing: .07em; text-transform: uppercase; }
    .directory-group-count { color: var(--muted); font-size: 10px; }
    .directory-list { overflow: hidden; border: 1px solid var(--line); border-radius: 11px; }
    .directory-row {
      display: grid; grid-template-columns: minmax(170px, 1fr) minmax(220px, auto) 22px;
      align-items: center; gap: 14px; width: 100%; padding: 13px 15px; color: inherit; background: transparent;
      border: 0; border-bottom: 1px solid var(--line); text-align: left; cursor: pointer;
    }
    .directory-row:last-child { border-bottom: 0; }
    .directory-row:hover { background: var(--soft); }
    .directory-name { font-size: 14px; font-weight: 730; }
    .directory-arrow { color: var(--accent); text-align: right; }
    .directory-empty { padding: 34px 24px; color: var(--muted); text-align: center; border: 1px dashed #555; border-radius: 11px; }
    .way-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; margin-top: 20px; }
    .way {
      display: flex; flex-direction: column; min-height: 210px; padding: 23px;
      background: var(--surface); border: 1px solid var(--line); border-radius: 16px;
      box-shadow: 0 6px 24px rgba(0,0,0,.12);
    }
    .way-icon {
      width: 38px; height: 38px; display: grid; place-items: center; margin-bottom: 20px;
      color: var(--accent); background: var(--accent-soft); border-radius: 11px; font-size: 19px;
    }
    .way h3 { margin: 0; font-size: 18px; letter-spacing: -.02em; }
    .way p { margin: 9px 0 20px; color: var(--muted); font-size: 14px; line-height: 1.55; }
    .way .example { align-self: flex-start; margin-top: auto; background: var(--surface); }
    .secondary-tools { display: grid; grid-template-columns: 1.2fr .8fr; gap: 12px; margin-top: 12px; }
    .disclosure {
      background: var(--surface); border: 1px solid var(--line); border-radius: 14px;
    }
    .disclosure summary {
      display: flex; align-items: center; justify-content: space-between; gap: 20px; padding: 17px 19px;
      list-style: none; font-size: 14px; font-weight: 720; cursor: pointer;
    }
    .disclosure summary::-webkit-details-marker { display: none; }
    .disclosure summary::after { content: "+"; color: var(--muted); font-size: 20px; font-weight: 400; }
    .disclosure[open] summary::after { content: "−"; }
    .disclosure-body { padding: 0 19px 19px; color: var(--muted); font-size: 14px; line-height: 1.55; }
    .disclosure-body p { margin: 0 0 13px; }
    .technical-examples { margin: 0; }
    .results { margin-top: 58px; scroll-margin-top: 28px; }
    .results[hidden] { display: none; }
    .results-head { display: flex; align-items: end; justify-content: space-between; gap: 20px; margin-bottom: 18px; }
    .result-meta { color: var(--muted); font-size: 13px; }
    .notice {
      display: flex; gap: 10px; align-items: flex-start; margin-bottom: 20px; padding: 13px 15px;
      color: #c2d9e4; background: var(--blue-soft); border: 1px solid #344854; border-radius: 12px; font-size: 13px; line-height: 1.5;
    }
    .notice[data-state="not_callable"],
    .notice[data-state="analysis_not_included"],
    .notice[data-state="unsupported_bundle_version"],
    .notice[data-state="insufficient_bundle_data"] {
      color: #e2cfaa; background: #30291d; border-color: #5b4c2d;
    }
    .notice svg { flex: 0 0 auto; margin-top: 1px; }
    .section { margin-top: 30px; }
    .section-title { display: flex; align-items: center; gap: 10px; margin-bottom: 11px; color: var(--muted); font-size: 13px; font-weight: 790; letter-spacing: .06em; text-transform: uppercase; }
    .count { padding: 3px 7px; color: var(--accent-dark); background: var(--accent-soft); border-radius: 999px; font-size: 11px; }
    .cards { display: grid; gap: 11px; }
    .section-variants .cards, .section-trait_variants .cards { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .record-list { overflow: hidden; background: var(--surface); border: 1px solid var(--line); border-radius: 13px; }
    .record-list-head, .record-row-summary {
      display: grid; align-items: center; gap: 14px; padding: 0 15px;
    }
    .record-layout-trait_variants .record-list-head, .record-layout-trait_variants .record-row-summary {
      grid-template-columns: minmax(100px, .85fr) minmax(82px, .65fr) minmax(90px, .8fr) minmax(210px, 1.7fr) minmax(90px, .72fr) minmax(76px, auto);
    }
    .record-layout-variants .record-list-head, .record-layout-variants .record-row-summary {
      grid-template-columns: minmax(130px, 1.2fr) minmax(90px, .7fr) minmax(100px, .9fr) minmax(105px, .75fr) minmax(76px, auto);
    }
    .record-layout-gwas .record-list-head, .record-layout-gwas .record-row-summary {
      grid-template-columns: minmax(220px, 1.8fr) minmax(110px, .75fr) minmax(120px, 1fr) minmax(105px, .72fr) minmax(76px, auto);
    }
    .record-list-head {
      min-height: 39px; color: var(--muted); background: var(--soft); border-bottom: 1px solid var(--line);
      font-size: 9px; font-weight: 800; letter-spacing: .07em; text-transform: uppercase;
    }
    .record-row { border-bottom: 1px solid var(--line); }
    .record-row:last-child { border-bottom: 0; }
    .record-row-summary {
      min-height: 54px; padding-top: 9px; padding-bottom: 9px; list-style: none; cursor: pointer;
    }
    .record-row-summary::-webkit-details-marker { display: none; }
    .record-row-summary:hover { background: var(--soft); }
    .record-row[open] > .record-row-summary { background: var(--soft); border-bottom: 1px solid var(--line); }
    .record-row-cell { min-width: 0; color: var(--muted); font-size: 12px; line-height: 1.35; overflow-wrap: anywhere; }
    .record-row-value { display: -webkit-box; overflow: hidden; -webkit-box-orient: vertical; -webkit-line-clamp: 2; }
    .record-row-primary { color: var(--ink); font-size: 13px; font-weight: 760; }
    .record-row-primary .record-row-value { -webkit-line-clamp: 1; }
    .record-row-arrow { color: var(--accent); font-size: 17px; text-align: center; transition: transform .15s ease; }
    .record-row[open] .record-row-arrow { transform: rotate(90deg); }
    .record-row-details { padding: 16px 15px 18px; background: #1b1b1b; }
    .record-row-fields { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px 20px; margin: 0; }
    .result-disclosure {
      overflow: hidden; background: var(--surface); border: 1px solid var(--line); border-radius: 14px;
    }
    .result-disclosure > summary {
      display: flex; align-items: center; justify-content: space-between; gap: 20px; padding: 17px 19px;
      list-style: none; cursor: pointer;
    }
    .result-disclosure > summary::-webkit-details-marker { display: none; }
    .result-disclosure > summary::after { content: "Show"; color: var(--accent); font-size: 12px; font-weight: 750; }
    .result-disclosure[open] > summary::after { content: "Hide"; }
    .result-disclosure .section-title { margin: 0; }
    .result-disclosure > .cards { padding: 0 14px 14px; }
    .result-disclosure > .paginated-results { padding: 0 14px 14px; }
    .result-pagination {
      display: flex; align-items: center; justify-content: space-between; gap: 14px; margin-top: 12px;
      padding-top: 12px; border-top: 1px solid var(--line);
    }
    .pagination-range { color: var(--muted); font-size: 12px; }
    .pagination-actions { display: flex; gap: 7px; }
    .pagination-button {
      min-height: 36px; padding: 0 12px; color: var(--accent-dark); background: var(--surface);
      border: 1px solid var(--line); border-radius: 9px; font-size: 12px; font-weight: 720; cursor: pointer;
    }
    .pagination-button:hover:not(:disabled) { border-color: #567665; background: var(--accent-soft); }
    .pagination-button:disabled { color: var(--muted-subtle); cursor: default; opacity: .7; }
    .card { padding: 23px; background: var(--surface); border: 1px solid var(--line); border-radius: 16px; box-shadow: 0 5px 20px rgba(0,0,0,.12); }
    .record-type { margin-bottom: 8px; color: var(--accent); font-size: 10px; font-weight: 800; letter-spacing: .09em; text-transform: uppercase; }
    .card-top { display: flex; align-items: flex-start; justify-content: space-between; gap: 18px; }
    .card-heading { min-width: 0; }
    .card h3 { margin: 0; font-size: 20px; letter-spacing: -.025em; }
    .card-id { padding-top: 3px; color: var(--muted); font-size: 12px; }
    .recorded-summary { margin: 12px 0 0; color: #ded9d3; font-size: 15px; line-height: 1.55; }
    .meaning-note {
      margin: 16px 0 0; padding: 12px 14px; color: var(--muted); background: var(--soft);
      border-left: 3px solid #567665; border-radius: 0 10px 10px 0; font-size: 13px; line-height: 1.5;
    }
    .personal-data {
      margin-top: 20px; padding: 18px; background: var(--accent-soft); border: 1px solid #365445; border-radius: 13px;
    }
    .data-group-label { margin: 0; color: var(--accent-dark); font-size: 10px; font-weight: 820; letter-spacing: .09em; text-transform: uppercase; }
    .data-group-copy { margin: 7px 0 0; color: #ded9d3; font-size: 13px; line-height: 1.5; }
    .personal-data .simple-fields { margin-top: 16px; }
    .reference-context { margin-top: 20px; padding-top: 18px; border-top: 1px solid var(--line); }
    .reference-context .data-group-label { color: var(--muted); }
    .reference-context .simple-fields { margin-top: 15px; }
    .simple-fields { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 15px 22px; margin: 20px 0 0; }
    .field dt { margin-bottom: 5px; color: var(--muted); font-size: 10px; font-weight: 760; letter-spacing: .07em; text-transform: uppercase; }
    .field dd { margin: 0; overflow-wrap: anywhere; font-size: 14px; line-height: 1.45; }
    .field a { color: var(--accent); font-weight: 680; text-decoration-thickness: 1px; text-underline-offset: 3px; }
    .reference-links { display: flex; flex-wrap: wrap; gap: 5px 12px; }
    .source-link { display: inline-flex; margin-top: 18px; color: var(--accent); font-size: 13px; font-weight: 720; text-underline-offset: 3px; }
    .clinical-conflict { margin-top: 16px; padding: 10px 12px; color: #e3c889; background: #332918; border: 1px solid #624b20; border-radius: 10px; font-size: 13px; font-weight: 680; }
    .clinical-sources { display: grid; gap: 8px; margin-top: 19px; padding-top: 16px; border-top: 1px solid var(--line); }
    .clinical-source { display: flex; align-items: baseline; flex-wrap: wrap; gap: 5px 10px; font-size: 12px; }
    .clinical-source .source-link { margin-top: 0; }
    .clinical-source strong { font-size: 13px; }
    .clinical-source span { color: var(--muted); }
    .technical-details { margin-top: 19px; padding-top: 16px; border-top: 1px solid var(--line); }
    .technical-details summary { color: var(--muted); font-size: 13px; font-weight: 680; cursor: pointer; }
    .technical-fields { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 15px 20px; margin: 17px 0 0; }
    .save-result-button {
      flex: 0 0 auto; min-height: 31px; padding: 0 10px; color: var(--accent-dark); background: var(--surface-raised);
      border: 1px solid var(--line); border-radius: 7px; font-size: 11px; font-weight: 740; cursor: pointer;
    }
    .save-result-button:hover { background: var(--accent-soft); }
    .save-result-button[aria-pressed="true"] { color: var(--button-ink); background: var(--button); border-color: var(--button); }
    .save-result-button:disabled { cursor: wait; opacity: .65; }
    .record-row-actions { display: flex; align-items: center; justify-content: flex-end; gap: 8px; }
    .record-row-actions .save-result-button { min-width: 53px; }
    .saved-results-head { display: flex; align-items: end; justify-content: space-between; gap: 24px; }
    .saved-export-actions { display: flex; gap: 8px; padding-bottom: 3px; }
    .saved-export-actions button { min-height: 36px; }
    .saved-feedback { min-height: 20px; margin: 10px 0 0; color: var(--muted); font-size: 12px; text-align: right; }
    .saved-result-list { margin-top: 18px; overflow: hidden; background: var(--surface); border: 1px solid var(--line); border-radius: 7px; }
    .saved-result-row { border-bottom: 1px solid var(--line); }
    .saved-result-row:last-child { border-bottom: 0; }
    .saved-result-row > summary {
      display: grid; grid-template-columns: minmax(0, 1fr) minmax(150px, auto) 16px; align-items: center;
      gap: 16px; min-height: 58px; padding: 10px 16px; list-style: none; cursor: pointer;
    }
    .saved-result-row > summary::-webkit-details-marker { display: none; }
    .saved-result-row > summary:hover, .saved-result-row[open] > summary { background: var(--soft); }
    .saved-result-title { min-width: 0; font-size: 14px; font-weight: 760; overflow-wrap: anywhere; }
    .saved-result-kind { color: var(--muted); font-size: 11px; text-align: right; }
    .saved-result-arrow { color: var(--accent); font-size: 17px; transition: transform .15s ease; }
    .saved-result-row[open] .saved-result-arrow { transform: rotate(90deg); }
    .saved-result-details { padding: 17px 16px 19px; background: #1b1b1b; border-top: 1px solid var(--line); }
    .saved-result-context { margin: 0 0 15px; color: var(--muted); font-size: 11px; }
    .saved-result-actions { display: flex; justify-content: flex-end; margin-top: 18px; padding-top: 14px; border-top: 1px solid var(--line); }
    .saved-empty { margin-top: 18px; }
    .genome-map-head { display: flex; align-items: end; justify-content: space-between; gap: 24px; }
    .map-build { padding-bottom: 5px; color: var(--muted); font-size: 12px; }
    .map-summary-strip {
      display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); margin-top: 24px;
      background: var(--surface); border-top: 1px solid var(--line); border-bottom: 1px solid var(--line);
    }
    .map-stat { min-width: 0; padding: 15px 17px; }
    .map-stat + .map-stat { border-left: 1px solid var(--line); }
    .map-stat span { display: block; color: var(--muted); font-size: 9px; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }
    .map-stat strong { display: block; margin-top: 5px; font-size: 14px; font-weight: 760; }
    .map-table-wrap { overflow-x: auto; padding-bottom: 10px; }
    .map-table { width: 100%; border-collapse: collapse; background: var(--surface); font-size: 12px; }
    .map-table th, .map-table td { padding: 10px 12px; border-bottom: 1px solid var(--line); text-align: left; }
    .map-table th { color: var(--muted); font-size: 9px; letter-spacing: .06em; text-transform: uppercase; }
    .region-browser-head { display: flex; align-items: end; justify-content: space-between; gap: 24px; }
    .region-search {
      display: flex; gap: 7px; margin-top: 24px; padding: 6px; background: var(--surface);
      border: 1px solid var(--line); border-radius: 8px;
    }
    .region-search input { flex: 1; min-width: 0; border: 0; outline: 0; background: transparent; }
    .region-examples { display: flex; align-items: center; flex-wrap: wrap; gap: 7px; margin-top: 10px; color: var(--muted); font-size: 11px; }
    .region-examples button {
      padding: 5px 8px; color: var(--accent-dark); background: transparent; border: 1px solid var(--line);
      border-radius: 999px; font-size: 11px; cursor: pointer;
    }
    .region-examples button:hover { background: var(--accent-soft); }
    .region-browser-status { margin-top: 25px; }
    .region-browser-workspace { margin-top: 28px; }
    .region-toolbar { display: flex; align-items: end; justify-content: space-between; gap: 24px; }
    .region-toolbar h2 { margin: 0; font-size: 22px; }
    .region-coordinate { margin: 5px 0 0; color: var(--muted); font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; }
    .region-controls { display: flex; gap: 6px; }
    .region-controls button {
      min-height: 34px; padding: 0 10px; color: var(--accent-dark); background: var(--surface); border: 1px solid var(--line);
      border-radius: 5px; font-size: 11px; font-weight: 720; cursor: pointer;
    }
    .region-controls button:hover:not(:disabled) { background: var(--accent-soft); }
    .region-controls button:disabled { cursor: default; opacity: .45; }
    .region-ruler {
      position: relative; display: flex; justify-content: space-between; min-height: 38px; margin: 20px 0 0 174px;
      color: var(--muted); border-top: 1px solid #5a5a5a; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 9px;
    }
    .region-ruler-tick { position: relative; padding-top: 8px; transform: translateX(-50%); }
    .region-ruler-tick::before { content: ""; position: absolute; top: -1px; left: 50%; width: 1px; height: 5px; background: #5a5a5a; }
    .region-ruler-tick:first-child { transform: none; }
    .region-ruler-tick:first-child::before { left: 0; }
    .region-ruler-tick:last-child { transform: translateX(0); }
    .region-ruler-tick:last-child::before { left: 100%; }
    .region-tracks { overflow: hidden; background: var(--surface); border-top: 1px solid var(--line); border-bottom: 1px solid var(--line); }
    .region-track-row { display: grid; grid-template-columns: 160px minmax(0, 1fr); gap: 14px; min-height: 68px; padding: 10px 14px; border-bottom: 1px solid var(--line); }
    .region-track-row:last-child { border-bottom: 0; }
    .region-track-label { padding-top: 4px; }
    .region-track-label strong { display: block; font-size: 11px; }
    .region-track-label span { display: block; margin-top: 5px; color: var(--muted); font-size: 9px; line-height: 1.35; }
    .region-track { position: relative; align-self: center; height: 42px; overflow: hidden; background: linear-gradient(to bottom, transparent 20px, #444 20px, #444 21px, transparent 21px); }
    .region-gene-feature {
      position: absolute; top: 13px; min-width: 3px; height: 16px; padding: 1px 5px; overflow: hidden;
      color: #d8eee3; background: #2a5a43; border: 1px solid #52866c; border-radius: 3px;
      font-size: 8px; font-weight: 760; white-space: nowrap; text-overflow: ellipsis; cursor: pointer;
    }
    .region-annotation-point {
      position: absolute; top: 11px; width: 9px; height: 20px; margin-left: -4px; padding: 0;
      background: #dc914d; border: 2px solid var(--surface); border-radius: 999px; box-shadow: 0 0 0 1px #f0b06f; cursor: pointer;
    }
    .region-density-track, .region-callability-track { display: flex; align-items: flex-end; gap: 1px; padding: 4px 0; background: none; }
    .region-variant-bin { flex: 1 1 0; min-width: 1px; height: calc(var(--height) * 30px); min-height: 1px; padding: 0; background: #368365; border: 0; border-radius: 1px 1px 0 0; cursor: pointer; }
    .region-variant-bin:disabled { cursor: default; opacity: .2; }
    .region-variant-bin:hover:not(:disabled), .region-variant-bin:focus-visible { outline: 2px solid var(--accent-dark); outline-offset: -2px; }
    .region-callability-bin { flex: 1 1 0; min-width: 1px; height: 12px; background: rgba(95,145,173,var(--coverage)); border-radius: 1px; }
    .region-callability-bin.site-bin { height: calc(var(--height) * 22px); min-height: 1px; background: #6e9db7; }
    .region-track-empty { display: flex; align-items: center; height: 100%; color: var(--muted); font-size: 10px; }
    .region-track-note { margin: 10px 0 0 174px; color: var(--muted); font-size: 10px; }
    .region-records { margin-top: 28px; padding-top: 20px; border-top: 1px solid var(--line); }
    .region-records-head { display: flex; align-items: baseline; justify-content: space-between; gap: 20px; margin-bottom: 12px; }
    .region-records-head h2 { margin: 0; font-size: 17px; }
    .region-records-head span { color: var(--muted); font-size: 11px; }
    .coverage-explanation { margin: 15px 0; color: var(--muted); font-size: 12px; }
    .coverage-table-wrap { padding: 0; border: 1px solid var(--line); border-radius: 7px; }
    .coverage-table-wrap .map-table tr:last-child td { border-bottom: 0; }
    .empty { padding: 38px; text-align: center; color: var(--muted); background: var(--surface); border: 1px dashed #555; border-radius: 14px; }
    .error { color: #f2b0ac; background: #351f20; border-color: #653537; }
    .spinner { display: inline-block; width: 15px; height: 15px; margin-right: 7px; vertical-align: -2px; border: 2px solid rgba(23,23,23,.4); border-top-color: var(--button-ink); border-radius: 50%; animation: spin .7s linear infinite; }
    @keyframes spin { to { transform: rotate(360deg); } }
    @media (max-width: 760px) {
      .shell { width: min(100% - 24px, 1040px); padding-top: 18px; }
      main { padding-top: 48px; }
      .way-grid, .secondary-tools { grid-template-columns: 1fr; }
      .way { min-height: 0; }
      .topic-library-head { align-items: flex-start; flex-direction: column; gap: 8px; }
      .topic-browser { grid-template-columns: 1fr; }
      .directory-toolbar { grid-template-columns: 1fr; }
      .section-variants .cards, .section-trait_variants .cards { grid-template-columns: 1fr; }
      .record-list-head { display: none; }
      .record-row-summary, .record-layout-trait_variants .record-row-summary,
      .record-layout-variants .record-row-summary, .record-layout-gwas .record-row-summary {
        grid-template-columns: minmax(0, 1fr) auto; gap: 7px 14px; padding-top: 13px; padding-bottom: 13px;
      }
      .record-row-cell { grid-column: 1; display: grid; grid-template-columns: 105px minmax(0, 1fr); gap: 10px; }
      .record-row-cell::before {
        content: attr(data-label); color: var(--muted); font-size: 9px; font-weight: 800; letter-spacing: .06em; text-transform: uppercase;
      }
      .record-row-primary { display: block; font-size: 14px; }
      .record-row-primary::before { content: none; }
      .record-row-arrow { grid-column: 2; grid-row: 1; }
      .record-row-actions { grid-column: 2; grid-row: 1; align-self: start; }
      .record-row-fields { grid-template-columns: 1fr 1fr; }
      .technical-fields { grid-template-columns: 1fr 1fr; }
      .open-card { grid-template-columns: auto 1fr; }
      .choose-button { grid-column: 1 / -1; }
      .trust-grid { grid-template-columns: 1fr; }
      .bundle-item { grid-template-columns: auto minmax(0, 1fr); }
      .bundle-actions { grid-column: 1 / -1; justify-content: flex-end; }
      .region-toolbar { align-items: flex-start; flex-direction: column; gap: 13px; }
      .region-ruler { margin-left: 0; }
      .region-track-row { grid-template-columns: 1fr; gap: 5px; }
      .region-track-label { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
      .region-track-label span { margin-top: 0; text-align: right; }
      .region-track-note { margin-left: 0; }
    }
    @media (max-width: 480px) {
      h1 { font-size: 40px; }
      .lede { font-size: 16px; }
      .search-panel { padding: 7px; }
      input[type="search"] { padding: 14px 12px; font-size: 15px; }
      .search-button { padding: 0 13px; font-size: 14px; }
      .simple-fields, .technical-fields, .record-row-fields { grid-template-columns: 1fr; }
      .record-row-cell { grid-template-columns: 90px minmax(0, 1fr); }
      .results-head { align-items: flex-start; flex-direction: column; gap: 5px; }
      .saved-results-head { align-items: flex-start; flex-direction: column; gap: 14px; }
      .saved-export-actions { width: 100%; }
      .saved-export-actions button { flex: 1; }
      .saved-feedback { text-align: left; }
      .saved-result-row > summary { grid-template-columns: minmax(0, 1fr) 16px; gap: 8px; }
      .saved-result-kind { grid-column: 1; grid-row: 2; text-align: left; }
      .saved-result-arrow { grid-column: 2; grid-row: 1; }
      .map-summary-strip { grid-template-columns: 1fr; }
      .map-stat + .map-stat { border-top: 1px solid var(--line); border-left: 0; }
      .chromosome-row { grid-template-columns: 30px minmax(170px, 1fr); gap: 9px; padding: 8px 10px; }
      .chromosome-count { grid-column: 2; text-align: left; }
      .welcome { padding-top: 52px; }
      .open-card { grid-template-columns: 1fr; }
      .open-icon { width: 46px; height: 46px; }
      .library-head { align-items: flex-start; flex-direction: column; gap: 5px; }
      .bundle-item { grid-template-columns: 1fr; }
      .bundle-avatar { width: 38px; height: 38px; }
      .bundle-actions { grid-column: auto; justify-content: stretch; }
      .bundle-actions button { flex: 1; }
      .nickname-form { align-items: stretch; flex-direction: column; }
      .nickname-input { width: 100%; }
      .directory-row { grid-template-columns: minmax(0, 1fr) 22px; gap: 8px; }
      .directory-row .topic-indicator { grid-column: 1 / -1; grid-row: 2; text-align: left; }
      .directory-arrow { grid-column: 2; grid-row: 1; }
      .region-search { align-items: stretch; flex-direction: column; }
      .region-search .search-button { min-height: 42px; }
      .region-controls { width: 100%; }
      .region-controls button { flex: 1; padding: 0 6px; }
      .region-records-head { align-items: flex-start; flex-direction: column; gap: 4px; }
    }

    /* Workbench layout. */
    body { background: #171717; }
    .shell {
      display: grid; grid-template-columns: 236px minmax(0, 1fr); width: 100%; min-height: 100vh; margin: 0; padding: 0;
    }
    header {
      position: sticky; top: 0; align-self: start; display: flex; flex-direction: column; align-items: stretch;
      justify-content: flex-start; height: 100vh; padding: 25px 18px 22px; color: var(--ink); background: #111111;
      border-right: 1px solid #303030;
    }
    .brand { align-items: flex-start; line-height: 1.15; }
    .mark { flex: 0 0 auto; }
    .sidebar-context { display: flex; min-height: 0; flex: 1; flex-direction: column; margin-top: 38px; }
    .sidebar-bundle { margin-top: auto; padding: 18px 9px 0; border-top: 1px solid var(--line); }
    .sidebar-label {
      margin: 0 0 9px; color: var(--muted-subtle); font-size: 9px; font-weight: 800; letter-spacing: .1em; text-transform: uppercase;
    }
    .sidebar-bundle-name { display: block; color: var(--ink); font-size: 15px; font-weight: 760; line-height: 1.3; overflow-wrap: anywhere; }
    .sidebar-bundle-status { display: block; margin-top: 7px; color: var(--accent); font-size: 10px; font-weight: 720; }
    .sidebar-bundle-meta { display: block; margin-top: 6px; color: var(--muted); font-size: 11px; line-height: 1.45; }
    .sidebar-bundle-link {
      margin-top: 11px; padding: 0; color: var(--muted); background: transparent; border: 0;
      font-size: 11px; font-weight: 720; text-align: left; cursor: pointer;
    }
    .sidebar-bundle-link:hover, .sidebar-bundle-link.is-active { color: var(--ink); text-decoration: underline; text-underline-offset: 3px; }
    .sidebar-nav { display: grid; gap: 3px; margin-top: 23px; }
    .sidebar-view-list { display: grid; gap: 3px; }
    .sidebar-nav .sidebar-label { margin: 0 9px 7px; }
    .sidebar-nav .sidebar-advanced-label {
      margin-top: 15px; padding-top: 17px; border-top: 1px solid var(--line);
    }
    .sidebar-nav-button {
      display: grid; grid-template-columns: 22px minmax(0, 1fr) auto; align-items: center; gap: 7px; width: 100%;
      min-height: 38px; padding: 0 9px; color: var(--muted); background: transparent; border: 0; border-radius: 5px;
      font-size: 12px; font-weight: 680; text-align: left; cursor: pointer;
    }
    .sidebar-nav-button:hover { color: var(--ink); background: #202020; }
    .sidebar-nav-button[aria-selected="true"], .sidebar-nav-button.is-active { color: var(--button-ink); background: var(--button); }
    .sidebar-nav-index { color: var(--muted-subtle); font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 9px; }
    .sidebar-nav-button[aria-selected="true"] .sidebar-nav-index, .sidebar-nav-button.is-active .sidebar-nav-index { color: #66615c; }
    .sidebar-nav-count { color: var(--muted-subtle); font-size: 9px; font-weight: 760; }
    .sidebar-nav-button[aria-selected="true"] .sidebar-nav-count, .sidebar-nav-button.is-active .sidebar-nav-count { color: #66615c; }
    .header-actions { align-items: stretch; flex-direction: column; width: 100%; margin-top: 13px; }
    .quit-button {
      width: 100%; color: var(--muted); background: #1b1b1b; border-color: var(--line); border-radius: 6px;
    }
    .quit-button:hover { color: var(--ink); background: #262626; }
    main { grid-column: 2; width: min(1080px, calc(100% - 64px)); margin: 0 auto; padding: 44px 0 72px; }
    .welcome { padding-top: 74px; }
    #explorer h1 { max-width: none; font-size: clamp(34px, 4vw, 48px); letter-spacing: -.045em; }
    #explorer .lede { margin-top: 9px; font-size: 15px; }
    #explorer .eyebrow { margin-bottom: 9px; }
    .workspace-view.topic-library, .workspace-view.results, .workspace-view.saved-results, .workspace-view.region-browser-view, .workspace-view.coverage-view { margin-top: 0; }
    #explorer .topic-library h1 { font-size: clamp(34px, 4vw, 44px); }
    #explorer .results h1 { font-size: clamp(30px, 3.2vw, 40px); }
    .workspace-back {
      margin: 0 0 23px; padding: 0; color: var(--accent-dark); background: transparent; border: 0;
      font-size: 13px; font-weight: 740; cursor: pointer;
    }
    .workspace-back:hover { text-decoration: underline; text-underline-offset: 3px; }
    .search-panel {
      margin-top: 23px; padding: 6px; background: var(--surface); border-color: var(--line); border-radius: 8px; box-shadow: none; backdrop-filter: none;
    }
    .search-button { border-radius: 5px; }
    .featured-search, .example { border-radius: 5px; }
    .secondary-tools { grid-template-columns: 1fr; margin-top: 18px; }
    .disclosure, .topic-browser, .record-list, .result-disclosure, .card, .open-card, .bundle-item, .trust-item, .saved-result-list, .chromosome-map {
      border-radius: 7px; box-shadow: none;
    }
    .topic-browser { display: block; background: var(--surface); }
    .directory-main { padding: 22px; }
    .directory-toolbar { display: flex; justify-content: flex-end; }

    @media (max-width: 980px) {
      .shell { grid-template-columns: 200px minmax(0, 1fr); }
      main { width: min(100% - 36px, 1080px); }
    }
    @media (max-width: 760px) {
      .shell { display: block; }
      header { position: static; height: auto; padding: 18px 16px; }
      .brand { align-items: center; }
      .sidebar-context { margin-top: 22px; }
      .sidebar-bundle { margin-top: 18px; padding-left: 0; padding-right: 0; }
      .sidebar-nav { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .sidebar-nav .sidebar-label { grid-column: 1 / -1; margin-left: 0; }
      .sidebar-view-list { display: contents; }
      .header-actions { margin-top: 14px; }
      main { width: min(100% - 24px, 1080px); padding-top: 48px; }
    }
  </style>
</head>
<body>
  <div class="shell">
    <header>
      <div class="brand">
        <img class="mark" src="__SUNFLOWER_DATA_URI__" alt="">
        <span class="brand-copy">
          <span class="brand-name">Offline Explorer</span>
          <span class="brand-byline">by Genome Computer</span>
        </span>
      </div>
      <div class="sidebar-context" id="sidebar-context" hidden>
        <nav class="sidebar-nav" aria-label="Explore this bundle">
          <p class="sidebar-label">Browse</p>
          <button class="sidebar-nav-button" id="sidebar-search" type="button">
            <span class="sidebar-nav-index">01</span><span>Genome search</span>
          </button>
          <div class="sidebar-view-list" role="tablist" aria-label="Topic views">
            <button class="sidebar-nav-button" type="button" role="tab" aria-controls="topic-catalog" data-sidebar-view="personal">
              <span class="sidebar-nav-index">02</span><span>Personal results</span><span class="sidebar-nav-count"></span>
            </button>
            <button class="sidebar-nav-button" type="button" role="tab" aria-controls="topic-catalog" data-sidebar-view="medications">
              <span class="sidebar-nav-index">03</span><span>Medications</span><span class="sidebar-nav-count"></span>
            </button>
            <button class="sidebar-nav-button" type="button" role="tab" aria-controls="topic-catalog" data-sidebar-view="conditions">
              <span class="sidebar-nav-index">04</span><span>Conditions</span><span class="sidebar-nav-count"></span>
            </button>
            <button class="sidebar-nav-button" type="button" role="tab" aria-controls="topic-catalog" data-sidebar-view="traits">
              <span class="sidebar-nav-index">05</span><span>Traits</span><span class="sidebar-nav-count"></span>
            </button>
          </div>
          <button class="sidebar-nav-button" id="sidebar-saved" type="button">
            <span class="sidebar-nav-index">06</span><span>Saved results</span><span class="sidebar-nav-count" id="sidebar-saved-count">0</span>
          </button>
          <p class="sidebar-label sidebar-advanced-label">Advanced tools</p>
          <button class="sidebar-nav-button" id="sidebar-map" type="button">
            <span class="sidebar-nav-index">07</span><span>Region browser</span>
          </button>
        </nav>
        <div class="sidebar-bundle">
          <p class="sidebar-label">Bundle details</p>
          <strong class="sidebar-bundle-name" id="sidebar-bundle-name">Genome bundle</strong>
          <span class="sidebar-bundle-status" id="validation">Verified</span>
          <span class="sidebar-bundle-meta">Genome spec <span id="spec-version">Loading</span> · <span id="build">Loading</span></span>
          <span class="sidebar-bundle-meta"><span id="snapshot">Loading</span> · <span id="stored">Loading</span> local data</span>
          <button class="sidebar-bundle-link" id="sidebar-coverage" type="button">Coverage &amp; quality</button>
        </div>
      </div>
      <div class="header-actions">
        <button class="quit-button" id="bundles-button" type="button" hidden>Manage bundles</button>
        <button class="quit-button" id="quit-button" type="button">Quit</button>
      </div>
    </header>

    <main class="welcome" id="welcome">
      <h1 id="welcome-title">Explore your genome bundle privately.</h1>
      <p class="lede" id="welcome-lede">Choose a compatible bundle to get started. It stays on this computer and is never uploaded.</p>

      <section class="bundle-library" id="bundle-library" aria-labelledby="library-title" hidden>
        <div class="library-head">
          <h2 id="library-title">Your bundles</h2>
          <p>Saved on this computer</p>
        </div>
        <div class="bundle-list" id="bundle-list"></div>
      </section>

      <div class="selection-status" id="selection-status" hidden aria-live="polite">
        <span class="status-spinner" id="status-spinner" aria-hidden="true"></span>
        <span id="selection-message"></span>
      </div>

      <section class="open-card" aria-labelledby="open-title">
        <div class="open-icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 7.5h5l1.6 2H20v8.5a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V7.5Z"/><path d="M4 8V6a2 2 0 0 1 2-2h3l1.6 2H18a2 2 0 0 1 2 2v1.5"/></svg>
        </div>
        <div class="open-copy">
          <h2 id="open-title">Add a genome bundle</h2>
          <p>Select a compatible genome bundle from this computer. The original file will not be changed.</p>
        </div>
        <button class="choose-button" id="choose-button" type="button">Add genome bundle</button>
      </section>

      <div class="trust-grid" aria-label="Privacy information">
        <div class="trust-item"><strong>Stays local</strong><span>The bundle is read only on this computer.</span></div>
        <div class="trust-item"><strong>No account or AI</strong><span>No sign-in, API key, or AI connection is required.</span></div>
        <div class="trust-item"><strong>No upload</strong><span>Explorer never copies the source bundle, and the app does not send it over the network.</span></div>
      </div>
    </main>

    <main id="explorer" hidden>
      <section class="workspace-view explorer-intro" id="view-search">
        <p class="eyebrow">Exploring <span id="active-bundle-name">your genome bundle</span></p>
        <h1>What would you like to explore?</h1>
        <p class="lede">Search this bundle by topic, medication, gene, or variant.</p>

        <div class="search-panel">
          <form id="search-form">
            <input id="search-input" type="search" aria-label="Search your genome bundle" autocomplete="off" spellcheck="false" placeholder="Try a medication, trait, condition, or gene" autofocus>
            <button class="search-button" id="search-button" type="submit">Search</button>
          </form>
        </div>
        <div class="featured-searches" aria-label="Popular searches">
          <span>Popular searches</span>
          <button class="featured-search" type="button" data-query="MTHFR">MTHFR</button>
          <button class="featured-search" type="button" data-query="Ehlers-Danlos">Ehlers-Danlos syndrome</button>
          <button class="featured-search" type="button" data-query="Parkinson">Parkinson's disease</button>
          <button class="featured-search" type="button" data-query="primary immunodeficiency">Primary immunodeficiency</button>
          <button class="featured-search" type="button" data-query="clopidogrel">Clopidogrel</button>
          <button class="featured-search" type="button" data-query="cholesterol">Cholesterol</button>
        </div>
        <div class="secondary-tools">
          <details class="disclosure">
            <summary>Looking for a specific gene or variant?</summary>
            <div class="disclosure-body">
              <p>You can search a gene name, rsID, or genomic position when you know the exact identifier.</p>
              <div class="examples technical-examples">
                <button class="example" type="button" data-query="CYP2C19">CYP2C19</button>
                <button class="example" type="button" data-query="rs11188082">rs11188082</button>
                <button class="example" type="button" data-query="chr10:94808278">chr10:94808278</button>
              </div>
            </div>
          </details>
        </div>
      </section>
      <section class="workspace-view topic-library" id="view-library" aria-labelledby="topic-library-title" hidden>
        <div class="topic-library-head">
          <div>
            <p class="eyebrow">Bundle library</p>
            <h1 id="topic-library-title">Personal results</h1>
            <p class="lede" id="topic-library-lede">Browse person-specific results recorded in this bundle.</p>
          </div>
          <div class="topic-summary" id="topic-summary"></div>
        </div>
        <div class="topic-catalog" id="topic-catalog" role="tabpanel"></div>
      </section>

      <section class="workspace-view region-browser-view" id="view-map" aria-labelledby="region-browser-title" hidden>
        <div class="region-browser-head">
          <div>
            <h1 id="region-browser-title">Region browser</h1>
            <p class="lede">Start with a gene, rsID, or GRCh38 coordinate recorded in this bundle.</p>
          </div>
          <div class="map-build" id="region-build"></div>
        </div>
        <form class="region-search" id="region-search-form">
          <input id="region-search-input" type="search" aria-label="Find a genomic region" autocomplete="off" spellcheck="false" placeholder="CYP2C19, rs429358, or chr10:94,700,000-95,000,000">
          <button class="search-button" id="region-search-button" type="submit">Open region</button>
        </form>
        <div class="region-examples" aria-label="Region browser examples">
          <span>Examples</span>
          <button type="button" data-region-query="CYP2C19">CYP2C19</button>
          <button type="button" data-region-query="rs11188082">rs11188082</button>
          <button type="button" data-region-query="chr10:94808278">chr10:94808278</button>
        </div>
        <div class="region-browser-status empty" id="region-browser-status">Choose a locus to see the records and context included in this bundle.</div>
        <div class="region-browser-workspace" id="region-browser-workspace" hidden>
          <div class="region-toolbar">
            <div>
              <p class="eyebrow" id="region-target-kind">Selected region</p>
              <h2 id="region-target-title"></h2>
              <p class="region-coordinate" id="region-coordinate"></p>
            </div>
            <div class="region-controls" aria-label="Region navigation">
              <button type="button" id="region-pan-left" aria-label="Pan region left">←</button>
              <button type="button" id="region-zoom-out">Zoom out</button>
              <button type="button" id="region-zoom-in">Zoom in</button>
              <button type="button" id="region-pan-right" aria-label="Pan region right">→</button>
            </div>
          </div>
          <div class="region-ruler" id="region-ruler" aria-label="Genomic coordinate ruler"></div>
          <div class="region-tracks" aria-label="Bundle tracks for this region">
            <div class="region-track-row">
              <div class="region-track-label"><strong>Genes</strong><span id="region-genes-meta"></span></div>
              <div class="region-track" id="region-gene-track"></div>
            </div>
            <div class="region-track-row">
              <div class="region-track-label"><strong>Recorded annotations</strong><span id="region-annotations-meta"></span></div>
              <div class="region-track region-point-track" id="region-annotation-track"></div>
            </div>
            <div class="region-track-row">
              <div class="region-track-label"><strong>Your variants</strong><span id="region-variants-meta"></span></div>
              <div class="region-track region-density-track" id="region-variant-track"></div>
            </div>
            <div class="region-track-row">
              <div class="region-track-label"><strong>Callability</strong><span id="region-callability-meta"></span></div>
              <div class="region-track region-callability-track" id="region-callability-track"></div>
            </div>
          </div>
          <p class="region-track-note" id="region-track-note">Tracks contain only fields recorded in the selected bundle.</p>
          <section class="region-records" aria-labelledby="region-records-title">
            <div class="region-records-head">
              <h2 id="region-records-title">Variant records in this region</h2>
              <span id="region-records-count"></span>
            </div>
            <div id="region-records-content"></div>
            <nav class="result-pagination" id="region-records-pagination" aria-label="Region variant pages" hidden>
              <span class="pagination-range" id="region-records-page-range" aria-live="polite"></span>
              <div class="pagination-actions">
                <button class="pagination-button" id="region-records-previous" type="button">Previous</button>
                <button class="pagination-button" id="region-records-next" type="button">Next</button>
              </div>
            </nav>
          </section>
        </div>
      </section>

      <section class="workspace-view coverage-view" id="view-coverage" aria-labelledby="coverage-title" hidden>
        <div class="genome-map-head">
          <div>
            <p class="eyebrow">Bundle details</p>
            <h1 id="coverage-title">Coverage &amp; quality</h1>
            <p class="lede">Technical chromosome and callability summary recorded in this bundle.</p>
          </div>
          <div class="map-build" id="map-build"></div>
        </div>
        <div class="map-summary-strip" aria-label="Coverage and quality summary">
          <div class="map-stat">
            <span>Recorded variant rows</span>
            <strong id="map-total">Loading</strong>
          </div>
          <div class="map-stat">
            <span>Callability data</span>
            <strong id="map-callability">Loading</strong>
          </div>
        </div>
        <p class="coverage-explanation">This is a bundle completeness and quality-control summary. It does not rank biological importance.</p>
        <div class="map-table-wrap coverage-table-wrap">
          <table class="map-table">
            <thead><tr><th>Chromosome</th><th>Length</th><th>Recorded variants</th><th>Callability</th></tr></thead>
            <tbody id="map-table-body"></tbody>
          </table>
        </div>
      </section>

      <section class="workspace-view saved-results" id="view-saved" aria-labelledby="saved-results-title" hidden>
        <div class="saved-results-head">
          <div>
            <h1 id="saved-results-title">Saved results</h1>
            <p class="lede">Records bookmarked from this bundle.</p>
          </div>
          <div class="saved-export-actions">
            <button class="text-button" id="export-json" type="button">Export JSON</button>
            <button class="text-button" id="export-csv" type="button">Export CSV</button>
          </div>
        </div>
        <p class="saved-feedback" id="saved-feedback" aria-live="polite"></p>
        <div id="saved-results-list"></div>
      </section>

      <section class="workspace-view results" id="results" hidden aria-live="polite">
        <button class="workspace-back" id="results-back" type="button">← Back</button>
        <div class="results-head">
          <h1 id="results-title">What the bundle records</h1>
          <div class="result-meta" id="result-meta"></div>
        </div>
        <div class="notice" id="result-notice" data-state="recorded">
          <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7.5v.5"/></svg>
          <span id="result-notice-text">These results are recorded in this bundle. Not a diagnosis.</span>
        </div>
        <div id="result-content"></div>
      </section>
    </main>
  </div>
  <script nonce="__NONCE__">
    const basePath = "__BASE_PATH__";
    const welcome = document.querySelector("#welcome");
    const explorer = document.querySelector("#explorer");
    const welcomeTitle = document.querySelector("#welcome-title");
    const welcomeLede = document.querySelector("#welcome-lede");
    const bundleLibrary = document.querySelector("#bundle-library");
    const bundleList = document.querySelector("#bundle-list");
    const openTitle = document.querySelector("#open-title");
    const chooseButton = document.querySelector("#choose-button");
    const selectionStatus = document.querySelector("#selection-status");
    const selectionMessage = document.querySelector("#selection-message");
    const statusSpinner = document.querySelector("#status-spinner");
    const form = document.querySelector("#search-form");
    const input = document.querySelector("#search-input");
    const button = document.querySelector("#search-button");
    const results = document.querySelector("#results");
    const content = document.querySelector("#result-content");
    const topicCatalog = document.querySelector("#topic-catalog");
    const topicSummary = document.querySelector("#topic-summary");
    const resultNotice = document.querySelector("#result-notice");
    const resultNoticeText = document.querySelector("#result-notice-text");
    const topicLibrary = document.querySelector(".topic-library");
    const topicLibraryTitle = document.querySelector("#topic-library-title");
    const topicLibraryLede = document.querySelector("#topic-library-lede");
    const viewSearch = document.querySelector("#view-search");
    const viewMap = document.querySelector("#view-map");
    const viewCoverage = document.querySelector("#view-coverage");
    const regionBuild = document.querySelector("#region-build");
    const regionSearchForm = document.querySelector("#region-search-form");
    const regionSearchInput = document.querySelector("#region-search-input");
    const regionSearchButton = document.querySelector("#region-search-button");
    const regionBrowserStatus = document.querySelector("#region-browser-status");
    const regionBrowserWorkspace = document.querySelector("#region-browser-workspace");
    const regionTargetKind = document.querySelector("#region-target-kind");
    const regionTargetTitle = document.querySelector("#region-target-title");
    const regionCoordinate = document.querySelector("#region-coordinate");
    const regionPanLeft = document.querySelector("#region-pan-left");
    const regionPanRight = document.querySelector("#region-pan-right");
    const regionZoomIn = document.querySelector("#region-zoom-in");
    const regionZoomOut = document.querySelector("#region-zoom-out");
    const regionRuler = document.querySelector("#region-ruler");
    const regionGenesMeta = document.querySelector("#region-genes-meta");
    const regionAnnotationsMeta = document.querySelector("#region-annotations-meta");
    const regionVariantsMeta = document.querySelector("#region-variants-meta");
    const regionCallabilityMeta = document.querySelector("#region-callability-meta");
    const regionGeneTrack = document.querySelector("#region-gene-track");
    const regionAnnotationTrack = document.querySelector("#region-annotation-track");
    const regionVariantTrack = document.querySelector("#region-variant-track");
    const regionCallabilityTrack = document.querySelector("#region-callability-track");
    const regionRecordsCount = document.querySelector("#region-records-count");
    const regionRecordsContent = document.querySelector("#region-records-content");
    const regionRecordsPagination = document.querySelector("#region-records-pagination");
    const regionRecordsPageRange = document.querySelector("#region-records-page-range");
    const regionRecordsPrevious = document.querySelector("#region-records-previous");
    const regionRecordsNext = document.querySelector("#region-records-next");
    const mapTotal = document.querySelector("#map-total");
    const mapCallability = document.querySelector("#map-callability");
    const mapBuild = document.querySelector("#map-build");
    const mapTableBody = document.querySelector("#map-table-body");
    const viewSaved = document.querySelector("#view-saved");
    const savedResultsList = document.querySelector("#saved-results-list");
    const savedFeedback = document.querySelector("#saved-feedback");
    const exportJson = document.querySelector("#export-json");
    const exportCsv = document.querySelector("#export-csv");
    const resultsBack = document.querySelector("#results-back");
    const sidebarContext = document.querySelector("#sidebar-context");
    const sidebarBundleName = document.querySelector("#sidebar-bundle-name");
    const sidebarSearch = document.querySelector("#sidebar-search");
    const sidebarMap = document.querySelector("#sidebar-map");
    const sidebarCoverage = document.querySelector("#sidebar-coverage");
    const sidebarSaved = document.querySelector("#sidebar-saved");
    const sidebarSavedCount = document.querySelector("#sidebar-saved-count");
    const sidebarViewButtons = Array.from(document.querySelectorAll("[data-sidebar-view]"));
    const bundlesButton = document.querySelector("#bundles-button");
    const quitButton = document.querySelector("#quit-button");
    const desktop = window.offlineExplorer?.desktop === true;
    if (desktop) quitButton.hidden = true;
    let statusTimer = null;
    let explorerReady = false;
    let latestStatus = null;
    let latestTopics = [];
    let activeDirectoryView = "personal";
    let activeWorkspaceRoute = "search";
    let resultReturnRoute = "search";
    let genomeMapBundleId = "";
    let genomeMapLoading = false;
    let regionPayload = null;
    let regionLoading = false;
    let regionOriginalTarget = null;
    let regionRequestToken = 0;
    let savedResults = [];
    let savedResultIds = new Set();
    let savedBundleId = "";

    const fieldLabels = {
      variant_id: "Variant identifier", rsid: "rsID", chrom: "Chromosome", pos: "Position",
      ref: "Reference allele", alt: "Alternate allele", genotype: "Genotype", zygosity: "Zygosity",
      call_confidence: "Call confidence", gene: "Gene annotation", gene_symbol: "Gene",
      hgvsp: "Protein change", clinvar_significance: "ClinVar classification",
      clinvar_review_stars: "ClinVar review", clinvar_id: "ClinVar record",
      clinvar_has_conflicts: "ClinVar conflicts", clinvar_conflict_summary: "Conflict summary",
      clinvar_submitters_count: "ClinVar submitters", finding_id: "Finding identifier",
      condition: "Condition", claim_type: "Claim type", classification: "Classification",
      called_alleles: "Recorded genotype", evidence_ids: "Evidence identifiers", review_status: "Review status",
      clinical_grade: "Clinical-grade flag", diplotype: "Recorded diplotype", phenotype: "Recorded phenotype",
      activity_score: "Activity score", copy_number: "Copy number", cpic_level: "CPIC evidence level",
      affected_drugs: "Related medications", guideline_url: "Recorded guideline",
      trait: "Trait", score_value: "Recorded score", percentile: "Recorded percentile",
      reference_population: "Comparison group recorded in bundle", training_source: "Training source",
      training_date: "Training date", effect_allele: "Effect allele", effect_size: "Effect size",
      effect_type: "Effect type", p_value: "P value", source: "Recorded source", pubmed_id: "PubMed",
      study_pmids: "Research references", study_accession: "Study accession",
      catalog_version: "Catalog version", source_version: "Source version",
      effect_allele_in_call: "Effect allele recorded in this genome",
      start_pos: "Gene start", end_pos: "Gene end", variant_count: "Variants recorded",
      actionable_count: "Actionable records"
    };

    const sectionLabels = {
      clinical_findings: "Clinical findings",
      variants: "Your recorded variants", genes: "Records for this gene",
      pharmacogenomics: "Medication-related records", polygenic_scores: "Traits and scores",
      trait_variants: "Related variants",
      gwas: "Research sources"
    };

    const recordLabels = {
      clinical_findings: "",
      variants: "Personal variant record", genes: "Personal gene summary",
      pharmacogenomics: "Bundle pharmacogenomic record", polygenic_scores: "Recorded score",
      trait_variants: "",
      gwas: ""
    };

    const primaryFields = {
      clinical_findings: ["classification", "called_alleles", "gene_symbol", "call_confidence", "review_status"],
      variants: ["zygosity", "call_confidence"],
      genes: ["variant_count", "actionable_count"],
      pharmacogenomics: [],
      polygenic_scores: ["percentile", "reference_population"],
      trait_variants: ["called_alleles", "matched_traits", "gene", "call_confidence", "study_pmids"],
      gwas: ["rsid", "gene", "source", "study_pmids", "study_accession"]
    };

    const topicKinds = {
      clinical: {
        label: "Clinical",
        icon: "+",
        prompt: "Which clinical findings are recorded in this bundle?"
      },
      medications: {
        label: "Medications",
        icon: "Rx",
        prompt: "Could this bundle contain a person-specific pharmacogenomic call linked to this medication?"
      },
      conditions: {
        label: "Conditions",
        icon: "+",
        prompt: "Does this bundle record a score or person-linked annotation mentioning this condition?"
      },
      traits: {
        label: "Traits",
        icon: "%",
        prompt: "Does this bundle record a score or person-linked annotation mentioning this trait?"
      }
    };

    const directoryViews = {
      personal: {
        label: "Personal results",
        title: "Personal results",
        description: "Browse person-specific results recorded in this bundle."
      },
      medications: {
        label: "Medications",
        title: "Medications",
        description: "Check this bundle for pharmacogenomic results on common medications."
      },
      conditions: {
        label: "Conditions",
        title: "Conditions",
        description: "Check this bundle for recorded scores and person-linked findings."
      },
      traits: {
        label: "Traits",
        title: "Traits",
        description: "Check this bundle for recorded scores and person-linked findings."
      }
    };

    function isPersonSpecificTopic(topic) {
      const sections = Array.isArray(topic.record_sections) ? topic.record_sections : [];
      return sections.includes("clinical_findings") || sections.includes("pharmacogenomics") || sections.includes("polygenic_scores");
    }

    function topicIndicator(topic) {
      const personal = topic.personal || {};
      const answerability = topic.answerability || {};
      const clinical = Array.isArray(personal.clinical_findings) ? personal.clinical_findings : [];
      const pgx = Array.isArray(personal.pharmacogenomics) ? personal.pharmacogenomics : [];
      const scores = Array.isArray(personal.polygenic_scores) ? personal.polygenic_scores : [];
      const hasPersonLinkedVariants = Boolean(personal.has_person_linked_variants);
      const indicator = document.createElement("span");
      indicator.className = "topic-indicator";
      const value = document.createElement("span");
      value.className = "topic-indicator-value";

      if (clinical.length === 1) {
        const finding = clinical[0];
        const classification = formatValue(finding.classification || "Clinical finding");
        value.textContent = finding.gene_symbol ? `${classification} · ${finding.gene_symbol}` : classification;
      } else if (clinical.length > 1) {
        value.textContent = `${clinical.length} clinical findings`;
      } else if (pgx.length === 1) {
        const result = pgx[0].phenotype || pgx[0].diplotype || "PGx result";
        value.textContent = `${result} · ${pgx[0].gene_symbol}`;
      } else if (pgx.length > 1) {
        value.textContent = `${pgx.length} PGx results`;
      } else if (scores.length === 1) {
        const percentile = Number(scores[0].percentile).toLocaleString(undefined, { maximumFractionDigits: 1 });
        value.textContent = `${percentile}th percentile`;
      } else if (scores.length > 1) {
        value.textContent = `${scores.length} scores`;
      } else if (hasPersonLinkedVariants) {
        indicator.classList.add("related");
        value.textContent = "Related variants";
      } else if (answerability.state === "analysis_included_no_record") {
        indicator.classList.add("no-data");
        value.textContent = "No matching record";
      } else if (answerability.state === "analysis_not_included") {
        indicator.classList.add("no-data");
        value.textContent = "Analysis not included";
      } else {
        indicator.classList.add("no-data");
        value.textContent = "Not enough bundle data";
      }
      indicator.append(value);
      return indicator;
    }

    function directoryRow(topic) {
      const row = document.createElement("button");
      row.className = "directory-row";
      row.type = "button";
      row.dataset.topicQuery = topic.query;
      row.dataset.answerabilityState = topic.answerability?.state || "insufficient_bundle_data";
      row.setAttribute("aria-label", `Search this bundle for ${topic.label}`);
      row.addEventListener("click", () => {
        input.value = topic.query;
        search(topic.query);
      });
      const name = document.createElement("span");
      name.className = "directory-name";
      name.textContent = topic.label;
      const arrow = document.createElement("span");
      arrow.className = "directory-arrow";
      arrow.setAttribute("aria-hidden", "true");
      arrow.textContent = "›";
      row.append(name, topicIndicator(topic), arrow);
      return row;
    }

    function topicsForDirectoryView(topics, view, filter) {
      const normalized = filter.trim().toLowerCase();
      return topics
        .filter(topic => view === "personal" ? isPersonSpecificTopic(topic) : topic.kind === view)
        .filter(topic => !normalized || `${topic.label} ${topic.group}`.toLowerCase().includes(normalized));
    }

    function directoryGroups(topics, view, filter) {
      const host = document.createElement("div");
      host.className = "directory-groups";
      const visible = topicsForDirectoryView(topics, view, filter);
      if (!visible.length) {
        const empty = document.createElement("div");
        empty.className = "directory-empty";
        empty.textContent = filter
          ? "No topics match that filter."
          : "This bundle does not contain a clinical finding, PGx result, or recorded score for these topics.";
        host.append(empty);
        return host;
      }
      const grouped = Object.groupBy(
        visible,
        topic => view === "personal" ? topicKinds[topic.kind].label : topic.group
      );
      Object.entries(grouped)
        .sort(([left], [right]) => left.localeCompare(right))
        .forEach(([groupName, groupTopics]) => {
          const section = document.createElement("section");
          section.className = "directory-group";
          const groupHead = document.createElement("div");
          groupHead.className = "directory-group-head";
          const heading = document.createElement("h4");
          heading.textContent = groupName;
          const count = document.createElement("span");
          count.className = "directory-group-count";
          count.textContent = `${groupTopics.length} ${groupTopics.length === 1 ? "topic" : "topics"}`;
          groupHead.append(heading, count);
          const list = document.createElement("div");
          list.className = "directory-list";
          groupTopics
            .sort((left, right) => left.label.localeCompare(right.label))
            .forEach(topic => list.append(directoryRow(topic)));
          section.append(groupHead, list);
          host.append(section);
        });
      return host;
    }

    function renderDirectory(topics) {
      const wrapper = document.createElement("div");
      wrapper.className = "topic-browser";
      let filterValue = "";

      const main = document.createElement("div");
      main.className = "directory-main";
      const toolbar = document.createElement("div");
      toolbar.className = "directory-toolbar";
      const filter = document.createElement("input");
      filter.className = "directory-filter";
      filter.type = "search";
      filter.setAttribute("aria-label", "Filter common topics");
      const listHost = document.createElement("div");

      const refresh = () => {
        const view = directoryViews[activeDirectoryView];
        filter.placeholder = activeDirectoryView === "personal" ? "Filter results" : `Filter ${view.label.toLowerCase()}`;
        listHost.replaceChildren(directoryGroups(topics, activeDirectoryView, filterValue));
      };

      filter.addEventListener("input", () => {
        filterValue = filter.value;
        refresh();
      });
      toolbar.append(filter);
      main.append(toolbar, listHost);
      wrapper.append(main);
      refresh();
      return wrapper;
    }

    function renderTopicCatalog(topics) {
      latestTopics = Array.isArray(topics) ? topics : [];
      sidebarViewButtons.forEach(control => {
        const view = control.dataset.sidebarView;
        const count = latestTopics.filter(topic => view === "personal" ? isPersonSpecificTopic(topic) : topic.kind === view).length;
        control.querySelector(".sidebar-nav-count").textContent = count;
      });
      const currentView = directoryViews[activeDirectoryView];
      const visibleCount = latestTopics.filter(topic => activeDirectoryView === "personal" ? isPersonSpecificTopic(topic) : topic.kind === activeDirectoryView).length;
      topicLibraryTitle.textContent = currentView.title;
      topicLibraryLede.textContent = currentView.description;
      topicSummary.textContent = `${visibleCount} ${visibleCount === 1 ? "topic" : "topics"}`;
      topicCatalog.replaceChildren(renderDirectory(latestTopics));
    }

    function updateSidebarRoute(route) {
      const searchActive = route === "search" || (route === "results" && resultReturnRoute === "search");
      sidebarSearch.classList.toggle("is-active", searchActive);
      if (searchActive) sidebarSearch.setAttribute("aria-current", "page");
      else sidebarSearch.removeAttribute("aria-current");
      const mapActive = route === "region" || (route === "results" && resultReturnRoute === "region");
      sidebarMap.classList.toggle("is-active", mapActive);
      if (mapActive) sidebarMap.setAttribute("aria-current", "page");
      else sidebarMap.removeAttribute("aria-current");
      const coverageActive = route === "coverage";
      sidebarCoverage.classList.toggle("is-active", coverageActive);
      if (coverageActive) sidebarCoverage.setAttribute("aria-current", "page");
      else sidebarCoverage.removeAttribute("aria-current");
      const savedActive = route === "saved" || (route === "results" && resultReturnRoute === "saved");
      sidebarSaved.classList.toggle("is-active", savedActive);
      if (savedActive) sidebarSaved.setAttribute("aria-current", "page");
      else sidebarSaved.removeAttribute("aria-current");
      sidebarViewButtons.forEach(control => {
        const selected = route === control.dataset.sidebarView ||
          (route === "results" && resultReturnRoute === control.dataset.sidebarView);
        control.setAttribute("aria-selected", String(selected));
      });
    }

    function showWorkspaceRoute(route, { historyMode = "push", focusSearch = false } = {}) {
      const isDirectoryRoute = Object.hasOwn(directoryViews, route);
      const resolvedRoute = route === "results" || route === "search" || route === "region" || route === "coverage" || route === "saved" || isDirectoryRoute ? route : "search";
      if (Object.hasOwn(directoryViews, resolvedRoute) && activeDirectoryView !== resolvedRoute) {
        activeDirectoryView = resolvedRoute;
        renderTopicCatalog(latestTopics);
      }
      viewSearch.hidden = resolvedRoute !== "search";
      topicLibrary.hidden = !Object.hasOwn(directoryViews, resolvedRoute);
      viewMap.hidden = resolvedRoute !== "region";
      viewCoverage.hidden = resolvedRoute !== "coverage";
      viewSaved.hidden = resolvedRoute !== "saved";
      results.hidden = resolvedRoute !== "results";
      activeWorkspaceRoute = resolvedRoute;
      updateSidebarRoute(resolvedRoute);

      const targetHash = `#${resolvedRoute}`;
      if (historyMode === "replace") window.history.replaceState({ route: resolvedRoute }, "", targetHash);
      else if (historyMode === "push" && window.location.hash !== targetHash) {
        window.history.pushState({ route: resolvedRoute }, "", targetHash);
      }
      window.scrollTo({ top: 0, behavior: "auto" });
      if (focusSearch) window.setTimeout(() => input.focus(), 0);
      if (resolvedRoute === "coverage") loadGenomeMap();
    }

    sidebarSearch.addEventListener("click", () => showWorkspaceRoute("search", { focusSearch: true }));
    sidebarMap.addEventListener("click", () => showWorkspaceRoute("region"));
    sidebarCoverage.addEventListener("click", () => showWorkspaceRoute("coverage"));
    sidebarSaved.addEventListener("click", () => showWorkspaceRoute("saved"));

    sidebarViewButtons.forEach(control => {
      control.addEventListener("click", () => showWorkspaceRoute(control.dataset.sidebarView));
    });

    resultsBack.addEventListener("click", () => {
      if (window.location.hash === "#results" && window.history.state?.route === "results") window.history.back();
      else showWorkspaceRoute(resultReturnRoute);
    });

    window.addEventListener("popstate", () => {
      if (!explorerReady) return;
      showWorkspaceRoute(window.location.hash.slice(1), { historyMode: "none" });
    });

    function formatBytes(bytes) {
      const units = ["B", "KiB", "MiB", "GiB"];
      let value = bytes;
      let index = 0;
      while (value >= 1024 && index < units.length - 1) { value /= 1024; index += 1; }
      return `${value.toFixed(index ? 1 : 0)} ${units[index]}`;
    }

    function formatBundleDate(value) {
      const parsed = new Date(value);
      if (Number.isNaN(parsed.getTime())) return "Date not recorded";
      return parsed.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
    }

    async function postJson(path, payload) {
      const options = { method: "POST" };
      if (payload !== undefined) {
        options.headers = { "Content-Type": "application/json" };
        options.body = JSON.stringify(payload);
      }
      const response = await fetch(`${basePath}${path}`, options);
      const status = await response.json();
      if (!response.ok) throw new Error(status.error || "The local request could not be completed.");
      return status;
    }

    function beginNicknameEdit(body, actions, entry) {
      if (body.querySelector(".nickname-form")) return;
      actions.hidden = true;
      const form = document.createElement("form");
      form.className = "nickname-form";
      const nickname = document.createElement("input");
      nickname.className = "nickname-input";
      nickname.type = "text";
      nickname.maxLength = 80;
      nickname.value = entry.nickname;
      nickname.setAttribute("aria-label", `Nickname for ${entry.file_name}`);
      const save = document.createElement("button");
      save.className = "secondary-button";
      save.type = "submit";
      save.textContent = "Save";
      const cancel = document.createElement("button");
      cancel.className = "text-button";
      cancel.type = "button";
      cancel.textContent = "Cancel";
      const error = document.createElement("p");
      error.className = "nickname-error";
      error.hidden = true;
      form.append(nickname, save, cancel);
      body.append(form, error);

      cancel.addEventListener("click", () => renderBundleLibrary(latestStatus));
      form.addEventListener("submit", async event => {
        event.preventDefault();
        save.disabled = true;
        cancel.disabled = true;
        error.hidden = true;
        try {
          const status = await postJson("/api/library/rename", {
            bundle_id: entry.bundle_id,
            nickname: nickname.value
          });
          renderAppStatus(status);
        } catch (requestError) {
          error.textContent = requestError.message;
          error.hidden = false;
          save.disabled = false;
          cancel.disabled = false;
        }
      });
      nickname.focus();
      nickname.select();
    }

    async function openSavedBundle(entry) {
      showSelectionStatus(`Opening ${entry.nickname} locally.`, { busy: true });
      bundleList.querySelectorAll("button").forEach(control => { control.disabled = true; });
      try {
        const status = await postJson("/api/library/open", { bundle_id: entry.bundle_id });
        renderAppStatus(status);
        if (status.status === "validating") scheduleStatusPoll(150);
      } catch (error) {
        showSelectionStatus(error.message, { error: true });
        refreshStatus();
      }
    }

    function bundleItem(entry, busy) {
      const item = document.createElement("article");
      item.className = "bundle-item";
      const avatar = document.createElement("div");
      avatar.className = "bundle-avatar";
      avatar.setAttribute("aria-hidden", "true");
      avatar.textContent = entry.nickname.trim().charAt(0) || "G";
      const body = document.createElement("div");
      const name = document.createElement("h3");
      name.className = "bundle-name";
      name.textContent = entry.nickname;
      const meta = document.createElement("p");
      meta.className = "bundle-meta";
      meta.textContent = `${entry.file_name} · Genome spec v${entry.schema_version} · ${entry.genome_build} · ${formatBundleDate(entry.generated_at)}`;
      body.append(name, meta);
      if (!entry.available) {
        const unavailable = document.createElement("p");
        unavailable.className = "bundle-meta bundle-unavailable";
        unavailable.textContent = "Source file is no longer available at its saved location.";
        body.append(unavailable);
      }
      const actions = document.createElement("div");
      actions.className = "bundle-actions";
      const rename = document.createElement("button");
      rename.className = "text-button";
      rename.type = "button";
      rename.textContent = "Rename";
      rename.disabled = busy;
      rename.addEventListener("click", () => beginNicknameEdit(body, actions, entry));
      const open = document.createElement("button");
      open.className = "secondary-button bundle-open";
      open.type = "button";
      open.textContent = "Open";
      open.disabled = busy || !entry.available;
      open.addEventListener("click", () => openSavedBundle(entry));
      actions.append(rename, open);
      item.append(avatar, body, actions);
      return item;
    }

    function renderBundleLibrary(status) {
      latestStatus = status;
      const bundles = Array.isArray(status?.bundles) ? status.bundles : [];
      const busy = status?.status === "choosing" || status?.status === "validating";
      bundleLibrary.hidden = bundles.length === 0;
      bundleList.replaceChildren(...bundles.map(entry => bundleItem(entry, busy)));
      if (bundles.length) {
        welcomeTitle.textContent = "Choose a genome bundle.";
        welcomeLede.textContent = "Reopen a previously verified bundle or add another. Nicknames and retained data stay on this computer.";
        openTitle.textContent = "Add another genome bundle";
        if (!busy) chooseButton.textContent = "Add another bundle";
      } else {
        welcomeTitle.textContent = "Explore your genome bundle privately.";
        welcomeLede.textContent = "Choose a compatible bundle to get started. It stays on this computer and is never uploaded.";
        openTitle.textContent = "Add a genome bundle";
        if (!busy) chooseButton.textContent = "Add genome bundle";
      }
    }

    function showSelectionStatus(message, { busy = false, error = false } = {}) {
      selectionStatus.hidden = !message;
      selectionStatus.classList.toggle("error", error);
      statusSpinner.hidden = !busy;
      selectionMessage.textContent = message;
    }

    function populateBundleStatus(status) {
      const cached = status.validation_mode === "cached";
      const nickname = status.active_nickname || "Genome bundle";
      document.querySelector("#active-bundle-name").textContent = nickname;
      sidebarBundleName.textContent = nickname;
      document.querySelector("#validation").textContent = cached ? "Previously verified" : "Verified";
      document.querySelector("#spec-version").textContent = `v${status.schema_version}`;
      document.querySelector("#build").textContent = status.genome_build;
      document.querySelector("#snapshot").textContent = formatBundleDate(status.generated_at);
      document.querySelector("#stored").textContent = formatBytes(status.stored_bytes);
    }

    function renderAppStatus(status) {
      renderBundleLibrary(status);
      if (status.status === "ready") {
        welcome.hidden = true;
        explorer.hidden = false;
        sidebarContext.hidden = false;
        bundlesButton.hidden = !(status.bundles || []).length;
        bundlesButton.disabled = false;
        chooseButton.disabled = false;
        populateBundleStatus(status);
        if (genomeMapBundleId && genomeMapBundleId !== status.active_bundle_id) {
          resetGenomeMap();
        }
        if (savedBundleId !== status.active_bundle_id) {
          savedBundleId = status.active_bundle_id;
          savedFeedback.textContent = "";
          setSavedResults([]);
          sidebarSavedCount.textContent = status.saved_count || 0;
          loadSavedResults();
        }
        if (!explorerReady) activeDirectoryView = "personal";
        renderTopicCatalog(status.topics);
        if (!explorerReady) {
          explorerReady = true;
          input.value = "";
          content.replaceChildren();
          resultReturnRoute = "search";
          showWorkspaceRoute("search", { historyMode: "replace", focusSearch: true });
        }
        return;
      }

      welcome.hidden = false;
      explorer.hidden = true;
      sidebarContext.hidden = true;
      bundlesButton.hidden = true;
      bundlesButton.disabled = false;
      explorerReady = false;
      resetGenomeMap();
      savedBundleId = "";
      setSavedResults([]);
      if (status.status === "choosing") {
        chooseButton.disabled = true;
        chooseButton.textContent = "Waiting for selection";
        showSelectionStatus("Choose a genome bundle in the file window that just opened.", { busy: true });
      } else if (status.status === "validating") {
        chooseButton.disabled = true;
        chooseButton.textContent = "Opening bundle";
        const name = status.archive_name || "your bundle";
        showSelectionStatus(`Opening ${name} locally. New bundles may take a few minutes to verify.`, { busy: true });
      } else if (status.status === "failed") {
        chooseButton.disabled = false;
        chooseButton.textContent = (status.bundles || []).length ? "Add another bundle" : "Choose another bundle";
        showSelectionStatus(status.error || "This bundle could not be opened.", { error: true });
      } else {
        chooseButton.disabled = false;
        showSelectionStatus("");
      }
    }

    function scheduleStatusPoll(delay = 350) {
      window.clearTimeout(statusTimer);
      statusTimer = window.setTimeout(refreshStatus, delay);
    }

    async function refreshStatus() {
      try {
        const response = await fetch(`${basePath}/api/status`);
        const status = await response.json();
        renderAppStatus(status);
        if (status.status === "choosing" || status.status === "validating") scheduleStatusPoll();
      } catch (error) {
        welcome.hidden = false;
        explorer.hidden = true;
        chooseButton.disabled = false;
        chooseButton.textContent = "Try again";
        showSelectionStatus("Offline Explorer could not check the local bundle status.", { error: true });
      }
    }

    function formatValue(value) {
      if (Array.isArray(value)) return value.join(", ");
      if (typeof value === "boolean") return value ? "Yes" : "No";
      return String(value).replaceAll("_", " ");
    }

    function capitalize(value) {
      return value ? value.charAt(0).toUpperCase() + value.slice(1) : value;
    }

    function matchingMedication(hit, query) {
      if (!Array.isArray(hit.affected_drugs)) return "";
      const normalized = query.toLowerCase();
      return hit.affected_drugs.find(drug => drug.toLowerCase().includes(normalized)) || "";
    }

    function titleFor(hit, query) {
      if (hit.section === "clinical_findings") return hit.condition;
      if (hit.section === "pharmacogenomics") {
        return hit.gene_symbol;
      }
      if (hit.section === "variants") return hit.gene || hit.rsid || "Recorded variant";
      if (hit.section === "trait_variants") return hit.rsid || hit.variant_id || hit.gene || "Recorded variant";
      if (hit.section === "genes") return hit.gene_symbol;
      return hit.trait || hit.rsid || "Recorded result";
    }

    function subtitleFor(hit, query) {
      if (hit.section === "pharmacogenomics") {
        const medication = matchingMedication(hit, query);
        return medication ? `Matched medication: ${capitalize(medication)}` : "Person-specific bundle result";
      }
      if (hit.section === "variants") return hit.rsid ? `Identifier: ${hit.rsid}` : "";
      if (hit.section === "genes") return "Personal variant records found";
      return hit.rsid ? `Identifier: ${hit.rsid}` : "";
    }

    function resetGenomeMap() {
      genomeMapBundleId = "";
      genomeMapLoading = false;
      mapBuild.textContent = "";
      mapTotal.textContent = "Loading";
      mapCallability.textContent = "Loading";
      mapTableBody.replaceChildren();
      regionRequestToken += 1;
      regionPayload = null;
      regionLoading = false;
      regionOriginalTarget = null;
      regionBuild.textContent = "";
      regionSearchInput.value = "";
      regionSearchButton.disabled = false;
      regionSearchButton.textContent = "Open region";
      regionBrowserStatus.hidden = false;
      regionBrowserStatus.classList.remove("error");
      regionBrowserStatus.textContent = "Choose a locus to see the records and context included in this bundle.";
      regionBrowserWorkspace.hidden = true;
      regionBrowserWorkspace.removeAttribute("aria-busy");
      regionRuler.replaceChildren();
      regionGeneTrack.replaceChildren();
      regionAnnotationTrack.replaceChildren();
      regionVariantTrack.replaceChildren();
      regionCallabilityTrack.replaceChildren();
      regionRecordsContent.replaceChildren();
      regionRecordsPagination.hidden = true;
    }

    function callabilityText(callability) {
      if (callability?.state === "available") {
        if (callability.kind === "interval_records") {
          return `${mapLength(callability.callable_bases)} marked callable`;
        }
        return `${Number(callability.record_count).toLocaleString("en-US")} callable sites · no coverage percentage`;
      }
      if (callability?.state === "included_empty") return "Included, no records";
      if (callability?.state === "summary_unavailable") return "Included, summary unavailable";
      if (callability?.state === "not_included") return "Not included in this bundle";
      return "Not evaluated";
    }

    function mapLength(value) {
      if (value < 1000000) return `${Number(value).toLocaleString("en-US")} bp`;
      return `${(value / 1000000).toFixed(1)} Mb`;
    }

    function mapPercent(value) {
      if (value > 0 && value < 0.01) return "<0.01%";
      return `${value.toFixed(value >= 10 ? 1 : 2)}%`;
    }

    function renderGenomeMap(payload) {
      mapBuild.textContent = payload.genome_build || "Genome build not recorded";
      mapCallability.textContent = callabilityText(payload.callability);
      mapTableBody.replaceChildren();

      if (!payload.supported) {
        mapTotal.textContent = "Overview unavailable";
        const row = document.createElement("tr");
        const cell = document.createElement("td");
        cell.colSpan = 4;
        cell.textContent = "A chromosome summary is not available for this genome build.";
        row.append(cell);
        mapTableBody.append(row);
        return;
      }

      const chromosomes = Array.isArray(payload.chromosomes) ? payload.chromosomes : [];
      mapTotal.textContent = `${Number(payload.total_variant_records).toLocaleString("en-US")} recorded variants`;
      chromosomes.forEach(chromosome => {
        const tableRow = document.createElement("tr");
        const callabilityCell = payload.callability?.state === "available"
          ? payload.callability.kind === "interval_records"
            ? typeof chromosome.callability_percent === "number"
              ? mapPercent(chromosome.callability_percent)
              : "No callable intervals"
            : chromosome.callability_records
              ? `${Number(chromosome.callability_records).toLocaleString("en-US")} callable sites`
              : "No callable sites"
          : payload.callability?.state === "included_empty"
            ? "No records"
            : "Not included";
        [
          chromosome.label,
          mapLength(chromosome.length),
          Number(chromosome.variant_count).toLocaleString("en-US"),
          callabilityCell
        ].forEach(value => {
          const cell = document.createElement("td");
          cell.textContent = value;
          tableRow.append(cell);
        });
        mapTableBody.append(tableRow);
      });
    }

    async function loadGenomeMap() {
      const requestedBundleId = latestStatus?.active_bundle_id;
      if (!requestedBundleId || genomeMapLoading || genomeMapBundleId === requestedBundleId) return;
      genomeMapLoading = true;
      try {
        const response = await fetch(`${basePath}/api/genome-map`);
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.error || "Coverage summary could not be loaded.");
        if (latestStatus?.active_bundle_id !== requestedBundleId) return;
        renderGenomeMap(payload);
        genomeMapBundleId = requestedBundleId;
      } catch (error) {
        mapTotal.textContent = "Overview unavailable";
        mapCallability.textContent = "Unavailable";
        mapTableBody.replaceChildren();
        const row = document.createElement("tr");
        const cell = document.createElement("td");
        cell.colSpan = 4;
        cell.textContent = error.message || "Coverage summary could not be loaded.";
        row.append(cell);
        mapTableBody.append(row);
      } finally {
        genomeMapLoading = false;
      }
    }

    function exactPosition(value) {
      return Number(value).toLocaleString("en-US");
    }

    function rulerPosition(value) {
      if (value >= 1000000000) return `${(value / 1000000000).toFixed(2)} Gb`;
      if (value >= 1000000) return `${(value / 1000000).toFixed(2)} Mb`;
      if (value >= 1000) return `${(value / 1000).toFixed(1)} kb`;
      return `${exactPosition(value)} bp`;
    }

    function trackOffset(position, region) {
      return Math.max(0, Math.min(100, (position - region.start) / Math.max(1, region.length - 1) * 100));
    }

    function trackSpan(start, end, region) {
      const clippedStart = Math.max(region.start, Number(start));
      const clippedEnd = Math.min(region.end, Number(end));
      const left = trackOffset(clippedStart, region);
      const right = trackOffset(clippedEnd, region);
      return { left, width: Math.max(.25, right - left) };
    }

    function emptyTrack(track, message) {
      track.replaceChildren();
      const empty = document.createElement("span");
      empty.className = "region-track-empty";
      empty.textContent = message;
      track.append(empty);
    }

    function renderRegionRuler(region) {
      regionRuler.replaceChildren();
      for (let index = 0; index < 5; index += 1) {
        const tick = document.createElement("span");
        tick.className = "region-ruler-tick";
        const position = Math.round(region.start + (region.length - 1) * index / 4);
        tick.textContent = rulerPosition(position);
        regionRuler.append(tick);
      }
    }

    function renderGeneTrack(payload) {
      const track = payload.genes || {};
      const genes = Array.isArray(track.genes) ? track.genes : [];
      if (track.state !== "available") {
        regionGenesMeta.textContent = track.state === "not_included" ? "Gene index not included" : "Unavailable";
        emptyTrack(regionGeneTrack, "No gene spans are available from this bundle.");
        return;
      }
      regionGenesMeta.textContent = genes.length ? `${genes.length} recorded gene ${genes.length === 1 ? "span" : "spans"}` : "No recorded gene spans";
      if (!genes.length) {
        emptyTrack(regionGeneTrack, "No bundle gene spans overlap this region.");
        return;
      }
      regionGeneTrack.replaceChildren();
      genes.forEach(gene => {
        const feature = document.createElement("button");
        feature.type = "button";
        feature.className = "region-gene-feature";
        const span = trackSpan(gene.start_pos, gene.end_pos, payload.region);
        feature.style.left = `${span.left}%`;
        feature.style.width = `${span.width}%`;
        feature.textContent = gene.gene_symbol;
        feature.title = `${gene.gene_symbol} · ${gene.chrom}:${exactPosition(gene.start_pos)}-${exactPosition(gene.end_pos)}`;
        feature.addEventListener("click", () => {
          regionSearchInput.value = gene.gene_symbol;
          loadRegion({ query: gene.gene_symbol });
        });
        regionGeneTrack.append(feature);
      });
    }

    function renderAnnotationTrack(payload) {
      const track = payload.annotations || {};
      const points = Array.isArray(track.points) ? track.points : [];
      if (track.state !== "available") {
        regionAnnotationsMeta.textContent = track.state === "not_included" ? "Annotation fields not included" : "Unavailable";
        emptyTrack(regionAnnotationTrack, "No recorded annotation track is available.");
        return;
      }
      const suffix = track.truncated ? " · first 200 shown" : "";
      regionAnnotationsMeta.textContent = `${Number(track.total).toLocaleString("en-US")} recorded ${track.total === 1 ? "annotation" : "annotations"}${suffix}`;
      if (!points.length) {
        emptyTrack(regionAnnotationTrack, "No recorded annotations in this region.");
        return;
      }
      regionAnnotationTrack.replaceChildren();
      points.forEach(point => {
        const marker = document.createElement("button");
        marker.type = "button";
        marker.className = "region-annotation-point";
        marker.style.left = `${trackOffset(Number(point.pos), payload.region)}%`;
        const identifier = point.rsid || point.variant_id || `${payload.region.chrom}:${point.pos}`;
        const gene = point.gene ? ` · ${point.gene}` : "";
        const labels = Array.isArray(point.labels) ? point.labels.join(", ") : "Recorded annotation";
        marker.title = `${identifier}${gene} · ${labels}`;
        marker.setAttribute("aria-label", `Open ${identifier}: ${labels}`);
        marker.addEventListener("click", () => {
          input.value = identifier;
          search(identifier);
        });
        regionAnnotationTrack.append(marker);
      });
    }

    function renderVariantTrack(payload) {
      const track = payload.variants || {};
      const bins = Array.isArray(track.bins) ? track.bins : [];
      const total = Number(track.total || 0);
      regionVariantsMeta.textContent = `${total.toLocaleString("en-US")} recorded ${total === 1 ? "variant" : "variants"}`;
      if (!bins.length || !total) {
        emptyTrack(regionVariantTrack, "No variant records in this region.");
        return;
      }
      const maxCount = Math.max(...bins.map(bin => Number(bin.variant_count || 0)), 1);
      regionVariantTrack.replaceChildren();
      bins.forEach(bin => {
        const bar = document.createElement("button");
        bar.type = "button";
        bar.className = "region-variant-bin";
        const count = Number(bin.variant_count || 0);
        bar.style.setProperty("--height", String(count ? Math.sqrt(count / maxCount) : 0));
        bar.title = `${exactPosition(bin.start)}-${exactPosition(bin.end)} · ${count.toLocaleString("en-US")} recorded variants`;
        bar.setAttribute("aria-label", `${count.toLocaleString("en-US")} recorded variants from ${exactPosition(bin.start)} to ${exactPosition(bin.end)}${count ? ". Open this interval" : ""}`);
        bar.disabled = !count;
        if (count) {
          bar.addEventListener("click", () => loadRegion({
            chrom: payload.region.chrom,
            start: bin.start,
            end: bin.end,
            page: 1
          }, { preserveTarget: true }));
        }
        regionVariantTrack.append(bar);
      });
    }

    function renderCallabilityTrack(payload) {
      const track = payload.callability || {};
      const bins = Array.isArray(track.bins) ? track.bins : [];
      if (track.state === "not_included") {
        regionCallabilityMeta.textContent = "Not included";
        emptyTrack(regionCallabilityTrack, "Callability data is not included in this bundle.");
        return;
      }
      if (track.state === "unavailable") {
        regionCallabilityMeta.textContent = "Unavailable";
        emptyTrack(regionCallabilityTrack, "The included callability data could not be summarized.");
        return;
      }
      if (track.kind === "interval_records") {
        const percent = Number(track.coverage_percent || 0);
        regionCallabilityMeta.textContent = `${mapPercent(percent)} of this region marked callable`;
        regionCallabilityTrack.replaceChildren();
        bins.forEach(bin => {
          const segment = document.createElement("span");
          segment.className = "region-callability-bin";
          const coverage = Number(bin.callability_percent || 0);
          segment.style.setProperty("--coverage", String(coverage / 100));
          segment.title = `${exactPosition(bin.start)}-${exactPosition(bin.end)} · ${mapPercent(coverage)} marked callable`;
          regionCallabilityTrack.append(segment);
        });
        return;
      }
      const sites = Number(track.site_count || 0);
      regionCallabilityMeta.textContent = `${sites.toLocaleString("en-US")} callable ${sites === 1 ? "site" : "sites"} · no coverage percentage`;
      if (!bins.length || !sites) {
        emptyTrack(regionCallabilityTrack, "No callable sites are recorded in this region.");
        return;
      }
      const maxSites = Math.max(...bins.map(bin => Number(bin.callable_site_count || 0)), 1);
      regionCallabilityTrack.replaceChildren();
      bins.forEach(bin => {
        const segment = document.createElement("span");
        segment.className = "region-callability-bin site-bin";
        const count = Number(bin.callable_site_count || 0);
        segment.style.setProperty("--height", String(count ? Math.sqrt(count / maxSites) : 0));
        segment.title = `${exactPosition(bin.start)}-${exactPosition(bin.end)} · ${count.toLocaleString("en-US")} callable sites`;
        regionCallabilityTrack.append(segment);
      });
    }

    function renderRegionRecords(payload) {
      const records = payload.records || {};
      const hits = Array.isArray(records.hits) ? records.hits : [];
      const total = Number(records.total || 0);
      const page = Number(records.page || 1);
      const pageSize = Number(records.page_size || 25);
      const pageCount = Number(records.page_count || 0);
      regionRecordsCount.textContent = `${total.toLocaleString("en-US")} ${total === 1 ? "record" : "records"}`;
      regionRecordsContent.replaceChildren();
      if (hits.length) {
        const context = `${payload.region.chrom}:${payload.region.start}-${payload.region.end}`;
        regionRecordsContent.append(recordsFor(hits, context, "variants"));
      } else {
        const empty = document.createElement("div");
        empty.className = "empty";
        empty.textContent = "No variant records were found in this region.";
        regionRecordsContent.append(empty);
      }
      const pageStart = total ? (page - 1) * pageSize + 1 : 0;
      const pageEnd = Math.min(page * pageSize, total);
      regionRecordsPagination.hidden = pageCount <= 1;
      regionRecordsPageRange.textContent = `${pageStart}-${pageEnd} of ${total.toLocaleString("en-US")}`;
      regionRecordsPrevious.disabled = page <= 1;
      regionRecordsNext.disabled = page >= pageCount;
    }

    function renderRegion(payload, { preserveTarget = false } = {}) {
      regionPayload = payload;
      if (!preserveTarget || !regionOriginalTarget) regionOriginalTarget = payload.target;
      const displayTarget = regionOriginalTarget || payload.target;
      const targetLabels = { gene: "Gene", rsid: "Variant", coordinate: "Coordinate", region: "Region" };
      regionTargetKind.textContent = targetLabels[displayTarget.kind] || "Selected region";
      regionTargetTitle.textContent = displayTarget.label;
      regionCoordinate.textContent = `${payload.region.chrom}:${exactPosition(payload.region.start)}-${exactPosition(payload.region.end)} · ${mapLength(payload.region.length)}`;
      regionBuild.textContent = payload.genome_build || latestStatus?.genome_build || "";
      regionSearchInput.value = displayTarget.label;
      regionBrowserStatus.hidden = true;
      regionBrowserStatus.classList.remove("error");
      regionBrowserWorkspace.hidden = false;
      renderRegionRuler(payload.region);
      renderGeneTrack(payload);
      renderAnnotationTrack(payload);
      renderVariantTrack(payload);
      renderCallabilityTrack(payload);
      renderRegionRecords(payload);
      regionZoomIn.disabled = payload.region.length <= 100;
      regionZoomOut.disabled = payload.region.length >= Math.min(25000000, payload.region.chromosome_length);
      regionPanLeft.disabled = payload.region.start <= 1;
      regionPanRight.disabled = payload.region.end >= payload.region.chromosome_length;
    }

    async function loadRegion(request, { preserveTarget = false, scrollRecords = false } = {}) {
      const token = ++regionRequestToken;
      const hadPayload = Boolean(regionPayload);
      regionLoading = true;
      regionSearchButton.disabled = true;
      regionSearchButton.innerHTML = '<span class="spinner"></span>Opening';
      regionBrowserWorkspace.setAttribute("aria-busy", "true");
      if (!preserveTarget) {
        regionOriginalTarget = null;
        regionBrowserWorkspace.hidden = true;
        regionBrowserStatus.hidden = false;
        regionBrowserStatus.classList.remove("error");
        regionBrowserStatus.textContent = "Opening this region...";
      }
      try {
        const payload = await postJson("/api/region-browser", request);
        if (token !== regionRequestToken) return;
        renderRegion(payload, { preserveTarget });
        if (scrollRecords) regionRecordsContent.scrollIntoView({ behavior: "smooth", block: "start" });
      } catch (error) {
        if (token !== regionRequestToken) return;
        regionBrowserStatus.hidden = false;
        regionBrowserStatus.classList.add("error");
        regionBrowserStatus.textContent = error.message || "This genome region could not be loaded.";
        if (!hadPayload || !preserveTarget) regionBrowserWorkspace.hidden = true;
      } finally {
        if (token === regionRequestToken) {
          regionLoading = false;
          regionSearchButton.disabled = false;
          regionSearchButton.textContent = "Open region";
          regionBrowserWorkspace.removeAttribute("aria-busy");
        }
      }
    }

    function navigateRegion({ scale = 1, shift = 0 } = {}) {
      if (!regionPayload || regionLoading) return;
      const region = regionPayload.region;
      const requestedLength = Math.max(100, Math.min(25000000, region.chromosome_length, Math.round(region.length * scale)));
      const center = Math.round((region.start + region.end) / 2 + region.length * shift);
      const maximumStart = Math.max(1, region.chromosome_length - requestedLength + 1);
      const start = Math.min(maximumStart, Math.max(1, center - Math.floor(requestedLength / 2)));
      const end = start + requestedLength - 1;
      loadRegion({ chrom: region.chrom, start, end, page: 1 }, { preserveTarget: true });
    }

    regionSearchForm.addEventListener("submit", event => {
      event.preventDefault();
      const query = regionSearchInput.value.trim();
      if (query) loadRegion({ query, page: 1 });
    });
    document.querySelectorAll("[data-region-query]").forEach(example => {
      example.addEventListener("click", () => {
        regionSearchInput.value = example.dataset.regionQuery;
        loadRegion({ query: example.dataset.regionQuery, page: 1 });
      });
    });
    regionZoomIn.addEventListener("click", () => navigateRegion({ scale: .5 }));
    regionZoomOut.addEventListener("click", () => navigateRegion({ scale: 2 }));
    regionPanLeft.addEventListener("click", () => navigateRegion({ shift: -.5 }));
    regionPanRight.addEventListener("click", () => navigateRegion({ shift: .5 }));
    regionRecordsPrevious.addEventListener("click", () => {
      if (!regionPayload || regionLoading || regionPayload.records.page <= 1) return;
      loadRegion({
        chrom: regionPayload.region.chrom,
        start: regionPayload.region.start,
        end: regionPayload.region.end,
        page: regionPayload.records.page - 1
      }, { preserveTarget: true, scrollRecords: true });
    });
    regionRecordsNext.addEventListener("click", () => {
      if (!regionPayload || regionLoading || regionPayload.records.page >= regionPayload.records.page_count) return;
      loadRegion({
        chrom: regionPayload.region.chrom,
        start: regionPayload.region.start,
        end: regionPayload.region.end,
        page: regionPayload.records.page + 1
      }, { preserveTarget: true, scrollRecords: true });
    });

    function recordForSave(hit) {
      return Object.fromEntries(
        Object.entries(hit).filter(([key]) => !key.startsWith("_"))
      );
    }

    function updateSaveButtons() {
      document.querySelectorAll(".save-result-button").forEach(control => {
        const saved = savedResultIds.has(control.dataset.recordKey);
        const title = control.dataset.recordTitle || "result";
        control.setAttribute("aria-pressed", String(saved));
        control.setAttribute("aria-label", `${saved ? "Saved" : "Save"} ${title}`);
        control.textContent = saved ? "Saved" : "Save";
      });
    }

    function setSavedResults(records) {
      savedResults = Array.isArray(records) ? records : [];
      savedResultIds = new Set(savedResults.map(entry => entry.saved_id));
      sidebarSavedCount.textContent = savedResults.length;
      renderSavedResults();
      updateSaveButtons();
    }

    async function toggleSavedResult(hit, query, control) {
      const recordKey = hit._record_key;
      if (!recordKey) return;
      control.disabled = true;
      try {
        const payload = savedResultIds.has(recordKey)
          ? await postJson("/api/saved/remove", { saved_id: recordKey })
          : await postJson("/api/saved/add", { query, record: recordForSave(hit) });
        setSavedResults(payload.records);
      } catch (error) {
        control.title = error.message || "This result could not be saved.";
      } finally {
        control.disabled = false;
      }
    }

    function saveButtonFor(hit, query) {
      const control = document.createElement("button");
      control.className = "save-result-button";
      control.type = "button";
      control.dataset.recordKey = hit._record_key || "";
      control.dataset.recordTitle = titleFor(hit, query) || "result";
      control.addEventListener("click", event => {
        event.preventDefault();
        event.stopPropagation();
        toggleSavedResult(hit, query, control);
      });
      const saved = savedResultIds.has(control.dataset.recordKey);
      control.setAttribute("aria-pressed", String(saved));
      control.setAttribute("aria-label", `${saved ? "Saved" : "Save"} ${control.dataset.recordTitle}`);
      control.textContent = saved ? "Saved" : "Save";
      return control;
    }

    function savedResultRow(entry) {
      const record = entry.record || {};
      const row = document.createElement("details");
      row.className = "saved-result-row";
      const summary = document.createElement("summary");
      const title = document.createElement("span");
      title.className = "saved-result-title";
      title.textContent = titleFor(record, entry.query) || "Saved result";
      const kind = document.createElement("span");
      kind.className = "saved-result-kind";
      kind.textContent = sectionLabels[entry.section] || formatValue(entry.section);
      const arrow = document.createElement("span");
      arrow.className = "saved-result-arrow";
      arrow.setAttribute("aria-hidden", "true");
      arrow.textContent = "›";
      summary.append(title, kind, arrow);

      const details = document.createElement("div");
      details.className = "saved-result-details";
      const context = document.createElement("p");
      context.className = "saved-result-context";
      context.textContent = `Saved from search: ${entry.query} · ${formatBundleDate(entry.saved_at)}`;
      const fields = document.createElement("dl");
      fields.className = "technical-fields";
      const preferredFields = {
        clinical_findings: ["classification", "called_alleles", "gene_symbol", "call_confidence", "review_status"],
        pharmacogenomics: ["diplotype", "phenotype", "gene_symbol", "activity_score", "copy_number", "cpic_level", "affected_drugs", "guideline_url"],
        polygenic_scores: ["percentile", "reference_population", "trait", "score_value", "training_source", "training_date"],
        trait_variants: ["called_alleles", "gene", "matched_traits", "call_confidence", "rsid", "variant_id", "study_pmids"],
        genes: ["gene_symbol", "variant_count", "actionable_count", "chrom", "start_pos", "end_pos"],
        variants: ["zygosity", "gene", "call_confidence", "rsid", "variant_id", "chrom", "pos", "ref", "alt"],
        gwas: ["trait", "rsid", "gene", "source", "study_pmids", "study_accession"]
      };
      const orderedKeys = [
        ...(preferredFields[entry.section] || []),
        ...Object.keys(record).filter(key => !(preferredFields[entry.section] || []).includes(key))
      ];
      [...new Set(orderedKeys)].forEach(key => {
        const value = record[key];
        if (key === "section" || key.startsWith("_") || value === null || value === undefined || value === "") return;
        fields.append(fieldElement(key, value, entry.section));
      });
      const actions = document.createElement("div");
      actions.className = "saved-result-actions";
      const remove = document.createElement("button");
      remove.className = "text-button";
      remove.type = "button";
      remove.textContent = "Remove";
      remove.addEventListener("click", async () => {
        remove.disabled = true;
        try {
          const payload = await postJson("/api/saved/remove", { saved_id: entry.saved_id });
          setSavedResults(payload.records);
        } catch (error) {
          savedFeedback.textContent = error.message || "This saved result could not be removed.";
          remove.disabled = false;
        }
      });
      actions.append(remove);
      details.append(context, fields, actions);
      row.append(summary, details);
      return row;
    }

    function renderSavedResults() {
      exportJson.disabled = savedResults.length === 0;
      exportCsv.disabled = savedResults.length === 0;
      savedResultsList.replaceChildren();
      if (!savedResults.length) {
        const empty = document.createElement("div");
        empty.className = "empty saved-empty";
        empty.textContent = "Save a result from any search to keep it here.";
        savedResultsList.append(empty);
        return;
      }
      const list = document.createElement("div");
      list.className = "saved-result-list";
      savedResults.forEach(entry => list.append(savedResultRow(entry)));
      savedResultsList.append(list);
    }

    async function loadSavedResults() {
      try {
        const response = await fetch(`${basePath}/api/saved`);
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.error || "Saved results could not be loaded.");
        if (payload.bundle_id !== savedBundleId) return;
        setSavedResults(payload.records);
      } catch (error) {
        savedFeedback.textContent = error.message || "Saved results could not be loaded.";
      }
    }

    async function exportSavedResults(format, control) {
      if (!desktop || !savedResults.length) return;
      savedFeedback.textContent = "";
      control.disabled = true;
      try {
        const result = await window.offlineExplorer.exportSaved(format);
        if (result.saved) savedFeedback.textContent = `Exported ${result.file_name}.`;
      } catch (error) {
        savedFeedback.textContent = error.message || "Saved results could not be exported.";
      } finally {
        control.disabled = false;
      }
    }

    exportJson.hidden = !desktop;
    exportCsv.hidden = !desktop;
    exportJson.addEventListener("click", () => exportSavedResults("json", exportJson));
    exportCsv.addEventListener("click", () => exportSavedResults("csv", exportCsv));

    function summaryFor(hit, query) {
      if (hit.section === "pharmacogenomics") {
        return `This bundle contains a person-specific pharmacogenomic result for ${hit.gene_symbol}.`;
      }
      if (hit.section === "polygenic_scores") return `The bundle contains a recorded score for ${hit.trait}.`;
      if (hit.section === "genes") {
        return `Your bundle contains ${formatValue(hit.variant_count)} personal variant records assigned to ${hit.gene_symbol}.`;
      }
      return hit.gene
        ? `Your bundle contains a personal variant record annotated to ${hit.gene}.`
        : "Your bundle contains this personal variant record.";
    }

    function meaningFor(hit) {
      if (hit.section === "genes") {
        return "This shows that the bundle has personal variant records for this gene. It is not a test of whether the gene itself is present or absent.";
      }
      return "";
    }

    function fieldLabelFor(section, key) {
      if (section === "gwas" && key === "gene") return "Gene named by research";
      if (section === "clinical_findings" && key === "call_confidence") return "Technical call quality";
      if (section === "trait_variants" && key === "called_alleles") return "Recorded genotype";
      if (section === "trait_variants" && key === "matched_traits") return "Matching recorded topics";
      if (section === "trait_variants" && key === "recorded_traits") return "Recorded topic labels";
      if (section === "trait_variants" && key === "study_pmids") return "Research references";
      if (section === "variants" && key === "gene") return "Gene annotation";
      return fieldLabels[key] || key.replaceAll("_", " ");
    }

    function fieldElement(key, value, section) {
      const wrapper = document.createElement("div");
      wrapper.className = "field";
      const label = document.createElement("dt");
      label.textContent = fieldLabelFor(section, key);
      const detail = document.createElement("dd");
      if (typeof value === "string" && value.startsWith("https://")) {
        const link = document.createElement("a");
        link.href = value;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.textContent = "Open recorded source";
        detail.append(link);
      } else if (key === "study_pmids" || key === "pubmed_id") {
        const identifiers = (Array.isArray(value) ? value : [value]).map(String).filter(identifier => /^\d+$/.test(identifier));
        if (identifiers.length) {
          detail.classList.add("reference-links");
          identifiers.forEach(identifier => {
            const link = document.createElement("a");
            link.href = `https://pubmed.ncbi.nlm.nih.gov/${identifier}/`;
            link.target = "_blank";
            link.rel = "noopener noreferrer";
            link.textContent = `PubMed ${identifier}`;
            detail.append(link);
          });
        } else {
          detail.textContent = formatValue(value);
        }
      } else if (key === "study_accession" && typeof value === "string" && /^GCST\d+$/i.test(value)) {
        const link = document.createElement("a");
        link.href = `https://www.ebi.ac.uk/gwas/studies/${encodeURIComponent(value)}`;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.textContent = `GWAS Catalog ${value}`;
        detail.append(link);
      } else if (key === "clinvar_id" && typeof value === "string") {
        const link = document.createElement("a");
        link.href = /^\d+$/.test(value)
          ? `https://www.ncbi.nlm.nih.gov/clinvar/variation/${encodeURIComponent(value)}/`
          : `https://www.ncbi.nlm.nih.gov/clinvar/?term=${encodeURIComponent(value)}`;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.textContent = `ClinVar ${value}`;
        detail.append(link);
      } else if (key === "clinvar_review_stars") {
        detail.textContent = `${value} of 4 stars`;
      } else if (key === "called_alleles" && Array.isArray(value)) {
        detail.textContent = value.join(" / ");
      } else if (key === "source" && value === "gwas_catalog") {
        detail.textContent = "GWAS Catalog";
      } else {
        detail.textContent = formatValue(value);
      }
      wrapper.append(label, detail);
      return wrapper;
    }

    function appendClinicalFindingData(card, hit) {
      if (hit.clinvar_has_conflicts) {
        const conflict = document.createElement("div");
        conflict.className = "clinical-conflict";
        conflict.textContent = hit.clinvar_conflict_summary
          ? `Conflicting ClinVar submissions · ${formatValue(hit.clinvar_conflict_summary)}`
          : "Conflicting ClinVar submissions";
        card.append(conflict);
      }

      const evidence = Array.isArray(hit.evidence) ? hit.evidence : [];
      const clinvarEvidence = evidence.find(item => String(item?.source || "").toLowerCase() === "clinvar");
      const reviewStatus = clinvarEvidence?.review_status || (
        hit.clinvar_review_stars !== null && hit.clinvar_review_stars !== undefined
          ? `${hit.clinvar_review_stars} of 4 stars`
          : ""
      );
      const visible = { ...hit, review_status: reviewStatus };
      const fields = document.createElement("dl");
      fields.className = "simple-fields";
      ["classification", "called_alleles", "gene_symbol", "call_confidence", "review_status"].forEach(key => {
        const value = visible[key];
        if (value !== null && value !== undefined && value !== "") {
          fields.append(fieldElement(key, value, hit.section));
        }
      });
      if (fields.children.length) card.append(fields);

      const sources = document.createElement("div");
      sources.className = "clinical-sources";
      const links = new Set();
      evidence.forEach(item => {
        if (!item || typeof item !== "object") return;
        const sourceName = formatValue(item.source || "Recorded source");
        const sourceId = item.source_record_id ? String(item.source_record_id) : "";
        const row = document.createElement("div");
        row.className = "clinical-source";
        if (String(item.source || "").toLowerCase() === "clinvar" && sourceId) {
          const link = document.createElement("a");
          link.className = "source-link";
          link.href = /^\d+$/.test(sourceId)
            ? `https://www.ncbi.nlm.nih.gov/clinvar/variation/${encodeURIComponent(sourceId)}/`
            : `https://www.ncbi.nlm.nih.gov/clinvar/?term=${encodeURIComponent(sourceId)}`;
          link.target = "_blank";
          link.rel = "noopener noreferrer";
          link.textContent = `ClinVar ${sourceId}`;
          row.append(link);
          links.add(sourceId);
        } else {
          const name = document.createElement("strong");
          name.textContent = sourceId ? `${sourceName} ${sourceId}` : sourceName;
          row.append(name);
        }
        const metadata = [
          item.source_version,
          item.retrieved_at ? formatBundleDate(item.retrieved_at) : ""
        ].filter(value => value !== null && value !== undefined && value !== "");
        if (metadata.length) {
          const detail = document.createElement("span");
          detail.textContent = metadata.join(" · ");
          row.append(detail);
        }
        sources.append(row);
      });
      if (hit.clinvar_id && !links.has(String(hit.clinvar_id))) {
        const row = document.createElement("div");
        row.className = "clinical-source";
        const link = document.createElement("a");
        link.className = "source-link";
        link.href = /^\d+$/.test(String(hit.clinvar_id))
          ? `https://www.ncbi.nlm.nih.gov/clinvar/variation/${encodeURIComponent(hit.clinvar_id)}/`
          : `https://www.ncbi.nlm.nih.gov/clinvar/?term=${encodeURIComponent(hit.clinvar_id)}`;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.textContent = `ClinVar ${hit.clinvar_id}`;
        row.append(link);
        sources.append(row);
      }
      if (sources.children.length) card.append(sources);
    }

    function appendPharmacogenomicsData(card, hit, query) {
      const personal = document.createElement("section");
      personal.className = "personal-data";
      const personalLabel = document.createElement("h4");
      personalLabel.className = "data-group-label";
      personalLabel.textContent = "Person-specific data from this bundle";
      const personalCopy = document.createElement("p");
      personalCopy.className = "data-group-copy";
      personalCopy.textContent = "These values describe the person represented by this bundle.";
      const personalFields = document.createElement("dl");
      personalFields.className = "simple-fields";
      ["diplotype", "phenotype", "activity_score", "copy_number"].forEach(key => {
        const value = hit[key];
        if (value !== null && value !== undefined && value !== "") {
          personalFields.append(fieldElement(key, value, hit.section));
        }
      });
      personal.append(personalLabel, personalCopy, personalFields);
      card.append(personal);

      const context = document.createElement("section");
      context.className = "reference-context";
      const contextLabel = document.createElement("h4");
      contextLabel.className = "data-group-label";
      contextLabel.textContent = "Reference context included in the bundle";
      const contextCopy = document.createElement("p");
      contextCopy.className = "data-group-copy";
      const medication = matchingMedication(hit, query);
      contextCopy.textContent = medication
        ? `The bundle links ${hit.gene_symbol} with recorded guidance for ${capitalize(medication)}. This context is not unique to this person.`
        : `The bundle includes recorded medication guidance for ${hit.gene_symbol}. This context is not unique to this person.`;
      const contextFields = document.createElement("dl");
      contextFields.className = "simple-fields";
      if (hit.cpic_level !== null && hit.cpic_level !== undefined && hit.cpic_level !== "") {
        contextFields.append(fieldElement("cpic_level", hit.cpic_level, hit.section));
      }
      context.append(contextLabel, contextCopy, contextFields);
      if (typeof hit.guideline_url === "string" && hit.guideline_url.startsWith("https://")) {
        const source = document.createElement("a");
        source.className = "source-link";
        source.href = hit.guideline_url;
        source.target = "_blank";
        source.rel = "noopener noreferrer";
        source.textContent = "View recorded guideline";
        context.append(source);
      }
      card.append(context);
    }

    function cardFor(hit, query) {
      const card = document.createElement("article");
      card.className = "card";
      const compact = hit.section === "clinical_findings" || hit.section === "trait_variants" || hit.section === "gwas";

      if (!compact) {
        const type = document.createElement("div");
        type.className = "record-type";
        type.textContent = recordLabels[hit.section] || "Bundle record";
        card.append(type);
      }

      const top = document.createElement("div");
      top.className = "card-top";
      const heading = document.createElement("div");
      heading.className = "card-heading";
      const title = document.createElement("h3");
      title.textContent = titleFor(hit, query);
      const subtitle = document.createElement("div");
      subtitle.className = "card-id";
      subtitle.textContent = subtitleFor(hit, query);
      heading.append(title);
      if (!compact && subtitle.textContent) heading.append(subtitle);
      top.append(heading, saveButtonFor(hit, query));
      card.append(top);

      if (!compact) {
        const summary = document.createElement("p");
        summary.className = "recorded-summary";
        summary.textContent = summaryFor(hit, query);
        card.append(summary);

        const meaning = meaningFor(hit);
        if (meaning) {
          const note = document.createElement("p");
          note.className = "meaning-note";
          note.textContent = meaning;
          card.append(note);
        }
      }

      if (hit.section === "clinical_findings") {
        appendClinicalFindingData(card, hit);
      } else if (hit.section === "pharmacogenomics") {
        appendPharmacogenomicsData(card, hit, query);
      } else {
        const simple = document.createElement("dl");
        simple.className = "simple-fields";
        (primaryFields[hit.section] || []).forEach(key => {
          const value = hit[key];
          if (value !== null && value !== undefined && value !== "") simple.append(fieldElement(key, value, hit.section));
        });
        if (simple.children.length) card.append(simple);
      }

      if (hit.section !== "pharmacogenomics" && typeof hit.guideline_url === "string" && hit.guideline_url.startsWith("https://")) {
        const source = document.createElement("a");
        source.className = "source-link";
        source.href = hit.guideline_url;
        source.target = "_blank";
        source.rel = "noopener noreferrer";
        source.textContent = "View recorded guideline";
        card.append(source);
      }

      const technical = document.createElement("details");
      technical.className = "technical-details";
      const technicalSummary = document.createElement("summary");
      technicalSummary.textContent = "Technical details";
      const fields = document.createElement("dl");
      fields.className = "technical-fields";
      const alreadyShown = new Set(primaryFields[hit.section] || []);
      Object.entries(hit).forEach(([key, value]) => {
        if (key === "section" || key.startsWith("_") || value === null || value === undefined || value === "") return;
        if (hit.section === "clinical_findings" && [
          "condition", "classification", "called_alleles", "gene_symbol", "call_confidence",
          "clinvar_has_conflicts", "clinvar_conflict_summary", "clinvar_review_stars",
          "clinvar_submitters_count", "clinvar_id", "evidence"
        ].includes(key)) return;
        if ((hit.section === "trait_variants" || hit.section === "gwas") && alreadyShown.has(key)) return;
        fields.append(fieldElement(key, value, hit.section));
      });
      technical.append(technicalSummary, fields);
      card.append(technical);
      return card;
    }

    function sectionHeading(sectionName, count, showCount = true) {
      const heading = document.createElement("div");
      heading.className = "section-title";
      const label = document.createElement("span");
      label.textContent = sectionLabels[sectionName] || sectionName;
      heading.append(label);
      if (showCount) {
        const badge = document.createElement("span");
        badge.className = "count";
        badge.textContent = count;
        heading.append(badge);
      }
      return heading;
    }

    function cardsFor(hits, query) {
      const cards = document.createElement("div");
      cards.className = "cards";
      hits.forEach(hit => cards.append(cardFor(hit, query)));
      return cards;
    }

    const compactRecordSections = new Set(["variants", "trait_variants", "gwas"]);

    function compactValue(key, value) {
      if (value === null || value === undefined || value === "") return "Not recorded";
      if (key === "called_alleles" && Array.isArray(value)) return value.join(" / ");
      if (key === "source" && value === "gwas_catalog") return "GWAS Catalog";
      return formatValue(value);
    }

    function recordColumnsFor(hit) {
      if (hit.section === "trait_variants") {
        return [
          { label: "Variant", key: hit.rsid ? "rsid" : "variant_id", value: hit.rsid || hit.variant_id },
          { label: "Genotype", key: "called_alleles", value: hit.called_alleles },
          { label: "Gene", key: "gene", value: hit.gene },
          { label: "Matching topic", key: "matched_traits", value: hit.matched_traits },
          { label: "Call confidence", key: "call_confidence", value: hit.call_confidence }
        ];
      }
      if (hit.section === "gwas") {
        return [
          { label: "Research topic", key: "trait", value: hit.trait },
          { label: "Variant", key: hit.rsid ? "rsid" : "variant_id", value: hit.rsid || hit.variant_id },
          { label: "Gene", key: "gene", value: hit.gene },
          { label: "Source", key: "source", value: hit.source }
        ];
      }
      return [
        { label: "Variant", key: hit.rsid ? "rsid" : "variant_id", value: hit.rsid || hit.variant_id },
        { label: "Zygosity", key: "zygosity", value: hit.zygosity },
        { label: "Gene", key: "gene", value: hit.gene },
        { label: "Call confidence", key: "call_confidence", value: hit.call_confidence }
      ];
    }

    function recordRowFor(hit, query) {
      const row = document.createElement("details");
      row.className = "record-row";
      const summary = document.createElement("summary");
      summary.className = "record-row-summary";
      const columns = recordColumnsFor(hit);
      columns.forEach((column, index) => {
        const cell = document.createElement("span");
        cell.className = `record-row-cell${index === 0 ? " record-row-primary" : ""}`;
        cell.dataset.label = column.label;
        const value = document.createElement("span");
        value.className = "record-row-value";
        value.textContent = compactValue(column.key, column.value);
        value.title = value.textContent;
        cell.append(value);
        summary.append(cell);
      });
      const actions = document.createElement("span");
      actions.className = "record-row-actions";
      const arrow = document.createElement("span");
      arrow.className = "record-row-arrow";
      arrow.setAttribute("aria-hidden", "true");
      arrow.textContent = "›";
      actions.append(saveButtonFor(hit, query), arrow);
      summary.append(actions);

      const details = document.createElement("div");
      details.className = "record-row-details";
      const fields = document.createElement("dl");
      fields.className = "record-row-fields";
      const shownKeys = new Set(columns.map(column => column.key));
      Object.entries(hit).forEach(([key, value]) => {
        if (key === "section" || key.startsWith("_") || shownKeys.has(key) || value === null || value === undefined || value === "") return;
        fields.append(fieldElement(key, value, hit.section));
      });
      details.append(fields);
      row.append(summary, details);
      return row;
    }

    function recordListFor(hits, query, sectionName) {
      const list = document.createElement("div");
      list.className = `record-list record-layout-${sectionName}`;
      const head = document.createElement("div");
      head.className = "record-list-head";
      head.setAttribute("aria-hidden", "true");
      recordColumnsFor(hits[0]).forEach(column => {
        const label = document.createElement("span");
        label.textContent = column.label;
        head.append(label);
      });
      head.append(document.createElement("span"));
      list.append(head, ...hits.map(hit => recordRowFor(hit, query)));
      return list;
    }

    function recordsFor(hits, query, sectionName) {
      return compactRecordSections.has(sectionName)
        ? recordListFor(hits, query, sectionName)
        : cardsFor(hits, query);
    }

    function paginatedResults(hits, query, sectionName) {
      const pageSize = compactRecordSections.has(sectionName) ? 10 : 4;
      if (hits.length <= pageSize) return recordsFor(hits, query, sectionName);

      const wrapper = document.createElement("div");
      wrapper.className = "paginated-results";
      const pageContent = document.createElement("div");
      pageContent.className = "result-page";
      const pagination = document.createElement("nav");
      pagination.className = "result-pagination";
      pagination.setAttribute("aria-label", `${sectionLabels[sectionName] || sectionName} pages`);
      const range = document.createElement("span");
      range.className = "pagination-range";
      range.setAttribute("aria-live", "polite");
      const actions = document.createElement("div");
      actions.className = "pagination-actions";
      const previous = document.createElement("button");
      previous.className = "pagination-button";
      previous.type = "button";
      previous.textContent = "Previous";
      previous.setAttribute("aria-label", `Previous page of ${sectionLabels[sectionName] || sectionName}`);
      const next = document.createElement("button");
      next.className = "pagination-button";
      next.type = "button";
      next.textContent = "Next";
      next.setAttribute("aria-label", `Next page of ${sectionLabels[sectionName] || sectionName}`);
      actions.append(previous, next);
      pagination.append(range, actions);
      wrapper.append(pageContent, pagination);

      let page = 0;
      const pageCount = Math.ceil(hits.length / pageSize);
      const renderPage = ({ scroll = false } = {}) => {
        const start = page * pageSize;
        const end = Math.min(start + pageSize, hits.length);
        pageContent.replaceChildren(recordsFor(hits.slice(start, end), query, sectionName));
        range.textContent = `${start + 1}-${end} of ${hits.length}`;
        previous.disabled = page === 0;
        next.disabled = page === pageCount - 1;
        if (scroll) pageContent.scrollIntoView({ behavior: "smooth", block: "start" });
      };
      previous.addEventListener("click", () => {
        if (page === 0) return;
        page -= 1;
        renderPage({ scroll: true });
      });
      next.addEventListener("click", () => {
        if (page === pageCount - 1) return;
        page += 1;
        renderPage({ scroll: true });
      });
      renderPage();
      return wrapper;
    }

    function answerabilityPresentation(answerability) {
      const state = answerability?.state || "insufficient_bundle_data";
      if (state === "recorded") {
        return {
          title: "Personal records found",
          notice: "These results are recorded in this bundle. Not a diagnosis."
        };
      }
      if (state === "callable_no_matching_alternate") {
        return {
          title: "No matching alternate record",
          notice: "This position is recorded as callable, but no matching alternate variant was found. This is not a negative health test."
        };
      }
      if (state === "not_callable") {
        return {
          title: "Position not reliably callable",
          notice: "The bundle cannot determine whether a matching variant is present at this position."
        };
      }
      if (state === "analysis_included_no_record") {
        const subject = answerability?.topic_kind === "medications"
          ? "medication"
          : answerability?.topic_kind === "conditions"
            ? "condition"
            : "trait";
        return {
          title: "No matching record",
          notice: `Relevant analysis is included, but this bundle does not record a personal result for this ${subject}.`
        };
      }
      if (state === "analysis_not_included") {
        if (answerability?.scope === "topic") {
          const subject = answerability?.topic_kind === "medications"
            ? "medication"
            : answerability?.topic_kind === "conditions"
              ? "condition"
              : "trait";
          return {
            title: "Analysis not included",
            notice: `This bundle does not include the analysis needed to answer this ${subject}.`
          };
        }
        return {
          title: "Callability not included",
          notice: "This bundle does not include the site-level callability needed to explain a missing variant."
        };
      }
      if (state === "unsupported_bundle_version") {
        return {
          title: "Bundle version cannot answer",
          notice: "This bundle version does not provide the site-level callability needed to explain a missing variant."
        };
      }
      if (answerability?.reason === "rsid_has_no_offline_coordinate_mapping") {
        return {
          title: "Not enough bundle data",
          notice: "No matching rsID record was found, and this bundle does not provide the offline coordinate mapping needed to check callability."
        };
      }
      if (answerability?.reason === "no_site_level_callability_record") {
        return {
          title: "Not enough bundle data",
          notice: "No matching variant was found, and this bundle has no callability record for the position, so it remains unresolved."
        };
      }
      if (answerability?.reason === "relevant_analysis_unavailable") {
        return {
          title: "Not enough bundle data",
          notice: "This bundle lists relevant analysis data, but it could not be read well enough to answer this topic."
        };
      }
      return {
        title: "Not enough bundle data",
        notice: "No matching personal record was found, and the bundle does not provide enough evidence to interpret that absence."
      };
    }

    function renderSearch(payload) {
      const count = payload.hits.length;
      const grouped = Object.groupBy(payload.hits, hit => hit.section);
      const hasPersonLinkedRecords = Boolean(grouped.clinical_findings?.length || grouped.trait_variants?.length);
      const presentation = answerabilityPresentation(payload.answerability);
      document.querySelector("#results-title").textContent = presentation.title;
      const resultContext = `Search: ${payload.query}`;
      document.querySelector("#result-meta").textContent = hasPersonLinkedRecords
        ? resultContext
        : count
          ? `${resultContext} · ${count} recorded ${count === 1 ? "match" : "matches"}`
          : resultContext;
      results.dataset.answerabilityState = payload.answerability?.state || "insufficient_bundle_data";
      resultNotice.hidden = false;
      resultNotice.dataset.state = results.dataset.answerabilityState;
      resultNoticeText.textContent = presentation.notice;
      content.replaceChildren();
      if (!count) return;
      const sectionOrder = ["clinical_findings", "pharmacogenomics", "polygenic_scores", "trait_variants", "genes", "variants", "gwas"];
      const hasClearerRecord = Boolean(
        grouped.clinical_findings?.length ||
        grouped.pharmacogenomics?.length ||
        grouped.polygenic_scores?.length ||
        grouped.trait_variants?.length
      );
      sectionOrder.filter(sectionName => grouped[sectionName]?.length).forEach(sectionName => {
        const hits = grouped[sectionName];
        const section = document.createElement("section");
        section.className = `section section-${sectionName}`;
        const isSecondary = hasClearerRecord && (sectionName === "variants" || sectionName === "gwas");
        const showCount = !hasPersonLinkedRecords || !["clinical_findings", "trait_variants", "gwas"].includes(sectionName);
        if (isSecondary) {
          const disclosure = document.createElement("details");
          disclosure.className = "result-disclosure";
          const summary = document.createElement("summary");
          summary.append(sectionHeading(sectionName, hits.length, showCount));
          disclosure.append(summary, paginatedResults(hits, payload.query, sectionName));
          section.append(disclosure);
        } else {
          section.append(sectionHeading(sectionName, hits.length, showCount), paginatedResults(hits, payload.query, sectionName));
        }
        content.append(section);
      });
    }

    async function search(query) {
      if (activeWorkspaceRoute !== "results") resultReturnRoute = activeWorkspaceRoute;
      showWorkspaceRoute("results");
      button.disabled = true;
      button.innerHTML = '<span class="spinner"></span>Searching';
      document.querySelector("#results-title").textContent = "Searching";
      document.querySelector("#result-meta").textContent = "";
      resultNotice.hidden = true;
      content.innerHTML = '<div class="empty">Searching this bundle...</div>';
      try {
        const response = await fetch(`${basePath}/api/search`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ query })
        });
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.error || "Search failed");
        renderSearch(payload);
      } catch (error) {
        document.querySelector("#results-title").textContent = "Search unavailable";
        document.querySelector("#result-meta").textContent = "";
        resultNotice.hidden = true;
        content.innerHTML = '<div class="empty error"></div>';
        content.firstElementChild.textContent = error.message;
      } finally {
        button.disabled = false;
        button.textContent = "Search";
      }
    }

    form.addEventListener("submit", event => {
      event.preventDefault();
      const query = input.value.trim();
      if (query) search(query);
    });

    document.querySelectorAll(".example").forEach(example => {
      example.addEventListener("click", () => {
        input.value = example.dataset.query || example.textContent;
        search(input.value);
      });
    });

    document.querySelectorAll(".featured-search").forEach(shortcut => {
      shortcut.addEventListener("click", () => {
        input.value = shortcut.dataset.query || shortcut.textContent;
        search(input.value);
      });
    });

    chooseButton.addEventListener("click", async () => {
      chooseButton.disabled = true;
      chooseButton.textContent = "Opening file selector";
      showSelectionStatus("Opening the local file selector.", { busy: true });
      try {
        const status = desktop
          ? await window.offlineExplorer.chooseBundle()
          : await postJson("/api/select");
        renderAppStatus(status);
        if (status.status === "choosing" || status.status === "validating") scheduleStatusPoll(150);
      } catch (error) {
        chooseButton.disabled = false;
        chooseButton.textContent = "Try again";
        showSelectionStatus(error.message || "The local file selector could not be opened.", { error: true });
      }
    });
    if (desktop) {
      window.offlineExplorer.onChooseBundleRequested(() => chooseButton.click());
    }

    bundlesButton.addEventListener("click", async () => {
      window.clearTimeout(statusTimer);
      bundlesButton.disabled = true;
      try {
        const status = await postJson("/api/library/show");
        renderAppStatus(status);
      } catch (error) {
        bundlesButton.disabled = false;
      }
    });

    quitButton.addEventListener("click", async () => {
      window.clearTimeout(statusTimer);
      quitButton.disabled = true;
      quitButton.textContent = "Stopping";
      try {
        if (desktop) {
          await window.offlineExplorer.quit();
        } else {
          await fetch(`${basePath}/api/shutdown`, { method: "POST" });
        }
      } finally {
        document.body.innerHTML = '<main class="shell"><p class="eyebrow">Offline Explorer stopped</p><h1>Your local session has ended.</h1><p class="lede">You can close this tab. Your source bundle was not modified.</p></main>';
      }
    });

    refreshStatus();
  </script>
</body>
</html>'''


_resource_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
_sunflower_bytes = (_resource_root / "assets" / "genome-computer-sunflower.png").read_bytes()
_sunflower_data_uri = "data:image/png;base64," + base64.b64encode(_sunflower_bytes).decode("ascii")
PAGE = PAGE.replace("__SUNFLOWER_DATA_URI__", _sunflower_data_uri)
