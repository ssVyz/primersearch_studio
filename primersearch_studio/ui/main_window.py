"""The main application window: layout, menus, run orchestration, persistence."""

from __future__ import annotations

import base64
from pathlib import Path

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QDockWidget,
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QSplitter,
)

from .. import __version__
from ..config import AppConfig
from ..fasta import FastaInfo, scan_fasta, write_primers_fasta
from ..models import PrimerHit, RunResult
from ..params import validate_oligo
from ..project import Project, ProjectError, PROJECT_SUFFIX
from ..runner import PrimerSearchRunner
from .dialogs import AppSettingsDialog, TextSetDialog, about_text
from .kept_primers_panel import KeptPrimersPanel
from .parameters_dock import ParametersPanel
from .results_panel import ResultsPanel

_PROJECT_FILTER = f"primersearch_studio project (*{PROJECT_SUFFIX})"
_FASTA_FILTER = "FASTA files (*.fasta *.fa *.fna *.txt);;All files (*)"


class MainWindow(QMainWindow):
    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self.config = config
        self.project = Project(params=config.defaults)
        self.runner = PrimerSearchRunner(self)
        self._alignment_info: FastaInfo | None = None
        self._dirty = False
        self._loading = False

        self.setWindowTitle("primersearch_studio")
        self._build_central()
        self._build_parameters_dock()
        self._build_statusbar()
        self._build_actions()
        self._build_menus()
        self._build_toolbar()
        self._connect_runner()

        self._apply_project_to_ui()
        self._restore_window_state()
        self._update_run_enabled()
        self._update_title()

    # ------------------------------------------------------------------ UI build

    def _build_central(self) -> None:
        self.kept_panel = KeptPrimersPanel()
        self.results_panel = ResultsPanel()
        self.kept_panel.changed.connect(self._mark_dirty)
        self.results_panel.keep_requested.connect(self._on_keep_requested)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.kept_panel)
        splitter.addWidget(self.results_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        splitter.setChildrenCollapsible(False)
        self._splitter = splitter
        self.setCentralWidget(splitter)

        self.kept_panel.set_spacing(self.config.triplet_spacing)
        self.results_panel.set_spacing(self.config.triplet_spacing)

    def _build_parameters_dock(self) -> None:
        self.parameters_panel = ParametersPanel()
        self.parameters_panel.changed.connect(self._on_params_changed)
        dock = QDockWidget("Parameters", self)
        dock.setObjectName("parameters_dock")
        dock.setWidget(self.parameters_panel)
        dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.addDockWidget(Qt.RightDockWidgetArea, dock)
        self._parameters_dock = dock

    def _build_statusbar(self) -> None:
        self._alignment_label = QLabel("No alignment loaded")
        self._run_status = QLabel("")
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)  # indeterminate
        self._progress.setMaximumWidth(160)
        self._progress.setVisible(False)
        bar = self.statusBar()
        bar.addWidget(self._alignment_label, 1)
        bar.addPermanentWidget(self._run_status)
        bar.addPermanentWidget(self._progress)

    def _build_actions(self) -> None:
        self.act_new = QAction("&New Project", self, shortcut=QKeySequence.New, triggered=self._new_project)
        self.act_open = QAction("&Open Project…", self, shortcut=QKeySequence.Open, triggered=self._open_project)
        self.act_save = QAction("&Save Project", self, shortcut=QKeySequence.Save, triggered=self._save_project)
        self.act_save_as = QAction("Save Project &As…", self, shortcut=QKeySequence.SaveAs, triggered=self._save_project_as)
        self.act_load_alignment = QAction("&Load Alignment…", self, shortcut=QKeySequence("Ctrl+L"), triggered=self._load_alignment)
        self.act_export_fasta = QAction("Export Primer Set as &FASTA…", self, triggered=self._export_fasta)
        self.act_export_csv = QAction("Export Results as &CSV…", self, triggered=self._export_csv)
        self.act_view_text = QAction("View Primer Set as &Text…", self, triggered=self._view_text)
        self.act_settings = QAction("App &Settings…", self, triggered=self._app_settings)
        self.act_quit = QAction("E&xit", self, shortcut=QKeySequence.Quit, triggered=self.close)

        self.act_update = QAction("&Update (run primersearch)", self, shortcut=QKeySequence("F5"), triggered=self._on_update)
        self.act_cancel = QAction("&Cancel run", self, shortcut=QKeySequence("Esc"), triggered=self._on_cancel)
        self.act_cancel.setEnabled(False)
        self.act_save_defaults = QAction("Save Current Parameters as &Defaults", self, triggered=self._save_defaults)

        self.act_spacing = QAction("&Triplet spacing (display)", self, checkable=True)
        self.act_spacing.setChecked(self.config.triplet_spacing)
        self.act_spacing.toggled.connect(self._toggle_spacing)

        self.act_about = QAction("&About", self, triggered=self._about)

    def _build_menus(self) -> None:
        menubar = self.menuBar()
        file_menu = menubar.addMenu("&File")
        file_menu.addActions([self.act_new, self.act_open, self.act_save, self.act_save_as])
        file_menu.addSeparator()
        file_menu.addAction(self.act_load_alignment)
        file_menu.addSeparator()
        file_menu.addActions([self.act_export_fasta, self.act_export_csv, self.act_view_text])
        file_menu.addSeparator()
        file_menu.addAction(self.act_settings)
        file_menu.addSeparator()
        file_menu.addAction(self.act_quit)

        run_menu = menubar.addMenu("&Run")
        run_menu.addActions([self.act_update, self.act_cancel])
        run_menu.addSeparator()
        run_menu.addAction(self.act_save_defaults)

        view_menu = menubar.addMenu("&View")
        view_menu.addAction(self.act_spacing)
        view_menu.addSeparator()
        view_menu.addAction(self._parameters_dock.toggleViewAction())

        help_menu = menubar.addMenu("&Help")
        help_menu.addAction(self.act_about)

    def _build_toolbar(self) -> None:
        toolbar = self.addToolBar("Main")
        toolbar.setObjectName("main_toolbar")
        toolbar.setMovable(False)
        toolbar.addAction(self.act_load_alignment)
        toolbar.addSeparator()
        toolbar.addAction(self.act_update)
        toolbar.addAction(self.act_cancel)

    def _connect_runner(self) -> None:
        self.runner.succeeded.connect(self._on_run_succeeded)
        self.runner.failed.connect(self._on_run_failed)
        self.runner.cancelled.connect(self._on_run_cancelled)
        self.runner.finished.connect(self._on_run_finished)

    # ------------------------------------------------------------------ dirty / title

    def _mark_dirty(self) -> None:
        if self._loading:
            return
        if not self._dirty:
            self._dirty = True
            self._update_title()

    def _on_params_changed(self) -> None:
        self._update_run_enabled()  # incremental params may toggle, etc.
        self._mark_dirty()

    def _update_title(self) -> None:
        marker = "•  " if self._dirty else ""
        self.setWindowTitle(f"{marker}{self.project.name} — primersearch_studio {__version__}")

    # ------------------------------------------------------------------ project lifecycle

    def _apply_project_to_ui(self) -> None:
        self._loading = True
        try:
            self.parameters_panel.set_params(self.project.params)
            self.kept_panel.set_primers(self.project.primers)
            self.results_panel.clear()
            self._alignment_info = None
            if self.project.alignment_path:
                self._scan_alignment(self.project.alignment_path, announce_missing=True)
            else:
                self._alignment_label.setText("No alignment loaded")
        finally:
            self._loading = False
        self._dirty = False
        self._update_run_enabled()
        self._update_title()

    def _sync_project_from_ui(self) -> None:
        self.project.params = self.parameters_panel.params()
        self.project.primers = self.kept_panel.primers()
        # alignment_path is updated directly when loading an alignment.

    def _confirm_discard(self) -> bool:
        """Return True if it's safe to discard the current project."""
        if not self._dirty:
            return True
        choice = QMessageBox.question(
            self, "Unsaved changes",
            "This project has unsaved changes. Save before continuing?",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            QMessageBox.Save,
        )
        if choice == QMessageBox.Cancel:
            return False
        if choice == QMessageBox.Save:
            return self._save_project()
        return True

    def _new_project(self) -> None:
        if not self._confirm_discard():
            return
        self.project = Project(params=self.config.defaults)
        self._apply_project_to_ui()

    def _open_project(self) -> None:
        if not self._confirm_discard():
            return
        start_dir = self.config.last_project_dir or str(Path.home())
        path, _ = QFileDialog.getOpenFileName(self, "Open Project", start_dir, _PROJECT_FILTER)
        if not path:
            return
        try:
            project = Project.load(path)
        except ProjectError as exc:
            QMessageBox.critical(self, "Cannot open project", str(exc))
            return
        self.project = project
        self.config.last_project = path
        self.config.last_project_dir = str(Path(path).parent)
        self._apply_project_to_ui()

    def _save_project(self) -> bool:
        if not self.project.path:
            return self._save_project_as()
        return self._write_project(self.project.path)

    def _save_project_as(self) -> bool:
        start_dir = self.config.last_project_dir or str(Path.home())
        suggested = str(Path(start_dir) / (self.project.name + PROJECT_SUFFIX))
        path, _ = QFileDialog.getSaveFileName(self, "Save Project As", suggested, _PROJECT_FILTER)
        if not path:
            return False
        return self._write_project(path)

    def _write_project(self, path: str) -> bool:
        self._sync_project_from_ui()
        try:
            self.project.save(path)
        except OSError as exc:
            QMessageBox.critical(self, "Cannot save project", str(exc))
            return False
        self.config.last_project = self.project.path or path
        self.config.last_project_dir = str(Path(path).parent)
        self._dirty = False
        self._update_title()
        self._run_status.setText("Project saved.")
        return True

    # ------------------------------------------------------------------ alignment

    def _load_alignment(self) -> None:
        start_dir = self.config.last_alignment_dir or str(Path.home())
        path, _ = QFileDialog.getOpenFileName(self, "Load Alignment (FASTA)", start_dir, _FASTA_FILTER)
        if not path:
            return
        self.config.last_alignment_dir = str(Path(path).parent)
        if self._scan_alignment(path):
            self.project.alignment_path = path
            self._mark_dirty()
        self._update_run_enabled()

    def _scan_alignment(self, path: str, *, announce_missing: bool = False) -> bool:
        if not Path(path).exists():
            self._alignment_info = None
            self._alignment_label.setText(f"⚠ alignment not found: {path}")
            if announce_missing:
                self._run_status.setText("Referenced alignment is missing.")
            return False
        try:
            info = scan_fasta(path)
        except OSError as exc:
            QMessageBox.critical(self, "Cannot read alignment", str(exc))
            return False
        self._alignment_info = info
        name = Path(path).name
        self._alignment_label.setText(f"{name} — {info.summary()}")
        if info.sequence_count == 0:
            QMessageBox.warning(
                self, "No sequences",
                "No FASTA sequences were found in that file. primersearch needs an "
                "aligned FASTA (>header lines followed by sequence).",
            )
        elif not info.is_aligned:
            self._alignment_label.setText(
                f"⚠ {name} — {info.summary()}"
            )
        return True

    # ------------------------------------------------------------------ run

    def _update_run_enabled(self) -> None:
        can_run = (
            self._alignment_info is not None
            and self._alignment_info.sequence_count > 0
            and not self.runner.is_running()
        )
        self.act_update.setEnabled(can_run)

    def _on_update(self) -> None:
        if self.runner.is_running():
            return
        if not self._alignment_info or not self.project.alignment_path:
            QMessageBox.information(self, "No alignment", "Load an alignment FASTA first.")
            return
        if not Path(self.project.alignment_path).exists():
            QMessageBox.warning(self, "Alignment missing",
                                "The alignment file no longer exists. Load it again.")
            return

        injected = self.kept_panel.sequences()
        for seq in injected:
            err = validate_oligo(seq)
            if err:
                QMessageBox.warning(self, "Invalid kept primer",
                                    f"Sequence {seq!r}: {err}")
                return

        params = self.parameters_panel.params()
        binary = self.config.resolved_binary()

        self._set_running_ui(True)
        self._run_status.setText("Running primersearch…")
        try:
            self.runner.run(binary, self.project.alignment_path, params, injected)
        except RuntimeError as exc:
            self._set_running_ui(False)
            QMessageBox.warning(self, "Cannot run", str(exc))

    def _on_cancel(self) -> None:
        if self.runner.is_running():
            self._run_status.setText("Cancelling…")
            self.runner.cancel()

    def _set_running_ui(self, running: bool) -> None:
        self._progress.setVisible(running)
        self.act_cancel.setEnabled(running)
        self.act_update.setEnabled(not running and self._alignment_info is not None
                                   and self._alignment_info.sequence_count > 0)
        self.act_load_alignment.setEnabled(not running)

    def _on_run_succeeded(self, result: RunResult) -> None:
        self.results_panel.show_result(result)
        self.kept_panel.set_coverage_summary(result.total_sequences, result.kept_coverage_pct)
        msg = f"Done — {result.primer_count} primers, {result.final_coverage_pct:.1f}% coverage."
        if result.message:
            msg += " (see note above results)"
        self._run_status.setText(msg)

    def _on_run_failed(self, message: str) -> None:
        self._run_status.setText("Run failed.")
        QMessageBox.critical(self, "primersearch error", message)

    def _on_run_cancelled(self) -> None:
        self._run_status.setText("Run cancelled.")

    def _on_run_finished(self) -> None:
        self._set_running_ui(False)
        self._update_run_enabled()

    # ------------------------------------------------------------------ keep / exports

    def _on_keep_requested(self, hits: list) -> None:
        added = 0
        skipped = 0
        for hit in hits:
            if isinstance(hit, PrimerHit):
                if self.kept_panel.add_primer(hit.as_primer()):
                    added += 1
                else:
                    skipped += 1
        parts = []
        if added:
            parts.append(f"kept {added}")
        if skipped:
            parts.append(f"{skipped} already in set")
        self._run_status.setText("; ".join(parts) or "Nothing to keep.")

    def _view_text(self) -> None:
        dialog = TextSetDialog(self, self.kept_panel.primers())
        dialog.exec()

    def _export_fasta(self) -> None:
        if self.kept_panel.count() == 0:
            QMessageBox.information(self, "Nothing to export", "There are no kept primers.")
            return
        start_dir = self.config.last_export_dir or str(Path.home())
        suggested = str(Path(start_dir) / f"{self.project.name}_primers.fasta")
        path, _ = QFileDialog.getSaveFileName(self, "Export Primer Set as FASTA",
                                              suggested, _FASTA_FILTER)
        if not path:
            return
        self.config.last_export_dir = str(Path(path).parent)
        try:
            write_primers_fasta(path, self.kept_panel.primers())
        except OSError as exc:
            QMessageBox.critical(self, "Export failed", str(exc))
            return
        self._run_status.setText(f"Exported {self.kept_panel.count()} primers to FASTA.")

    def _export_csv(self) -> None:
        csv_text = self.results_panel.results_csv()
        if not csv_text:
            QMessageBox.information(self, "Nothing to export",
                                    "Run primersearch first to produce results.")
            return
        start_dir = self.config.last_export_dir or str(Path.home())
        suggested = str(Path(start_dir) / f"{self.project.name}_results.csv")
        path, _ = QFileDialog.getSaveFileName(self, "Export Results as CSV", suggested,
                                              "CSV files (*.csv);;All files (*)")
        if not path:
            return
        self.config.last_export_dir = str(Path(path).parent)
        try:
            with open(path, "w", encoding="utf-8", newline="") as handle:
                handle.write(csv_text)
        except OSError as exc:
            QMessageBox.critical(self, "Export failed", str(exc))
            return
        self._run_status.setText("Exported results to CSV.")

    # ------------------------------------------------------------------ settings / about

    def _app_settings(self) -> None:
        dialog = AppSettingsDialog(self, self.config.binary_path)
        if dialog.exec():
            self.config.binary_path = dialog.binary_path()
            self._persist_config()
            self._run_status.setText("App settings saved.")

    def _save_defaults(self) -> None:
        self.config.defaults = self.parameters_panel.params()
        self._persist_config()
        self._run_status.setText("Saved current parameters as defaults.")

    def _toggle_spacing(self, enabled: bool) -> None:
        self.config.triplet_spacing = enabled
        self.kept_panel.set_spacing(enabled)
        self.results_panel.set_spacing(enabled)
        self._persist_config()

    def _about(self) -> None:
        QMessageBox.about(self, "About primersearch_studio", about_text())

    # ------------------------------------------------------------------ config / window state

    def _persist_config(self) -> None:
        try:
            self.config.save()
        except OSError:
            pass  # never block the UI on a config write failure

    def _restore_window_state(self) -> None:
        if self.config.window_geometry:
            self.restoreGeometry(QByteArray.fromBase64(self.config.window_geometry.encode("ascii")))
        else:
            self.resize(1180, 720)
        if self.config.window_state:
            self.restoreState(QByteArray.fromBase64(self.config.window_state.encode("ascii")))

    def _save_window_state(self) -> None:
        self.config.window_geometry = bytes(self.saveGeometry().toBase64()).decode("ascii")
        self.config.window_state = bytes(self.saveState().toBase64()).decode("ascii")

    # ------------------------------------------------------------------ close

    def closeEvent(self, event) -> None:
        if self.runner.is_running():
            self.runner.cancel()
        if not self._confirm_discard():
            event.ignore()
            return
        self._save_window_state()
        self._persist_config()
        event.accept()
