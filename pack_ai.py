"""Backwards-compatible facade for Pack AI 1.x imports and script execution.

New integrations should import the stable contracts from ``packai`` and call
``PackService.pack``. This module remains intentionally thin so existing users
and tests can migrate without a flag day.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, TypedDict

_SRC = Path(__file__).parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from packai.archive import ArchiveService
from packai.cli import ConsoleReporter, build_parser, main
from packai.cli import print_findings as _print_core_findings
from packai.clipboard import (
    copy_path_as_text,
    copy_text_to_clipboard,
    copy_zip_with_powershell,
)
from packai.contracts import FileFinding as CoreFileFinding
from packai.contracts import GitContextResult
from packai.contracts import SecretFinding as CoreSecretFinding
from packai.errors import PackValidationError
from packai.git import build_git_context
from packai.git import get_git_commit_info as _get_git_commit_info
from packai.git import run_git_command as _run_git_command
from packai.naming import build_default_zip_stem as _build_default_zip_stem
from packai.naming import sanitize_filename
from packai.policy import (
    ALLOWED_DOT_DIR_NAMES,
    DEFAULT_IGNORE,
    GIT_CONTEXT_FILENAME,
    IGNORED_DIR_NAMES,
    SAFE_ENV_EXAMPLES,
    SECRET_FILE_PATTERNS,
    SECRET_PATTERNS,
    SENSITIVE_ASSIGNMENT_PATTERNS,
    STRICT_EXCLUDE_PATTERNS,
    build_git_exclude_pathspecs,
    build_runtime_exclude_patterns,
    is_ignored_dir_name,
    is_probably_binary,
    mask_secret,
    matches_any_path_pattern,
    should_ignore_path,
)
from packai.policy import (
    load_ignore_file as _load_ignore_file,
)
from packai.policy import (
    load_project_ignore as _load_project_ignore,
)
from packai.policy import (
    normalize_cli_exclude_paths as _normalize_cli_exclude_paths,
)
from packai.policy import (
    scan_file_for_secrets as _scan_file_for_secrets,
)
from packai.policy import (
    scan_text_for_secrets as _scan_text_for_secrets,
)
from packai.version import VERSION


class SecretFinding(TypedDict):
    type: str
    secret: str
    line: int | None


class FileFinding(TypedDict):
    rel: str
    details: list[SecretFinding]
    reason: str
    forced: bool


def get_version() -> str:
    return VERSION


def _legacy_secret(finding: CoreSecretFinding) -> SecretFinding:
    return {
        "type": finding.kind,
        "secret": finding.masked_value,
        "line": finding.line,
    }


def _legacy_file(finding: CoreFileFinding) -> FileFinding:
    return {
        "rel": finding.relative_path,
        "details": [_legacy_secret(detail) for detail in finding.details],
        "reason": finding.reason,
        "forced": finding.forced,
    }


def load_ignore_file(path: Path) -> list[str]:
    try:
        return _load_ignore_file(path)
    except PackValidationError as exc:
        raise SystemExit(f"❌ {exc}") from exc


def load_project_ignore(root: Path) -> list[str]:
    try:
        return _load_project_ignore(root)
    except PackValidationError as exc:
        raise SystemExit(f"❌ {exc}") from exc


def normalize_cli_exclude_paths(root: Path, exclude_paths: list[str]) -> list[str]:
    try:
        return _normalize_cli_exclude_paths(root, exclude_paths)
    except PackValidationError as exc:
        raise SystemExit(f"❌ {exc}") from exc


def scan_text_for_secrets(content: str) -> list[SecretFinding]:
    return [_legacy_secret(finding) for finding in _scan_text_for_secrets(content)]


def scan_file_for_secrets(path: Path) -> list[SecretFinding]:
    return [_legacy_secret(finding) for finding in _scan_file_for_secrets(path)]


def run_git_command(root: Path, args: list[str]) -> str | None:
    return _run_git_command(root, args)


def build_git_context_markdown(
    root: Path,
    exclude_dirs: list[str] | None = None,
) -> tuple[str | None, str | None]:
    result = build_git_context(root, exclude_dirs or (), runner=run_git_command)
    return result.markdown, result.unavailable_reason


class _LegacyGitContextProvider:
    def build(self, root: Path, exclude_dirs: tuple[str, ...] = ()) -> GitContextResult:
        markdown, reason = build_git_context_markdown(root, list(exclude_dirs))
        return GitContextResult(markdown, reason)


def copy_git_context_to_clipboard(
    root: Path,
    force: bool = False,
    exclude_dirs: list[str] | None = None,
) -> tuple[str, list[FileFinding]]:
    markdown, reason = build_git_context_markdown(root, exclude_dirs=exclude_dirs)
    if markdown is None:
        return f"failed:{reason}", []

    details = scan_text_for_secrets(markdown)
    findings: list[FileFinding] = []
    if details:
        findings.append(
            {
                "rel": GIT_CONTEXT_FILENAME,
                "details": details,
                "reason": "git_context_secret_found",
                "forced": force,
            }
        )
        if not force:
            return "blocked_secret", findings

    return ("copied" if copy_text_to_clipboard(markdown) else "copy_failed"), findings


def copy_zip(zip_path: Path, mode: str) -> str:
    if mode == "none":
        return "none"
    if mode == "path":
        return "path" if copy_path_as_text(zip_path) else "failed"
    if mode == "file":
        if copy_zip_with_powershell(zip_path):
            return "file"
        if copy_path_as_text(zip_path):
            return "path_fallback"
    return "failed"


def create_zip(
    root: Path,
    output_zip: Path,
    ignore_patterns: list[str],
    include_env_example: bool,
    force: bool = False,
    include_git_context: bool = False,
    exclude_dirs: list[str] | None = None,
) -> tuple[int, int, list[FileFinding]]:
    result = ArchiveService(_LegacyGitContextProvider()).create_archive(
        root=root,
        output_zip=output_zip,
        ignore_patterns=ignore_patterns,
        include_env_example=include_env_example,
        force=force,
        include_git_context=include_git_context,
        exclude_dirs=exclude_dirs or (),
        reporter=ConsoleReporter(),
    )
    return (
        result.included_count,
        result.ignored_count,
        [_legacy_file(finding) for finding in result.findings],
    )


def get_git_commit_info(root: Path) -> tuple[str | None, str | None]:
    return _get_git_commit_info(root)


def build_default_zip_stem(root: Path) -> str:
    return _build_default_zip_stem(root, commit_info_getter=get_git_commit_info)


def print_findings(total_findings: list[FileFinding]) -> None:
    core_findings = tuple(
        CoreFileFinding(
            relative_path=finding["rel"],
            details=tuple(
                CoreSecretFinding(
                    kind=detail["type"],
                    masked_value=detail["secret"],
                    line=detail["line"],
                )
                for detail in finding["details"]
            ),
            reason=finding["reason"],  # type: ignore[arg-type]
            forced=finding.get("forced", False),
        )
        for finding in total_findings
    )
    _print_core_findings(core_findings)


__all__ = [
    name
    for name, value in globals().copy().items()
    if not name.startswith("_") and value is not Any
]


if __name__ == "__main__":
    raise SystemExit(main())
