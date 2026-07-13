from __future__ import annotations

import subprocess
from pathlib import Path

from packai.git import get_git_commit_info, run_git_command


def test_git_helpers_treat_invalid_working_directory_as_unavailable(
    monkeypatch,
    tmp_path: Path,
) -> None:
    invalid_root = tmp_path / "missing"

    def raise_invalid_directory(*args: object, **kwargs: object) -> None:
        raise NotADirectoryError("invalid working directory")

    monkeypatch.setattr(subprocess, "run", raise_invalid_directory)

    assert run_git_command(invalid_root, ["status"]) is None
    assert get_git_commit_info(invalid_root) == (None, None)
