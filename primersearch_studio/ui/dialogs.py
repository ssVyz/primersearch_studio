"""Modal dialogs: add/edit a primer, app settings, and a copy-as-text view."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from ..fasta import primers_to_fasta
from ..models import Primer, RunResult
from ..params import normalize_oligo, validate_oligo
from ..report import format_result_report
from ..runner import check_binary

MONOSPACE = QFont("Consolas")
MONOSPACE.setStyleHint(QFont.Monospace)


class PrimerDialog(QDialog):
    """Add or edit a kept primer (label, sequence, notes) with live validation."""

    def __init__(self, parent: QWidget | None = None, primer: Primer | None = None) -> None:
        super().__init__(parent)
        self._original = primer
        self.setWindowTitle("Edit primer" if primer else "Add primer")
        self.setMinimumWidth(460)

        self._label = QLineEdit(primer.label if primer else "")
        self._sequence = QLineEdit(primer.sequence if primer else "")
        self._sequence.setFont(MONOSPACE)
        self._notes = QPlainTextEdit(primer.notes if primer else "")
        self._notes.setFixedHeight(70)
        self._error = QLabel("")
        self._error.setStyleSheet("color: #c0392b;")
        self._error.setWordWrap(True)

        form = QFormLayout()
        form.addRow("Label:", self._label)
        form.addRow("Sequence:", self._sequence)
        form.addRow("Notes:", self._notes)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self._error)
        layout.addWidget(self._buttons)

        self._sequence.textChanged.connect(self._revalidate)
        self._revalidate()

    def _revalidate(self) -> None:
        error = validate_oligo(self._sequence.text())
        self._error.setText(error or "")
        self._buttons.button(QDialogButtonBox.Ok).setEnabled(error is None)

    def result_primer(self) -> Primer:
        """Build the resulting primer; stats are cleared if the sequence changed."""
        sequence = normalize_oligo(self._sequence.text())
        label = self._label.text().strip()
        notes = self._notes.toPlainText().strip()
        if self._original is None:
            return Primer(sequence=sequence, label=label, notes=notes)

        primer = self._original
        changed = sequence != primer.sequence
        primer.sequence = sequence
        primer.label = label
        primer.notes = notes
        if changed and primer.tm is not None:
            primer.stats_stale = True
        return primer


class AppSettingsDialog(QDialog):
    """Configure the primersearch binary location (app-level setting)."""

    def __init__(self, parent: QWidget | None = None, binary_path: str = "") -> None:
        super().__init__(parent)
        self.setWindowTitle("App Settings")
        self.setMinimumWidth(560)

        self._path = QLineEdit(binary_path)
        self._path.setPlaceholderText("(empty — use 'primersearch' from PATH)")
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse)
        test = QPushButton("Test")
        test.clicked.connect(self._test)

        path_row = QHBoxLayout()
        path_row.addWidget(self._path, 1)
        path_row.addWidget(browse)
        path_row.addWidget(test)

        self._status = QLabel("")
        self._status.setWordWrap(True)

        hint = QLabel(
            "Path to the primersearch executable. Leave empty to use the copy on "
            "your PATH. Use Test to verify it responds to --version."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #555;")

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        form = QFormLayout()
        form.addRow("Binary:", path_row)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(hint)
        layout.addWidget(self._status)
        layout.addWidget(buttons)

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Locate primersearch executable")
        if path:
            self._path.setText(path)

    def _test(self) -> None:
        binary = self._path.text().strip() or "primersearch"
        ok, message = check_binary(binary)
        if ok:
            self._status.setStyleSheet("color: #1e8449;")
            self._status.setText(f"OK — {message}")
        else:
            self._status.setStyleSheet("color: #c0392b;")
            self._status.setText(f"Failed — {message}")

    def binary_path(self) -> str:
        return self._path.text().strip()


class TextSetDialog(QDialog):
    """Show the kept primer set as copy-pasteable text (FASTA or plain list)."""

    def __init__(self, parent: QWidget | None = None, primers: list[Primer] | None = None) -> None:
        super().__init__(parent)
        self._primers = primers or []
        self.setWindowTitle("Primer set as text")
        self.resize(560, 460)

        self._format = QComboBox()
        self._format.addItems(["FASTA", "Sequences only", "Label<TAB>Sequence"])
        self._format.currentIndexChanged.connect(self._render)

        self._text = QPlainTextEdit()
        self._text.setReadOnly(True)
        self._text.setFont(MONOSPACE)
        self._text.setLineWrapMode(QPlainTextEdit.NoWrap)

        copy = QPushButton("Copy to clipboard")
        copy.clicked.connect(self._copy)
        close = QPushButton("Close")
        close.clicked.connect(self.accept)

        btn_row = QHBoxLayout()
        btn_row.addWidget(QLabel("Format:"))
        btn_row.addWidget(self._format)
        btn_row.addStretch(1)
        btn_row.addWidget(copy)
        btn_row.addWidget(close)

        layout = QVBoxLayout(self)
        layout.addWidget(self._text, 1)
        layout.addLayout(btn_row)

        self._render()

    def _render(self) -> None:
        kind = self._format.currentText()
        if kind == "FASTA":
            text = primers_to_fasta(self._primers)
        elif kind == "Sequences only":
            text = "\n".join(p.sequence for p in self._primers)
            text += "\n" if self._primers else ""
        else:
            rows = [f"{p.label or f'primer_{i}'}\t{p.sequence}"
                    for i, p in enumerate(self._primers, start=1)]
            text = "\n".join(rows) + ("\n" if rows else "")
        self._text.setPlainText(text)

    def _copy(self) -> None:
        QGuiApplication.clipboard().setText(self._text.toPlainText())


class ResultsReportDialog(QDialog):
    """Show the full run result as the copy-pasteable text report the CLI emits."""

    def __init__(
        self,
        parent: QWidget | None = None,
        result: RunResult | None = None,
        *,
        spacing: bool = True,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Results as text")
        self.resize(760, 620)

        self._text = QPlainTextEdit()
        self._text.setReadOnly(True)
        self._text.setFont(MONOSPACE)
        self._text.setLineWrapMode(QPlainTextEdit.NoWrap)
        if result is not None:
            self._text.setPlainText(format_result_report(result, spacing=spacing))

        copy = QPushButton("Copy to clipboard")
        copy.clicked.connect(self._copy)
        close = QPushButton("Close")
        close.clicked.connect(self.accept)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_row.addWidget(copy)
        btn_row.addWidget(close)

        layout = QVBoxLayout(self)
        layout.addWidget(self._text, 1)
        layout.addLayout(btn_row)

    def _copy(self) -> None:
        QGuiApplication.clipboard().setText(self._text.toPlainText())


def about_text() -> str:
    return (
        f"<h3>primersearch_studio {__version__}</h3>"
        "<p>A GUI front-end for the <b>primersearch</b> primer-design tool.</p>"
        "<p>Build a primer set iteratively: keep primers on the left, run the "
        "tool to see suggestions on the right, and pull good candidates across "
        "until coverage reaches 100%.</p>"
    )
