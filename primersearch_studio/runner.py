"""Drive primersearch as a child process, off the UI thread.

A :class:`QThread` worker runs ``subprocess.Popen`` so the GUI stays responsive,
the console window never flashes on Windows (``CREATE_NO_WINDOW``), and
cancellation is a clean ``kill()`` (the tool is CPU-bound, so killing is safe).

Runs pass ``--progress jsonl``: primersearch then writes one JSON object per
line to stderr (``progress`` events while it works, an ``error`` event before a
non-zero exit) while stdout carries only the result document. The worker reads
stderr line by line as it arrives and forwards progress to the UI; stdout is
drained on a helper thread so a large result can never block the pipe.
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading

from PySide6.QtCore import QObject, QThread, Signal

from .models import ResultError, RunProgress, RunResult
from .params import RunParameters, build_cli_args

# Always-on flags that make a run machine-friendly, deterministic, and
# side-effect-free (Section 2 of the integration guide), plus the
# machine-readable progress stream on stderr (primersearch >= 0.1.1).
BASE_FLAGS = ["--format", "json", "--no-config", "--silent", "--progress", "jsonl"]

_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)


def _popen_kwargs() -> dict:
    kwargs: dict = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = _CREATE_NO_WINDOW
    return kwargs


class _RunWorker(QThread):
    """Executes one primersearch command and reports the parsed outcome."""

    succeeded = Signal(object)  # RunResult
    failed = Signal(str)
    cancelled = Signal()
    progress = Signal(object)  # RunProgress

    def __init__(self, command: list[str], parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._command = command
        self._proc: subprocess.Popen | None = None
        self._cancel_requested = False
        self._lock = threading.Lock()

    def cancel(self) -> None:
        with self._lock:
            self._cancel_requested = True
            if self._proc is not None and self._proc.poll() is None:
                try:
                    self._proc.kill()
                except OSError:
                    pass

    def run(self) -> None:  # executes in the worker thread
        try:
            with self._lock:
                if self._cancel_requested:
                    self.cancelled.emit()
                    return
                self._proc = subprocess.Popen(
                    self._command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    **_popen_kwargs(),
                )
            stdout_b, error_message, plain_stderr = self._collect_output(self._proc)
        except FileNotFoundError:
            self.failed.emit(
                "could not start primersearch — check the binary path in App Settings"
            )
            return
        except OSError as exc:
            self.failed.emit(f"could not start primersearch: {exc}")
            return

        if self._cancel_requested:
            self.cancelled.emit()
            return

        stdout = (stdout_b or b"").decode("utf-8", errors="replace")
        returncode = self._proc.returncode

        if returncode != 0:
            if returncode == 2 and "--progress" in plain_stderr:
                # clap rejected the flag: a build from before the progress stream.
                self.failed.emit(
                    "This primersearch build does not support --progress (live "
                    "progress needs primersearch 0.1.1 or newer). Update primersearch "
                    "or point App Settings at a newer build.\n\n" + plain_stderr
                )
                return
            self.failed.emit(
                error_message or plain_stderr or f"primersearch exited with code {returncode}"
            )
            return

        try:
            doc = json.loads(stdout)
        except json.JSONDecodeError as exc:
            self.failed.emit(f"could not parse primersearch JSON output: {exc}")
            return

        try:
            result = RunResult.from_doc(doc)
        except ResultError as exc:
            self.failed.emit(str(exc))
            return

        self.succeeded.emit(result)

    def _collect_output(self, proc: subprocess.Popen) -> tuple[bytes, str, str]:
        """Stream stderr until EOF, emitting progress; return
        ``(stdout bytes, JSON error message, remaining plain stderr text)``.
        """
        chunks: list[bytes] = []
        drain = threading.Thread(target=lambda: chunks.append(proc.stdout.read()), daemon=True)
        drain.start()

        error_message = ""
        plain: list[str] = []
        for raw in proc.stderr:
            line = raw.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            event = _parse_event(line)
            if event is None:
                plain.append(line)  # clap errors, the plain "error: …" line, info
            elif event.get("type") == "progress":
                self.progress.emit(RunProgress.from_dict(event))
            elif event.get("type") == "error":
                error_message = str(event.get("message", "")).strip()

        drain.join()
        proc.wait()
        stdout = chunks[0] if chunks else b""
        if error_message:
            # The JSON error repeats the plain "error: …" line; keep only the rest.
            plain = [ln for ln in plain if ln != f"error: {error_message}"]
        return stdout, error_message, "\n".join(plain)


def _parse_event(line: str) -> dict | None:
    """A ``--progress jsonl`` event, or ``None`` for a plain-text stderr line."""
    if not line.startswith("{"):
        return None
    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        return None
    return event if isinstance(event, dict) else None


class PrimerSearchRunner(QObject):
    """Runs a single primersearch invocation at a time and reports the outcome."""

    succeeded = Signal(object)  # RunResult
    failed = Signal(str)
    cancelled = Signal()
    progress = Signal(object)  # RunProgress, while a run is in progress
    finished = Signal()  # always emitted after succeeded/failed/cancelled

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._worker: _RunWorker | None = None
        self._command: list[str] = []

    # --- public API --------------------------------------------------------

    def is_running(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    @property
    def last_command(self) -> list[str]:
        return list(self._command)

    def run(
        self,
        binary: str,
        fasta_path: str,
        params: RunParameters,
        injected: list[str] | None = None,
        excluded: list[str] | None = None,
    ) -> None:
        if self.is_running():
            raise RuntimeError("a run is already in progress")

        self._command = [
            binary,
            fasta_path,
            *BASE_FLAGS,
            *build_cli_args(params, injected, excluded),
        ]

        worker = _RunWorker(self._command, self)
        worker.succeeded.connect(self.succeeded)
        worker.failed.connect(self.failed)
        worker.cancelled.connect(self.cancelled)
        worker.progress.connect(self.progress)
        worker.finished.connect(self._on_worker_finished)
        self._worker = worker
        worker.start()

    def cancel(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._worker.cancel()

    # --- internals ---------------------------------------------------------

    def _on_worker_finished(self) -> None:
        worker = self._worker
        self._worker = None
        if worker is not None:
            worker.deleteLater()
        self.finished.emit()


def check_binary(binary: str, timeout: float = 10.0) -> tuple[bool, str]:
    """Synchronously probe ``binary --version`` for the App Settings 'Test' button."""
    try:
        proc = subprocess.run(
            [binary, "--version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
            **_popen_kwargs(),
        )
    except FileNotFoundError:
        return False, f"not found: {binary!r}"
    except OSError as exc:
        return False, f"could not run: {exc}"
    except subprocess.TimeoutExpired:
        return False, "timed out probing --version"

    if proc.returncode != 0:
        return False, (proc.stderr or proc.stdout or "non-zero exit").strip()
    return True, (proc.stdout or proc.stderr or "").strip()
