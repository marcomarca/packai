from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, ClassVar

from packai.gui import launcher
from packai.gui.contracts import GuiLaunchOptions


class _FakeEvent:
    def __init__(self) -> None:
        self.callbacks: list[Any] = []

    def __iadd__(self, callback: Any) -> _FakeEvent:
        self.callbacks.append(callback)
        return self


class _FakeWindow:
    def __init__(self) -> None:
        self.events = SimpleNamespace(loaded=_FakeEvent(), closed=_FakeEvent())
        self.scripts: list[str] = []

    def run_js(self, code: str) -> None:
        self.scripts.append(code)


class _FakeWebview:
    def __init__(self) -> None:
        self.window = _FakeWindow()
        self.created: dict[str, object] = {}

    def create_window(self, title: str, url: str, **kwargs: object) -> _FakeWindow:
        self.created = {"title": title, "url": url, **kwargs}
        return self.window

    def start(self, func=None, **_kwargs: object) -> None:
        assert func is None
        for callback in self.window.events.loaded.callbacks:
            callback()
        for callback in self.window.events.closed.callbacks:
            callback()


class _FakeMonitor:
    instances: ClassVar[list[_FakeMonitor]] = []

    def __init__(self, root: Path, callback: Any) -> None:
        self.root = root
        self.callback = callback
        self.mode = "events"
        self.started = False
        self.stopped = False
        self.instances.append(self)

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True


def test_launch_gui_reports_missing_optional_dependency(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    def missing(_name: str) -> object:
        raise ImportError("missing")

    monkeypatch.setattr(launcher.importlib, "import_module", missing)

    status = launcher.launch_gui(GuiLaunchOptions(root=tmp_path))

    assert status == 3
    error = capsys.readouterr().err
    assert "uv sync --locked --extra gui" in error
    assert "CLI" in error


def test_launch_gui_uses_local_resources_and_stops_monitor(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fake_webview = _FakeWebview()
    _FakeMonitor.instances.clear()
    real_import_module = launcher.importlib.import_module
    monkeypatch.setattr(
        launcher.importlib,
        "import_module",
        lambda name: fake_webview if name == "webview" else real_import_module(name),
    )
    monkeypatch.setattr(launcher, "DirectoryChangeMonitor", _FakeMonitor)

    status = launcher.launch_gui(GuiLaunchOptions(root=tmp_path))

    assert status == 0
    assert fake_webview.created["title"] == "Pack AI"
    assert str(fake_webview.created["url"]).startswith("file:")
    assert fake_webview.created["js_api"].__class__.__name__ == "GuiBridge"
    assert _FakeMonitor.instances[0].started is True
    assert _FakeMonitor.instances[0].stopped is True
    assert any("packaiMonitorReady" in script for script in fake_webview.window.scripts)


def test_local_html_csp_allows_pywebview_bridge_without_remote_network() -> None:
    from importlib import resources

    html = (
        resources.files("packai.gui.resources").joinpath("index.html").read_text(encoding="utf-8")
    )

    assert "script-src 'self' file: 'unsafe-eval'" in html
    assert "connect-src 'none'" in html
    assert "http://" not in html
    assert "https://" not in html
