"""Left panel: the user's kept primer set (the ``--inject`` oligos)."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..models import Primer
from ..params import group_oligo
from .dialogs import MONOSPACE, PrimerDialog

_STALE_COLOR = QColor("#b9770e")


class KeptPrimersPanel(QWidget):
    """Editable list of kept primers, plus a combined-coverage summary."""

    changed = Signal()  # the set was mutated

    COLUMNS = ["Label", "Sequence", "Tm (°C)", "Position", "Cov %"]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._primers: list[Primer] = []
        self._spacing = False

        title = QLabel("Kept primers (injected into every run)")
        title.setStyleSheet("font-weight: 600;")

        self._table = QTableWidget(0, len(self.COLUMNS))
        self._table.setHorizontalHeaderLabels(self.COLUMNS)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Interactive)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        for col in range(2, len(self.COLUMNS)):
            header.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        self._table.doubleClicked.connect(lambda *_: self._edit_selected())
        self._table.itemSelectionChanged.connect(self._update_button_state)

        self._add_btn = QPushButton("Add…")
        self._edit_btn = QPushButton("Edit…")
        self._remove_btn = QPushButton("Remove")
        self._up_btn = QPushButton("↑")
        self._down_btn = QPushButton("↓")
        self._add_btn.clicked.connect(self._add)
        self._edit_btn.clicked.connect(self._edit_selected)
        self._remove_btn.clicked.connect(self._remove_selected)
        self._up_btn.clicked.connect(lambda: self._move(-1))
        self._down_btn.clicked.connect(lambda: self._move(1))

        btn_row = QHBoxLayout()
        for btn in (self._add_btn, self._edit_btn, self._remove_btn):
            btn_row.addWidget(btn)
        btn_row.addStretch(1)
        btn_row.addWidget(self._up_btn)
        btn_row.addWidget(self._down_btn)

        self._summary = QLabel("No primers kept yet.")
        self._summary.setWordWrap(True)
        self._summary.setStyleSheet("color: #555;")

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(self._table, 1)
        layout.addLayout(btn_row)
        layout.addWidget(self._summary)

        self._update_button_state()

    # --- data access -------------------------------------------------------

    def primers(self) -> list[Primer]:
        return list(self._primers)

    def sequences(self) -> list[str]:
        return [p.sequence for p in self._primers if p.sequence]

    def count(self) -> int:
        return len(self._primers)

    def set_spacing(self, enabled: bool) -> None:
        """Toggle triplet spacing in the sequence column (display only)."""
        self._spacing = enabled
        self._rebuild()

    def set_primers(self, primers: list[Primer]) -> None:
        self._primers = list(primers)
        self._rebuild()
        self.changed.emit()

    def add_primer(self, primer: Primer) -> bool:
        """Add a primer unless its sequence already exists. Returns True if added."""
        existing = {p.sequence for p in self._primers}
        if primer.sequence in existing:
            return False
        self._primers.append(primer)
        self._rebuild()
        self.changed.emit()
        return True

    # --- editing actions ---------------------------------------------------

    def _add(self) -> None:
        dialog = PrimerDialog(self)
        if dialog.exec():
            if not self.add_primer(dialog.result_primer()):
                self._flash_summary("That sequence is already in the set.")

    def _edit_selected(self) -> None:
        row = self._current_row()
        if row is None:
            return
        dialog = PrimerDialog(self, primer=self._primers[row])
        if dialog.exec():
            self._primers[row] = dialog.result_primer()
            self._rebuild()
            self._table.selectRow(row)
            self.changed.emit()

    def _remove_selected(self) -> None:
        rows = sorted(self._selected_rows(), reverse=True)
        if not rows:
            return
        for row in rows:
            del self._primers[row]
        self._rebuild()
        self.changed.emit()

    def _move(self, delta: int) -> None:
        row = self._current_row()
        if row is None:
            return
        target = row + delta
        if not (0 <= target < len(self._primers)):
            return
        self._primers[row], self._primers[target] = (
            self._primers[target],
            self._primers[row],
        )
        self._rebuild()
        self._table.selectRow(target)
        self.changed.emit()

    # --- selection helpers -------------------------------------------------

    def _selected_rows(self) -> list[int]:
        return sorted({idx.row() for idx in self._table.selectionModel().selectedRows()})

    def _current_row(self) -> int | None:
        rows = self._selected_rows()
        return rows[0] if rows else None

    def _update_button_state(self) -> None:
        has_sel = bool(self._selected_rows())
        self._edit_btn.setEnabled(len(self._selected_rows()) == 1)
        self._remove_btn.setEnabled(has_sel)
        self._up_btn.setEnabled(len(self._selected_rows()) == 1)
        self._down_btn.setEnabled(len(self._selected_rows()) == 1)

    # --- rendering ---------------------------------------------------------

    def _rebuild(self) -> None:
        self._table.setRowCount(len(self._primers))
        for row, primer in enumerate(self._primers):
            label = primer.label or f"(primer {row + 1})"
            self._set_item(row, 0, label)
            seq_text = group_oligo(primer.sequence) if self._spacing else primer.sequence
            self._set_item(row, 1, seq_text, mono=True)

            if primer.tm is not None:
                tm_text = f"{primer.tm:.1f}"
                pos_text = primer.position_label or "—"
                cov_text = (
                    f"{primer.coverage_pct:.1f}"
                    if primer.coverage_pct is not None
                    else "—"
                )
                if primer.stats_stale:
                    tm_text += " *"
            else:
                tm_text = pos_text = cov_text = "—"

            self._set_item(row, 2, tm_text, stale=primer.stats_stale)
            self._set_item(row, 3, pos_text, stale=primer.stats_stale)
            self._set_item(row, 4, cov_text, stale=primer.stats_stale)

            tooltip = primer.notes.strip()
            if primer.stats_stale:
                tooltip = ("(stats are stale — sequence edited since last run)\n" + tooltip).strip()
            if tooltip:
                for col in range(len(self.COLUMNS)):
                    item = self._table.item(row, col)
                    if item:
                        item.setToolTip(tooltip)

        self._update_button_state()
        self._refresh_summary()

    def _set_item(self, row: int, col: int, text: str, *, mono: bool = False, stale: bool = False) -> None:
        item = QTableWidgetItem(text)
        if mono:
            item.setFont(MONOSPACE)
        if stale:
            item.setForeground(_STALE_COLOR)
        self._table.setItem(row, col, item)

    # --- summary -----------------------------------------------------------

    def _refresh_summary(self) -> None:
        n = len(self._primers)
        if n == 0:
            self._summary.setText("No primers kept yet.")
        else:
            self._summary.setText(f"{n} primer{'s' if n != 1 else ''} kept.")

    def set_coverage_summary(self, total_sequences: int, kept_coverage_pct: float) -> None:
        """Update the summary after a run with the kept set's combined coverage."""
        n = len(self._primers)
        if n == 0:
            self._summary.setText("No primers kept yet.")
            return
        covered = round(kept_coverage_pct / 100.0 * total_sequences)
        complete = kept_coverage_pct >= 99.9995
        prefix = "✓ " if complete else ""
        self._summary.setStyleSheet(
            "color: #1e8449; font-weight: 600;" if complete else "color: #555;"
        )
        self._summary.setText(
            f"{prefix}{n} kept primer{'s' if n != 1 else ''} cover "
            f"{covered}/{total_sequences} sequences ({kept_coverage_pct:.1f}%)"
            + (" — full coverage." if complete else ".")
        )

    def _flash_summary(self, message: str) -> None:
        self._summary.setStyleSheet("color: #c0392b;")
        self._summary.setText(message)
