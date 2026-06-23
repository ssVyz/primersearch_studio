"""Application entry point: build the QApplication and show the main window."""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from .config import AppConfig
from .ui.main_window import MainWindow


def apply_light_theme(app: QApplication) -> None:
    """Force a consistent light theme regardless of the OS (e.g. Windows dark mode).

    The app's accent colors (status banner, injected-row highlight, hint text)
    assume a light background, so we pin a light palette via the palette-respecting
    Fusion style and, where supported, request the Light color scheme so native
    bits (title bar, scroll bars) follow too.
    """
    app.setStyle("Fusion")

    # Qt 6.8+: ask the platform for a light scheme. Harmless / ignored elsewhere.
    try:
        app.styleHints().setColorScheme(Qt.ColorScheme.Light)
    except (AttributeError, TypeError):
        pass

    text = QColor("#1a1a1a")
    disabled = QColor("#a0a0a0")
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor("#f3f3f3"))
    palette.setColor(QPalette.WindowText, text)
    palette.setColor(QPalette.Base, QColor("#ffffff"))
    palette.setColor(QPalette.AlternateBase, QColor("#f5f5f5"))
    palette.setColor(QPalette.ToolTipBase, QColor("#ffffdc"))
    palette.setColor(QPalette.ToolTipText, text)
    palette.setColor(QPalette.Text, text)
    palette.setColor(QPalette.Button, QColor("#f0f0f0"))
    palette.setColor(QPalette.ButtonText, text)
    palette.setColor(QPalette.BrightText, QColor("#c0392b"))
    palette.setColor(QPalette.Highlight, QColor("#3a7bd5"))
    palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.Link, QColor("#0066cc"))
    palette.setColor(QPalette.PlaceholderText, QColor("#888888"))
    for role in (QPalette.Text, QPalette.WindowText, QPalette.ButtonText):
        palette.setColor(QPalette.Disabled, role, disabled)
    app.setPalette(palette)


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("primersearch_studio")
    app.setOrganizationName("primersearch_studio")
    apply_light_theme(app)

    config = AppConfig.load()
    window = MainWindow(config)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
