"""Lightweight FASTA helpers: scan an alignment for metadata, write a primer set."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

_LABEL_SANITIZE = re.compile(r"\s+")


@dataclass
class FastaInfo:
    """Cheap metadata about a loaded FASTA file (no full sequence retained)."""

    path: str
    sequence_count: int
    min_length: int
    max_length: int

    @property
    def is_aligned(self) -> bool:
        """All sequences the same length (a precondition for primersearch)."""
        return self.sequence_count > 0 and self.min_length == self.max_length

    def summary(self) -> str:
        if self.sequence_count == 0:
            return "no sequences found"
        if self.is_aligned:
            return f"{self.sequence_count} sequences, {self.max_length} bp (aligned)"
        return (
            f"{self.sequence_count} sequences, "
            f"{self.min_length}–{self.max_length} bp (UNEVEN lengths)"
        )


def scan_fasta(path: str | Path) -> FastaInfo:
    """Stream a FASTA file and return sequence count + length range.

    Reads line by line so even large alignments stay cheap. Raises OSError if
    the file cannot be read.
    """
    count = 0
    cur_len = 0
    min_len: int | None = None
    max_len = 0
    have_record = False

    def _close_record() -> None:
        nonlocal min_len, max_len
        if not have_record:
            return
        if min_len is None or cur_len < min_len:
            min_len = cur_len
        if cur_len > max_len:
            max_len = cur_len

    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            if line.startswith(">"):
                _close_record()
                count += 1
                cur_len = 0
                have_record = True
            elif have_record:
                cur_len += len(line)
        _close_record()

    return FastaInfo(
        path=str(path),
        sequence_count=count,
        min_length=min_len or 0,
        max_length=max_len,
    )


def sanitize_label(label: str, fallback: str) -> str:
    """Turn a user label into a FASTA-header-safe token."""
    cleaned = _LABEL_SANITIZE.sub("_", label.strip())
    return cleaned or fallback


def primers_to_fasta(primers: Iterable, *, label_prefix: str = "primer") -> str:
    """Render kept primers as FASTA text. Each item needs ``.sequence``/``.label``."""
    lines: list[str] = []
    used: set[str] = set()
    for i, primer in enumerate(primers, start=1):
        base = sanitize_label(getattr(primer, "label", ""), f"{label_prefix}_{i}")
        name = base
        suffix = 1
        while name in used:
            suffix += 1
            name = f"{base}_{suffix}"
        used.add(name)
        lines.append(f">{name}")
        lines.append(getattr(primer, "sequence", ""))
    return "\n".join(lines) + ("\n" if lines else "")


def write_primers_fasta(path: str | Path, primers: Iterable, *, label_prefix: str = "primer") -> None:
    text = primers_to_fasta(primers, label_prefix=label_prefix)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
