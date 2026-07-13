"""PyWebView launcher kept optional so the traditional CLI remains lightweight."""

from __future__ import annotations

import importlib
import json
import os
import sys
from collections.abc import Callable
from importlib import resources
from typing import Protocol, cast

from packai.gui.api import GuiBridge
from packai.gui.contracts import GuiLaunchOptions
from packai.gui.watcher import DirectoryChangeMonitor


class EventLike(Protocol):
    def __iadd__(self, callback: Callable[..., object]) -> EventLike: ...


class WindowEvents(Protocol):
    loaded: EventLike
    closed: EventLike


class WindowLike(Protocol):
    events: WindowEvents

    def run_js(self, code: str) -> None: ...


class WebviewModule(Protocol):
    def create_window(self, title: str, url: str, **kwargs: object) -> WindowLike | None: ...

    def start(self, func: Callable[[], None] | None = None, **kwargs: object) -> None: ...


def launch_gui(options: GuiLaunchOptions) -> int:
    """Launch the local desktop GUI or return an actionable installation error."""
    try:
        webview = cast(WebviewModule, importlib.import_module("webview"))
    except ImportError:
        _print_missing_dependency_error()
        return 3

    bridge = GuiBridge(options)
    resource_directory = resources.files("packai.gui.resources")

    try:
        with resources.as_file(resource_directory) as resource_path:
            index_path = resource_path.joinpath("index.html")
            window = webview.create_window(
                "Pack AI",
                index_path.resolve().as_uri(),
                js_api=bridge,
                width=1360,
                height=860,
                min_size=(980, 640),
                background_color="#0b1020",
                text_select=True,
            )
            if window is None:
                raise RuntimeError("PyWebView no devolvió una ventana válida.")
            monitor = DirectoryChangeMonitor(
                options.root,
                lambda: _notify_filesystem_change(window, bridge),
            )

            def on_loaded(*_args: object) -> None:
                monitor.start()
                payload = json.dumps({"mode": monitor.mode})
                window.run_js(f"window.packaiMonitorReady && window.packaiMonitorReady({payload});")

            def on_closed(*_args: object) -> None:
                monitor.stop()

            window.events.loaded += on_loaded
            window.events.closed += on_closed
            webview.start(debug=False)
        return 0
    except Exception as exc:
        _print_startup_error(exc)
        return 3


def _notify_filesystem_change(window: WindowLike, bridge: GuiBridge) -> None:
    bridge.invalidate_cache()
    payload = json.dumps({"reason": "filesystem_changed"})
    try:
        window.run_js(
            f"window.packaiFilesystemChanged && window.packaiFilesystemChanged({payload});"
        )
    except Exception:
        # The window may be loading or already closing. The next explicit refresh
        # or pack still performs a complete scan, so no correctness is lost.
        return


def _print_missing_dependency_error() -> None:
    print(
        "❌ La interfaz gráfica no está instalada.\n"
        "   1. Actualiza tu lockfile: uv lock\n"
        "   2. Instala la GUI: uv sync --locked --extra gui\n"
        "   3. Prueba: uv run packai gui .\n"
        "   El CLI tradicional sigue disponible: uv run packai .",
        file=sys.stderr,
    )
    if os.name == "nt":
        print(
            "   Si la ventana no inicia: winget install -e --id Microsoft.EdgeWebView2Runtime",
            file=sys.stderr,
        )
        print(
            "   Si winget falla, instala o repara WebView2 Evergreen Runtime desde Microsoft.",
            file=sys.stderr,
        )


def _print_startup_error(exc: Exception) -> None:
    print(
        f"❌ No se pudo iniciar la interfaz gráfica: {type(exc).__name__}: {exc}", file=sys.stderr
    )
    print("   1. Ejecuta: uv lock", file=sys.stderr)
    print("   2. Ejecuta: uv sync --locked --extra gui", file=sys.stderr)
    if os.name == "nt":
        print(
            "   3. Ejecuta: winget install -e --id Microsoft.EdgeWebView2Runtime",
            file=sys.stderr,
        )
        print(
            "      Si winget falla, instala o repara WebView2 Evergreen Runtime desde Microsoft.",
            file=sys.stderr,
        )
    elif sys.platform == "darwin":
        print("   3. Verifica que macOS WebKit esté disponible y actualizado.", file=sys.stderr)
    else:
        print(
            "   3. El extra gui instala el backend Qt; verifica que exista una "
            "sesión gráfica DISPLAY/Wayland activa.",
            file=sys.stderr,
        )
        print(
            "      Diagnóstico opcional: PYWEBVIEW_GUI=qt uv run packai gui .",
            file=sys.stderr,
        )
    print("   4. Reintenta: uv run packai gui .", file=sys.stderr)
    print("   El comando CLI tradicional sigue disponible: uv run packai .", file=sys.stderr)
