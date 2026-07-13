"""Stable application contracts shared by CLI, GUI, and other front ends."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

FindingReason = Literal[
    "secret_found",
    "sensitive_forced",
    "git_context_secret_found",
]
ProgressKind = Literal[
    "pack_started",
    "directory_included",
    "file_included",
    "path_ignored",
    "git_context_included",
    "warning",
]


@dataclass(frozen=True, slots=True)
class SecretFinding:
    """A masked secret detection safe to display in a UI or report."""

    kind: str
    masked_value: str
    line: int | None


@dataclass(frozen=True, slots=True)
class FileFinding:
    """Security finding associated with one archive member."""

    relative_path: str
    details: tuple[SecretFinding, ...]
    reason: FindingReason
    forced: bool = False


@dataclass(frozen=True, slots=True)
class ProgressEvent:
    """Presentation-neutral progress event emitted by the pack service."""

    kind: ProgressKind
    relative_path: str | None = None
    depth: int = 0
    message: str | None = None
    forced: bool = False


ProgressReporter = Callable[[ProgressEvent], None]


@dataclass(frozen=True, slots=True)
class PackRequest:
    """Validated input boundary for creating one archive."""

    root: Path
    output_zip: Path
    include_env_example: bool = True
    force: bool = False
    include_git_context: bool = False
    exclude_paths: tuple[str, ...] = ()
    extra_ignore_patterns: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PackResult:
    """Stable result returned independently of any user interface."""

    output_zip: Path
    included_count: int
    ignored_count: int
    findings: tuple[FileFinding, ...]
    included_files: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class GitContextResult:
    """Result of generating last-commit context without exceptions for absence."""

    markdown: str | None
    unavailable_reason: str | None = None


class GitContextProvider(Protocol):
    """Port implemented by Git adapters and fakes used in tests."""

    def build(self, root: Path, exclude_dirs: Sequence[str] = ()) -> GitContextResult:
        """Build Markdown for the latest commit or describe why it is unavailable."""
