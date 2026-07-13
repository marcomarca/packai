"""Cross-platform archive naming policies."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable
from pathlib import Path

from packai.git import get_git_commit_info

CommitInfoGetter = Callable[[Path], tuple[str | None, str | None]]


def sanitize_filename(name: str) -> str:
    """Return a portable filename component and mitigate Windows reserved names."""
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    sanitized = re.sub(r"[^a-zA-Z0-9.\-_]", "_", ascii_name)
    sanitized = re.sub(r"_{2,}", "_", sanitized).strip("_")

    windows_reserved = {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{index}" for index in range(1, 10)),
        *(f"LPT{index}" for index in range(1, 10)),
    }
    if Path(sanitized).stem.upper() in windows_reserved:
        sanitized = f"_{sanitized}"
    return sanitized


def build_default_zip_stem(
    root: Path,
    *,
    commit_info_getter: CommitInfoGetter = get_git_commit_info,
) -> str:
    """Build a stable project/hash archive stem without commit-subject churn."""
    project_name = root.name or "project"
    safe_project_name = sanitize_filename(project_name) or "project"
    if len(safe_project_name) > 80:
        safe_project_name = safe_project_name[:77] + "..."

    _, git_hash = commit_info_getter(root)
    if git_hash:
        return f"{safe_project_name}-{git_hash}"
    return safe_project_name
