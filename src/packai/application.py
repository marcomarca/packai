"""High-level use cases for front ends such as CLI and future GUIs."""

from __future__ import annotations

from pathlib import Path

from packai.archive import ArchiveService
from packai.contracts import (
    GitContextProvider,
    PackPreview,
    PackRequest,
    PackResult,
    ProgressReporter,
    TokenEstimator,
)
from packai.errors import PackValidationError
from packai.policy import (
    DEFAULT_IGNORE,
    build_runtime_exclude_patterns,
    load_project_ignore,
    normalize_cli_exclude_paths,
)


class PackService:
    """Application facade that owns validation and policy composition."""

    def __init__(
        self,
        git_context_provider: GitContextProvider | None = None,
        token_estimator: TokenEstimator | None = None,
    ) -> None:
        self._archive_service = ArchiveService(git_context_provider, token_estimator)

    def preview(
        self,
        request: PackRequest,
        reporter: ProgressReporter | None = None,
    ) -> PackPreview:
        """Analyze the exact prospective payload without creating a ZIP."""
        root, exclude_dirs, ignore_patterns = self._prepare(request)
        return self._archive_service.preview_archive(
            root=root,
            output_zip=request.output_zip,
            ignore_patterns=ignore_patterns,
            include_env_example=request.include_env_example,
            include_lockfiles=request.include_lockfiles,
            force=request.force,
            include_git_context=request.include_git_context,
            exclude_dirs=exclude_dirs,
            token_top=request.token_top,
            reporter=reporter,
        )

    def pack(self, request: PackRequest, reporter: ProgressReporter | None = None) -> PackResult:
        """Validate a request, compose ignore policy, and create an atomic archive."""
        root, exclude_dirs, ignore_patterns = self._prepare(request)
        return self._archive_service.create_archive(
            root=root,
            output_zip=request.output_zip,
            ignore_patterns=ignore_patterns,
            include_env_example=request.include_env_example,
            include_lockfiles=request.include_lockfiles,
            force=request.force,
            include_git_context=request.include_git_context,
            exclude_dirs=exclude_dirs,
            token_top=request.token_top,
            reporter=reporter,
        )

    @staticmethod
    def _prepare(request: PackRequest) -> tuple[Path, list[str], tuple[str, ...]]:
        if request.token_top < 0:
            raise PackValidationError("token_top no puede ser negativo.")
        root = request.root.expanduser().resolve()
        exclude_dirs = normalize_cli_exclude_paths(root, request.exclude_paths)
        ignore_patterns = (
            *DEFAULT_IGNORE,
            *load_project_ignore(root),
            *build_runtime_exclude_patterns(exclude_dirs),
            *request.extra_ignore_patterns,
        )
        return root, exclude_dirs, ignore_patterns
