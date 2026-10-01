"""Excluded 3′ signatures: oligos the search must never reproduce (``--exclude``).

Any discovered candidate whose 3′ end matches one of these (aligned at the 3′
end, IUPAC set-intersection over the shorter length) is dropped and the search
picks the best non-excluded candidate instead. These are *filters*, not inputs:
they are never emitted and never appear in the results.

Entries reuse the :class:`Primer` model (and :class:`PrimerDialog`) for their
label/sequence/notes; the Tm/coverage stat fields stay unused.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
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


class ExcludedPrimersPanel(QWidget):
    """Editable list of excluded 3′ signatures passed as ``--exclude`` oligos."""

    changed = Signal()  # the set was mutated

    COLUMNS = ["Label", "Sequence"]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._primers: list[Primer] = []
        self._spacing = False

        title = QLabel("Excluded 3′ signatures")
        title.setStyleSheet("font-weight: 600;")

        hint = QLabel(
            "Candidates whose 3′ end matches one of these are dropped, so new "
            "primers avoid the 3′ ends of primers you use elsewhere. Give them in "
            "the same orientation as the run (for reverse runs, the reverse-"
            "complement form you would order), just like kept primers. Ignored in "
            "fixed-slice mode, except in optimize-by-mismatch mode."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #555;")

        self._table = QTableWidget(0, len(self.COLUMNS))
        self._table.setHorizontalHeaderLabels(self.COLUMNS)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Interactive)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        self._table.doubleClicked.connect(lambda *_: self._edit_selected())
        self._table.itemSelectionChanged.connect(self._update_button_state)

        self._add_btn = QPushButton("Add…")
        self._edit_btn = QPushButton("Edit…")
        self._remove_btn = QPushButton("Remove")
        self._add_btn.clicked.connect(self._add)
        self._edit_btn.clicked.connect(self._edit_selected)
        self._remove_btn.clicked.connect(self._remove_selected)

        btn_row = QHBoxLayout()
        for btn in (self._add_btn, self._edit_btn, self._remove_btn):
            btn_row.addWidget(btn)
        btn_row.addStretch(1)

        self._summary = QLabel("No signatures excluded.")
        self._summary.setWordWrap(True)
        self._summary.setStyleSheet("color: #555;")

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(hint)
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
        """Add an oligo unless its sequence already exists. Returns True if added."""
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
                self._flash_summary("That sequence is already excluded.")

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

    # --- selection helpers -------------------------------------------------

    def _selected_rows(self) -> list[int]:
        return sorted({idx.row() for idx in self._table.selectionModel().selectedRows()})

    def _current_row(self) -> int | None:
        rows = self._selected_rows()
        return rows[0] if rows else None

    def _update_button_state(self) -> None:
        rows = self._selected_rows()
        self._edit_btn.setEnabled(len(rows) == 1)
        self._remove_btn.setEnabled(bool(rows))

    # --- rendering ---------------------------------------------------------

    def _rebuild(self) -> None:
        self._table.setRowCount(len(self._primers))
        for row, primer in enumerate(self._primers):
            label = primer.label or f"(excluded {row + 1})"
            self._set_item(row, 0, label)
            seq_text = group_oligo(primer.sequence) if self._spacing else primer.sequence
            self._set_item(row, 1, seq_text, mono=True)

            tooltip = primer.notes.strip()
            if tooltip:
                for col in range(len(self.COLUMNS)):
                    item = self._table.item(row, col)
                    if item:
                        item.setToolTip(tooltip)

        self._update_button_state()
        self._refresh_summary()

    def _set_item(self, row: int, col: int, text: str, *, mono: bool = False) -> None:
        item = QTableWidgetItem(text)
        if mono:
            item.setFont(MONOSPACE)
        self._table.setItem(row, col, item)

    # --- summary -----------------------------------------------------------

    def _refresh_summary(self) -> None:
        n = len(self._primers)
        if n == 0:
            self._summary.setStyleSheet("color: #555;")
            self._summary.setText("No signatures excluded.")
        else:
            self._summary.setStyleSheet("color: #555;")
            self._summary.setText(
                f"{n} signature{'s' if n != 1 else ''} excluded from the search."
            )

    def _flash_summary(self, message: str) -> None:
        self._summary.setStyleSheet("color: #c0392b;")
        self._summary.setText(message)
