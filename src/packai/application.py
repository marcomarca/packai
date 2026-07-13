"""High-level use case for front ends such as CLI and future GUIs."""

from __future__ import annotations

from packai.archive import ArchiveService
from packai.contracts import GitContextProvider, PackRequest, PackResult, ProgressReporter
from packai.policy import (
    DEFAULT_IGNORE,
    build_runtime_exclude_patterns,
    load_project_ignore,
    normalize_cli_exclude_paths,
)


class PackService:
    """Application facade that owns validation and policy composition."""

    def __init__(self, git_context_provider: GitContextProvider | None = None) -> None:
        self._archive_service = ArchiveService(git_context_provider)

    def pack(self, request: PackRequest, reporter: ProgressReporter | None = None) -> PackResult:
        """Validate a request, compose ignore policy, and create an atomic archive."""
        root = request.root.expanduser().resolve()
        exclude_dirs = normalize_cli_exclude_paths(root, request.exclude_paths)
        ignore_patterns = (
            *DEFAULT_IGNORE,
            *load_project_ignore(root),
            *build_runtime_exclude_patterns(exclude_dirs),
            *request.extra_ignore_patterns,
        )
        return self._archive_service.create_archive(
            root=root,
            output_zip=request.output_zip,
            ignore_patterns=ignore_patterns,
            include_env_example=request.include_env_example,
            force=request.force,
            include_git_context=request.include_git_context,
            exclude_dirs=exclude_dirs,
            reporter=reporter,
        )
