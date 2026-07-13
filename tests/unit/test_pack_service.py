from __future__ import annotations

import zipfile
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from packai import (
    ArchiveCreationError,
    GitContextResult,
    PackRequest,
    PackService,
    PackValidationError,
    ProgressEvent,
)
from packai.archive import ArchiveService


class FakeGitContextProvider:
    def __init__(self, markdown: str = "## Diff\n\n```diff\n+safe\n```\n") -> None:
        self.markdown = markdown
        self.calls: list[tuple[Path, tuple[str, ...]]] = []

    def build(self, root: Path, exclude_dirs: tuple[str, ...] = ()) -> GitContextResult:
        self.calls.append((root, tuple(exclude_dirs)))
        return GitContextResult(self.markdown)


def test_pack_service_returns_ui_neutral_result_and_progress_events(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / "main.py").write_text("print('ok')", encoding="utf-8")
    (root / ".env").write_text("TOKEN=not-packaged", encoding="utf-8")
    output = tmp_path / "result.zip"
    events: list[ProgressEvent] = []

    result = PackService().pack(PackRequest(root=root, output_zip=output), reporter=events.append)

    assert result.output_zip == output.resolve()
    assert result.included_count == 1
    assert result.ignored_count >= 1
    assert result.included_files == ("main.py",)
    assert next(event.kind for event in events) == "pack_started"
    assert any(event.kind == "file_included" for event in events)
    with zipfile.ZipFile(output) as archive:
        assert archive.namelist() == ["main.py"]

    with pytest.raises(FrozenInstanceError):
        result.included_count = 99  # type: ignore[misc]


def test_pack_service_injects_git_provider_and_normalized_exclusions(tmp_path: Path) -> None:
    root = tmp_path / "project"
    excluded = root / "cache" / "tmp"
    excluded.mkdir(parents=True)
    (root / "main.py").write_text("print('ok')", encoding="utf-8")
    (excluded / "ignored.py").write_text("print('ignored')", encoding="utf-8")
    provider = FakeGitContextProvider()
    output = tmp_path / "result.zip"

    result = PackService(provider).pack(
        PackRequest(
            root=root,
            output_zip=output,
            include_git_context=True,
            exclude_paths=("./cache/tmp/",),
        )
    )

    assert provider.calls == [(root.resolve(), ("cache/tmp",))]
    assert "cache/tmp/ignored.py" not in result.included_files
    assert "git--diff_last_commit.md" in result.included_files


def test_archive_creation_is_atomic_when_writing_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / "main.py").write_text("print('ok')", encoding="utf-8")
    output = tmp_path / "result.zip"
    output.write_bytes(b"previous archive")

    def fail_write(*args: object, **kwargs: object) -> None:
        raise OSError("simulated write failure")

    monkeypatch.setattr(zipfile.ZipFile, "write", fail_write)

    with pytest.raises(ArchiveCreationError, match="simulated write failure"):
        ArchiveService().create_archive(
            root=root,
            output_zip=output,
            ignore_patterns=(),
            include_env_example=True,
        )

    assert output.read_bytes() == b"previous archive"
    assert list(tmp_path.glob(".result.zip.*.tmp")) == []


def test_pack_service_rejects_missing_root(tmp_path: Path) -> None:
    with pytest.raises(PackValidationError, match="no existe"):
        PackService().pack(
            PackRequest(
                root=tmp_path / "missing",
                output_zip=tmp_path / "result.zip",
            )
        )
