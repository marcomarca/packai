"""Event-driven project monitoring with a low-frequency polling fallback."""

from __future__ import annotations

import importlib
import os
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Protocol, cast

from packai.policy import (
    DEFAULT_IGNORE,
    is_ignored_dir_name,
    load_project_ignore,
    should_ignore_path,
)


class ObserverLike(Protocol):
    def schedule(self, event_handler: object, path: str, *, recursive: bool) -> object: ...

    def start(self) -> None: ...

    def stop(self) -> None: ...

    def join(self, timeout: float | None = None) -> None: ...


class _EventHandler:
    def __init__(self, callback: Callable[[], None], root: Path) -> None:
        self._callback = callback
        self._root = root

    def dispatch(self, event: object) -> None:
        source = getattr(event, "src_path", None)
        destination = getattr(event, "dest_path", None)
        if self._relevant(source) or self._relevant(destination):
            self._callback()

    def _relevant(self, raw_path: object) -> bool:
        if not isinstance(raw_path, str):
            return False
        try:
            relative = Path(raw_path).resolve().relative_to(self._root)
        except (OSError, ValueError):
            return False
        return not any(is_ignored_dir_name(part) for part in relative.parts[:-1])


class DirectoryChangeMonitor:
    """Coalesce filesystem bursts and notify the GUI once per stable change."""

    def __init__(
        self,
        root: Path,
        callback: Callable[[], None],
        *,
        debounce_seconds: float = 0.65,
        polling_seconds: float = 3.0,
    ) -> None:
        self._root = root.resolve()
        self._callback = callback
        self._debounce_seconds = debounce_seconds
        self._polling_seconds = polling_seconds
        self._observer: ObserverLike | None = None
        self._timer: threading.Timer | None = None
        self._poll_thread: threading.Thread | None = None
        self._stopped = threading.Event()
        self.mode = "not_started"

    def start(self) -> None:
        if self.mode != "not_started":
            return
        try:
            observers = importlib.import_module("watchdog.observers")
            observer_factory = cast(Callable[[], ObserverLike], observers.Observer)
            observer = observer_factory()
            observer.schedule(
                _EventHandler(self._debounce, self._root), str(self._root), recursive=True
            )
            observer.start()
            self._observer = observer
            self.mode = "events"
        except (ImportError, OSError, RuntimeError):
            self.mode = "polling"
            self._poll_thread = threading.Thread(
                target=self._poll,
                name="packai-gui-polling-monitor",
                daemon=True,
            )
            self._poll_thread.start()

    def stop(self) -> None:
        self._stopped.set()
        timer = self._timer
        if timer is not None:
            timer.cancel()
        if self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout=2.0)
        if self._poll_thread is not None and self._poll_thread.is_alive():
            self._poll_thread.join(timeout=2.0)

    def _debounce(self) -> None:
        if self._stopped.is_set():
            return
        if self._timer is not None:
            self._timer.cancel()
        self._timer = threading.Timer(self._debounce_seconds, self._notify)
        self._timer.daemon = True
        self._timer.start()

    def _notify(self) -> None:
        if not self._stopped.is_set():
            self._callback()

    def _poll(self) -> None:
        previous = self._snapshot()
        while not self._stopped.wait(self._polling_seconds):
            current = self._snapshot()
            if current != previous:
                previous = current
                self._debounce()

    def _snapshot(self) -> tuple[tuple[str, int, int], ...]:
        snapshot: list[tuple[str, int, int]] = []
        patterns = (*DEFAULT_IGNORE, *load_project_ignore(self._root))
        for dirpath, dirnames, filenames in os.walk(self._root):
            current = Path(dirpath)
            relative_parent = current.relative_to(self._root)
            dirnames[:] = [
                name
                for name in dirnames
                if self._should_poll_directory(relative_parent, name, patterns)
            ]
            for filename in sorted(filenames):
                path = current / filename
                try:
                    stat = path.stat()
                    relative = path.relative_to(self._root).as_posix()
                except OSError:
                    continue
                ignore_type = should_ignore_path(relative, patterns, include_env_example=True)
                if ignore_type in {"strict", "pattern"}:
                    continue
                snapshot.append((relative, stat.st_mtime_ns, stat.st_size))
        return tuple(snapshot)

    @staticmethod
    def _should_poll_directory(
        relative_parent: Path,
        name: str,
        patterns: tuple[str, ...],
    ) -> bool:
        if is_ignored_dir_name(name):
            return False
        relative_path = Path(name) if relative_parent == Path(".") else relative_parent / name
        relative = relative_path.as_posix()
        return should_ignore_path(f"{relative}/", patterns, include_env_example=True) is None
