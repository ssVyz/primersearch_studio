"""Working-session persistence: the ``.psproj`` project file (JSON).

A project bundles the loaded alignment path, the run parameters, and the kept
primer set. It is independent of the app-level config so users can keep many
primer-design sessions side by side.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .models import Primer
from .params import RunParameters

PROJECT_SUFFIX = ".psproj"
PROJECT_SCHEMA = 1


class ProjectError(ValueError):
    """Raised when a project file is malformed or has an unknown schema."""


@dataclass
class Project:
    """The in-memory working session."""

    alignment_path: str = ""
    params: RunParameters = field(default_factory=RunParameters)
    primers: list[Primer] = field(default_factory=list)
    excludes: list[Primer] = field(default_factory=list)  # --exclude 3′ signatures
    path: str | None = None  # where this project was last saved/loaded

    @property
    def name(self) -> str:
        return Path(self.path).stem if self.path else "Untitled"

    def to_dict(self) -> dict:
        return {
            "schema": PROJECT_SCHEMA,
            "alignment_path": self.alignment_path,
            "params": self.params.to_dict(),
            "primers": [p.to_dict() for p in self.primers],
            "excludes": [p.to_dict() for p in self.excludes],
        }

    def save(self, path: str | Path) -> None:
        path = Path(path)
        if path.suffix != PROJECT_SUFFIX:
            path = path.with_suffix(PROJECT_SUFFIX)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(self.to_dict(), handle, indent=2)
        self.path = str(path)

    @classmethod
    def load(cls, path: str | Path) -> "Project":
        path = Path(path)
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            raise ProjectError(f"could not read project: {exc}") from exc

        if not isinstance(data, dict):
            raise ProjectError("project file is not a JSON object")
        schema = data.get("schema")
        if schema != PROJECT_SCHEMA:
            raise ProjectError(
                f"unsupported project schema {schema!r} (this build expects {PROJECT_SCHEMA})"
            )
        return cls(
            alignment_path=str(data.get("alignment_path", "")),
            params=RunParameters.from_dict(data.get("params")),
            primers=[Primer.from_dict(p) for p in data.get("primers", [])],
            excludes=[Primer.from_dict(p) for p in data.get("excludes", [])],
            path=str(path),
        )
