"""Render a :class:`RunResult` as the plain-text report the CLI emits.

This reproduces the layout of the tool's own ``.txt`` output (see
``output_demo.txt``) from the parsed JSON document, so the GUI can show a
copy-pasteable text view that matches what users get from the command line.

The format is *modelled* on the reference output rather than byte-identical:
the header row is aligned to the data columns (the reference has a small
header offset), and a few setting labels whose exact wording the JSON contract
does not document — non-fixed analysis, ``no_ambiguities`` mode, the enforced
Tm case — use the descriptive phrasings noted inline below.
"""

from __future__ import annotations

from .models import RunResult
from .params import group_oligo

RULE_WIDTH = 90
_RULE = "=" * RULE_WIDTH
_THIN = "-" * RULE_WIDTH

_PREPROC_LABEL_W = 28  # value column in the preprocessing block
_SETTINGS_LABEL_W = 18  # value column in the settings block

# Table column widths (relative to the end of the sequence column). These
# reproduce the reference output's spacing; the sequence and index columns size
# themselves to their content.
_COUNT_W = 6
_PCT_W = 9
_CUMUL_W = 10
_TM_W = 9


def _compact_pct(value: float) -> str:
    """Render a percentage without a trailing ``.0`` (e.g. ``66.0`` -> ``66``)."""
    number = float(value)
    if number == int(number):
        return str(int(number))
    return f"{number:g}"


def _label(text: str, width: int) -> str:
    return text.ljust(width)


def format_result_report(result: RunResult, *, spacing: bool = True) -> str:
    """Build the full text report for ``result``.

    ``spacing`` controls triplet grouping of the sequence column (e.g.
    ``GAR AAY TGR``), matching the app's display toggle.
    """
    lines: list[str] = []
    lines += _preprocessing_section(result)
    lines.append("")
    lines += _results_section(result, spacing)
    return "\n".join(lines) + "\n"


def _preprocessing_section(result: RunResult) -> list[str]:
    pre = result.preprocessing
    removed = pre.get("removed", {})
    title = "PRIMER SEARCH PREPROCESSING"
    out = [title, "=" * len(title)]
    out.append(_label("Original sequences:", _PREPROC_LABEL_W) + str(pre.get("original_count", 0)))
    out.append(_label("Valid sequences:", _PREPROC_LABEL_W) + str(pre.get("valid_count", 0)))
    out.append(_label("Majority sequence length:", _PREPROC_LABEL_W)
               + f"{pre.get('majority_length', 0)} bp")
    out.append("")
    out.append("Removed due to quality issues:")
    out.append(_label("  - Gaps (- or .):", _PREPROC_LABEL_W) + str(removed.get("gaps", 0)))
    out.append(_label("  - Ambiguous bases:", _PREPROC_LABEL_W) + str(removed.get("ambiguous", 0)))
    out.append(_label("  - Invalid characters:", _PREPROC_LABEL_W) + str(removed.get("invalid", 0)))
    out.append(_label("  - Wrong length:", _PREPROC_LABEL_W) + str(removed.get("wrong_length", 0)))
    out.append(_label("  - Total removed:", _PREPROC_LABEL_W) + str(removed.get("total", 0)))
    return out


def _results_section(result: RunResult, spacing: bool) -> list[str]:
    out = [_RULE, "PRIMER SEARCH RESULTS", _RULE, ""]
    if result.message:
        out.append(f"Note: {result.message}")
        out.append("")
    out += _settings_lines(result)
    out += ["", _THIN, ""]
    out += _table_lines(result, spacing)
    out += ["", _RULE]
    return out


def _settings_lines(result: RunResult) -> list[str]:
    s = result.settings

    # Analysis: only the fixed-slice wording is documented; non-fixed runs
    # perform the positional search.
    if s.get("fixed"):
        analysis = "Fixed slice (search skipped)"
    else:
        analysis = "Positional search"

    mode = s.get("mode", "")
    if mode == "incremental":
        target = _compact_pct(s.get("target_coverage_pct", 0.0))
        max_amb = int(s.get("max_ambiguities", 0))
        unit = "ambiguity" if max_amb == 1 else "ambiguities"
        search_mode = f"Incremental (target {target}%, max {max_amb} {unit})"
    elif mode == "no_ambiguities":
        search_mode = "No ambiguities (exact match)"
    else:
        search_mode = mode or "?"

    orientation = "Reverse (anti-sense)" if s.get("orientation") == "reverse" else "Forward (sense)"

    tm = f"{float(s.get('tm_threshold', 0.0)):.1f}°C"
    if not s.get("tm_threshold_enforced", True):
        tm += " (not enforced; see per-primer Tm)"

    three_prime = int(s.get("three_prime_match", 0))
    three_prime_text = f"{three_prime} base" if three_prime == 1 else f"{three_prime} bases"

    rows = [
        ("Analysis:", analysis),
        ("Search Mode:", search_mode),
        ("Orientation:", orientation),
        ("Total Sequences:", str(result.total_sequences)),
        ("Primers Found:", str(result.primer_count)),
        ("Tm Threshold:", tm),
        ("Oligo Conc:", f"{float(s.get('oligo_concentration_um', 0.0)):.3f} µM"),
        ("Na+ Conc:", f"{float(s.get('na_concentration_mm', 0.0)):.1f} mM"),
        ("Mg2+ Conc:", f"{float(s.get('mg_concentration_mm', 0.0)):.2f} mM"),
        ("dNTP Conc:", f"{float(s.get('dntp_concentration_mm', 0.0)):.2f} mM"),
        ("3' Perfect Match:", three_prime_text),
        ("Exclude N:", "Yes" if s.get("exclude_n") else "No"),
    ]
    return [_label(label, _SETTINGS_LABEL_W) + value for label, value in rows]


def _table_lines(result: RunResult, spacing: bool) -> list[str]:
    primers = result.primers
    sequences = [group_oligo(p.sequence) if spacing else p.sequence for p in primers]

    seq_w = max([len("Sequence")] + [len(s) for s in sequences])
    idx_w = max([1] + [len(str(p.index)) for p in primers])
    # Widen the count column only if some count needs more room than the
    # reference width (keeps at least a two-space gap after the sequence).
    count_w = max([_COUNT_W] + [len(str(p.coverage_count)) + 2 for p in primers])

    def row(idx: str, seq: str, count: str, pct: str, cumul: str, tm: str, pos: str) -> str:
        return (
            f"{idx:>{idx_w}}   {seq:<{seq_w}}"
            f"{count:>{count_w}}{pct:>{_PCT_W}}{cumul:>{_CUMUL_W}}{tm:>{_TM_W}}   {pos}"
        )

    lines = [
        row("#", "Sequence", "Count", "%", "Total%", "Tm(°C)", "Position"),
        _THIN,
    ]
    for primer, seq in zip(primers, sequences):
        lines.append(row(
            str(primer.index),
            seq,
            str(primer.coverage_count),
            f"{primer.coverage_pct:.1f}%",
            f"{primer.cumulative_pct:.1f}%",
            f"{primer.tm:.1f}",
            primer.position_label,
        ))
    return lines
