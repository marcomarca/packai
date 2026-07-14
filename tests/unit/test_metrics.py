from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from packai import GitContextResult, PackRequest, PackService, TokenEstimate
from packai.cli import build_parser, render_pack_metrics


class WordTokenEstimator:
    name = "test:words"

    def estimate(self, text: str) -> TokenEstimate:
        return TokenEstimate(count=len(text.split()), method=self.name)


class FailingTokenEstimator:
    name = "test:failing"

    def estimate(self, text: str) -> TokenEstimate:
        raise RuntimeError("tokenizer unavailable")


class FakeGitContextProvider:
    def build(self, root: Path, exclude_dirs: tuple[str, ...] = ()) -> GitContextResult:
        return GitContextResult("git context has four tokens")


def _png_bytes() -> bytes:
    return b"\x89PNG\r\n\x1a\n" + b"binary-image-data"


def _pdf_bytes() -> bytes:
    return b"%PDF-1.7\n%binary-pdf-data\n"


def test_pack_metrics_use_exact_archive_payload_and_include_safe_binary_assets(
    tmp_path: Path,
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    source_a = b"one two three"
    source_b = b"one"
    image = _png_bytes()
    pdf = _pdf_bytes()
    (root / "a.py").write_bytes(source_a)
    (root / "b.md").write_bytes(source_b)
    (root / "diagram.png").write_bytes(image)
    (root / "reference.pdf").write_bytes(pdf)
    (root / "tool.exe").write_bytes(b"MZ" + b"not-allowed")
    output = tmp_path / "result.zip"

    result = PackService(token_estimator=WordTokenEstimator()).pack(
        PackRequest(root=root, output_zip=output, token_top=2)
    )

    assert result.metrics is not None
    assert result.metrics.included_files == 4
    assert result.metrics.text_files == 2
    assert result.metrics.binary_files == 2
    assert result.metrics.uncompressed_size == len(source_a + source_b + image + pdf)
    assert result.metrics.zip_size == output.stat().st_size
    assert result.metrics.estimated_tokens == 4
    assert result.metrics.code_files == 1
    assert result.metrics.code_lines == 1
    assert [
        (item.language, item.files, item.code_lines) for item in result.metrics.language_code_lines
    ] == [("Python", 1, 1)]
    assert [item.relative_path for item in result.metrics.largest_token_files] == [
        "a.py",
        "b.md",
    ]
    assert [item.token_count for item in result.metrics.largest_token_files] == [3, 1]
    assert result.metrics.degraded is False

    with zipfile.ZipFile(output) as archive:
        assert set(archive.namelist()) == {"a.py", "b.md", "diagram.png", "reference.pdf"}
        assert archive.read("a.py") == source_a
        assert archive.read("diagram.png") == image
        assert archive.read("reference.pdf") == pdf


def test_binary_assets_can_still_be_explicitly_excluded(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / "diagram.png").write_bytes(_png_bytes())
    output = tmp_path / "result.zip"

    result = PackService(token_estimator=WordTokenEstimator()).pack(
        PackRequest(
            root=root,
            output_zip=output,
            extra_ignore_patterns=("*.png",),
        )
    )

    assert result.included_files == ()
    assert result.metrics is not None
    assert result.metrics.binary_files == 0


def test_executable_magic_is_rejected_even_with_an_image_extension(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / "disguised.png").write_bytes(b"MZ" + b"executable-content")
    output = tmp_path / "result.zip"

    result = PackService(token_estimator=WordTokenEstimator()).pack(
        PackRequest(root=root, output_zip=output)
    )

    assert "disguised.png" not in result.included_files
    assert result.metrics is not None
    assert result.metrics.included_files == 0


def test_preview_calculates_metrics_without_compressing_and_git_context_counts_as_text(
    tmp_path: Path,
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / "main.py").write_text("two tokens", encoding="utf-8")
    output = tmp_path / "result.zip"
    service = PackService(FakeGitContextProvider(), WordTokenEstimator())
    request = PackRequest(
        root=root,
        output_zip=output,
        include_git_context=True,
        token_top=10,
    )

    preview = service.preview(request)

    assert not output.exists()
    assert preview.metrics is not None
    assert preview.metrics.zip_size is None
    assert preview.metrics.included_files == 2
    assert preview.metrics.text_files == 2
    assert preview.metrics.estimated_tokens == 7
    assert {item.relative_path for item in preview.metrics.largest_token_files} == {
        "main.py",
        "git--diff_last_commit.md",
    }

    result = service.pack(request)
    assert result.metrics is not None
    assert result.metrics.zip_size == output.stat().st_size
    assert result.metrics.estimated_tokens == preview.metrics.estimated_tokens
    assert result.metrics.uncompressed_size == preview.metrics.uncompressed_size


def test_tokenizer_failure_uses_degraded_fallback(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    payload = "abcdefgh"
    (root / "main.txt").write_text(payload, encoding="utf-8")

    result = PackService(token_estimator=FailingTokenEstimator()).pack(
        PackRequest(root=root, output_zip=tmp_path / "result.zip")
    )

    assert result.metrics is not None
    assert result.metrics.estimated_tokens == 2
    assert result.metrics.degraded is True
    assert "heuristic:utf8-bytes/4" in result.metrics.tokenizer


def test_total_metrics_failure_does_not_prevent_archive_creation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / "main.py").write_text("safe", encoding="utf-8")
    output = tmp_path / "result.zip"
    service = PackService(token_estimator=WordTokenEstimator())

    def fail_metrics(*args: object, **kwargs: object) -> None:
        raise RuntimeError("metrics unavailable")

    monkeypatch.setattr(service._archive_service._metrics_analyzer, "analyze", fail_metrics)

    result = service.pack(PackRequest(root=root, output_zip=output))

    assert output.exists()
    assert result.metrics is None
    with zipfile.ZipFile(output) as archive:
        assert archive.read("main.py") == b"safe"


def test_legacy_cp1252_text_is_counted_without_modifying_archive_bytes(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    payload = "café résumé".encode("cp1252")
    (root / "legacy.txt").write_bytes(payload)
    output = tmp_path / "result.zip"

    result = PackService(token_estimator=WordTokenEstimator()).pack(
        PackRequest(root=root, output_zip=output)
    )

    assert result.metrics is not None
    assert result.metrics.text_files == 1
    assert result.metrics.estimated_tokens == 2
    with zipfile.ZipFile(output) as archive:
        assert archive.read("legacy.txt") == payload


def test_cli_token_top_and_metrics_renderer(tmp_path: Path) -> None:
    args = build_parser().parse_args(["--token-top", "10", "."])
    assert args.token_top == 10

    root = tmp_path / "project"
    root.mkdir()
    (root / "main.py").write_text("one two", encoding="utf-8")
    result = PackService(token_estimator=WordTokenEstimator()).pack(
        PackRequest(root=root, output_zip=tmp_path / "result.zip")
    )
    assert result.metrics is not None
    rendered = render_pack_metrics(result.metrics)
    assert "Archivos incluidos:" in rendered
    assert "Tokens estimados:" in rendered
    assert "Líneas de código:" in rendered
    assert "Líneas de código por lenguaje:" in rendered
    assert "Python" in rendered
    assert "Archivos con más tokens:" in rendered
    assert "main.py" in rendered

    with pytest.raises(SystemExit):
        build_parser().parse_args(["--token-top", "-1", "."])


def test_code_lines_are_non_empty_physical_lines_grouped_by_language(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / "main.py").write_text(
        "# comment\n\nvalue = 1\r\nprint(value)",
        encoding="utf-8",
    )
    (root / "app.ts").write_text(
        "// comment\n\nconst value = 1;\n",
        encoding="utf-8",
    )
    (root / "Dockerfile").write_text(
        "FROM python:3.12\n\nRUN echo ok\n",
        encoding="utf-8",
    )
    (root / "README.md").write_text("# Not source code\n", encoding="utf-8")
    (root / "run-tool").write_text(
        "#!/usr/bin/env bash\n\necho ok\n",
        encoding="utf-8",
    )

    result = PackService(token_estimator=WordTokenEstimator()).pack(
        PackRequest(root=root, output_zip=tmp_path / "result.zip")
    )

    assert result.metrics is not None
    assert result.metrics.text_files == 5
    assert result.metrics.code_files == 4
    assert result.metrics.code_lines == 9
    assert [
        (item.language, item.files, item.code_lines) for item in result.metrics.language_code_lines
    ] == [
        ("Python", 1, 3),
        ("Dockerfile", 1, 2),
        ("Shell", 1, 2),
        ("TypeScript", 1, 2),
    ]
