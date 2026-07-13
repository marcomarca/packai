from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from packai.gui import watcher


class _ImmediateTimer:
    def __init__(self, _seconds: float, callback: Any) -> None:
        self.callback = callback
        self.daemon = False
        self.cancelled = False

    def start(self) -> None:
        if not self.cancelled:
            self.callback()

    def cancel(self) -> None:
        self.cancelled = True


class _FakeObserver:
    def __init__(self) -> None:
        self.handler: object | None = None
        self.path = ""
        self.recursive = False
        self.started = False
        self.stopped = False

    def schedule(self, event_handler: object, path: str, *, recursive: bool) -> object:
        self.handler = event_handler
        self.path = path
        self.recursive = recursive
        return object()

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True

    def join(self, timeout: float | None = None) -> None:
        assert timeout == 2.0


def test_event_monitor_coalesces_relevant_changes_and_ignores_policy_paths(
    tmp_path: Path,
    monkeypatch,
) -> None:
    root = tmp_path / "project"
    (root / "src").mkdir(parents=True)
    (root / ".git").mkdir()
    observer = _FakeObserver()
    monkeypatch.setattr(
        watcher.importlib,
        "import_module",
        lambda _name: SimpleNamespace(Observer=lambda: observer),
    )
    monkeypatch.setattr(watcher.threading, "Timer", _ImmediateTimer)
    notifications: list[str] = []
    monitor = watcher.DirectoryChangeMonitor(root, lambda: notifications.append("changed"))

    monitor.start()
    assert monitor.mode == "events"
    assert observer.started is True
    assert observer.recursive is True
    assert observer.handler is not None

    observer.handler.dispatch(SimpleNamespace(src_path=str(root / ".git" / "config")))
    assert notifications == []

    observer.handler.dispatch(SimpleNamespace(src_path=str(root / "src" / "main.py")))
    assert notifications == ["changed"]

    monitor.stop()
    assert observer.stopped is True


def test_polling_snapshot_prunes_project_ignored_directories(tmp_path: Path) -> None:
    root = tmp_path / "project"
    ignored = root / "generated" / "deep"
    included = root / "src"
    ignored.mkdir(parents=True)
    included.mkdir(parents=True)
    (root / ".ignore2packai").write_text("generated/\n", encoding="utf-8")
    (ignored / "large.txt").write_text("ignored", encoding="utf-8")
    (included / "main.py").write_text("included", encoding="utf-8")
    monitor = watcher.DirectoryChangeMonitor(root, lambda: None)

    snapshot = monitor._snapshot()

    paths = {item[0] for item in snapshot}
    assert "src/main.py" in paths
    assert "generated/deep/large.txt" not in paths


def test_polling_snapshot_keeps_allowed_dot_directories_and_ignores_irrelevant_files(
    tmp_path: Path,
) -> None:
    root = tmp_path / "project"
    workflow = root / ".github" / "workflows"
    workflow.mkdir(parents=True)
    (workflow / "quality.yml").write_text("name: quality", encoding="utf-8")
    (root / "archive.zip").write_bytes(b"not relevant to the next pack")
    monitor = watcher.DirectoryChangeMonitor(root, lambda: None)

    paths = {item[0] for item in monitor._snapshot()}

    assert ".github/workflows/quality.yml" in paths
    assert "archive.zip" not in paths
