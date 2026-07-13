"""Archive creation service with atomic output and injected external ports."""

from __future__ import annotations

import os
import tempfile
import zipfile
from collections.abc import Sequence
from pathlib import Path

from packai.contracts import (
    FileFinding,
    GitContextProvider,
    PackResult,
    ProgressEvent,
    ProgressReporter,
    SecretFinding,
)
from packai.errors import ArchiveCreationError, PackValidationError
from packai.git import SubprocessGitContextProvider
from packai.policy import (
    GIT_CONTEXT_FILENAME,
    is_probably_binary,
    scan_file_for_secrets,
    scan_text_for_secrets,
    should_ignore_path,
)


class ArchiveService:
    """Create archives without depending on a console or GUI framework."""

    def __init__(self, git_context_provider: GitContextProvider | None = None) -> None:
        self._git_context_provider = git_context_provider or SubprocessGitContextProvider()

    def create_archive(
        self,
        *,
        root: Path,
        output_zip: Path,
        ignore_patterns: Sequence[str],
        include_env_example: bool,
        force: bool = False,
        include_git_context: bool = False,
        exclude_dirs: Sequence[str] = (),
        reporter: ProgressReporter | None = None,
    ) -> PackResult:
        """Create one archive and replace the destination only after complete success."""
        root_resolved = root.expanduser().resolve()
        output_resolved = output_zip.expanduser().resolve()
        self._validate_paths(root_resolved, output_resolved)
        output_resolved.parent.mkdir(parents=True, exist_ok=True)

        descriptor, temporary_name = tempfile.mkstemp(
            dir=output_resolved.parent,
            prefix=f".{output_resolved.name}.",
            suffix=".tmp",
        )
        os.close(descriptor)
        temporary_path = Path(temporary_name)

        try:
            result = self._write_archive(
                root=root_resolved,
                output_zip=output_resolved,
                temporary_zip=temporary_path,
                ignore_patterns=tuple(ignore_patterns),
                include_env_example=include_env_example,
                force=force,
                include_git_context=include_git_context,
                exclude_dirs=tuple(exclude_dirs),
                reporter=reporter,
            )
            os.replace(temporary_path, output_resolved)
        except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
            temporary_path.unlink(missing_ok=True)
            raise ArchiveCreationError(f"No se pudo crear el ZIP {output_resolved}: {exc}") from exc
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise

        return PackResult(
            output_zip=output_resolved,
            included_count=result.included_count,
            ignored_count=result.ignored_count,
            findings=result.findings,
            included_files=result.included_files,
        )

    @staticmethod
    def _validate_paths(root: Path, output_zip: Path) -> None:
        if not root.exists():
            raise PackValidationError(f"La ruta no existe: {root}")
        if not root.is_dir():
            raise PackValidationError(f"La ruta no es una carpeta: {root}")
        if output_zip.exists() and output_zip.is_dir():
            raise PackValidationError(
                f"La salida debe ser un archivo ZIP, no una carpeta: {output_zip}"
            )

    def _write_archive(
        self,
        *,
        root: Path,
        output_zip: Path,
        temporary_zip: Path,
        ignore_patterns: tuple[str, ...],
        include_env_example: bool,
        force: bool,
        include_git_context: bool,
        exclude_dirs: tuple[str, ...],
        reporter: ProgressReporter | None,
    ) -> PackResult:
        included_count = 0
        ignored_count = 0
        findings: list[FileFinding] = []
        included_names: set[str] = set()

        self._emit(reporter, ProgressEvent(kind="pack_started", message=root.name))
        with zipfile.ZipFile(temporary_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for dirpath, dirnames, filenames in os.walk(root):
                current_dir = Path(dirpath)
                kept_dirnames: list[str] = []
                for directory_name in sorted(dirnames):
                    directory_path = current_dir / directory_name
                    relative_directory = f"{directory_path.relative_to(root).as_posix()}/"
                    ignore_type = should_ignore_path(
                        relative_directory,
                        ignore_patterns,
                        include_env_example,
                    )
                    if ignore_type in ("strict", "pattern") or directory_path.is_symlink():
                        ignored_count += 1
                        self._emit(
                            reporter,
                            ProgressEvent(kind="path_ignored", relative_path=relative_directory),
                        )
                        continue
                    kept_dirnames.append(directory_name)
                dirnames[:] = kept_dirnames

                relative_dir = current_dir.relative_to(root)
                depth = len(relative_dir.parts) if relative_dir != Path(".") else 0
                if relative_dir != Path("."):
                    self._emit(
                        reporter,
                        ProgressEvent(
                            kind="directory_included",
                            relative_path=relative_dir.as_posix(),
                            depth=depth,
                        ),
                    )

                for filename in sorted(filenames):
                    path = current_dir / filename
                    resolved_path = path.resolve()
                    if path.is_symlink():
                        ignored_count += 1
                        continue
                    if resolved_path in {output_zip, temporary_zip}:
                        continue

                    relative_path = path.relative_to(root).as_posix()
                    ignore_type = should_ignore_path(
                        relative_path,
                        ignore_patterns,
                        include_env_example,
                    )
                    if ignore_type in ("strict", "pattern"):
                        ignored_count += 1
                        continue

                    forced_by_name = ignore_type == "sensitive"
                    if forced_by_name and not force:
                        ignored_count += 1
                        continue
                    if is_probably_binary(path):
                        ignored_count += 1
                        continue

                    file_findings = scan_file_for_secrets(path)
                    if file_findings:
                        findings.append(
                            FileFinding(
                                relative_path=relative_path,
                                details=file_findings,
                                reason="secret_found",
                                forced=force,
                            )
                        )
                        if not force:
                            ignored_count += 1
                            continue
                    elif forced_by_name:
                        findings.append(
                            FileFinding(
                                relative_path=relative_path,
                                details=(
                                    SecretFinding(
                                        kind="Nombre sensible forzado",
                                        masked_value="Coincide con patrón de seguridad",
                                        line=None,
                                    ),
                                ),
                                reason="sensitive_forced",
                                forced=True,
                            )
                        )

                    archive.write(path, arcname=relative_path)
                    included_names.add(relative_path)
                    included_count += 1
                    self._emit(
                        reporter,
                        ProgressEvent(
                            kind="file_included",
                            relative_path=relative_path,
                            depth=depth,
                            forced=bool(file_findings or forced_by_name),
                        ),
                    )

            if include_git_context:
                included_count, ignored_count = self._append_git_context(
                    archive=archive,
                    root=root,
                    force=force,
                    exclude_dirs=exclude_dirs,
                    included_names=included_names,
                    findings=findings,
                    included_count=included_count,
                    ignored_count=ignored_count,
                    reporter=reporter,
                )

        return PackResult(
            output_zip=output_zip,
            included_count=included_count,
            ignored_count=ignored_count,
            findings=tuple(findings),
            included_files=tuple(sorted(included_names)),
        )

    def _append_git_context(
        self,
        *,
        archive: zipfile.ZipFile,
        root: Path,
        force: bool,
        exclude_dirs: tuple[str, ...],
        included_names: set[str],
        findings: list[FileFinding],
        included_count: int,
        ignored_count: int,
        reporter: ProgressReporter | None,
    ) -> tuple[int, int]:
        if GIT_CONTEXT_FILENAME in included_names:
            self._emit(
                reporter,
                ProgressEvent(
                    kind="warning",
                    message=(
                        f"Ya existe {GIT_CONTEXT_FILENAME}; no se generó contexto Git para evitar duplicados."
                    ),
                ),
            )
            return included_count, ignored_count + 1

        context = self._git_context_provider.build(root, exclude_dirs)
        if context.markdown is None:
            self._emit(
                reporter,
                ProgressEvent(
                    kind="warning",
                    message=(
                        f"No se pudo generar {GIT_CONTEXT_FILENAME}: "
                        f"{context.unavailable_reason or 'motivo desconocido'}"
                    ),
                ),
            )
            return included_count, ignored_count + 1

        context_findings = scan_text_for_secrets(context.markdown)
        if context_findings:
            findings.append(
                FileFinding(
                    relative_path=GIT_CONTEXT_FILENAME,
                    details=context_findings,
                    reason="git_context_secret_found",
                    forced=force,
                )
            )
            if not force:
                self._emit(
                    reporter,
                    ProgressEvent(
                        kind="warning",
                        message=f"{GIT_CONTEXT_FILENAME} omitido por posibles secretos.",
                    ),
                )
                return included_count, ignored_count + 1

        archive.writestr(GIT_CONTEXT_FILENAME, context.markdown)
        included_names.add(GIT_CONTEXT_FILENAME)
        self._emit(
            reporter,
            ProgressEvent(kind="git_context_included", relative_path=GIT_CONTEXT_FILENAME),
        )
        return included_count + 1, ignored_count

    @staticmethod
    def _emit(reporter: ProgressReporter | None, event: ProgressEvent) -> None:
        if reporter is not None:
            reporter(event)
