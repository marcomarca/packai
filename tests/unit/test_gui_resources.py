from __future__ import annotations

import re
from importlib import resources


def _resource_text(name: str) -> str:
    return resources.files("packai.gui.resources").joinpath(name).read_text(encoding="utf-8")


def _css_declarations(css: str, selector: str) -> str:
    match = re.search(rf"{re.escape(selector)}\s*\{{(?P<body>[^}}]*)\}}", css)
    assert match is not None, f"No se encontró el selector {selector!r}"
    return " ".join(match.group("body").split())


def test_gui_root_is_permanently_bound_to_the_native_viewport() -> None:
    css = _resource_text("styles.css")

    root = _css_declarations(css, "#root")
    shell = _css_declarations(css, ".app-shell")
    workspace = _css_declarations(css, ".workspace")
    side_panel = _css_declarations(css, ".side-panel")

    assert "position: fixed" in root
    assert "inset: 0" in root
    assert "overflow: hidden" in root
    assert 'grid-template-areas: "topbar" "error" "workspace" "dock"' in shell
    assert "minmax(0, 1fr)" in shell
    assert "grid-area: workspace" in workspace
    assert "overflow: hidden" in workspace
    assert "overflow-y: auto" in side_panel
    assert "overflow-anchor: none" in side_panel


def test_gui_toggle_input_cannot_escape_its_visual_control() -> None:
    css = _resource_text("styles.css")

    control = _css_declarations(css, ".toggle-control")
    checkbox = _css_declarations(css, ".toggle-control > input")

    assert "position: relative" in control
    assert "position: absolute" in checkbox
    assert "inset: 0" in checkbox
    assert "width: 100%" in checkbox
    assert "height: 100%" in checkbox


def test_gui_viewport_guard_also_runs_when_a_control_receives_focus() -> None:
    javascript = _resource_text("app.js")

    assert "document.addEventListener('focusin', this.viewportGuard, true);" in javascript
    assert "document.removeEventListener('focusin', this.viewportGuard, true);" in javascript
    assert "window.addEventListener('scroll', this.viewportGuard, false);" in javascript
    assert "window.addEventListener('resize', this.viewportGuard, false);" in javascript
    assert (
        "this.visualViewport.addEventListener('resize', this.viewportGuard, false);" in javascript
    )
    assert "App.prototype.componentDidUpdate" in javascript
    assert "App.prototype.keepFocusedOptionVisible" in javascript
    assert "control.scrollIntoView({ block: 'nearest', inline: 'nearest' });" in javascript
    assert "self.stabilizeViewport();" in javascript
    assert "resetDocumentScroll();" in javascript
