# primersearch_studio

A PySide6 desktop GUI for **primersearch** — a tool that finds a small set of
PCR primers covering every sequence in an aligned DNA set. primersearch_studio
drives the tool as a subprocess (always via explicit CLI flags, never its
on-disk `settings.ini`) and gives you an environment to build primer sets
iteratively.

## The workflow

```
┌─────────────────────────────┬─────────────────────────────┐
│  Kept primers (left)        │  Tool output (right)        │
│  → injected into every run  │  → suggestions from the run │
│                             │                             │
│  [Add] [Edit] [Remove] ↑ ↓  │   Keep selected →           │
└─────────────────────────────┴─────────────────────────────┘
              Parameters dock (right) · status bar (bottom)
```

1. **Load an alignment** (`File → Load Alignment…`). The status bar shows how
   many sequences were read and whether they're the same length. You can load a
   different FASTA at any time.
2. Tune the run in the **Parameters** dock (Tm/conditions, mode, orientation,
   fixed-slice, 3′ match, incremental and optimize-by-mismatch options, IUPAC
   restrictions, threads).
3. Click **Update** (`F5`). primersearch runs off the UI thread; results appear
   on the right with coverage, Tm, and position for each primer.
4. **Keep** good candidates: select rows on the right and click *Keep selected →*
   (or double-click). They move to the left and are injected into the next run.
5. Re-run and iterate until the kept set reaches **100% coverage** (shown in the
   left-panel summary).

Everything on the left is passed to primersearch as `--inject` oligos. Injected
primers are listed first in the output and badged `inject`.

## Running

```bash
uv run python main.py
# or
uv run python -m primersearch_studio
```

## Configuring the binary

By default primersearch_studio calls `primersearch` from your `PATH`. To point
at a specific build, use `File → App Settings…`, browse to the executable, and
hit **Test** to confirm it responds. The path is stored in the app config.

## Files

- **App config** — `primersearch_studio.toml` in the project root: binary path,
  default parameters, window layout (machine-local; gitignored).
- **Projects** — `*.psproj` (JSON) via `File → Open/Save`: the loaded alignment
  path, run parameters, and the kept primer set. Keep one per design session.

## Exporting

- `File → Export Primer Set as FASTA…` — the kept set as a FASTA file.
- `File → Export Results as CSV…` — the current output table.
- `File → View Primer Set as Text…` — copy-pasteable FASTA / sequence list /
  label+sequence, with a copy-to-clipboard button.

## Notes

- Orientation is per-project ("one side at a time"). Injected oligos must match
  the run's orientation; for a reverse run, keep the reverse-complement form
  (which is what primersearch returns for `--rev` runs).
- In **fixed-slice** mode the whole alignment is treated as one region and the
  Tm threshold is reported but not enforced.
- **optimize-by-mismatch** mode searches exhaustively for the best set of *n*
  oligos (each with *y* ambiguity codes) when sequences may be bound with up to
  / exactly *x* mismatches. Kept primers are fixed members of the set and count
  toward *n*. Each counted sequence is credited to its best-matching oligo, so
  the Cov column adds up to the set's coverage; a mismatch breakdown below the
  results shows how many sequences the set binds with 0, 1, … mismatches. The
  search is exponential in the worst case — if a run hits the candidate or
  work limit it fails with an explanation; reduce mismatches/ambiguities/set
  size, use fixed-slice mode on a narrow slice, or raise the limits.
- primersearch quality-filters the input; sequences with gaps, ambiguous bases,
  or the wrong length are dropped. The count is surfaced above the results.

## Requirements

- Python ≥ 3.12, the `primersearch` executable, and the dependencies in
  `pyproject.toml` (`pyside6`, `tomli-w`), installed via `uv sync`.
