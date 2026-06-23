"""Convenience launcher: ``uv run python main.py`` starts the GUI."""

from primersearch_studio.app import main

if __name__ == "__main__":
    raise SystemExit(main())
