import argparse
import ctypes
import fnmatch
import os
import re
import struct
import subprocess
import zipfile
from pathlib import Path

try:
    import win32clipboard
    import win32con
    HAS_PYWIN32 = True
except ImportError:
    HAS_PYWIN32 = False

# Patrones de exclusión por defecto
DEFAULT_IGNORE = [
    ".git/*", "node_modules/*", ".venv/*", "venv/*", "env/*", "__pycache__/*",
    "dist/*", "build/*", ".next/*", ".nuxt/*", "coverage/*", ".pytest_cache/*",
    ".mypy_cache/*", ".idea/*", ".vscode/*", ".cache/*", "target/*",
    ".env", ".env.*", "*.pem", "*.key", "*.p12", "*.pfx", "id_rsa", "id_ed25519",
    "*.kubeconfig", "kubeconfig", ".npmrc", ".pypirc", "credentials.json",
    "service-account*.json", "firebase-adminsdk*.json", "google-credentials*.json",
    "*.log", "*.tmp", "*.cache", "*.zip", "*.tar", "*.gz", "*.rar", "*.7z",
    "*.sqlite", "*.db", "*.png", "*.jpg", "*.jpeg", "*.gif", "*.webp", "*.mp4",
    "*.mov", "*.pdf", "*.xlsx", "*.docx",
]

SECRET_PATTERNS = {
    "AWS Key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "OpenAI Key": re.compile(r"sk-[a-zA-Z0-9]{32,}|sk-proj-[a-zA-Z0-9\-_]{48,}"),
    "Generic Private Key": re.compile(r"-----BEGIN (RSA|EC|PGP|OPENSSH) PRIVATE KEY-----"),
    "Google API Key": re.compile(r"AIza[0-9A-Za-z\\-_]{35}"),
    "Slack Token": re.compile(r"xox[baprs]-[0-9a-zA-Z]{10,48}"),
    "GitHub Token": re.compile(r"gh[opsu]_[0-9a-zA-Z]{36}"),
}

def load_aiignore(root: Path) -> list[str]:
    aiignore = root / ".aiignore"
    if not aiignore.exists(): return []
    patterns = []
    try:
        for line in aiignore.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#"): continue
            patterns.append(line)
    except Exception: pass
    return patterns

def should_ignore_path(relative_path: str, patterns: list[str]) -> bool:
    normalized = relative_path.replace("\\", "/")
    for pattern in patterns:
        pattern = pattern.strip().replace("\\", "/")
        if not pattern: continue
        if pattern.endswith("/") and normalized.startswith(pattern): return True
        if fnmatch.fnmatch(normalized, pattern): return True
        if fnmatch.fnmatch(Path(normalized).name, pattern): return True
    return False

def contains_secrets(file_path: Path) -> tuple[bool, str | None]:
    if file_path.stat().st_size > 1024 * 1024: return False, None
    for encoding in ["utf-8", "utf-16", "latin-1"]:
        try:
            content = file_path.read_text(encoding=encoding, errors="strict")
            for name, pattern in SECRET_PATTERNS.items():
                if pattern.search(content): return True, name
            break
        except (UnicodeDecodeError, Exception): continue
    return False, None

def copy_file_to_clipboard(file_path: Path) -> bool:
    """Copia un archivo al portapapeles de Windows (como objeto pegable)."""
    abs_path = str(file_path.resolve())
    
    # 1. Intentar con PowerShell (el método más nativo y fiable en Windows moderno)
    try:
        # Comando para copiar archivo al portapapeles
        cmd = f'powershell -Command "Set-Clipboard -Path \'{abs_path}\'"'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            return True
    except Exception:
        pass

    # 2. Intentar con pywin32 (como respaldo o si PS falla)
    if HAS_PYWIN32:
        try:
            # Estructura DROPFILES
            files_bytes = (abs_path + "\0\0").encode("utf-16le")
            dropfiles = struct.pack("IiiII", 20, 0, 0, 0, 1) + files_bytes
            
            kernel32 = ctypes.windll.kernel32
            h_mem = kernel32.GlobalAlloc(0x0042, len(dropfiles)) # GHND
            if h_mem:
                ptr = kernel32.GlobalLock(h_mem)
                ctypes.memmove(ptr, dropfiles, len(dropfiles))
                kernel32.GlobalUnlock(h_mem)
                
                win32clipboard.OpenClipboard()
                try:
                    win32clipboard.EmptyClipboard()
                    win32clipboard.SetClipboardData(win32con.CF_HDROP, h_mem)
                    return True
                finally:
                    win32clipboard.CloseClipboard()
        except Exception:
            pass
            
    return False

def create_zip(root: Path, output_zip: Path, patterns: list[str], scan_secrets: bool = True) -> tuple[int, int, list[str]]:
    included, ignored, secret_warnings = 0, 0, []
    with zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_DEFLATED) as zipf:
        for path in root.rglob("*"):
            if not path.is_file() or path.resolve() == output_zip.resolve(): continue
            relative = path.relative_to(root).as_posix()
            if should_ignore_path(relative, patterns):
                ignored += 1
                continue
            if scan_secrets:
                has_secret, secret_type = contains_secrets(path)
                if has_secret:
                    secret_warnings.append(f"SALTADO: {relative}")
                    ignored += 1
                    continue
            zipf.write(path, arcname=relative)
            included += 1
    return included, ignored, secret_warnings

def main():
    parser = argparse.ArgumentParser(description="Pack AI project to ZIP.")
    parser.add_argument("folder", nargs="*", help="Carpeta.")
    args = parser.parse_args()

    folder_path = " ".join(args.folder) if args.folder else "."
    root = Path(folder_path).expanduser().resolve()
    if not root.exists(): return

    name = root.name if root.name else "project"
    output_zip = root.parent / f"{name}.zip"

    patterns = DEFAULT_IGNORE + load_aiignore(root)
    print(f"Empaquetando: {root.name}...")
    
    included, ignored, _ = create_zip(root, output_zip, patterns)

    if copy_file_to_clipboard(output_zip):
        status = "✅ ZIP copiado. ¡Ya puedes darle a Pegar (Ctrl+V)!"
    else:
        status = f"❌ Error al copiar. El archivo está en: {output_zip}"

    print("-" * 30)
    print(f"Incluidos: {included} | Ignorados: {ignored}")
    print(status)
    print("-" * 30)

if __name__ == "__main__":
    main()
