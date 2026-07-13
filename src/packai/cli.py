"""Thin CLI adapter for the PackService application contract."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from packai.application import PackService
from packai.clipboard import copy_text_to_clipboard, copy_zip
from packai.config import INCLUDE_ENV_EXAMPLE
from packai.contracts import FileFinding, PackRequest, ProgressEvent
from packai.errors import PackAIError, PackValidationError
from packai.git import SubprocessGitContextProvider
from packai.naming import build_default_zip_stem
from packai.policy import GIT_CONTEXT_FILENAME, normalize_cli_exclude_paths, scan_text_for_secrets
from packai.version import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Empaqueta proyecto en ZIP para IA.")
    parser.add_argument("--version", "-v", action="version", version=f"Pack AI {__version__}")
    parser.add_argument(
        "--copy",
        choices=["file", "path", "none"],
        default="file",
        help="Modo de copiado.",
    )
    parser.add_argument("--output", help="Ruta del ZIP de salida.")
    parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Forzar inclusión de archivos con alertas (excepto .env).",
    )
    parser.add_argument(
        "--commit-clipboard",
        "-c",
        action="store_true",
        dest="copy_git_context",
        help=f"Copia al portapapeles el Markdown de {GIT_CONTEXT_FILENAME} sin crear ZIP.",
    )
    parser.add_argument(
        "-g",
        action="store_true",
        dest="include_git_context",
        help=f"Incluye {GIT_CONTEXT_FILENAME} con el diff del último commit confirmado.",
    )
    parser.add_argument(
        "--exclude",
        "--exclude-path",
        "-e",
        "-E",
        "-I",
        action="append",
        default=[],
        dest="exclude_paths",
        metavar="REL_DIR",
        help="Excluye una carpeta relativa al proyecto y todos sus hijos. Repetible.",
    )
    parser.add_argument(
        "--no-env-example",
        action="store_false",
        dest="include_env_example",
        default=INCLUDE_ENV_EXAMPLE,
        help="No incluir archivos .env.example.",
    )
    parser.add_argument("folder", nargs="?", default=".", help="Carpeta a procesar.")
    return parser


class ConsoleReporter:
    """Render progress events without leaking console concerns into the service."""

    def __call__(self, event: ProgressEvent) -> None:
        if event.kind == "pack_started":
            print(f"Empaquetando: {event.message}...")
        elif event.kind == "directory_included" and event.relative_path:
            indent = "    " * max(event.depth - 1, 0)
            print(f"{indent}    📁 {Path(event.relative_path).name}")
        elif event.kind == "file_included" and event.relative_path:
            indent = "    " * event.depth
            icon = "🚀" if event.forced else "📄"
            print(f"{indent}    {icon} {Path(event.relative_path).name}")
        elif event.kind == "git_context_included" and event.relative_path:
            print(f"📄 {event.relative_path}")
        elif event.kind == "warning" and event.message:
            print(f"⚠️  {event.message}")


def print_findings(findings: tuple[FileFinding, ...]) -> None:
    for finding in findings:
        status = "INCLUIDO (FORZADO)" if finding.forced else "EXCLUIDO"
        icon = "🚀" if finding.forced else "⚠️"
        print(f"{icon}  {status}: {finding.relative_path}")
        for detail in finding.details:
            print(f"    Tipo: {detail.kind}")
            if detail.line is not None:
                print(f"    Línea: {detail.line}")
            print(f"    Secreto: {detail.masked_value}")
        action = "incluido o copiado a pesar de la alerta" if finding.forced else "omitido"
        print(f"    Acción: {action}\n")


def _copy_git_context(root: Path, *, force: bool, exclude_paths: list[str]) -> int:
    exclude_dirs = normalize_cli_exclude_paths(root, exclude_paths)
    context = SubprocessGitContextProvider().build(root, exclude_dirs)
    if context.markdown is None:
        print(
            f"❌ No se pudo generar {GIT_CONTEXT_FILENAME}: "
            f"{context.unavailable_reason or 'motivo desconocido'}"
        )
        return 1

    findings = scan_text_for_secrets(context.markdown)
    if findings and not force:
        finding = FileFinding(
            relative_path=GIT_CONTEXT_FILENAME,
            details=findings,
            reason="git_context_secret_found",
            forced=False,
        )
        print_findings((finding,))
        print(f"⚠️ {GIT_CONTEXT_FILENAME} no se copió por posibles secretos. Usa -cf para forzar.")
        return 1

    if findings:
        print_findings(
            (
                FileFinding(
                    relative_path=GIT_CONTEXT_FILENAME,
                    details=findings,
                    reason="git_context_secret_found",
                    forced=True,
                ),
            )
        )

    if not copy_text_to_clipboard(context.markdown):
        print(f"❌ Error al copiar {GIT_CONTEXT_FILENAME} al portapapeles.")
        return 1
    print(f"✅ {GIT_CONTEXT_FILENAME} copiado al portapapeles.")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.folder).expanduser().resolve()

    try:
        if not root.exists():
            raise PackValidationError(f"La ruta no existe: {root}")
        if not root.is_dir():
            raise PackValidationError(f"La ruta no es una carpeta: {root}")

        if args.copy_git_context:
            return _copy_git_context(root, force=args.force, exclude_paths=args.exclude_paths)

        name = build_default_zip_stem(root)
        output_zip = (
            Path(args.output).expanduser().resolve() if args.output else root.parent / f"{name}.zip"
        )
        result = PackService().pack(
            PackRequest(
                root=root,
                output_zip=output_zip,
                include_env_example=args.include_env_example,
                force=args.force,
                include_git_context=args.include_git_context,
                exclude_paths=tuple(args.exclude_paths),
            ),
            reporter=ConsoleReporter(),
        )
        print_findings(result.findings)
        copy_result = copy_zip(result.output_zip, args.copy)
        status_messages = {
            "file": "✅ ZIP copiado al portapapeles.",
            "path": "✅ Ruta copiada.",
            "path_fallback": "⚠️ Fallo al copiar archivo; se copió la ruta como texto.",
            "none": "✅ ZIP creado sin copiar.",
            "failed": f"❌ Error al copiar. Archivo en: {result.output_zip}",
        }
        status = status_messages.get(copy_result, status_messages["failed"])
        print(
            "-" * 30
            + f"\nIncluidos: {result.included_count} | Ignorados: {result.ignored_count}\n"
            + status
            + "\n"
            + "-" * 30
        )
        return 0
    except PackAIError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 2
