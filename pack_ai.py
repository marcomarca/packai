import argparse
import fnmatch
import os
import re
import zipfile
from pathlib import Path

try:
    import pyperclip
except ImportError:
    pyperclip = None

# Patrones de exclusión por defecto
DEFAULT_IGNORE = [
    # Carpetas
    ".git/*",
    "node_modules/*",
    ".venv/*",
    "venv/*",
    "env/*",
    "__pycache__/*",
    "dist/*",
    "build/*",
    ".next/*",
    ".nuxt/*",
    "coverage/*",
    ".pytest_cache/*",
    ".mypy_cache/*",
    ".idea/*",
    ".vscode/*",
    ".cache/*",
    "target/*",

    # Secretos (por extensión o nombre)
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "*.p12",
    "*.pfx",
    "id_rsa",
    "id_ed25519",
    "*.kubeconfig",
    "kubeconfig",
    ".npmrc",
    ".pypirc",
    "credentials.json",
    "service-account*.json",
    "firebase-adminsdk*.json",
    "google-credentials*.json",

    # Basura / binarios pesados / Inútiles para IA
    "*.log",
    "*.tmp",
    "*.cache",
    "*.zip",
    "*.tar",
    "*.gz",
    "*.rar",
    "*.7z",
    "*.sqlite",
    "*.db",
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.gif",
    "*.webp",
    "*.mp4",
    "*.mov",
    "*.pdf",
    "*.xlsx",
    "*.docx",
]

# Regex para detección de secretos en contenido
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
    if not aiignore.exists():
        return []

    patterns = []
    try:
        for line in aiignore.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            patterns.append(line)
    except Exception as e:
        print(f"Advertencia: No se pudo leer .aiignore: {e}")
    
    return patterns


def should_ignore_path(relative_path: str, patterns: list[str]) -> bool:
    normalized = relative_path.replace("\\", "/")

    for pattern in patterns:
        pattern = pattern.strip().replace("\\", "/")
        if not pattern:
            continue

        # Soporte para carpetas tipo "node_modules/"
        if pattern.endswith("/"):
            if normalized.startswith(pattern):
                return True

        if fnmatch.fnmatch(normalized, pattern):
            return True

        # También probar contra el nombre del archivo
        if fnmatch.fnmatch(Path(normalized).name, pattern):
            return True

    return False


def contains_secrets(file_path: Path) -> tuple[bool, str | None]:
    """Escanea el contenido de un archivo en busca de patrones de secretos."""
    # Solo escanear archivos de texto razonablemente pequeños
    if file_path.stat().st_size > 1024 * 1024:  # > 1MB saltar
        return False, None

    # Intentar leer con diferentes codificaciones
    for encoding in ["utf-8", "utf-16", "latin-1"]:
        try:
            content = file_path.read_text(encoding=encoding, errors="strict")
            for name, pattern in SECRET_PATTERNS.items():
                if pattern.search(content):
                    return True, name
            # Si llegamos aquí sin errores, el archivo se leyó bien y no tiene secretos
            break
        except (UnicodeDecodeError, Exception):
            continue
    
    return False, None


def create_zip(root: Path, output_zip: Path, patterns: list[str], scan_secrets: bool = True) -> tuple[int, int, list[str]]:
    included = 0
    ignored = 0
    secret_warnings = []

    with zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_DEFLATED) as zipf:
        for path in root.rglob("*"):
            if not path.is_file():
                continue

            # Evitar incluir el propio ZIP de salida si está dentro del root
            if path.resolve() == output_zip.resolve():
                continue

            relative = path.relative_to(root).as_posix()

            # 1. Ignorar por ruta/nombre
            if should_ignore_path(relative, patterns):
                ignored += 1
                continue

            # 2. Ignorar por contenido (secretos)
            if scan_secrets:
                has_secret, secret_type = contains_secrets(path)
                if has_secret:
                    secret_warnings.append(f"SALTADO (Secret detected: {secret_type}): {relative}")
                    ignored += 1
                    continue

            zipf.write(path, arcname=relative)
            included += 1

    return included, ignored, secret_warnings


def main():
    parser = argparse.ArgumentParser(
        description="Empaqueta una carpeta en ZIP para enviarla a una IA, excluyendo secretos y archivos innecesarios."
    )

    parser.add_argument(
        "folder",
        nargs="?",
        default=".",
        help="Ruta de la carpeta que quieres comprimir. Por defecto: carpeta actual"
    )

    parser.add_argument(
        "-o",
        "--output",
        help="Ruta del ZIP de salida. Por defecto: <nombre_carpeta>_ai.zip"
    )

    parser.add_argument(
        "--no-scan",
        action="store_true",
        help="Desactiva el escaneo de secretos por contenido."
    )

    args = parser.parse_args()

    root = Path(args.folder).expanduser().resolve()

    if not root.exists():
        print(f"Error: La ruta no existe: {root}")
        return

    if not root.is_dir():
        print(f"Error: La ruta no es una carpeta: {root}")
        return

    # Generar nombre de salida por defecto si no se provee
    if args.output:
        output_zip = Path(args.output).expanduser().resolve()
    else:
        # Si root es ".", usar el nombre de la carpeta actual
        name = root.name if root.name else "project"
        output_zip = root.parent / f"{name}_ai.zip"

    custom_ignore = load_aiignore(root)
    patterns = DEFAULT_IGNORE + custom_ignore

    print(f"--- Empaquetando: {root} ---")
    print(f"--- Destino: {output_zip} ---")
    
    included, ignored, warnings = create_zip(root, output_zip, patterns, not args.no_scan)

    for warn in warnings:
        print(f"⚠️  {warn}")

    if pyperclip:
        try:
            pyperclip.copy(str(output_zip))
            clipboard_msg = "✅ Ruta copiada al portapapeles."
        except Exception as e:
            clipboard_msg = f"❌ Error al copiar al portapapeles: {e}"
    else:
        clipboard_msg = "ℹ️ No se copió al portapapeles. (pyperclip no disponible)"

    print("-" * 40)
    print(f"ZIP creado con éxito.")
    print(f"Archivos incluidos: {included}")
    print(f"Archivos ignorados: {ignored}")
    print(clipboard_msg)
    print("-" * 40)


if __name__ == "__main__":
    main()
