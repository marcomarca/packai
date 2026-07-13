from __future__ import annotations

from pathlib import Path

import pack_ai
from packai import PackRequest, PackResult, PackService, ProgressEvent


def test_new_public_api_exports_frontend_contracts() -> None:
    assert PackRequest.__module__ == "packai.contracts"
    assert PackResult.__module__ == "packai.contracts"
    assert ProgressEvent.__module__ == "packai.contracts"
    assert callable(PackService().pack)


def test_legacy_facade_preserves_existing_callable_surface(tmp_path: Path) -> None:
    required_callables = {
        "build_default_zip_stem",
        "build_git_context_markdown",
        "build_parser",
        "build_runtime_exclude_patterns",
        "copy_git_context_to_clipboard",
        "copy_zip",
        "create_zip",
        "get_git_commit_info",
        "normalize_cli_exclude_paths",
        "sanitize_filename",
        "scan_file_for_secrets",
        "should_ignore_path",
    }

    for name in required_callables:
        assert callable(getattr(pack_ai, name))
    assert pack_ai.GIT_CONTEXT_FILENAME == "git--diff_last_commit.md"
    project = tmp_path / "project"
    project.mkdir()
    assert pack_ai.build_default_zip_stem(project).startswith("project")
