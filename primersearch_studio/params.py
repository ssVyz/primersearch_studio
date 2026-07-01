"""Run parameters and the CLI-argument builder.

This module is the single source of truth for how UI state maps onto
primersearch command-line flags. The three machine-friendly flags
(``--format json``, ``--no-config``, ``--silent``) are always added by the
runner, never here — this builder only emits the *parameter* flags.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields

# Valid primer letters: A/C/G/T plus IUPAC ambiguity codes.
IUPAC_CODES = frozenset("ACGTRYSWKMBDHVN")

MODE_NO_AMBIGUITIES = "no-ambiguities"
MODE_INCREMENTAL = "incremental"
MODES = (MODE_NO_AMBIGUITIES, MODE_INCREMENTAL)

ORIENTATION_FORWARD = "forward"
ORIENTATION_REVERSE = "reverse"
ORIENTATIONS = (ORIENTATION_FORWARD, ORIENTATION_REVERSE)


@dataclass
class RunParameters:
    """All tunable parameters for a primersearch run.

    Defaults mirror the tool's built-in defaults (Section 6 of the integration
    guide), so a freshly constructed instance reproduces a bare ``--no-config``
    run.
    """

    # Thermodynamic / Tm
    tm: float = 55.0
    oligo: float = 0.2
    na: float = 50.0
    mg: float = 3.0
    dntp: float = 0.8
    # Search behavior
    mode: str = MODE_NO_AMBIGUITIES
    fixed: bool = False
    orientation: str = ORIENTATION_FORWARD
    three_prime: int = 0
    # Incremental-only
    target: float = 50.0
    max_amb: int = 1
    max_seeds: int = 50
    exclude_n: bool = False
    only_twofold: bool = False
    # Process control
    threads: int = 0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict | None) -> "RunParameters":
        if not data:
            return cls()
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})


def _fmt_number(value: float | int) -> str:
    """Render a number for the CLI without scientific notation or trailing noise."""
    if isinstance(value, bool):  # guard: bool is a subclass of int
        raise TypeError("expected a number, got bool")
    if isinstance(value, int):
        return str(value)
    # Floats: trim a trailing ".0" but keep meaningful decimals.
    text = repr(float(value))
    return text


def normalize_oligo(sequence: str) -> str:
    """Strip *all* whitespace (incl. internal triplet spacing) and upper-case."""
    return "".join(sequence.split()).upper()


def group_oligo(sequence: str, size: int = 3, sep: str = " ") -> str:
    """Display helper: insert ``sep`` every ``size`` bases (e.g. AAT TGT AGT T).

    Cosmetic only — never feed the result back as a real oligo; normalize first.
    """
    seq = normalize_oligo(sequence)
    if not seq or size <= 0:
        return seq
    return sep.join(seq[i:i + size] for i in range(0, len(seq), size))


def validate_oligo(sequence: str) -> str | None:
    """Return an error message if ``sequence`` is not a valid oligo, else None."""
    seq = normalize_oligo(sequence)
    if not seq:
        return "sequence is empty"
    bad = sorted(set(seq) - IUPAC_CODES)
    if bad:
        return f"invalid base(s): {', '.join(bad)} (allowed: A C G T + IUPAC codes)"
    return None


def build_cli_args(
    params: RunParameters,
    injected: list[str] | None = None,
    excluded: list[str] | None = None,
) -> list[str]:
    """Build the parameter portion of the primersearch command line.

    Does *not* include the binary, the input path, or the
    ``--format/--no-config/--silent`` flags — the runner adds those. Numeric and
    enum parameters are always emitted (explicit and deterministic); boolean
    switches are emitted only when on, per the integration guide.

    ``excluded`` oligos are passed via ``--exclude`` so the search never
    reproduces their 3′ signature. They are emitted verbatim (same orientation
    convention as ``--inject``); the tool ignores them in ``--fixed`` mode.
    """
    args: list[str] = []

    # Thermodynamic / conditions — always explicit.
    args += ["--tm", _fmt_number(params.tm)]
    args += ["--oligo", _fmt_number(params.oligo)]
    args += ["--na", _fmt_number(params.na)]
    args += ["--mg", _fmt_number(params.mg)]
    args += ["--dntp", _fmt_number(params.dntp)]

    # Search behavior. CLI uses hyphenated mode spelling.
    args += ["--mode", params.mode]
    if params.fixed:
        args += ["--fixed"]
    if params.orientation == ORIENTATION_REVERSE:
        args += ["--rev"]
    if params.three_prime and params.three_prime > 0:
        args += ["--three-prime", str(params.three_prime)]

    # Incremental-only parameters are meaningless (and clutter the command) in
    # no-ambiguities mode.
    if params.mode == MODE_INCREMENTAL:
        args += ["--target", _fmt_number(params.target)]
        args += ["--max-amb", str(params.max_amb)]
        args += ["--max-seeds", str(params.max_seeds)]
        if params.exclude_n:
            args += ["--exclude-n"]
        if params.only_twofold:
            args += ["--only-twofold"]

    if params.threads and params.threads > 0:
        args += ["-j", str(params.threads)]

    for oligo in injected or []:
        normalized = normalize_oligo(oligo)
        if normalized:
            args += ["--inject", normalized]

    for oligo in excluded or []:
        normalized = normalize_oligo(oligo)
        if normalized:
            args += ["--exclude", normalized]

    return args
