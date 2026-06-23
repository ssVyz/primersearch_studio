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
        return cls(
            raw=doc,
            preprocessing=doc.get("preprocessing", {}),
            settings=doc.get("settings", {}),
            total_sequences=int(result.get("total_sequences", 0)),
            primer_count=int(result.get("primer_count", len(primers))),
            injected_count=int(result.get("injected_count", 0)),
            message=str(result.get("message", "") or ""),
            primers=primers,
        )

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
        """
        injected = [p for p in self.primers if p.injected]
        return injected[-1].cumulative_pct if injected else 0.0
