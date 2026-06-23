"""App-level configuration, stored as TOML in the project root.

Per the design decisions, the root config holds only *app-level* state: the
primersearch binary location, the default run parameters, and window/layout
state. The working session (kept primers + alignment + per-run params) lives in
separate ``.psproj`` project files (see :mod:`primersearch_studio.project`).
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

import tomli_w

from .params import RunParameters

CONFIG_FILENAME = "primersearch_studio.toml"


def project_root() -> Path:
    """Repo root (the directory that contains this package), independent of cwd."""
    return Path(__file__).resolve().parent.parent


def config_path() -> Path:
    return project_root() / CONFIG_FILENAME


@dataclass
class AppConfig:
    """Persisted application settings."""

    binary_path: str = ""  # empty => resolve "primersearch" on PATH
    defaults: RunParameters = field(default_factory=RunParameters)
    triplet_spacing: bool = False  # display oligos grouped in threes (AAT TGT …)
    last_project: str = ""
    last_project_dir: str = ""
    last_alignment_dir: str = ""
    last_export_dir: str = ""
    window_geometry: str = ""  # base64-encoded QByteArray
    window_state: str = ""  # base64-encoded QByteArray

    # --- binary resolution -------------------------------------------------

    def resolved_binary(self) -> str:
        """The command to invoke: the configured path, or bare ``primersearch``."""
        return self.binary_path.strip() or "primersearch"

    # --- persistence -------------------------------------------------------

    @classmethod
    def load(cls, path: Path | None = None) -> "AppConfig":
        path = path or config_path()
        if not path.exists():
            return cls()
        try:
            with open(path, "rb") as handle:
                data = tomllib.load(handle)
        except (OSError, tomllib.TOMLDecodeError):
            # A corrupt config should never block startup; fall back to defaults.
            return cls()

        window = data.get("window", {})
        recent = data.get("recent", {})
        return cls(
            binary_path=str(data.get("binary_path", "")),
            defaults=RunParameters.from_dict(data.get("defaults")),
            triplet_spacing=bool(data.get("triplet_spacing", False)),
            last_project=str(recent.get("last_project", "")),
            last_project_dir=str(recent.get("last_project_dir", "")),
            last_alignment_dir=str(recent.get("last_alignment_dir", "")),
            last_export_dir=str(recent.get("last_export_dir", "")),
            window_geometry=str(window.get("geometry", "")),
            window_state=str(window.get("state", "")),
        )

    def save(self, path: Path | None = None) -> None:
        path = path or config_path()
        data = {
            "binary_path": self.binary_path,
            "triplet_spacing": self.triplet_spacing,
            "defaults": self.defaults.to_dict(),
            "recent": {
                "last_project": self.last_project,
                "last_project_dir": self.last_project_dir,
                "last_alignment_dir": self.last_alignment_dir,
                "last_export_dir": self.last_export_dir,
            },
            "window": {
                "geometry": self.window_geometry,
                "state": self.window_state,
            },
        }
        with open(path, "wb") as handle:
            tomli_w.dump(data, handle)
