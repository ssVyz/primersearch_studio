"""Domain models: the kept-primer record and the parsed run result."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .params import normalize_oligo

SUPPORTED_FORMAT_VERSION = 1


@dataclass
class Primer:
    """A primer the user is keeping on the left panel.

    ``sequence`` is the only field the run actually needs (it becomes an
    ``--inject`` value). The remaining fields are bookkeeping: a user-supplied
    label/notes plus stats captured from the output row this primer was pulled
    from. ``stats_stale`` is set when the sequence is edited after stats were
    captured, so the UI can show the stats as out-of-date.
    """

    sequence: str
    label: str = ""
    notes: str = ""
    tm: float | None = None
    position_label: str = ""
    coverage_count: int | None = None
    coverage_pct: float | None = None
    stats_stale: bool = False

    def to_dict(self) -> dict:
        return {
            "sequence": self.sequence,
            "label": self.label,
            "notes": self.notes,
            "tm": self.tm,
            "position_label": self.position_label,
            "coverage_count": self.coverage_count,
            "coverage_pct": self.coverage_pct,
            "stats_stale": self.stats_stale,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Primer":
        return cls(
            sequence=normalize_oligo(str(data.get("sequence", ""))),
            label=str(data.get("label", "")),
            notes=str(data.get("notes", "")),
            tm=data.get("tm"),
            position_label=str(data.get("position_label", "")),
            coverage_count=data.get("coverage_count"),
            coverage_pct=data.get("coverage_pct"),
            stats_stale=bool(data.get("stats_stale", False)),
        )

    def has_stats(self) -> bool:
        return self.tm is not None and not self.stats_stale


@dataclass
class PrimerHit:
    """One primer from a primersearch result (``result.primers[i]``)."""

    index: int
    sequence: str
    coverage_count: int
    coverage_pct: float
    cumulative_pct: float
    tm: float
    ambiguity_count: int
    injected: bool
    align_start: int
    align_end: int
    position_label: str

    @classmethod
    def from_dict(cls, data: dict) -> "PrimerHit":
        return cls(
            index=int(data["index"]),
            sequence=str(data["sequence"]),
            coverage_count=int(data["coverage_count"]),
            coverage_pct=float(data["coverage_pct"]),
            cumulative_pct=float(data["cumulative_pct"]),
            tm=float(data["tm"]),
            ambiguity_count=int(data.get("ambiguity_count", 0)),
            injected=bool(data.get("injected", False)),
            align_start=int(data.get("align_start", 0)),
            align_end=int(data.get("align_end", 0)),
            position_label=str(data.get("position_label", "")),
        )

    def as_primer(self) -> Primer:
        """Build a kept-primer record from this hit, carrying over its stats."""
        return Primer(
            sequence=self.sequence,
            tm=self.tm,
            position_label=self.position_label,
            coverage_count=self.coverage_count,
            coverage_pct=self.coverage_pct,
            stats_stale=False,
        )


@dataclass
class MismatchLevel:
    """Sequences whose best-matching oligo has exactly ``mismatches`` mismatches."""

    mismatches: int
    count: int
    pct: float


@dataclass
class MismatchBreakdown:
    """Set-level coverage of an optimize-by-mismatch run (``result.mismatch_breakdown``).

    Every sequence is scored by its best-matching oligo in the set. ``counted``
    is the optimized objective (the sum of the primers' ``coverage_count``);
    the remaining fields are search statistics.
    """

    counted: int
    counted_pct: float
    levels: list[MismatchLevel]
    not_covered: int
    not_covered_pct: float
    windows: int
    candidates_generated: int
    candidates_after_reduction: int
    evaluations: int

    @classmethod
    def from_dict(cls, data: dict) -> "MismatchBreakdown":
        return cls(
            counted=int(data.get("counted", 0)),
            counted_pct=float(data.get("counted_pct", 0.0)),
            levels=[
                MismatchLevel(
                    mismatches=int(level["mismatches"]),
                    count=int(level["count"]),
                    pct=float(level["pct"]),
                )
                for level in data.get("levels", [])
            ],
            not_covered=int(data.get("not_covered", 0)),
            not_covered_pct=float(data.get("not_covered_pct", 0.0)),
            windows=int(data.get("windows", 0)),
            candidates_generated=int(data.get("candidates_generated", 0)),
            candidates_after_reduction=int(data.get("candidates_after_reduction", 0)),
            evaluations=int(data.get("evaluations", 0)),
        )


class ResultError(ValueError):
    """Raised when a JSON document does not match the expected contract."""


@dataclass
class RunResult:
    """A parsed primersearch JSON document."""

    raw: dict
    preprocessing: dict
    settings: dict
    total_sequences: int
    primer_count: int
    injected_count: int
    message: str
    primers: list[PrimerHit] = field(default_factory=list)
    # Only present in optimize-by-mismatch mode.
    mismatch: MismatchBreakdown | None = None

    @classmethod
    def from_doc(cls, doc: dict) -> "RunResult":
        version = doc.get("format_version")
        if version != SUPPORTED_FORMAT_VERSION:
            raise ResultError(
                f"unsupported format_version {version!r} "
                f"(this build understands {SUPPORTED_FORMAT_VERSION})"
            )
        result = doc.get("result", {})
        primers = [PrimerHit.from_dict(p) for p in result.get("primers", [])]
        breakdown = result.get("mismatch_breakdown")
        return cls(
            raw=doc,
            preprocessing=doc.get("preprocessing", {}),
            settings=doc.get("settings", {}),
            total_sequences=int(result.get("total_sequences", 0)),
            primer_count=int(result.get("primer_count", len(primers))),
            injected_count=int(result.get("injected_count", 0)),
            message=str(result.get("message", "") or ""),
            primers=primers,
            mismatch=MismatchBreakdown.from_dict(breakdown) if breakdown else None,
        )

    @property
    def is_mismatch_mode(self) -> bool:
        """True for an optimize-by-mismatch result (best-match credited coverage)."""
        return self.settings.get("mode") == "optimize_by_mismatch"

    @property
    def final_coverage_pct(self) -> float:
        """Cumulative coverage reached by the full primer list (0 if empty)."""
        return self.primers[-1].cumulative_pct if self.primers else 0.0

    @property
    def kept_coverage_pct(self) -> float:
        """Coverage reached by the injected (kept) primers alone.

        Injected primers are emitted first and ``cumulative_pct`` is monotonic,
        so the last injected primer's cumulative value is the kept set's
        combined coverage.

        In optimize-by-mismatch mode this is the coverage *credited* to the
        kept primers instead: each counted sequence goes to its best-matching
        oligo in the whole set (ties to the one listed first), so a sequence a
        found oligo matches better is not counted here.
        """
        injected = [p for p in self.primers if p.injected]
        return injected[-1].cumulative_pct if injected else 0.0
