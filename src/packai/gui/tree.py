"""Folder-only project tree used by the graphical selection surface."""

from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from packai.policy import DEFAULT_IGNORE, load_project_ignore, should_ignore_path


@dataclass(frozen=True, slots=True)
class FolderNode:
    """One visible folder and its selectable policy state."""

    name: str
    relative_path: str
    disabled: bool
    disabled_reason: str | None
    direct_file_count: int
    children: tuple[FolderNode, ...]


def scan_folder_tree(
    root: Path,
    *,
    include_env_example: bool,
    extra_ignore_patterns: Sequence[str] = (),
) -> tuple[FolderNode, ...]:
    """Return folders while retaining policy-blocked nodes as disabled leaves.

    Blocked folders are deliberately not traversed. This keeps ``node_modules``,
    virtual environments, Git internals, and caches visible without paying the
    cost of enumerating their potentially large subtrees.
    """
    patterns = (*DEFAULT_IGNORE, *load_project_ignore(root), *extra_ignore_patterns)
    return _scan_children(root, root, patterns, include_env_example)


def _scan_children(
    root: Path,
    current: Path,
    patterns: Sequence[str],
    include_env_example: bool,
) -> tuple[FolderNode, ...]:
    try:
        entries = sorted(os.scandir(current), key=lambda entry: entry.name.casefold())
    except OSError:
        return ()

    nodes: list[FolderNode] = []
    for entry in entries:
        try:
            is_directory = entry.is_dir(follow_symlinks=False)
        except OSError:
            continue
        if not is_directory:
            continue

        path = Path(entry.path)
        relative = path.relative_to(root).as_posix()
        relative_directory = f"{relative}/"
        if entry.is_symlink():
            nodes.append(
                FolderNode(
                    name=entry.name,
                    relative_path=relative,
                    disabled=True,
                    disabled_reason="Enlace simbólico no permitido",
                    direct_file_count=0,
                    children=(),
                )
            )
            continue

        ignore_type = should_ignore_path(
            relative_directory,
            tuple(patterns),
            include_env_example,
        )
        if ignore_type in {"strict", "pattern"}:
            reason = (
                "Bloqueado por política de seguridad"
                if ignore_type == "strict"
                else "Ignorado por la política del proyecto"
            )
            nodes.append(
                FolderNode(
                    name=entry.name,
                    relative_path=relative,
                    disabled=True,
                    disabled_reason=reason,
                    direct_file_count=0,
                    children=(),
                )
            )
            continue

        direct_file_count = _count_direct_files(path)
        nodes.append(
            FolderNode(
                name=entry.name,
                relative_path=relative,
                disabled=False,
                disabled_reason=None,
                direct_file_count=direct_file_count,
                children=_scan_children(root, path, patterns, include_env_example),
            )
        )
    return tuple(nodes)


def _count_direct_files(path: Path) -> int:
    try:
        with os.scandir(path) as entries:
            return sum(1 for entry in entries if entry.is_file(follow_symlinks=False))
    except OSError:
        return 0
