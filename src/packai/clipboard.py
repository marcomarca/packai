"""Windows clipboard adapter kept outside the application core."""

from __future__ import annotations

import subprocess
from pathlib import Path


def copy_zip_with_powershell(zip_path: Path) -> bool:
    """Copy a ZIP to the Windows clipboard as a pasteable file."""
    resolved = zip_path.expanduser().resolve()
    if not resolved.is_file():
        return False
    script = "& { Set-Clipboard -LiteralPath $args[0] }"
    for executable in ("powershell", "pwsh"):
        try:
            result = subprocess.run(
                [executable, "-NoProfile", "-Command", script, str(resolved)],
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError:
            continue
        if result.returncode == 0:
            return True
    return False


def copy_path_as_text(path: Path) -> bool:
    """Copy an absolute path to the Windows clipboard as text."""
    script = "& { Set-Clipboard -Value $args[0] }"
    for executable in ("powershell", "pwsh"):
        try:
            result = subprocess.run(
                [executable, "-NoProfile", "-Command", script, str(path.resolve())],
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError:
            continue
        if result.returncode == 0:
            return True
    return False


def copy_text_to_clipboard(text: str) -> bool:
    """Copy text to the Windows clipboard through stdin."""
    script = "& { $inputText = [Console]::In.ReadToEnd(); Set-Clipboard -Value $inputText }"
    for executable in ("powershell", "pwsh"):
        try:
            result = subprocess.run(
                [executable, "-NoProfile", "-Command", script],
                input=text,
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError:
            continue
        if result.returncode == 0:
            return True
    return False


def copy_zip(zip_path: Path, mode: str) -> str:
    """Apply the CLI clipboard mode and return a stable status code."""
    if mode == "none":
        return "none"
    if mode == "path":
        return "path" if copy_path_as_text(zip_path) else "failed"
    if mode == "file":
        if copy_zip_with_powershell(zip_path):
            return "file"
        if copy_path_as_text(zip_path):
            return "path_fallback"
    return "failed"
