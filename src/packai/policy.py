"""Pure path and secret-scanning policies."""

from __future__ import annotations

import fnmatch
import re
from pathlib import Path, PureWindowsPath
from typing import Final

from packai.contracts import SecretFinding
from packai.errors import PackValidationError

# Directorios que se ignoran en cualquier nivel de la ruta
IGNORED_DIR_NAMES = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    "dist",
    "build",
    ".next",
    ".nuxt",
    "coverage",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".uv-cache",
    ".idea",
    ".vscode",
    ".cache",
    "target",
}

# Directorios ocultos que si suelen aportar contexto al revisar el proyecto.
ALLOWED_DOT_DIR_NAMES = {".github"}

# Extensiones o patrones de archivos basura adicionales
DEFAULT_IGNORE = [
    "*.pyc",
    "*.pyo",
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
    "*.mp4",
    "*.mov",
    "*.xlsx",
    "*.docx",
    "*.exe",
    "*.dll",
    "*.so",
    "*.dylib",
    "*.jar",
    "*.war",
    "*.wasm",
    "*.bin",
    "*.dat",
    "*.class",
    "*.o",
    "*.obj",
]

# Archivos sensibles que se excluyen siempre por nombre
STRICT_EXCLUDE_PATTERNS = [
    ".env",
    ".env.*",
    "**/.env",
    "**/.env.*",
]

SECRET_FILE_PATTERNS = [
    ".env",
    ".env.*",
    "*.env",
    "*.pem",
    "*.key",
    "*.p8",
    "*.p12",
    "*.pfx",
    "*.crt",
    "*.cer",
    "id_rsa",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
    "known_hosts",
    "authorized_keys",
    ".npmrc",
    ".pypirc",
    ".netrc",
    ".dockercfg",
    "docker-compose.override.yml",
    "credentials",
    "credentials.json",
    "service-account*.json",
    "*service_account*.json",
    "firebase-adminsdk*.json",
    "google-credentials*.json",
    "gcloud*.json",
    "kubeconfig",
    "*.kubeconfig",
    "secrets.yml",
    "secrets.yaml",
    "secrets.json",
    "secret.yml",
    "secret.yaml",
    "secret.json",
    "local.settings.json",
    "appsettings.Production.json",
    "appsettings.Local.json",
    "application-prod.yml",
    "application-prod.yaml",
    "terraform.tfvars",
    "*.tfvars",
    "*.tfstate",
    "*.tfstate.backup",
]

# Archivos de ejemplo de entorno que pueden permitirse (se escanean igual)
SAFE_ENV_EXAMPLES = {".env.example", ".env.sample", ".env.template"}
GIT_CONTEXT_FILENAME = "git--diff_last_commit.md"

# Patrones de alta confianza para tokens con prefijo
SECRET_PATTERNS = {
    "OpenAI API Key": re.compile(
        r"\b(?:sk-" + r"[A-Za-z0-9]{32,}|sk-proj-" + r"[A-Za-z0-9_-]{48,})\b"
    ),
    "Groq API Key": re.compile(r"\bgsk_" + r"[A-Za-z0-9_-]{32,}\b"),
    "Anthropic API Key": re.compile(r"\bsk-ant-" + r"[A-Za-z0-9_-]{32,}\b"),
    "Hugging Face Token": re.compile(r"\bhf_" + r"[A-Za-z0-9]{30,}\b"),
    "Replicate API Token": re.compile(r"\br8_" + r"[A-Za-z0-9]{32,}\b"),
    "Perplexity API Key": re.compile(r"\bpplx-" + r"[A-Za-z0-9]{32,}\b"),
    "Generic SK API Key": re.compile(r"\bsk-" + r"[A-Za-z0-9_-]{32,}\b"),
    "AWS Access Key ID": re.compile(r"\b(?:" + r"AKIA|ASIA)[0-9A-Z]{16}\b"),
    "AWS Secret Access Key Context": re.compile(
        r"(?i)\baws_secret_access_key\b\s*[:=]\s*[\"']?[A-Za-z0-9/+=]{40}[\"']?"
    ),
    "Google API Key": re.compile(r"\bAIza" + r"[0-9A-Za-z_-]{35}\b"),
    "Google OAuth Client Secret": re.compile(r"\bGOCSPX-" + r"[A-Za-z0-9_-]{20,}\b"),
    "Google Service Account Private Key": re.compile(
        r"-----BEGIN " + r"PRIVATE KEY-----[\s\S]+?-----END " + r"PRIVATE KEY-----"
    ),
    "Azure Storage Connection String": re.compile(
        r"(?i)\bDefaultEndpointsProtocol=https?;AccountName=[^;]+;AccountKey=[A-Za-z0-9+/=]{60,};EndpointSuffix="
    ),
    "Azure Storage Account Key Context": re.compile(
        r"(?i)\b(?:azure|account).{0,30}(?:key|secret)\b\s*[:=]\s*[\"']?[A-Za-z0-9+/=]{60,}[\"']?"
    ),
    "Cloudflare API Token Context": re.compile(
        r"(?i)\b(?:cloudflare|cf)_(?:api_)?(?:token|key)\b\s*[:=]\s*[\"']?[A-Za-z0-9_-]{30,}[\"']?"
    ),
    "DigitalOcean Token": re.compile(r"\bdop_v1_[A-Fa-f0-9]{64}\b"),
    "Heroku API Key Context": re.compile(
        r"(?i)\bheroku(?:_api)?_key\b\s*[:=]\s*[\"']?[A-Fa-f0-9]{32}[\"']?"
    ),
    "GitHub Classic Token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36}\b"),
    "GitHub Fine-Grained Token": re.compile(r"\bgithub_pat_[A-Za-z0-9_]{40,}\b"),
    "GitLab Token": re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}\b"),
    "GitLab OAuth Token": re.compile(r"\bgloas-[A-Za-z0-9_-]{20,}\b"),
    "NPM Token": re.compile(r"\bnpm_[A-Za-z0-9]{36}\b"),
    "PyPI Token": re.compile(r"\bpypi-[A-Za-z0-9_-]{50,}\b"),
    "Generic Private Key": re.compile(
        r"-----BEGIN (?:RSA|DSA|EC|OPENSSH|PGP|PRIVATE) PRIVATE KEY-----"
    ),
    "Stripe Secret Key": re.compile(r"\bsk_(?:live|test)_[A-Za-z0-9]{20,}\b"),
    "Slack Token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,100}\b"),
    "Discord Bot Token": re.compile(
        r"\b[A-Za-z0-9_-]{24}\.[A-Za-z0-9_-]{6}\.[A-Za-z0-9_-]{25,110}\b"
    ),
    "Telegram Bot Token": re.compile(r"\b[0-9]{8,12}:[A-Za-z0-9_-]{30,}\b"),
    "SendGrid API Key": re.compile(r"\bSG\.[A-Za-z0-9_-]{16,32}\.[A-Za-z0-9_-]{32,80}\b"),
    "JWT Token": re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
}

# Patrones contextuales para asignaciones sospechosas
SENSITIVE_ASSIGNMENT_PATTERNS = {
    "Generic API Key Assignment": re.compile(
        r"(?i)\b[A-Z0-9_]*(?:API_KEY|ACCESS_KEY|SECRET_KEY|PRIVATE_KEY|APP_KEY)[A-Z0-9_]*\b\s*[:=]\s*[\"']?[^\"'\s]{12,}[\"']?"
    ),
    "Generic Token Assignment": re.compile(
        r"(?i)\b[A-Z0-9_]*(?:TOKEN|AUTH_TOKEN|ACCESS_TOKEN|REFRESH_TOKEN|ID_TOKEN)[A-Z0-9_]*\b\s*[:=]\s*[\"']?[^\"'\s]{12,}[\"']?"
    ),
    "Generic Password Assignment": re.compile(
        r"(?i)\b[A-Z0-9_]*(?:PASSWORD|PASSWD|PWD)[A-Z0-9_]*\b\s*[:=]\s*[\"']?[^\"'\s]{8,}[\"']?"
    ),
    "Generic DB Connection String": re.compile(
        r"(?i)\b(?:DATABASE_URL|DB_URL|DATABASE_URI|MONGO_URI|REDIS_URL)\b\s*[:=]\s*[\"']?[^\"'\s]{12,}[\"']?"
    ),
}

MAX_SECRET_SCAN_BYTES: Final = 1024 * 1024


def mask_secret(value: str, visible_start: int = 6, visible_end: int = 4) -> str:
    """Mask a detected value so reports do not leak the complete secret."""
    value = value.strip()
    if len(value) <= visible_start + visible_end:
        return "*" * len(value)
    return f"{value[:visible_start]}...{value[-visible_end:]}"


def load_ignore_file(path: Path) -> list[str]:
    """Load non-comment patterns while supporting common text encodings."""
    if not path.exists():
        return []
    for encoding in ("utf-8", "utf-16", "latin-1"):
        try:
            content = path.read_text(encoding=encoding)
            return [
                line.strip()
                for line in content.splitlines()
                if line.strip() and not line.strip().startswith("#")
            ]
        except UnicodeDecodeError:
            continue
        except OSError as exc:
            raise PackValidationError(f"No se pudo leer {path}: {exc}") from exc
    raise PackValidationError(
        f"No se pudo decodificar {path} (probablemente binario o formato inválido)"
    )


def load_project_ignore(root: Path) -> list[str]:
    """Load project-specific exclusion patterns."""
    return load_ignore_file(root / ".ignore2packai")


def is_probably_binary(path: Path, sample_size: int = 4096) -> bool:
    """Detect likely binary files by checking for NUL bytes."""
    try:
        with path.open("rb") as file_handle:
            return b"\x00" in file_handle.read(sample_size)
    except OSError:
        return True


def is_ignored_dir_name(name: str) -> bool:
    """Return whether a directory is globally excluded."""
    return name in IGNORED_DIR_NAMES or (name.startswith(".") and name not in ALLOWED_DOT_DIR_NAMES)


def matches_any_path_pattern(relative_path: str, patterns: list[str]) -> bool:
    normalized = relative_path.replace("\\", "/")
    name = Path(normalized).name
    return any(
        fnmatch.fnmatch(normalized, pattern) or fnmatch.fnmatch(name, pattern)
        for pattern in patterns
    )


def normalize_cli_exclude_paths(
    root: Path, exclude_paths: list[str] | tuple[str, ...]
) -> list[str]:
    """Validate and normalize project-relative directories selected for exclusion."""
    normalized_dirs: list[str] = []
    seen: set[str] = set()
    root_resolved = root.resolve()

    for raw_path in exclude_paths:
        raw = str(raw_path).strip()
        if not raw:
            raise PackValidationError("La ruta de exclusión no puede estar vacía.")

        windows_path = PureWindowsPath(raw)
        if Path(raw).is_absolute() or windows_path.is_absolute() or windows_path.drive:
            raise PackValidationError(
                f"La exclusión debe ser relativa al proyecto, no absoluta: {raw}"
            )

        normalized = raw.replace("\\", "/").strip()
        if normalized == "~" or normalized.startswith("~/"):
            raise PackValidationError(
                f"La exclusión debe ser relativa al proyecto, no al home del usuario: {raw}"
            )

        parts = [part for part in normalized.split("/") if part and part != "."]
        if not parts:
            raise PackValidationError("No puedes excluir la raíz completa del proyecto con '.'.")
        if any(part == ".." for part in parts):
            raise PackValidationError(
                f"La exclusión no puede salir del proyecto usando '..': {raw}"
            )

        relative = "/".join(parts)
        candidate = (root_resolved / relative).resolve()
        try:
            candidate.relative_to(root_resolved)
        except ValueError as exc:
            raise PackValidationError(f"La exclusión apunta fuera del proyecto: {raw}") from exc

        if not candidate.exists():
            raise PackValidationError(
                f"La carpeta a excluir no existe dentro del proyecto: {relative}"
            )
        if not candidate.is_dir():
            raise PackValidationError(
                f"La exclusión debe apuntar a una carpeta, no a un archivo: {relative}"
            )

        relative = candidate.relative_to(root_resolved).as_posix()
        if relative not in seen:
            normalized_dirs.append(relative)
            seen.add(relative)

    return normalized_dirs


def build_runtime_exclude_patterns(exclude_dirs: list[str] | tuple[str, ...]) -> list[str]:
    """Convert relative directories to exact recursive archive patterns."""
    return [f"{directory.rstrip('/')}/**" for directory in exclude_dirs]


def build_git_exclude_pathspecs(exclude_dirs: list[str] | tuple[str, ...]) -> list[str]:
    """Convert relative directories to Git exclusion pathspecs."""
    return [f":(exclude){directory.rstrip('/')}/**" for directory in exclude_dirs]


def should_ignore_path(
    relative_path: str,
    patterns: list[str] | tuple[str, ...],
    include_env_example: bool = True,
    ignore_secrets: bool = False,
) -> str | None:
    """Classify a path as strict, sensitive, pattern-based, or included."""
    normalized = relative_path.replace("\\", "/")
    is_dir_path = normalized.endswith("/")
    path_obj = Path(normalized)
    parts = path_obj.parts
    name = path_obj.name

    directory_parts = parts if is_dir_path else parts[:-1]
    if any(is_ignored_dir_name(part) for part in directory_parts):
        return "strict"

    is_safe_env = include_env_example and name in SAFE_ENV_EXAMPLES
    if not is_safe_env and matches_any_path_pattern(normalized, STRICT_EXCLUDE_PATTERNS):
        return "strict"

    if not is_safe_env:
        if name == ".env" or fnmatch.fnmatch(name, ".env.*") or fnmatch.fnmatch(name, "*.env"):
            return "strict"
        if not ignore_secrets and any(
            fnmatch.fnmatch(name, pattern) for pattern in SECRET_FILE_PATTERNS
        ):
            return "sensitive"

    for raw_pattern in patterns:
        pattern = raw_pattern.strip().replace("\\", "/")
        if not pattern:
            continue
        if pattern.endswith("/"):
            directory_pattern = pattern.rstrip("/")
            if normalized.startswith(pattern) or f"/{directory_pattern}/" in f"/{normalized}/":
                return "pattern"
        if fnmatch.fnmatch(normalized, pattern) or fnmatch.fnmatch(name, pattern):
            return "pattern"

    return None


def scan_text_for_secrets(content: str) -> tuple[SecretFinding, ...]:
    """Scan text using high-confidence and contextual secret patterns."""
    findings: list[SecretFinding] = []
    occupied_ranges: list[tuple[int, int]] = []

    def line_number(position: int) -> int:
        return content.count("\n", 0, position) + 1

    def overlaps(start: int, end: int) -> bool:
        return any(
            not (end <= old_start or start >= old_end) for old_start, old_end in occupied_ranges
        )

    for kind, pattern in SECRET_PATTERNS.items():
        for match in pattern.finditer(content):
            start, end = match.span()
            if overlaps(start, end):
                continue
            findings.append(
                SecretFinding(
                    kind=kind,
                    masked_value=mask_secret(match.group(0)),
                    line=line_number(start),
                )
            )
            occupied_ranges.append((start, end))

    for kind, pattern in SENSITIVE_ASSIGNMENT_PATTERNS.items():
        for match in pattern.finditer(content):
            start, end = match.span()
            if overlaps(start, end):
                continue
            findings.append(
                SecretFinding(
                    kind=kind,
                    masked_value=mask_secret(match.group(0)),
                    line=line_number(start),
                )
            )
            occupied_ranges.append((start, end))

    return tuple(findings)


def scan_file_for_secrets(path: Path) -> tuple[SecretFinding, ...]:
    """Scan a text file while translating read failures into explicit findings."""
    try:
        size = path.stat().st_size
    except OSError as exc:
        return (
            SecretFinding(
                kind="No se pudo leer el archivo",
                masked_value=str(exc),
                line=None,
            ),
        )

    if size > MAX_SECRET_SCAN_BYTES:
        return (
            SecretFinding(
                kind="Archivo demasiado grande para escaneo",
                masked_value=f"{size} bytes",
                line=None,
            ),
        )

    for encoding in ("utf-8", "utf-16", "latin-1"):
        try:
            content = path.read_text(encoding=encoding, errors="strict")
            return scan_text_for_secrets(content)
        except UnicodeDecodeError:
            continue
        except OSError as exc:
            return (
                SecretFinding(
                    kind="No se pudo leer el archivo",
                    masked_value=str(exc),
                    line=None,
                ),
            )

    return (
        SecretFinding(
            kind="No se pudo decodificar el archivo para escaneo",
            masked_value="Probablemente binario o formato inválido",
            line=None,
        ),
    )
