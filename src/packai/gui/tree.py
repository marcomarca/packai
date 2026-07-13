"""Folder-only project tree used by the graphical selection surface."""

from __future__ import annotations

import os
from collections.abc import Sequence
from contextlib import suppress
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
    total_size_bytes: int | None
    children: tuple[FolderNode, ...]


def scan_folder_tree(
    root: Path,
    *,
    include_env_example: bool,
    extra_ignore_patterns: Sequence[str] = (),
) -> tuple[FolderNode, ...]:
    """Return folders with recursive disk sizes for selectable subtrees.

    Blocked folders remain visible as disabled leaves, but they are never
    traversed or measured. This is especially important for ``node_modules``,
    virtual environments, Git internals, and build caches.

    Folder sizes represent regular files physically contained in the visible
    subtree. The exact size selected for the archive remains the preview metric
    because secret scanning and content classification may omit individual files.
    """
    patterns = (*DEFAULT_IGNORE, *load_project_ignore(root), *extra_ignore_patterns)
    nodes, _, _ = _scan_directory(root, root, patterns, include_env_example)
    return nodes


def _scan_directory(
    root: Path,
    current: Path,
    patterns: Sequence[str],
    include_env_example: bool,
) -> tuple[tuple[FolderNode, ...], int, int]:
    try:
        entries = sorted(os.scandir(current), key=lambda entry: entry.name.casefold())
    except OSError:
        return (), 0, 0

    nodes: list[FolderNode] = []
    direct_file_count = 0
    total_size_bytes = 0

    for entry in entries:
        try:
            if entry.is_file(follow_symlinks=False):
                direct_file_count += 1
                with suppress(OSError):
                    total_size_bytes += entry.stat(follow_symlinks=False).st_size
                continue
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
                    total_size_bytes=None,
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
                    total_size_bytes=None,
                    children=(),
                )
            )
            continue

        children, child_direct_file_count, child_total_size = _scan_directory(
            root,
            path,
            patterns,
            include_env_example,
        )
        nodes.append(
            FolderNode(
                name=entry.name,
                relative_path=relative,
                disabled=False,
                disabled_reason=None,
                direct_file_count=child_direct_file_count,
                total_size_bytes=child_total_size,
                children=children,
            )
        )
        total_size_bytes += child_total_size

    return tuple(nodes), direct_file_count, total_size_bytes
