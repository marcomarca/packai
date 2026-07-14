"""Archive planning and atomic creation with UI-neutral metrics."""

from __future__ import annotations

import os
import tempfile
import zipfile
import zlib
from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path

from packai.content import classify_content
from packai.contracts import (
    FileFinding,
    GitContextProvider,
    PackMetrics,
    PackPreview,
    PackResult,
    ProgressEvent,
    ProgressReporter,
    SecretFinding,
    TokenEstimator,
)
from packai.errors import ArchiveCreationError, PackValidationError
from packai.git import SubprocessGitContextProvider
from packai.metrics import ArchiveMetricsAnalyzer, MetricsEntry
from packai.policy import (
    GIT_CONTEXT_FILENAME,
    MAX_SECRET_SCAN_BYTES,
    scan_text_for_secrets,
    should_ignore_path,
)
from packai.tokenization import build_default_token_estimator


@dataclass(frozen=True, slots=True)
class ArchivePlan:
    """Immutable bytes and decisions shared by preview and ZIP creation."""

    entries: tuple[MetricsEntry, ...]
    ignored_count: int
    findings: tuple[FileFinding, ...]
    included_files: tuple[str, ...]

    @property
    def included_count(self) -> int:
        return len(self.entries)


class ArchiveService:
    """Plan, analyze, and create archives without console or GUI dependencies."""

    def __init__(
        self,
        git_context_provider: GitContextProvider | None = None,
        token_estimator: TokenEstimator | None = None,
    ) -> None:
        self._git_context_provider = git_context_provider or SubprocessGitContextProvider()
        estimator = token_estimator or build_default_token_estimator()
        self._metrics_analyzer = ArchiveMetricsAnalyzer(estimator)

    def preview_archive(
        self,
        *,
        root: Path,
        output_zip: Path,
        ignore_patterns: Sequence[str],
        include_env_example: bool,
        force: bool = False,
        include_git_context: bool = False,
        exclude_dirs: Sequence[str] = (),
        token_top: int = 3,
        reporter: ProgressReporter | None = None,
    ) -> PackPreview:
        """Calculate exact pre-compression metrics without creating a ZIP."""
        root_resolved = root.expanduser().resolve()
        output_resolved = output_zip.expanduser().resolve()
        self._validate_paths(root_resolved, output_resolved)
        plan = self._build_plan(
            root=root_resolved,
            output_zip=output_resolved,
            ignore_patterns=tuple(ignore_patterns),
            include_env_example=include_env_example,
            force=force,
            include_git_context=include_git_context,
            exclude_dirs=tuple(exclude_dirs),
            reporter=reporter,
        )
        metrics = self._safe_analyze(plan, token_top=token_top, reporter=reporter)
        return PackPreview(
            output_zip=output_resolved,
            included_count=plan.included_count,
            ignored_count=plan.ignored_count,
            findings=plan.findings,
            included_files=plan.included_files,
            metrics=metrics,
        )

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
        token_top: int = 3,
        reporter: ProgressReporter | None = None,
    ) -> PackResult:
        """Create one archive and replace the destination only after complete success."""
        root_resolved = root.expanduser().resolve()
        output_resolved = output_zip.expanduser().resolve()
        self._validate_paths(root_resolved, output_resolved)

        plan = self._build_plan(
            root=root_resolved,
            output_zip=output_resolved,
            ignore_patterns=tuple(ignore_patterns),
            include_env_example=include_env_example,
            force=force,
            include_git_context=include_git_context,
            exclude_dirs=tuple(exclude_dirs),
            reporter=reporter,
        )
        # Metrics are computed before compression from the exact immutable bytes
        # that will be written. A metrics failure never invalidates the archive.
        metrics = self._safe_analyze(plan, token_top=token_top, reporter=reporter)

        output_resolved.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            dir=output_resolved.parent,
            prefix=f".{output_resolved.name}.",
            suffix=".tmp",
        )
        os.close(descriptor)
        temporary_path = Path(temporary_name)

        try:
            self._write_plan(temporary_path, plan)
            self._verify_archive(temporary_path, plan)
            os.replace(temporary_path, output_resolved)
        except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
            temporary_path.unlink(missing_ok=True)
            raise ArchiveCreationError(f"No se pudo crear el ZIP {output_resolved}: {exc}") from exc
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise

        metrics = self._attach_zip_size(metrics, output_resolved, reporter)
        return PackResult(
            output_zip=output_resolved,
            included_count=plan.included_count,
            ignored_count=plan.ignored_count,
            findings=plan.findings,
            included_files=plan.included_files,
            metrics=metrics,
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

    def _build_plan(
        self,
        *,
        root: Path,
        output_zip: Path,
        ignore_patterns: tuple[str, ...],
        include_env_example: bool,
        force: bool,
        include_git_context: bool,
        exclude_dirs: tuple[str, ...],
        reporter: ProgressReporter | None,
    ) -> ArchivePlan:
        ignored_count = 0
        findings: list[FileFinding] = []
        entries: list[MetricsEntry] = []
        included_names: set[str] = set()

        self._emit(reporter, ProgressEvent(kind="pack_started", message=root.name))
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
                if path.is_symlink():
                    ignored_count += 1
                    continue
                try:
                    resolved_path = path.resolve()
                except OSError:
                    ignored_count += 1
                    continue
                if resolved_path == output_zip:
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

                try:
                    data = path.read_bytes()
                except OSError as exc:
                    ignored_count += 1
                    self._emit(
                        reporter,
                        ProgressEvent(
                            kind="warning",
                            message=f"No se pudo leer {relative_path}; se omitió: {exc}",
                        ),
                    )
                    continue

                classification = classify_content(path, data)
                if classification.kind in {"unsupported_binary", "executable"}:
                    ignored_count += 1
                    if classification.kind == "executable":
                        self._emit(
                            reporter,
                            ProgressEvent(
                                kind="warning",
                                message=f"Ejecutable omitido: {relative_path}",
                            ),
                        )
                    continue

                file_findings: tuple[SecretFinding, ...] = ()
                if classification.kind == "text":
                    assert classification.text is not None
                    file_findings = self._scan_in_memory_text(classification.text, len(data))
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
                if not file_findings and forced_by_name:
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

                entries.append(
                    MetricsEntry(
                        relative_path=relative_path,
                        data=data,
                        text_encoding=(
                            classification.encoding if classification.kind == "text" else None
                        ),
                    )
                )
                included_names.add(relative_path)
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
            ignored_count = self._append_git_context_to_plan(
                entries=entries,
                root=root,
                force=force,
                exclude_dirs=exclude_dirs,
                included_names=included_names,
                findings=findings,
                ignored_count=ignored_count,
                reporter=reporter,
            )

        return ArchivePlan(
            entries=tuple(entries),
            ignored_count=ignored_count,
            findings=tuple(findings),
            included_files=tuple(sorted(included_names)),
        )

    def _append_git_context_to_plan(
        self,
        *,
        entries: list[MetricsEntry],
        root: Path,
        force: bool,
        exclude_dirs: tuple[str, ...],
        included_names: set[str],
        findings: list[FileFinding],
        ignored_count: int,
        reporter: ProgressReporter | None,
    ) -> int:
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
            return ignored_count + 1

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
            return ignored_count + 1

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
                return ignored_count + 1

        entries.append(
            MetricsEntry(
                relative_path=GIT_CONTEXT_FILENAME,
                data=context.markdown.encode("utf-8"),
                text_encoding="utf-8",
            )
        )
        included_names.add(GIT_CONTEXT_FILENAME)
        self._emit(
            reporter,
            ProgressEvent(kind="git_context_included", relative_path=GIT_CONTEXT_FILENAME),
        )
        return ignored_count

    @staticmethod
    def _scan_in_memory_text(content: str, byte_size: int) -> tuple[SecretFinding, ...]:
        if byte_size > MAX_SECRET_SCAN_BYTES:
            return (
                SecretFinding(
                    kind="Archivo demasiado grande para escaneo",
                    masked_value=f"{byte_size} bytes",
                    line=None,
                ),
            )
        return scan_text_for_secrets(content)

    @staticmethod
    def _write_plan(temporary_zip: Path, plan: ArchivePlan) -> None:
        with zipfile.ZipFile(
            temporary_zip,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
            allowZip64=True,
            strict_timestamps=False,
        ) as archive:
            for entry in plan.entries:
                archive.writestr(entry.relative_path, entry.data)

    @staticmethod
    def _verify_archive(temporary_zip: Path, plan: ArchivePlan) -> None:
        """Fully read and validate the temporary ZIP before atomic replacement."""
        expected_names = [entry.relative_path for entry in plan.entries]
        expected_data = {entry.relative_path: entry.data for entry in plan.entries}
        with zipfile.ZipFile(temporary_zip, "r", allowZip64=True) as archive:
            bad_member = archive.testzip()
            if bad_member is not None:
                raise zipfile.BadZipFile(f"CRC inválido en {bad_member}")

            infos = archive.infolist()
            names = [info.filename for info in infos]
            if len(set(names)) != len(names):
                raise zipfile.BadZipFile("El ZIP contiene miembros duplicados.")
            if names != expected_names:
                raise zipfile.BadZipFile("Los miembros del ZIP no coinciden con el plan.")

            for info in infos:
                data = expected_data[info.filename]
                expected_crc = zlib.crc32(data) & 0xFFFFFFFF
                if info.compress_type != zipfile.ZIP_DEFLATED:
                    raise zipfile.BadZipFile(
                        f"Método de compresión inesperado para {info.filename}."
                    )
                if info.file_size != len(data) or expected_crc != info.CRC:
                    raise zipfile.BadZipFile(f"Tamaño o CRC inesperado para {info.filename}.")
                if archive.read(info) != data:
                    raise zipfile.BadZipFile(f"Contenido inesperado para {info.filename}.")

    def _safe_analyze(
        self,
        plan: ArchivePlan,
        *,
        token_top: int,
        reporter: ProgressReporter | None,
    ) -> PackMetrics | None:
        try:
            return self._metrics_analyzer.analyze(plan.entries, top_n=token_top)
        except Exception as exc:
            self._emit(
                reporter,
                ProgressEvent(
                    kind="warning",
                    message=f"No se pudieron calcular las métricas; el ZIP continuará: {exc}",
                ),
            )
            return None

    def _attach_zip_size(
        self,
        metrics: PackMetrics | None,
        output_zip: Path,
        reporter: ProgressReporter | None,
    ) -> PackMetrics | None:
        if metrics is None:
            return None
        try:
            return replace(metrics, zip_size=output_zip.stat().st_size)
        except OSError as exc:
            warning = f"No se pudo leer el tamaño final del ZIP: {exc}"
            self._emit(reporter, ProgressEvent(kind="warning", message=warning))
            return replace(
                metrics,
                complete=False,
                warnings=(*metrics.warnings, warning),
            )

    @staticmethod
    def _emit(reporter: ProgressReporter | None, event: ProgressEvent) -> None:
        if reporter is not None:
            reporter(event)
