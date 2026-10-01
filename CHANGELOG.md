# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Optimize-by-mismatch mode** (`--mode optimize-by-mismatch`): the new
  exhaustive primersearch method is selectable in the *Mode* dropdown. A new
  *Optimize-by-mismatch mode* parameter group (enabled only in that mode) sets
  the set size (`--n-oligos`), mismatches (`--mismatches`), the counting
  criterion (`--mismatch-mode lower-or-equal|exact`), ambiguities per oligo
  (`--ambiguities`), and the search-space limits (`--max-candidates`,
  `--max-work`; 0 = no limit, defaults match the tool). The parameters persist
  in projects and app defaults; older files load with the tool's defaults.
  - Results show a **mismatch breakdown** under the table (sequences bound with
    0, 1, … mismatches by their best-matching oligo, not covered, and the
    counted level in `exact` mode) plus the candidate/evaluation statistics;
    the info line reports coverage under the criterion and oligos used of *n*.
    Coverage-column tooltips explain best-match crediting.
  - *View Results as Text* renders the mode label, coverage line, 3′ note,
    candidate statistics and breakdown table like the CLI's text output.
  - Kept primers count toward the set size: a run with more kept primers than
    *Oligos in set* is stopped with an explanation before calling the tool. The
    kept-panel summary reports the coverage *credited* to kept primers in this
    mode.
  - Tool errors (e.g. a search-space limit hit) surface in the error dialog as
    before.

### Changed
- The *Forbid N* / *Only 2-fold* checkboxes moved from the *Incremental mode*
  group to a new *IUPAC restrictions* group, enabled in both incremental and
  optimize-by-mismatch mode (`--exclude-n` / `--only-twofold` are now also
  passed in optimize-by-mismatch runs).
- The excluded-signatures hint and `--exclude` docs note that the tool applies
  exclusions in fixed-slice runs of optimize-by-mismatch mode.
- **Excluded 3′ signatures** (`--exclude`): a new dock (tabbed with *Parameters*,
  toggleable via `View → Excluded 3′ signatures`) holding a project-scoped list
  of oligos the search must never reproduce. Each discovered candidate whose 3′
  end matches an excluded oligo (3′-anchored IUPAC set-intersection over the
  shorter length) is dropped, so new primers steer clear of the 3′ ends of
  primers used elsewhere (e.g. in a multiplex). Entries take a label/sequence/
  notes like kept primers, are validated before the run, persist in the
  `.psproj` project file, and honor the triplet-spacing display toggle. Kept
  (injected) primers are exempt and the tool ignores exclusions in fixed-slice
  mode (both noted in the panel). Passing no exclusions leaves runs byte-for-byte
  unchanged.
- **View Results as Text** (`File → View Results as Text…`, and a *View as text*
  button on the results panel): opens a separate window showing the full run —
  preprocessing, resolved settings, and the primer table — as a copy-pasteable,
  monospace text report matching the CLI's `.txt` output, with a *Copy to
  clipboard* button. Honors the triplet-spacing display toggle. (New
  `primersearch_studio.report` module renders the report from the parsed result.)
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
