"""Internal contracts for launching the optional graphical interface."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

CopyMode = Literal["file", "path", "none"]


@dataclass(frozen=True, slots=True)
class GuiLaunchOptions:
    """Initial GUI state derived from the ``packai gui`` command."""

    root: Path
    exclude_paths: tuple[str, ...] = ()
    force: bool = False
    include_git_context: bool = False
    include_env_example: bool = True
    token_top: int = 3
    copy_mode: CopyMode = "file"
    include_lockfiles: bool = True
