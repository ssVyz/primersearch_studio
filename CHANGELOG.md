# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Force a consistent **light theme** at startup (Fusion style + explicit light
  palette, and the Light color scheme where supported) so the app's accent
  colors render correctly even when the OS is in dark mode (e.g. Windows dark
  mode).
- **Triplet spacing** display toggle (`View → Triplet spacing`): renders oligo
  sequences grouped in threes (e.g. `AAT TGT AGT T`) in both the kept-primer and
  output tables. Display-only — injected oligos, copy, and FASTA/CSV exports stay
  unspaced. The setting is persisted in the app config. Sequence input now also
  tolerates internal whitespace (pasted spaced sequences are normalized).
- `primersearch_studio` PySide6 GUI front-end for the primersearch tool.
  - Iterative workflow: kept primers on the left (injected into every run),
    tool output on the right; pull suggested primers across to build the set.
  - **Update** runs primersearch off the UI thread (QProcess), cancellable,
    always via CLI flags (`--format json --no-config --silent` + parameters),
    never the on-disk `config.ini`.
  - Configurable binary path (defaults to `primersearch` on PATH) with a Test
    button; file-picker alignment loading with sequence-count metadata,
    re-loadable at any time.
  - Full parameters panel (Tm/conditions, mode, orientation, fixed-slice,
    3′ match, incremental-only options, threads).
  - Combined-coverage summary for the kept set; preprocessing-removal and
    `result.message` surfaced from each run.
  - Export: primer set to FASTA, results to CSV, copy-as-text view; root TOML
    app config plus separate `.psproj` project files (open/save).
- Dependencies: `pyside6`, `tomli-w`.

## [0.1.0] - 2026-06-23

### Added
- Initial project scaffolding (uv project, `main.py`, `pyproject.toml`).
- `CHANGELOG.md` for tracking changes.
- `CLAUDE.md` with instructions for future Claude Code instances.
