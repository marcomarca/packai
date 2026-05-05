import argparse
import fnmatch
import os
import re
import subprocess
import zipfile
import unicodedata
from pathlib import Path
from typing import TypedDict, Union

# Intentar cargar configuración externa
try:
    import config_pack_ai
    CONFIG_INCLUDE_ENV = getattr(config_pack_ai, "INCLUDE_ENV_EXAMPLE", True)
except ImportError:
    CONFIG_INCLUDE_ENV = True

class SecretFinding(TypedDict):
    type: str
    secret: str
    line: Union[int, None]

class FileFinding(TypedDict):
    rel: str
    details: list[SecretFinding]
    reason: str

def get_version():
    """Lee la versión desde pyproject.toml."""
    try:
        pyproject_path = Path(__file__).parent / "pyproject.toml"
        if pyproject_path.exists():
            content = pyproject_path.read_text(encoding="utf-8")
            match = re.search(r'version\s*=\s*["\']([^"\']+)["\']', content)
            if match:
                return match.group(1)
    except Exception:
        pass
    return "1.1.0"

VERSION = get_version()

# Directorios que se ignoran en cualquier nivel de la ruta
IGNORED_DIR_NAMES = {
    ".git", "node_modules", ".venv", "venv", "env", "__pycache__",
    "dist", "build", ".next", ".nuxt", "coverage", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", ".uv-cache", ".idea", ".vscode", ".cache", "target",
}

# Extensiones o patrones de archivos basura adicionales
DEFAULT_IGNORE = [
    "*.log", "*.tmp", "*.cache", "*.zip", "*.tar", "*.gz", "*.rar", "*.7z",
    "*.sqlite", "*.db", "*.png", "*.jpg", "*.jpeg", "*.gif", "*.webp", "*.mp4",
    "*.mov", "*.pdf", "*.xlsx", "*.docx", "*.exe", "*.dll", "*.so", "*.dylib",
    "*.jar", "*.war", "*.wasm", "*.bin", "*.dat", "*.class", "*.o", "*.obj",
]

# Archivos sensibles que se excluyen siempre por nombre
SECRET_FILE_PATTERNS = [
    ".aipass", ".env", ".env.*", "*.env", "*.pem", "*.key", "*.p8", "*.p12", "*.pfx",
    "*.crt", "*.cer", "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519",
    "known_hosts", "authorized_keys", ".npmrc", ".pypirc", ".netrc", ".dockercfg",
    "docker-compose.override.yml", "credentials", "credentials.json",
    "service-account*.json", "*service_account*.json", "firebase-adminsdk*.json",
    "google-credentials*.json", "gcloud*.json", "kubeconfig", "*.kubeconfig",
    "secrets.yml", "secrets.yaml", "secrets.json", "secret.yml",
    "secret.yaml", "secret.json", "local.settings.json", "appsettings.Production.json",
    "appsettings.Local.json", "application-prod.yml", "application-prod.yaml",
    "terraform.tfvars", "*.tfvars", "*.tfstate", "*.tfstate.backup",
]

# Archivos de ejemplo de entorno que pueden permitirse (se escanean igual)
SAFE_ENV_EXAMPLES = {".env.example", ".env.sample", ".env.template"}

# Patrones de alta confianza para tokens con prefijo
SECRET_PATTERNS = {
    "OpenAI API Key": re.compile(r"\b(?:sk-" + r"[A-Za-z0-9]{32,}|sk-proj-" + r"[A-Za-z0-9_-]{48,})\b"),
    "Groq API Key": re.compile(r"\bgsk_" + r"[A-Za-z0-9_-]{32,}\b"),
    "Anthropic API Key": re.compile(r"\bsk-ant-" + r"[A-Za-z0-9_-]{32,}\b"),
    "Hugging Face Token": re.compile(r"\bhf_" + r"[A-Za-z0-9]{30,}\b"),
    "Replicate API Token": re.compile(r"\br8_" + r"[A-Za-z0-9]{32,}\b"),
    "Perplexity API Key": re.compile(r"\bpplx-" + r"[A-Za-z0-9]{32,}\b"),
    "Generic SK API Key": re.compile(r"\bsk-" + r"[A-Za-z0-9_-]{32,}\b"),
    "AWS Access Key ID": re.compile(r"\b(?:" + r"AKIA|ASIA)[0-9A-Z]{16}\b"),
    "AWS Secret Access Key Context": re.compile(r"(?i)\baws_secret_access_key\b\s*[:=]\s*[\"']?[A-Za-z0-9/+=]{40}[\"']?"),
    "Google API Key": re.compile(r"\bAIza" + r"[0-9A-Za-z_-]{35}\b"),
    "Google OAuth Client Secret": re.compile(r"\bGOCSPX-" + r"[A-Za-z0-9_-]{20,}\b"),
    "Google Service Account Private Key": re.compile(r"-----BEGIN " + r"PRIVATE KEY-----[\s\S]+?-----END " + r"PRIVATE KEY-----"),
    "Azure Storage Connection String": re.compile(r"(?i)\bDefaultEndpointsProtocol=https?;AccountName=[^;]+;AccountKey=[A-Za-z0-9+/=]{60,};EndpointSuffix="),
    "Azure Storage Account Key Context": re.compile(r"(?i)\b(?:azure|account).{0,30}(?:key|secret)\b\s*[:=]\s*[\"']?[A-Za-z0-9+/=]{60,}[\"']?"),
    "Cloudflare API Token Context": re.compile(r"(?i)\b(?:cloudflare|cf)_(?:api_)?(?:token|key)\b\s*[:=]\s*[\"']?[A-Za-z0-9_-]{30,}[\"']?"),
    "DigitalOcean Token": re.compile(r"\bdop_v1_[A-Fa-f0-9]{64}\b"),
    "Heroku API Key Context": re.compile(r"(?i)\bheroku(?:_api)?_key\b\s*[:=]\s*[\"']?[A-Fa-f0-9]{32}[\"']?"),
    "GitHub Classic Token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36}\b"),
    "GitHub Fine-Grained Token": re.compile(r"\bgithub_pat_[A-Za-z0-9_]{40,}\b"),
    "GitLab Token": re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}\b"),
    "GitLab OAuth Token": re.compile(r"\bgloas-[A-Za-z0-9_-]{20,}\b"),
    "NPM Token": re.compile(r"\bnpm_[A-Za-z0-9]{36}\b"),
    "PyPI Token": re.compile(r"\bpypi-[A-Za-z0-9_-]{50,}\b"),
    "Generic Private Key": re.compile(r"-----BEGIN (?:RSA|DSA|EC|OPENSSH|PGP|PRIVATE) PRIVATE KEY-----"),
    "Stripe Secret Key": re.compile(r"\bsk_(?:live|test)_[A-Za-z0-9]{20,}\b"),
    "Slack Token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,100}\b"),
    "Discord Bot Token": re.compile(r"\b[A-Za-z0-9_-]{24}\.[A-Za-z0-9_-]{6}\.[A-Za-z0-9_-]{25,110}\b"),
    "Telegram Bot Token": re.compile(r"\b[0-9]{8,12}:[A-Za-z0-9_-]{30,}\b"),
    "SendGrid API Key": re.compile(r"\bSG\.[A-Za-z0-9_-]{16,32}\.[A-Za-z0-9_-]{32,80}\b"),
    "JWT Token": re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
}

# Patrones contextuales para asignaciones sospechosas
SENSITIVE_ASSIGNMENT_PATTERNS = {
    "Generic API Key Assignment": re.compile(r"(?i)\b[A-Z0-9_]*(?:API_KEY|ACCESS_KEY|SECRET_KEY|PRIVATE_KEY|APP_KEY)[A-Z0-9_]*\b\s*[:=]\s*[\"']?[^\"'\s]{12,}[\"']?"),
    "Generic Token Assignment": re.compile(r"(?i)\b[A-Z0-9_]*(?:TOKEN|AUTH_TOKEN|ACCESS_TOKEN|REFRESH_TOKEN|ID_TOKEN)[A-Z0-9_]*\b\s*[:=]\s*[\"']?[^\"'\s]{12,}[\"']?"),
    "Generic Password Assignment": re.compile(r"(?i)\b[A-Z0-9_]*(?:PASSWORD|PASSWD|PWD)[A-Z0-9_]*\b\s*[:=]\s*[\"']?[^\"'\s]{8,}[\"']?"),
    "Generic DB Connection String": re.compile(r"(?i)\b(?:DATABASE_URL|DB_URL|DATABASE_URI|MONGO_URI|REDIS_URL)\b\s*[:=]\s*[\"']?[^\"'\s]{12,}[\"']?"),
}

def mask_secret(value: str, visible_start: int = 6, visible_end: int = 4) -> str:
    """Oculta parte de un secreto para mostrarlo en el reporte."""
    value = value.strip()
    if len(value) <= visible_start + visible_end: return "*" * len(value)
    return f"{value[:visible_start]}...{value[-visible_end:]}"

def load_ignore_file(path: Path) -> list[str]:
    """Carga patrones de un archivo intentando varias codificaciones."""
    if not path.exists(): return []
    for enc in ["utf-8", "utf-16", "latin-1"]:
        try:
            content = path.read_text(encoding=enc)
            return [l.strip() for l in content.splitlines() if l.strip() and not l.strip().startswith("#")]
        except UnicodeDecodeError:
            continue
        except OSError as e:
            raise SystemExit(f"❌ No se pudo leer {path}: {e}")
    
    raise SystemExit(f"❌ No se pudo decodificar {path} (probablemente binario o formato inválido)")

def load_aiignore(root: Path) -> list[str]:
    """Carga patrones de exclusión total del ZIP."""
    return load_ignore_file(root / ".aiignore")

def load_aipass(root: Path) -> list[str]:
    """Carga patrones de archivos que saltan el escáner pero se incluyen en el ZIP."""
    return load_ignore_file(root / ".aipass")

def is_probably_binary(path: Path, sample_size: int = 4096) -> bool:
    """Detecta si un archivo es probablemente binario buscando bytes nulos."""
    try:
        with open(path, "rb") as f:
            chunk = f.read(sample_size)
        return b"\x00" in chunk
    except OSError:
        return True

def should_ignore_path(relative_path: str, patterns: list[str], include_env_example: bool = True, ignore_secrets: bool = False) -> Union[str, None]:
    """
    Verifica si una ruta debe ser ignorada. 
    Retorna el tipo de ignore ('strict', 'sensitive', 'pattern') o None.
    """
    normalized = relative_path.replace("\\", "/")
    path_obj = Path(normalized)
    parts = path_obj.parts
    name = path_obj.name

    # 1. Directorios bloqueados siempre
    if any(part in IGNORED_DIR_NAMES for part in parts):
        return "strict"

    # 2. .env y secretos
    is_safe_env = include_env_example and name in SAFE_ENV_EXAMPLES
    
    if not is_safe_env:
        # El usuario pide que .env NUNCA pase
        if name == ".env" or fnmatch.fnmatch(name, ".env.*") or fnmatch.fnmatch(name, "*.env"):
            return "strict"
        
        # Otros archivos potencialmente sensibles son bypassable con --force
        if not ignore_secrets:
            if any(fnmatch.fnmatch(name, p) for p in SECRET_FILE_PATTERNS):
                return "sensitive"
    
    # 3. Patrones de usuario (aiignore, defaults, aipass)
    for p in patterns:
        p = p.strip().replace("\\", "/")
        if not p: continue
        
        if p.endswith("/"):
            dir_p = p.rstrip("/")
            if normalized.startswith(p) or f"/{dir_p}/" in f"/{normalized}/":
                return "pattern"
        
        if fnmatch.fnmatch(normalized, p) or fnmatch.fnmatch(name, p):
            return "pattern"
            
    return None

def scan_file_for_secrets(path: Path) -> list[SecretFinding]:
    """Escanea el contenido de un archivo en busca de secretos."""
    if path.stat().st_size > 1024 * 1024:
        return [{
            "type": "Archivo demasiado grande para escaneo",
            "secret": f"{path.stat().st_size} bytes",
            "line": None,
        }]
    
    content = None
    for enc in ["utf-8", "utf-16", "latin-1"]:
        try:
            content = path.read_text(encoding=enc, errors="strict")
            break
        except UnicodeDecodeError:
            continue
        except OSError as e:
            return [{
                "type": "No se pudo leer el archivo",
                "secret": str(e),
                "line": None,
            }]
    
    if content is None:
        return [{
            "type": "No se pudo decodificar el archivo para escaneo",
            "secret": "Probablemente binario o formato inválido",
            "line": None,
        }]

    findings = []
    
    # Función auxiliar para calcular línea
    def get_line_no(text, pos):
        return text.count("\n", 0, pos) + 1

    # Para deduplicación por rango
    occupied_ranges = []

    def is_overlapping(start, end):
        for o_start, o_end in occupied_ranges:
            if not (end <= o_start or start >= o_end):
                return True
        return False

    # 1. Patrones de alta confianza (Tokens específicos)
    for name, p in SECRET_PATTERNS.items():
        for match in p.finditer(content):
            start, end = match.span()
            if is_overlapping(start, end): continue
            
            line = get_line_no(content, start)
            findings.append({
                "type": name,
                "secret": mask_secret(match.group(0)),
                "line": line
            })
            occupied_ranges.append((start, end))
    
    # 2. Asignaciones sensibles (Contextuales)
    for name, p in SENSITIVE_ASSIGNMENT_PATTERNS.items():
        for match in p.finditer(content):
            start, end = match.span()
            if is_overlapping(start, end): continue
            
            line = get_line_no(content, start)
            findings.append({
                "type": name,
                "secret": mask_secret(match.group(0)),
                "line": line
            })
            occupied_ranges.append((start, end))
    
    return findings

def copy_zip_with_powershell(zip_path: Path) -> bool:
    """Copia el ZIP al portapapeles de Windows como archivo pegable."""
    zip_path = Path(zip_path).expanduser().resolve()
    if not zip_path.exists() or not zip_path.is_file(): return False

    # Usamos un bloque de script para que PowerShell asigne los argumentos a $args
    script = "& { Set-Clipboard -LiteralPath $args[0] }"
    res = subprocess.run(
        ["powershell", "-NoProfile", "-Command", script, str(zip_path)],
        capture_output=True, text=True
    )
    return res.returncode == 0

def copy_path_as_text(path: Path) -> bool:
    """Copia la ruta absoluta al portapapeles como texto."""
    script = "& { Set-Clipboard -Value $args[0] }"
    res = subprocess.run(
        ["powershell", "-NoProfile", "-Command", script, str(path.resolve())],
        capture_output=True, text=True
    )
    return res.returncode == 0

def copy_zip(zip_path: Path, mode: str) -> str:
    """Gestiona el copiado del resultado según el modo elegido."""
    if mode == "none": return "none"
    if mode == "path":
        return "path" if copy_path_as_text(zip_path) else "failed"
    if mode == "file":
        if copy_zip_with_powershell(zip_path):
            return "file"
        # Fallback a texto si falla el copiado del archivo real
        if copy_path_as_text(zip_path):
            return "path_fallback"
        return "failed"
    return "failed"

def create_zip(root: Path, output_zip: Path, ignore_patterns: list[str], pass_patterns: list[str], include_env_example: bool, force: bool = False) -> tuple[int, int, list[FileFinding]]:
    """Crea el archivo ZIP evitando entrar en directorios ignorados."""
    incl, ign, findings = 0, 0, []
    output_zip_res = output_zip.resolve()

    with zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_DEFLATED) as zipf:
        print(f"Empaquetando: {root.name}...")
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = sorted([d for d in dirnames if d not in IGNORED_DIR_NAMES])
            filenames = sorted(filenames)
            
            rel_dir = Path(dirpath).relative_to(root)
            depth = len(rel_dir.parts) if rel_dir != Path(".") else 0
            
            # Imprimir nombre de la subcarpeta (si no es la raíz)
            if rel_dir != Path("."):
                indent_dir = "    " * (depth - 1)
                print(f"{indent_dir}    📁 {rel_dir.name}")
            
            indent_file = "    " * depth
            for f in filenames:
                path = Path(dirpath) / f
                if path.is_symlink():
                    ign += 1; continue
                if path.resolve() == output_zip_res: continue
                
                rel = path.relative_to(root).as_posix()
                
                # 1. Exclusión por nombre/patrón
                ignore_type = should_ignore_path(rel, ignore_patterns, include_env_example)
                
                if ignore_type in ("strict", "pattern"):
                    ign += 1; continue
                
                forced_by_name = False
                if ignore_type == "sensitive":
                    if not force:
                        ign += 1; continue
                    forced_by_name = True
                
                # 2. .aipass (bypass scanner)
                if should_ignore_path(rel, pass_patterns, ignore_secrets=True) == "pattern":
                    zipf.write(path, arcname=rel)
                    print(f"{indent_file}    ⚠️  Incluido sin escaneo por .aipass: {f}")
                    incl += 1; continue

                # 3. Detectar si es binario por contenido
                if is_probably_binary(path):
                    ign += 1; continue

                # 4. Escaneo normal
                f_findings = scan_file_for_secrets(path)
                if f_findings:
                    findings.append({
                        "rel": rel,
                        "details": f_findings,
                        "reason": "secret_found",
                        "forced": force
                    })
                    if not force:
                        ign += 1; continue
                    # Si force=True, continuamos para escribirlo
                elif forced_by_name:
                    findings.append({
                        "rel": rel,
                        "details": [{"type": "Nombre sensible forzado", "secret": "Coincide con patrón de seguridad", "line": None}],
                        "reason": "sensitive_forced",
                        "forced": True
                    })

                zipf.write(path, arcname=rel)
                status_icon = "🚀" if (f_findings or forced_by_name) else "📄"
                print(f"{indent_file}    {status_icon} {f}")
                incl += 1
    return incl, ign, findings

def get_git_commit_info(root: Path) -> tuple[str | None, str | None]:
    """Obtiene el asunto y el hash corto del último commit de git."""
    try:
        res = subprocess.run(
            ["git", "log", "-1", "--pretty=%s|%h"],
            cwd=root, capture_output=True, text=True, check=True
        )
        data = res.stdout.strip()
        if "|" in data:
            subject, short_hash = data.rsplit("|", 1)
            return subject, short_hash
        return data, None
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None, None

def sanitize_filename(name: str) -> str:
    """Limpia el nombre para que sea un nombre de archivo válido."""
    # Normalizar Unicode para quitar acentos y eñes (á -> a, ñ -> n)
    name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode('ascii')
    # Reemplazar cualquier cosa que no sea alfanumérica, punto, guion o guion bajo por "_"
    sanitized = re.sub(r'[^a-zA-Z0-9.\-_]', "_", name)
    # Limpiar guiones bajos consecutivos
    sanitized = re.sub(r'_{2,}', "_", sanitized).strip("_")
    
    # Mitigación para nombres reservados en Windows
    windows_reserved = {
        "CON", "PRN", "AUX", "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }
    # Comprobar el nombre base (stem)
    stem = Path(sanitized).stem.upper()
    if stem in windows_reserved:
        sanitized = f"_{sanitized}"
        
    return sanitized

def main():
    parser = argparse.ArgumentParser(description="Empaqueta proyecto en ZIP para IA.")
    parser.add_argument("--version", "-v", action="version", version=f"Pack AI {VERSION}")
    parser.add_argument("--copy", choices=["file", "path", "none"], default="file", help="Modo de copiado.")
    parser.add_argument("--output", help="Ruta del ZIP de salida.")
    parser.add_argument("--force", "-f", action="store_true", help="Forzar inclusión de archivos con alertas (excepto .env).")
    parser.add_argument("--no-env-example", action="store_false", dest="include_env_example", 
                        default=CONFIG_INCLUDE_ENV, help="No incluir archivos .env.example.")
    parser.add_argument("folder", nargs="?", default=".", help="Carpeta a procesar.")
    args = parser.parse_args()

    f_path = args.folder
    root = Path(f_path).expanduser().resolve()
    if not root.exists():
        raise SystemExit(f"❌ La ruta no existe: {root}")
    if not root.is_dir():
        raise SystemExit(f"❌ La ruta no es una carpeta: {root}")

    project_name = root.name if root.name else "project"
    safe_project_name = sanitize_filename(project_name) or "project"
    
    # Limitar nombre de proyecto para asegurar espacio al commit
    if len(safe_project_name) > 80:
        safe_project_name = safe_project_name[:77] + "..."
    
    name = safe_project_name
    
    # Intentar obtener el nombre del último commit y su hash
    git_subject, git_hash = get_git_commit_info(root)
    if git_subject:
        s_subject = sanitize_filename(git_subject)
        suffix = f"-{git_hash}" if git_hash else ""
        
        # El total debe ser de máximo 200 caracteres (incluyendo .zip)
        # Formato: [Project]-[Subject]-[Hash].zip
        # .zip = 4 chars, guion = 1 char
        max_total = 200
        reserved = len(suffix) + 5
        available_for_subject = max_total - len(safe_project_name) - reserved
        
        if available_for_subject > 3:
            if len(s_subject) > available_for_subject:
                s_subject = s_subject[:available_for_subject-3] + "..."
            name = f"{safe_project_name}-{s_subject}{suffix}"
        elif available_for_subject > 0:
            # Si hay poco espacio, metemos lo que quepa sin elipsis o simplemente el guion
            name = f"{safe_project_name}-{s_subject[:available_for_subject]}{suffix}"
        else:
            # Sin espacio para el sujeto
            name = f"{safe_project_name}{suffix}"

    out_zip = Path(args.output).expanduser().resolve() if args.output else root.parent / f"{name}.zip"

    ignore_patterns = DEFAULT_IGNORE + load_aiignore(root)
    pass_patterns = load_aipass(root)
    
    incl, ign, total_findings = create_zip(root, out_zip, ignore_patterns, pass_patterns, args.include_env_example, args.force)
    
    for f in total_findings:
        is_forced = f.get("forced", False)
        status = "INCLUIDO (FORZADO)" if is_forced else "EXCLUIDO"
        icon = "🚀" if is_forced else "⚠️"
        
        print(f"{icon}  {status}: {f['rel']}")
        for d in f['details']:
            print(f"    Tipo: {d['type']}")
            if d.get('line'): print(f"    Línea: {d['line']}")
            print(f"    Secreto: {d['secret']}")
        
        action = "añadido al ZIP a pesar de la alerta" if is_forced else "omitido del ZIP"
        print(f"    Acción: {action}\n")

    copy_res = copy_zip(out_zip, args.copy)
    
    status_msgs = {
        "file": "✅ ZIP copiado al portapapeles.",
        "path": "✅ Ruta copiada.",
        "path_fallback": "⚠️ Fallo al copiar archivo; se copió la ruta como texto.",
        "none": "✅ ZIP creado sin copiar.",
        "failed": f"❌ Error al copiar. Archivo en: {out_zip}",
    }
    st = status_msgs.get(copy_res, status_msgs["failed"])

    print("-" * 30 + f"\nIncluidos: {incl} | Ignorados: {ign}\n{st}\n" + "-" * 30)

if __name__ == "__main__":
    main()
