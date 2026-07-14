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

# Archivos que se excluyen siempre por nombre, incluso con --force.
# Añade aquí cualquier archivo que deba quedar bloqueado globalmente.
STRICT_EXCLUDE_PATTERNS = [
    ".env",
    ".env.*",
    "**/.env",
    "**/.env.*",
]

# Lockfiles are valuable dependency context and are included by default. The
# list is centralized so CLI, GUI, archive planning, and tests share exactly the
# same definition. Path patterns cover ecosystems whose lockfiles live in a
# conventional nested directory rather than at a project root.
LOCKFILE_NAMES = frozenset(
    {
        ".terraform.lock.hcl",
        "bun.lock",
        "bun.lockb",
        "cabal.project.freeze",
        "Cargo.lock",
        "Cartfile.resolved",
        "Chart.lock",
        "composer.lock",
        "conan.lock",
        "conda-lock.yaml",
        "conda-lock.yml",
        "deno.lock",
        "devenv.lock",
        "devbox.lock",
        "flake.lock",
        "Gemfile.lock",
        "go.sum",
        "go.work.sum",
        "gradle.lockfile",
        "helmfile.lock",
        "Manifest.toml",
        "mix.lock",
        "npm-shrinkwrap.json",
        "package-lock.json",
        "Package.resolved",
        "packages.lock.json",
        "paket.lock",
        "pdm.lock",
        "Pipfile.lock",
        "pixi.lock",
        "pnpm-lock.yaml",
        "pnpm-lock.yml",
        "Podfile.lock",
        "poetry.lock",
        "pubspec.lock",
        "pylock.toml",
        "renv.lock",
        "requirements-dev.lock",
        "requirements.lock",
        "shrinkwrap.yaml",
        "spago.lock",
        "stack.yaml.lock",
        "uv.lock",
        "vcpkg-lock.json",
        "yarn.lock",
    }
)
LOCKFILE_PATH_PATTERNS = (
    "gradle/dependency-locks/*.lockfile",
    "**/gradle/dependency-locks/*.lockfile",
)

LOCKFILE_NAME_KEYS = frozenset(name.casefold() for name in LOCKFILE_NAMES)

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

# Las reglas genéricas se aplican sobre asignaciones literales y sobre nombres
# de configuración que TERMINAN en un concepto sensible. No basta con contener
# la palabra ``token`` o ``password``: nombres de código como
# ``token_estimator`` y ``password_encoder`` no son credenciales.
_ASSIGNMENT_PATTERN = re.compile(
    r"""
    (?P<key>[\"']?[A-Za-z_][A-Za-z0-9_.-]*[\"']?)
    \s*(?::|(?<![=!<>])=(?!=|>))\s*
    (?:
        \"(?P<double>(?:\\.|[^\"\\])*)\"
        | '(?P<single>(?:\\.|[^'\\])*)'
        | (?P<bare>[A-Za-z0-9_./+:@-][A-Za-z0-9_./+=:@-]*)
    )
    """,
    re.VERBOSE,
)
_ASSIGNMENT_TRIGGER_PATTERN = re.compile(
    r"""
    (?:
        api[_-]?key|access[_-]?key|secret[_-]?key|private[_-]?key|app[_-]?key
        | token|password|passwd|pwd
        | database[_-]?url|db[_-]?url|database[_-]?uri|mongo[_-]?uri|redis[_-]?url
    )
    [\"']?\s*(?::|(?<![=!<>])=(?!=|>))
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Compatibilidad para integraciones 1.x que importaban este mapping. El
# escáner principal usa el parser conservador inferior; estas expresiones ya no
# aceptan una palabra sensible en cualquier posición del identificador.
SENSITIVE_ASSIGNMENT_PATTERNS = {
    "Generic API Key Assignment": re.compile(
        r"(?i)\b(?:[A-Z0-9]+[_\-.])*(?:API_KEY|ACCESS_KEY|SECRET_KEY|PRIVATE_KEY|APP_KEY)"
        r"\b\s*(?::|(?<![=!<>])=(?!=|>))\s*[\"']?[^\"'\s,)}\]]{12,}[\"']?"
    ),
    "Generic Token Assignment": re.compile(
        r"(?i)\b(?:[A-Z0-9]+[_\-.])*TOKEN\b\s*"
        r"(?::|(?<![=!<>])=(?!=|>))\s*[\"']?[^\"'\s,)}\]]{12,}[\"']?"
    ),
    "Generic Password Assignment": re.compile(
        r"(?i)\b(?:[A-Z0-9]+[_\-.])*(?:PASSWORD|PASSWD|PWD)\b\s*"
        r"(?::|(?<![=!<>])=(?!=|>))\s*[\"']?[^\"'\s,)}\]]{8,}[\"']?"
    ),
    "Generic DB Connection String": re.compile(
        r"(?i)\b(?:DATABASE_URL|DB_URL|DATABASE_URI|MONGO_URI|REDIS_URL)\b\s*"
        r"(?::|(?<![=!<>])=(?!=|>))\s*[\"']?[^\"'\s,)}\]]{12,}[\"']?"
    ),
}

_ASSIGNMENT_KEY_RULES: tuple[tuple[str, tuple[str, ...], int], ...] = (
    (
        "Generic API Key Assignment",
        ("api_key", "access_key", "secret_key", "private_key", "app_key"),
        12,
    ),
    ("Generic Token Assignment", ("token",), 12),
    ("Generic Password Assignment", ("password", "passwd", "pwd"), 8),
    (
        "Generic DB Connection String",
        ("database_url", "db_url", "database_uri", "mongo_uri", "redis_url"),
        12,
    ),
)

# Evita ejecutar decenas de expresiones regulares sobre archivos grandes cuando
# ni siquiera contienen el prefijo requerido. La comprobación final sigue
# haciéndose con la regex completa.
_SECRET_PATTERN_TRIGGERS: dict[str, tuple[str, ...]] = {
    "OpenAI API Key": ("sk-",),
    "Groq API Key": ("gsk_",),
    "Anthropic API Key": ("sk-ant-",),
    "Hugging Face Token": ("hf_",),
    "Replicate API Token": ("r8_",),
    "Perplexity API Key": ("pplx-",),
    "Generic SK API Key": ("sk-",),
    "AWS Access Key ID": ("AKIA", "ASIA"),
    "AWS Secret Access Key Context": ("aws_secret_access_key",),
    "Google API Key": ("AIza",),
    "Google OAuth Client Secret": ("GOCSPX-",),
    "Google Service Account Private Key": ("-----BEGIN PRIVATE KEY-----",),
    "Azure Storage Connection String": ("DefaultEndpointsProtocol=",),
    "Azure Storage Account Key Context": ("azure", "account"),
    "Cloudflare API Token Context": ("cloudflare", "cf_"),
    "DigitalOcean Token": ("dop_v1_",),
    "Heroku API Key Context": ("heroku",),
    "GitHub Classic Token": ("ghp_", "gho_", "ghu_", "ghs_", "ghr_"),
    "GitHub Fine-Grained Token": ("github_pat_",),
    "GitLab Token": ("glpat-",),
    "GitLab OAuth Token": ("gloas-",),
    "NPM Token": ("npm_",),
    "PyPI Token": ("pypi-",),
    "Generic Private Key": ("-----BEGIN",),
    "Stripe Secret Key": ("sk_live_", "sk_test_"),
    "Slack Token": ("xox",),
    "Discord Bot Token": (".",),
    "Telegram Bot Token": (":",),
    "SendGrid API Key": ("SG.",),
    "JWT Token": ("eyJ",),
}

# El recurso o200k ocupa ~3.8 MB. El límite debe impedir escaneos de archivos
# desproporcionados sin excluir recursos textuales normales del propio paquete.
MAX_SECRET_SCAN_BYTES: Final = 8 * 1024 * 1024


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


def is_lockfile_path(relative_path: str) -> bool:
    """Return whether a project-relative path is a recognized dependency lockfile."""
    normalized = relative_path.replace("\\", "/").rstrip("/")
    if not normalized:
        return False
    name = Path(normalized).name.casefold()
    normalized_key = normalized.casefold()
    return name in LOCKFILE_NAME_KEYS or any(
        fnmatch.fnmatch(normalized_key, pattern.casefold()) for pattern in LOCKFILE_PATH_PATTERNS
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
    include_lockfiles: bool = True,
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

    is_lockfile = not is_dir_path and is_lockfile_path(normalized)
    if is_lockfile:
        # This dedicated switch intentionally takes precedence over ordinary
        # ignore patterns. Otherwise a stale ``.ignore2packai`` entry or a
        # broad ``*.lock`` rule would make the GUI toggle misleading.
        return None if include_lockfiles else "pattern"

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


def _normalize_assignment_key(raw_key: str) -> str:
    """Normalize quoted, dotted, dashed, and camelCase configuration keys."""
    key = raw_key.strip().strip("\"'")
    key = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", key)
    return re.sub(r"[^A-Za-z0-9]+", "_", key).strip("_").casefold()


def _assignment_rule(raw_key: str) -> tuple[str, int] | None:
    normalized = _normalize_assignment_key(raw_key)
    for kind, suffixes, minimum_length in _ASSIGNMENT_KEY_RULES:
        if any(normalized == suffix or normalized.endswith(f"_{suffix}") for suffix in suffixes):
            return kind, minimum_length
    return None


def _looks_like_placeholder(value: str) -> bool:
    normalized = value.strip().strip("\"'").casefold()
    compact = re.sub(r"[^a-z0-9]+", "_", normalized).strip("_")
    if not compact:
        return True
    placeholder_fragments = (
        "changeme",
        "change_me",
        "dummy",
        "example",
        "fake",
        "not_packaged",
        "placeholder",
        "redacted",
        "replace_me",
        "sample",
        "your_api_key",
        "your_password",
        "your_token",
    )
    if any(fragment in compact for fragment in placeholder_fragments):
        return True

    # Numeraciones repetitivas como sk-1234567890... son fixtures habituales,
    # no claves válidas de los proveedores detectados por prefijo.
    payload = re.sub(
        r"^(?:sk(?:-proj|-ant)?-|gsk_|hf_|r8_|pplx-|npm_|pypi-|glpat-|gloas-)",
        "",
        normalized,
    )
    return bool(payload) and (payload.isdigit() or len(set(payload)) == 1)


def _plausible_assignment_value(value: str, minimum_length: int, *, quoted: bool) -> bool:
    stripped = value.strip()
    if len(stripped) < minimum_length or any(character.isspace() for character in stripped):
        return False
    if _looks_like_placeholder(stripped):
        return False

    # Un identificador desnudo suele ser una referencia de código o un nombre
    # de tipo (TOKEN = TokenProvider), no el valor literal de una credencial.
    return quoted or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", stripped) is None


def scan_text_for_secrets(content: str) -> tuple[SecretFinding, ...]:
    """Scan text using high-confidence tokens and conservative assignments."""
    findings: list[SecretFinding] = []
    occupied_ranges: list[tuple[int, int]] = []
    folded_content = content.casefold()

    def line_number(position: int) -> int:
        return content.count("\n", 0, position) + 1

    def overlaps(start: int, end: int) -> bool:
        return any(
            not (end <= old_start or start >= old_end) for old_start, old_end in occupied_ranges
        )

    for kind, pattern in SECRET_PATTERNS.items():
        triggers = _SECRET_PATTERN_TRIGGERS.get(kind, ())
        if triggers and not any(trigger.casefold() in folded_content for trigger in triggers):
            continue
        for match in pattern.finditer(content):
            start, end = match.span()
            if overlaps(start, end) or _looks_like_placeholder(match.group(0)):
                continue
            findings.append(
                SecretFinding(
                    kind=kind,
                    masked_value=mask_secret(match.group(0)),
                    line=line_number(start),
                )
            )
            occupied_ranges.append((start, end))

    assignment_matches = (
        _ASSIGNMENT_PATTERN.finditer(content)
        if _ASSIGNMENT_TRIGGER_PATTERN.search(content) is not None
        else ()
    )
    for match in assignment_matches:
        rule = _assignment_rule(match.group("key"))
        if rule is None:
            continue
        kind, minimum_length = rule
        value_group = next(
            name for name in ("double", "single", "bare") if match.group(name) is not None
        )
        value = match.group(value_group)
        assert value is not None
        start, end = match.span(value_group)
        if overlaps(start, end):
            continue
        if not _plausible_assignment_value(
            value,
            minimum_length,
            quoted=value_group != "bare",
        ):
            continue
        findings.append(
            SecretFinding(
                kind=kind,
                masked_value=mask_secret(value),
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
