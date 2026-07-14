"""Small, typed Python bridge exposed to the local React interface."""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import cast

from packai.application import PackService
from packai.clipboard import copy_text_to_clipboard, copy_zip
from packai.contracts import FileFinding, PackMetrics, PackRequest, ProgressEvent
from packai.errors import PackAIError, PackValidationError
from packai.gui.commands import build_commands
from packai.gui.contracts import CopyMode, GuiLaunchOptions
from packai.gui.tree import FolderNode, scan_folder_tree
from packai.naming import build_default_zip_stem
from packai.policy import normalize_cli_exclude_paths

type JsonValue = object
type JsonObject = dict[str, object]


class GuiBridge:
    """Presentation-neutral operations callable through ``window.pywebview.api``."""

    def __init__(self, options: GuiLaunchOptions) -> None:
        self._initial = replace(options, root=options.root.expanduser().resolve())
        self._lock = threading.RLock()
        self._service = PackService()
        self._preview_cache: dict[tuple[object, ...], JsonObject] = {}
        self._revision = 0

    def initialize(self) -> JsonObject:
        """Return the complete initial model expected by the React application."""
        return self._guard(lambda: self._refresh_model(self._payload_from_options(self._initial)))

    def refresh(self, payload: object) -> JsonObject:
        """Rescan the folder tree and recalculate metrics after filesystem changes."""
        return self._guard(lambda: self._refresh_model(self._require_payload(payload)))

    def preview(self, payload: object) -> JsonObject:
        """Calculate current metrics without creating an archive."""
        return self._guard(lambda: self._preview_model(self._require_payload(payload)))

    def pack(self, payload: object) -> JsonObject:
        """Rescan and create a fresh ZIP from the current project state."""
        return self._guard(lambda: self._pack_model(self._require_payload(payload)))

    def copy_command(self, command: object) -> JsonObject:
        """Copy a generated command using the existing safe clipboard adapter."""
        if not isinstance(command, str) or not command:
            return self._error(
                "invalid_command", "Comando inválido", "No hay un comando para copiar."
            )
        if copy_text_to_clipboard(command):
            return {"ok": True}
        return self._error(
            "clipboard_unavailable",
            "No se pudo usar el portapapeles",
            "Copia el comando manualmente. En Windows verifica que PowerShell esté disponible.",
        )

    def invalidate_cache(self) -> None:
        """Invalidate previews after a filesystem event without doing heavy work."""
        with self._lock:
            self._revision += 1
            self._preview_cache.clear()

    def _refresh_model(self, payload: JsonObject) -> JsonObject:
        with self._lock:
            self._preview_cache.clear()
            options, excluded = self._parse_options(payload)
            tree = scan_folder_tree(
                options.root,
                include_env_example=options.include_env_example,
            )
            preview = self._preview(options, excluded)
            return {
                "ok": True,
                "revision": self._revision,
                "root": str(options.root),
                "project_name": options.root.name or "project",
                "tree": [_folder_to_json(node) for node in tree],
                "excluded_paths": list(excluded),
                "options": _options_to_json(options),
                "preview": preview,
                "commands": build_commands(options, excluded),
            }

    def _preview_model(self, payload: JsonObject) -> JsonObject:
        with self._lock:
            options, excluded = self._parse_options(payload)
            preview = self._preview(options, excluded)
            return {
                "ok": True,
                "revision": self._revision,
                "excluded_paths": list(excluded),
                "options": _options_to_json(options),
                "preview": preview,
                "commands": build_commands(options, excluded),
            }

    def _pack_model(self, payload: JsonObject) -> JsonObject:
        with self._lock:
            options, excluded = self._parse_options(payload)
            output_zip = self._output_zip(options.root)
            events: list[ProgressEvent] = []
            result = self._service.pack(
                self._request(options, excluded, output_zip),
                reporter=events.append,
            )
            copy_status = copy_zip(result.output_zip, options.copy_mode)
            tree = scan_folder_tree(
                options.root,
                include_env_example=options.include_env_example,
            )
            self._preview_cache.clear()
            self._revision += 1
            return {
                "ok": True,
                "revision": self._revision,
                "output_zip": str(result.output_zip),
                "copy_status": copy_status,
                "copy_message": _copy_message(copy_status, result.output_zip),
                "tree": [_folder_to_json(node) for node in tree],
                "excluded_paths": list(excluded),
                "options": _options_to_json(options),
                "preview": _result_to_json(result.metrics, result.findings, events),
                "commands": build_commands(options, excluded),
            }

    def _preview(self, options: GuiLaunchOptions, excluded: tuple[str, ...]) -> JsonObject:
        key = (
            self._revision,
            excluded,
            options.force,
            options.include_git_context,
            options.include_env_example,
            options.token_top,
        )
        cached = self._preview_cache.get(key)
        if cached is not None:
            return cached

        events: list[ProgressEvent] = []
        preview = self._service.preview(
            self._request(options, excluded, self._output_zip(options.root)),
            reporter=events.append,
        )
        serialized = _result_to_json(preview.metrics, preview.findings, events)
        self._preview_cache[key] = serialized
        return serialized

    def _parse_options(self, payload: JsonObject) -> tuple[GuiLaunchOptions, tuple[str, ...]]:
        raw_excludes = payload.get("exclude_paths", list(self._initial.exclude_paths))
        if not isinstance(raw_excludes, list) or not all(
            isinstance(path, str) for path in raw_excludes
        ):
            raise PackValidationError("exclude_paths debe ser una lista de carpetas relativas.")

        excluded = self._sanitize_excludes(cast(list[str], raw_excludes))
        force = _bool_value(payload, "force", self._initial.force)
        include_git = _bool_value(
            payload,
            "include_git_context",
            self._initial.include_git_context,
        )
        include_env = _bool_value(
            payload,
            "include_env_example",
            self._initial.include_env_example,
        )
        token_top = _int_value(payload, "token_top", self._initial.token_top)
        if token_top < 0 or token_top > 100:
            raise PackValidationError("token_top debe estar entre 0 y 100.")
        copy_mode_raw = payload.get("copy_mode", self._initial.copy_mode)
        if copy_mode_raw not in {"file", "path", "none"}:
            raise PackValidationError("copy_mode debe ser file, path o none.")
        copy_mode = cast(CopyMode, copy_mode_raw)

        return (
            GuiLaunchOptions(
                root=self._initial.root,
                exclude_paths=excluded,
                force=force,
                include_git_context=include_git,
                include_env_example=include_env,
                token_top=token_top,
                copy_mode=copy_mode,
            ),
            excluded,
        )

    def _sanitize_excludes(self, raw_paths: list[str]) -> tuple[str, ...]:
        valid: list[str] = []
        for raw_path in raw_paths:
            candidate = self._initial.root / raw_path
            if not candidate.exists() or not candidate.is_dir():
                continue
            valid.extend(normalize_cli_exclude_paths(self._initial.root, (raw_path,)))

        ordered = sorted(set(valid), key=lambda item: (item.count("/"), item))
        minimal: list[str] = []
        for path in ordered:
            if any(path == parent or path.startswith(f"{parent}/") for parent in minimal):
                continue
            minimal.append(path)
        return tuple(minimal)

    @staticmethod
    def _request(
        options: GuiLaunchOptions, excluded: tuple[str, ...], output_zip: Path
    ) -> PackRequest:
        return PackRequest(
            root=options.root,
            output_zip=output_zip,
            include_env_example=options.include_env_example,
            force=options.force,
            include_git_context=options.include_git_context,
            exclude_paths=excluded,
            token_top=options.token_top,
        )

    @staticmethod
    def _output_zip(root: Path) -> Path:
        return root.parent / f"{build_default_zip_stem(root)}.zip"

    @staticmethod
    def _payload_from_options(options: GuiLaunchOptions) -> JsonObject:
        return {
            "exclude_paths": list(options.exclude_paths),
            "force": options.force,
            "include_git_context": options.include_git_context,
            "include_env_example": options.include_env_example,
            "token_top": options.token_top,
            "copy_mode": options.copy_mode,
        }

    @staticmethod
    def _require_payload(payload: object) -> JsonObject:
        if not isinstance(payload, dict) or not all(isinstance(key, str) for key in payload):
            raise PackValidationError("La configuración de la interfaz no es válida.")
        return cast(JsonObject, payload)

    def _guard(self, operation: Callable[[], JsonObject]) -> JsonObject:
        try:
            return operation()
        except PackAIError as exc:
            return self._error("packai_error", "No se pudo completar la operación", str(exc))
        except Exception as exc:  # UI boundary: return a safe, actionable error object.
            return self._error(
                "unexpected_error",
                "Error inesperado en la interfaz",
                f"{type(exc).__name__}: {exc}",
            )

    @staticmethod
    def _error(code: str, title: str, message: str) -> JsonObject:
        return {
            "ok": False,
            "error": {
                "code": code,
                "title": title,
                "message": message,
                "resolution": "Actualiza el proyecto y vuelve a intentarlo. El CLI tradicional sigue disponible.",
            },
        }


def _bool_value(payload: JsonObject, key: str, default: bool) -> bool:
    value = payload.get(key, default)
    if not isinstance(value, bool):
        raise PackValidationError(f"{key} debe ser verdadero o falso.")
    return value


def _int_value(payload: JsonObject, key: str, default: int) -> int:
    value = payload.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int):
        raise PackValidationError(f"{key} debe ser un número entero.")
    return value


def _folder_to_json(node: FolderNode) -> JsonObject:
    return {
        "name": node.name,
        "path": node.relative_path,
        "disabled": node.disabled,
        "disabled_reason": node.disabled_reason,
        "direct_file_count": node.direct_file_count,
        "total_size_bytes": node.total_size_bytes,
        "children": [_folder_to_json(child) for child in node.children],
    }


def _options_to_json(options: GuiLaunchOptions) -> JsonObject:
    return {
        "force": options.force,
        "include_git_context": options.include_git_context,
        "include_env_example": options.include_env_example,
        "token_top": options.token_top,
        "copy_mode": options.copy_mode,
    }


def _result_to_json(
    metrics: PackMetrics | None,
    findings: tuple[FileFinding, ...],
    events: list[ProgressEvent],
) -> JsonObject:
    warnings = [event.message for event in events if event.kind == "warning" and event.message]
    return {
        "metrics": _metrics_to_json(metrics),
        "findings": [_finding_to_json(finding) for finding in findings],
        "warnings": warnings,
    }


def _metrics_to_json(metrics: PackMetrics | None) -> JsonValue:
    if metrics is None:
        return None
    return {
        "included_files": metrics.included_files,
        "text_files": metrics.text_files,
        "binary_files": metrics.binary_files,
        "code_files": metrics.code_files,
        "code_lines": metrics.code_lines,
        "uncompressed_size": metrics.uncompressed_size,
        "zip_size": metrics.zip_size,
        "estimated_tokens": metrics.estimated_tokens,
        "tokenizer": metrics.tokenizer,
        "degraded": metrics.degraded,
        "complete": metrics.complete,
        "warnings": list(metrics.warnings),
        "language_code_lines": [
            {
                "language": item.language,
                "files": item.files,
                "code_lines": item.code_lines,
            }
            for item in metrics.language_code_lines
        ],
        "largest_token_files": [
            {
                "relative_path": item.relative_path,
                "token_count": item.token_count,
                "uncompressed_size": item.uncompressed_size,
            }
            for item in metrics.largest_token_files
        ],
    }


def _finding_to_json(finding: FileFinding) -> JsonObject:
    return {
        "relative_path": finding.relative_path,
        "reason": finding.reason,
        "forced": finding.forced,
        "details": [
            {
                "kind": detail.kind,
                "masked_value": detail.masked_value,
                "line": detail.line,
            }
            for detail in finding.details
        ],
    }


def _copy_message(status: str, output_zip: Path) -> str:
    messages = {
        "file": "ZIP creado y copiado al portapapeles.",
        "path": "ZIP creado y ruta copiada al portapapeles.",
        "path_fallback": "ZIP creado. No se pudo copiar el archivo; se copió su ruta.",
        "none": "ZIP creado sin copiar al portapapeles.",
        "failed": f"ZIP creado en {output_zip}, pero el portapapeles no estuvo disponible.",
    }
    return messages.get(status, messages["failed"])
