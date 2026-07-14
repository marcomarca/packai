"""Reproducible command rendering for the GUI."""

from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path

from packai.config import INCLUDE_LOCKFILES
from packai.gui.contracts import GuiLaunchOptions


def build_commands(options: GuiLaunchOptions, exclude_paths: tuple[str, ...]) -> dict[str, str]:
    """Build direct-pack and reopen-GUI commands from the same state."""
    folder = _display_folder(options.root)
    common = _common_arguments(options, exclude_paths)
    direct = ["packai", folder, *common, "--copy", options.copy_mode]
    gui = ["packai", "gui", folder, *common, "--copy", options.copy_mode]
    return {
        "pack": _join_command(direct),
        "gui": _join_command(gui),
    }


def _common_arguments(options: GuiLaunchOptions, exclude_paths: tuple[str, ...]) -> list[str]:
    arguments: list[str] = []
    for path in sorted(exclude_paths):
        arguments.extend(("-e", path))
    if options.force:
        arguments.append("--force")
    if options.include_git_context:
        arguments.append("-g")
    if not options.include_env_example:
        arguments.append("--no-env-example")
    if options.include_lockfiles != INCLUDE_LOCKFILES:
        arguments.append("--lockfiles" if options.include_lockfiles else "--no-lockfiles")
    if options.token_top != 3:
        arguments.extend(("--token-top", str(options.token_top)))
    return arguments


def _display_folder(root: Path) -> str:
    try:
        if root.resolve() == Path.cwd().resolve():
            return "."
    except OSError:
        pass
    return str(root)


def _join_command(parts: list[str]) -> str:
    if os.name == "nt":
        return subprocess.list2cmdline(parts)
    return shlex.join(parts)
