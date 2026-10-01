"""The Parameters dock: every primersearch run flag, mapped to a widget."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..params import (
    MISMATCH_MODES,
    MODE_INCREMENTAL,
    MODE_OPTIMIZE_BY_MISMATCH,
    MODES,
    ORIENTATION_REVERSE,
    ORIENTATIONS,
    RunParameters,
)

# Upper bound for the search-space limit fields: the largest integer a double
# (QDoubleSpinBox) still represents exactly, far beyond any practical limit.
_LIMIT_MAX = float(2**53)


class ParametersPanel(QWidget):
    """Form of all run parameters. Emits :attr:`changed` on any edit."""

    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        # --- thermodynamic / conditions ---
        self._tm = self._dspin(0.0, 120.0, 1, 0.5)
        self._oligo = self._dspin(0.0, 10000.0, 3, 0.1)
        self._na = self._dspin(0.0, 10000.0, 2, 1.0)
        self._mg = self._dspin(0.0, 10000.0, 2, 0.1)
        self._dntp = self._dspin(0.0, 10000.0, 2, 0.1)

        tm_box = QGroupBox("Thermodynamic / conditions")
        tm_form = QFormLayout(tm_box)
        tm_form.addRow("Tm threshold (°C):", self._tm)
        tm_form.addRow("Oligo conc. (µM):", self._oligo)
        tm_form.addRow("Na⁺ (mM):", self._na)
        tm_form.addRow("Mg²⁺ (mM):", self._mg)
        tm_form.addRow("dNTP (mM):", self._dntp)

        # --- search behavior ---
        self._mode = QComboBox()
        self._mode.addItems(MODES)
        self._orientation = QComboBox()
        self._orientation.addItems(ORIENTATIONS)
        self._fixed = QCheckBox("Fixed-slice mode (whole alignment = one region; Tm not enforced)")
        self._fixed.setToolTip(
            "Treat the entire input alignment as one slice and only generate the "
            "variants needed to cover it. The Tm threshold is reported but not enforced.\n"
            "In optimize-by-mismatch mode the slice's consensus is deconstructed into "
            "candidate oligos instead — far cheaper than searching the whole alignment."
        )
        self._three_prime = self._spin(0, 100)
        self._three_prime.setToolTip(
            "Number of 3′ bases that must be perfectly conserved (0 disables).\n"
            "In optimize-by-mismatch mode these bases also carry no ambiguity codes, "
            "and a sequence with a mismatch there counts as not covered."
        )

        search_box = QGroupBox("Search behavior")
        search_form = QFormLayout(search_box)
        search_form.addRow("Mode:", self._mode)
        search_form.addRow("Orientation:", self._orientation)
        search_form.addRow("3′ perfect match (bases):", self._three_prime)
        search_form.addRow(self._fixed)

        # --- incremental-only ---
        self._target = self._dspin(0.0, 100.0, 1, 1.0)
        self._max_amb = self._spin(0, 50)
        self._max_seeds = self._spin(0, 1000000)

        self._incremental_box = QGroupBox("Incremental mode")
        inc_form = QFormLayout(self._incremental_box)
        inc_form.addRow("Target coverage (%):", self._target)
        inc_form.addRow("Max ambiguities:", self._max_amb)
        inc_form.addRow("Max seeds (0 = no cap):", self._max_seeds)

        # --- optimize-by-mismatch-only ---
        self._n_oligos = self._spin(1, 1000)
        self._n_oligos.setToolTip(
            "Size of the optimized set. Kept primers are fixed members of the set "
            "and count toward it; fewer oligos are listed when more cannot improve "
            "the result."
        )
        self._mismatches = self._spin(0, 100)
        self._mismatches.setToolTip("Mismatch count of the coverage criterion.")
        self._mismatch_mode = QComboBox()
        self._mismatch_mode.addItems(MISMATCH_MODES)
        self._mismatch_mode.setToolTip(
            "Each sequence is scored by its best-matching oligo in the set.\n"
            "lower-or-equal: counts when that oligo has at most this many mismatches "
            "(ties broken by fewest total mismatches).\n"
            "exact: counts only with exactly this many mismatches; better matches "
            "do not count."
        )
        self._ambiguities = self._spin(0, 100)
        self._ambiguities.setToolTip(
            "IUPAC ambiguity codes per oligo: exactly this many, or fewer where a "
            "region has fewer variable positions."
        )
        self._max_candidates = self._limit_spin()
        self._max_candidates.setToolTip(
            "Abort when more than this many candidate oligos would be enumerated "
            "(estimated before any work starts). 0 = no limit."
        )
        self._max_work = self._limit_spin()
        self._max_work.setToolTip(
            "Abort when the set search needs more than this many candidate "
            "evaluations. 0 = no limit."
        )

        self._mismatch_box = QGroupBox("Optimize-by-mismatch mode")
        mm_form = QFormLayout(self._mismatch_box)
        mm_form.addRow("Oligos in set:", self._n_oligos)
        mm_form.addRow("Mismatches:", self._mismatches)
        mm_form.addRow("Count sequences with:", self._mismatch_mode)
        mm_form.addRow("Ambiguities per oligo:", self._ambiguities)
        mm_form.addRow("Max candidates (0 = no limit):", self._max_candidates)
        mm_form.addRow("Max work (0 = no limit):", self._max_work)
        mm_hint = QLabel(
            "Exhaustive search: run time grows quickly with mismatches and "
            "ambiguities, then with the set size. Fixed-slice mode on a narrow "
            "slice is far cheaper. Kept primers count toward the set."
        )
        mm_hint.setWordWrap(True)
        mm_hint.setStyleSheet("color: #555;")
        mm_form.addRow(mm_hint)

        # --- IUPAC restrictions (both ambiguity modes) ---
        self._exclude_n = QCheckBox("Forbid N (4-fold) consensus codes")
        self._only_twofold = QCheckBox("Only 2-fold codes (R/Y/S/W/K/M)")

        self._iupac_box = QGroupBox("IUPAC restrictions")
        self._iupac_box.setToolTip(
            "Applies to incremental and optimize-by-mismatch modes. Where a code "
            "is forbidden, optimize-by-mismatch uses the widest allowed sub-codes."
        )
        iupac_form = QFormLayout(self._iupac_box)
        iupac_form.addRow(self._exclude_n)
        iupac_form.addRow(self._only_twofold)

        # --- process ---
        self._threads = self._spin(0, 256)
        proc_box = QGroupBox("Process")
        proc_form = QFormLayout(proc_box)
        proc_form.addRow("Threads (0 = all cores):", self._threads)

        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.addWidget(tm_box)
        inner_layout.addWidget(search_box)
        inner_layout.addWidget(self._incremental_box)
        inner_layout.addWidget(self._mismatch_box)
        inner_layout.addWidget(self._iupac_box)
        inner_layout.addWidget(proc_box)
        inner_layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(inner)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(scroll)

        # Wire change signals.
        for spin in (self._tm, self._oligo, self._na, self._mg, self._dntp,
                     self._target, self._three_prime, self._max_amb,
                     self._max_seeds, self._n_oligos, self._mismatches,
                     self._ambiguities, self._max_candidates, self._max_work,
                     self._threads):
            spin.valueChanged.connect(self.changed)
        self._mode.currentIndexChanged.connect(self._on_mode_changed)
        self._orientation.currentIndexChanged.connect(self.changed)
        self._mismatch_mode.currentIndexChanged.connect(self.changed)
        for check in (self._fixed, self._exclude_n, self._only_twofold):
            check.toggled.connect(self.changed)

        self.set_params(RunParameters())
        self._on_mode_changed()

    # --- widget factories --------------------------------------------------

    @staticmethod
    def _dspin(lo: float, hi: float, decimals: int, step: float) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(lo, hi)
        spin.setDecimals(decimals)
        spin.setSingleStep(step)
        return spin

    @staticmethod
    def _spin(lo: int, hi: int) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(lo, hi)
        return spin

    @staticmethod
    def _limit_spin() -> QDoubleSpinBox:
        """Integer field for the search-space limits, which exceed QSpinBox's
        32-bit range (a double holds them exactly)."""
        spin = QDoubleSpinBox()
        spin.setRange(0.0, _LIMIT_MAX)
        spin.setDecimals(0)
        spin.setSingleStep(100_000_000)
        spin.setGroupSeparatorShown(True)
        return spin

    # --- mode gating -------------------------------------------------------

    def _apply_mode_gating(self) -> None:
        mode = self._mode.currentText()
        self._incremental_box.setEnabled(mode == MODE_INCREMENTAL)
        self._mismatch_box.setEnabled(mode == MODE_OPTIMIZE_BY_MISMATCH)
        self._iupac_box.setEnabled(mode in (MODE_INCREMENTAL, MODE_OPTIMIZE_BY_MISMATCH))

    def _on_mode_changed(self) -> None:
        self._apply_mode_gating()
        self.changed.emit()

    # --- get / set ---------------------------------------------------------

    def params(self) -> RunParameters:
        return RunParameters(
            tm=self._tm.value(),
            oligo=self._oligo.value(),
            na=self._na.value(),
            mg=self._mg.value(),
            dntp=self._dntp.value(),
            mode=self._mode.currentText(),
            fixed=self._fixed.isChecked(),
            orientation=self._orientation.currentText(),
            three_prime=self._three_prime.value(),
            target=self._target.value(),
            max_amb=self._max_amb.value(),
            max_seeds=self._max_seeds.value(),
            exclude_n=self._exclude_n.isChecked(),
            only_twofold=self._only_twofold.isChecked(),
            mismatch_mode=self._mismatch_mode.currentText(),
            n_oligos=self._n_oligos.value(),
            mismatches=self._mismatches.value(),
            ambiguities=self._ambiguities.value(),
            max_candidates=int(self._max_candidates.value()),
            max_work=int(self._max_work.value()),
            threads=self._threads.value(),
        )

    def set_params(self, params: RunParameters) -> None:
        """Load values without emitting a storm of change signals."""
        widgets = [
            self._tm, self._oligo, self._na, self._mg, self._dntp,
            self._mode, self._orientation, self._fixed, self._three_prime,
            self._target, self._max_amb, self._max_seeds,
            self._exclude_n, self._only_twofold,
            self._mismatch_mode, self._n_oligos, self._mismatches,
            self._ambiguities, self._max_candidates, self._max_work,
            self._threads,
        ]
        for w in widgets:
            w.blockSignals(True)
        try:
            self._tm.setValue(params.tm)
            self._oligo.setValue(params.oligo)
            self._na.setValue(params.na)
            self._mg.setValue(params.mg)
            self._dntp.setValue(params.dntp)
            self._mode.setCurrentText(params.mode if params.mode in MODES else MODES[0])
            self._orientation.setCurrentText(
                params.orientation if params.orientation in ORIENTATIONS else ORIENTATIONS[0]
            )
            self._fixed.setChecked(params.fixed)
            self._three_prime.setValue(params.three_prime)
            self._target.setValue(params.target)
            self._max_amb.setValue(params.max_amb)
            self._max_seeds.setValue(params.max_seeds)
            self._exclude_n.setChecked(params.exclude_n)
            self._only_twofold.setChecked(params.only_twofold)
            self._mismatch_mode.setCurrentText(
                params.mismatch_mode if params.mismatch_mode in MISMATCH_MODES
                else MISMATCH_MODES[0]
            )
            self._n_oligos.setValue(params.n_oligos)
            self._mismatches.setValue(params.mismatches)
            self._ambiguities.setValue(params.ambiguities)
            self._max_candidates.setValue(float(params.max_candidates))
            self._max_work.setValue(float(params.max_work))
            self._threads.setValue(params.threads)
        finally:
            for w in widgets:
                w.blockSignals(False)
        self._apply_mode_gating()
        self.changed.emit()
