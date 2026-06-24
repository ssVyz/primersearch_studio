"""Right panel: primersearch output — preprocessing, settings, and the primer table."""

from __future__ import annotations

import csv
import io

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QGuiApplication
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..models import PrimerHit, RunResult
from ..params import group_oligo
from .dialogs import MONOSPACE, ResultsReportDialog

_INJECTED_BG = QColor("#eaf2fb")


class ResultsPanel(QWidget):
    """Renders a RunResult and lets the user pull primers across to the kept set."""

    keep_requested = Signal(list)  # list[PrimerHit]

    COLUMNS = ["#", "Sequence", "Cov", "Cov %", "Cumul %", "Tm (°C)", "Position", "Src"]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._result: RunResult | None = None
        self._spacing = False

        title = QLabel("Tool output")
        title.setStyleSheet("font-weight: 600;")

        self._message = QLabel("")
        self._message.setWordWrap(True)
        self._message.setVisible(False)
        self._message.setStyleSheet(
            "background: #fdebd0; color: #7e5109; padding: 6px; border-radius: 4px;"
        )

        self._info = QLabel("Run the tool to see primer suggestions here.")
        self._info.setWordWrap(True)
        self._info.setStyleSheet("color: #555;")

        self._table = QTableWidget(0, len(self.COLUMNS))
        self._table.setHorizontalHeaderLabels(self.COLUMNS)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        for col in (0, 2, 3, 4, 5, 6, 7):
            header.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        self._table.doubleClicked.connect(lambda *_: self._keep_selected())
        self._table.itemSelectionChanged.connect(self._update_button_state)

        self._keep_btn = QPushButton("Keep selected →")
        self._keep_btn.clicked.connect(self._keep_selected)
        self._copy_btn = QPushButton("Copy sequence")
        self._copy_btn.clicked.connect(self._copy_selected)
        self._text_btn = QPushButton("View as text")
        self._text_btn.setToolTip("Open the full result as copy-pasteable text")
        self._text_btn.clicked.connect(self.open_report_dialog)

        btn_row = QHBoxLayout()
        btn_row.addWidget(self._keep_btn)
        btn_row.addWidget(self._copy_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(self._text_btn)

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(self._message)
        layout.addWidget(self._info)
        layout.addWidget(self._table, 1)
        layout.addLayout(btn_row)

        self._update_button_state()

    # --- public API --------------------------------------------------------

    @property
    def result(self) -> RunResult | None:
        return self._result

    def set_spacing(self, enabled: bool) -> None:
        """Toggle triplet spacing in the sequence column (display only)."""
        self._spacing = enabled
        if self._result is None:
            return
        for row, hit in enumerate(self._result.primers):
            item = self._table.item(row, 1)
            if item is not None:
                item.setText(group_oligo(hit.sequence) if enabled else hit.sequence)

    def clear(self) -> None:
        self._result = None
        self._table.setRowCount(0)
        self._message.setVisible(False)
        self._info.setText("Run the tool to see primer suggestions here.")
        self._update_button_state()

    def show_result(self, result: RunResult) -> None:
        self._result = result
        self._info.setText(self._build_info(result))
        if result.message:
            self._message.setText(result.message)
            self._message.setVisible(True)
        else:
            self._message.setVisible(False)

        self._table.setRowCount(len(result.primers))
        for row, hit in enumerate(result.primers):
            self._set_item(row, 0, str(hit.index), hit)
            seq_text = group_oligo(hit.sequence) if self._spacing else hit.sequence
            self._set_item(row, 1, seq_text, hit, mono=True)
            self._set_item(row, 2, str(hit.coverage_count), hit)
            self._set_item(row, 3, f"{hit.coverage_pct:.1f}", hit)
            self._set_item(row, 4, f"{hit.cumulative_pct:.1f}", hit)
            self._set_item(row, 5, f"{hit.tm:.1f}", hit)
            self._set_item(row, 6, hit.position_label, hit)
            self._set_item(row, 7, "inject" if hit.injected else "search", hit)
        self._update_button_state()

    # --- info / preprocessing line ----------------------------------------

    @staticmethod
    def _build_info(result: RunResult) -> str:
        pre = result.preprocessing
        removed = pre.get("removed", {})
        total_removed = removed.get("total", 0)
        settings = result.settings
        parts = [
            f"{result.total_sequences} sequences covered",
            f"{result.primer_count} primers ({result.injected_count} injected)",
            f"final coverage {result.final_coverage_pct:.1f}%",
            f"mode {settings.get('mode', '?')}",
            f"orientation {settings.get('orientation', '?')}",
        ]
        line = " · ".join(parts)
        if total_removed:
            line += (
                f"\n⚠ {total_removed} input sequence(s) removed in preprocessing "
                f"(gaps {removed.get('gaps', 0)}, ambiguous {removed.get('ambiguous', 0)}, "
                f"invalid {removed.get('invalid', 0)}, wrong length {removed.get('wrong_length', 0)})."
            )
        return line

    # --- actions -----------------------------------------------------------

    def _selected_hits(self) -> list[PrimerHit]:
        if not self._result:
            return []
        rows = sorted({idx.row() for idx in self._table.selectionModel().selectedRows()})
        return [self._result.primers[r] for r in rows if 0 <= r < len(self._result.primers)]

    def _keep_selected(self) -> None:
        hits = self._selected_hits()
        if hits:
            self.keep_requested.emit(hits)

    def _copy_selected(self) -> None:
        hits = self._selected_hits()
        if hits:
            QGuiApplication.clipboard().setText("\n".join(h.sequence for h in hits))

    def open_report_dialog(self) -> None:
        """Open the full result as a copy-pasteable text report."""
        if self._result is None:
            QMessageBox.information(
                self, "No results", "Run primersearch first to produce results."
            )
            return
        dialog = ResultsReportDialog(self, self._result, spacing=self._spacing)
        dialog.exec()

    def _update_button_state(self) -> None:
        has_sel = bool(self._table.selectionModel().selectedRows()) if self._result else False
        self._keep_btn.setEnabled(has_sel)
        self._copy_btn.setEnabled(has_sel)
        self._text_btn.setEnabled(self._result is not None)

    # --- rendering helper --------------------------------------------------

    def _set_item(self, row: int, col: int, text: str, hit: PrimerHit, *, mono: bool = False) -> None:
        item = QTableWidgetItem(text)
        if mono:
            item.setFont(MONOSPACE)
        if hit.injected:
            item.setBackground(_INJECTED_BG)
        self._table.setItem(row, col, item)

    # --- CSV export --------------------------------------------------------

    def results_csv(self) -> str:
        """Serialize the current result table as CSV text (empty if no result)."""
        if not self._result:
            return ""
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(
            ["index", "sequence", "coverage_count", "coverage_pct",
             "cumulative_pct", "tm", "ambiguity_count", "injected", "position_label"]
        )
        for hit in self._result.primers:
            writer.writerow([
                hit.index, hit.sequence, hit.coverage_count,
                f"{hit.coverage_pct:.4f}", f"{hit.cumulative_pct:.4f}",
                f"{hit.tm:.4f}", hit.ambiguity_count,
                "true" if hit.injected else "false", hit.position_label,
            ])
        return buffer.getvalue()
