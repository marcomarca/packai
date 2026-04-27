import argparse
import fnmatch
import os
import re
import subprocess
import zipfile
from pathlib import Path

# Directorios que se ignoran en cualquier nivel de la ruta
IGNORED_DIR_NAMES = {
    ".git", "node_modules", ".venv", "venv", "env", "__pycache__",
    "dist", "build", ".next", ".nuxt", "coverage", ".pytest_cache",
    ".mypy_cache", ".idea", ".vscode", ".cache", "target",
}

# Extensiones o patrones de archivos basura adicionales
DEFAULT_IGNORE = [
    "*.log", "*.tmp", "*.cache", "*.zip", "*.tar", "*.gz", "*.rar", "*.7z",
    "*.sqlite", "*.db", "*.png", "*.jpg", "*.jpeg", "*.gif", "*.webp", "*.mp4",
    "*.mov", "*.pdf", "*.xlsx", "*.docx",
]

# Archivos sensibles que se excluyen siempre por nombre
SECRET_FILE_PATTERNS = [
    ".env", ".env.*", "*.env", "*.pem", "*.key", "*.p8", "*.p12", "*.pfx",
    "*.crt", "*.cer", "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519",
    "known_hosts", "authorized_keys", ".npmrc", ".pypirc", ".netrc", ".dockercfg",
    "docker-compose.override.yml", "credentials", "credentials.json",
    "service-account*.json", "*service_account*.json", "firebase-adminsdk*.json",
    "google-credentials*.json", "gcloud*.json", "kubeconfig", "*.kubeconfig",
    "config", "secrets.yml", "secrets.yaml", "secrets.json", "secret.yml",
    "secret.yaml", "secret.json", "local.settings.json", "appsettings.Production.json",
    "appsettings.Local.json", "application-prod.yml", "application-prod.yaml",
    "terraform.tfvars", "*.tfvars", "*.tfstate", "*.tfstate.backup",
]

# Patrones de alta confianza para tokens con prefijo
SECRET_PATTERNS = {
    "OpenAI API Key": re.compile(r"\b(?:sk-[A-Za-z0-9]{32,}|sk-proj-[A-Za-z0-9_-]{48,})\b"),
    "Groq API Key": re.compile(r"\bgsk_[A-Za-z0-9_-]{32,}\b"),
    "Anthropic API Key": re.compile(r"\bsk-ant-[A-Za-z0-9_-]{32,}\b"),
    "Hugging Face Token": re.compile(r"\bhf_[A-Za-z0-9]{30,}\b"),
    "Replicate API Token": re.compile(r"\br8_[A-Za-z0-9]{32,}\b"),
    "Perplexity API Key": re.compile(r"\bpplx-[A-Za-z0-9]{32,}\b"),
    "Generic SK API Key": re.compile(r"\bsk-[A-Za-z0-9_-]{32,}\b"),
    "AWS Access Key ID": re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    "AWS Secret Access Key Context": re.compile(r"(?i)\baws_secret_access_key\b\s*[:=]\s*[\"']?[A-Za-z0-9/+=]{40}[\"']?"),
    "Google API Key": re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    "Google OAuth Client Secret": re.compile(r"\bGOCSPX-[A-Za-z0-9_-]{20,}\b"),
    "Google Service Account Private Key": re.compile(r"-----BEGIN PRIVATE KEY-----[\s\S]+?-----END PRIVATE KEY-----"),
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

def load_aiignore(root: Path) -> list[str]:
    """Carga patrones de exclusión total del ZIP."""
    aiignore = root / ".aiignore"
    if not aiignore.exists(): return []
    try:
        lines = aiignore.read_text(encoding="utf-8", errors="ignore").splitlines()
        return [l.strip() for l in lines if l.strip() and not l.strip().startswith("#")]
    except Exception: return []

def load_aipass(root: Path) -> list[str]:
    """Carga patrones de archivos que saltan el escáner pero se incluyen en el ZIP."""
    aipass = root / ".aipass"
    if not aipass.exists(): return []
    try:
        lines = aipass.read_text(encoding="utf-8", errors="ignore").splitlines()
        return [l.strip() for l in lines if l.strip() and not l.strip().startswith("#")]
    except Exception: return []

def should_ignore_path(relative_path: str, patterns: list[str]) -> bool:
    """Verifica si una ruta debe ser ignorada por nombre o patrón."""
    normalized = relative_path.replace("\\", "/")
    path_obj = Path(normalized)
    parts = path_obj.parts
    name = path_obj.name

    # Ignorar si algún directorio en la ruta está en la lista negra
    if any(part in IGNORED_DIR_NAMES for part in parts):
        return True

    # Comprobar contra lista de archivos secretos
    if any(fnmatch.fnmatch(name, p) for p in SECRET_FILE_PATTERNS):
        return True
    
    for p in patterns:
        p = p.strip().replace("\\", "/")
        if not p: continue
        if p.endswith("/") and normalized.startswith(p): return True
        if fnmatch.fnmatch(normalized, p) or fnmatch.fnmatch(name, p): return True
    return False

def scan_file_for_secrets(path: Path) -> list[str]:
    """Escanea el contenido de un archivo en busca de secretos."""
    if path.stat().st_size > 1024 * 1024:
        return [f"Archivo demasiado grande para escaneo: {path.stat().st_size} bytes"]
    
    findings = []
    for enc in ["utf-8", "utf-16", "latin-1"]:
        try:
            content = path.read_text(encoding=enc, errors="strict")
            for name, p in SECRET_PATTERNS.items():
                if match := p.search(content):
                    findings.append(f"{name}: {mask_secret(match.group(0))}")
            
            for name, p in SENSITIVE_ASSIGNMENT_PATTERNS.items():
                if match := p.search(content):
                    findings.append(f"{name}: {mask_secret(match.group(0))}")
            break
        except (UnicodeDecodeError, Exception): continue
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

def copy_zip(zip_path: Path, mode: str) -> bool:
    """Gestiona el copiado del resultado según el modo elegido."""
    if mode == "none": return True
    if mode == "path": return copy_path_as_text(zip_path)
    if mode == "file":
        if copy_zip_with_powershell(zip_path): return True
        return copy_path_as_text(zip_path)
    return False

def create_zip(root: Path, output_zip: Path, ignore_patterns: list[str], pass_patterns: list[str]) -> tuple[int, int, list[str]]:
    """Crea el archivo ZIP evitando entrar en directorios ignorados."""
    incl, ign, findings = 0, 0, []
    output_zip_res = output_zip.resolve()

    with zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_DEFLATED) as zipf:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in IGNORED_DIR_NAMES]
            
            for f in filenames:
                path = Path(dirpath) / f
                if path.is_symlink():
                    ign += 1; continue
                if path.resolve() == output_zip_res: continue
                
                rel = path.relative_to(root).as_posix()
                
                # 1. Exclusión total del ZIP
                if should_ignore_path(rel, ignore_patterns):
                    ign += 1; continue
                
                # 2. Saltarse el escáner pero incluir en ZIP
                if should_ignore_path(rel, pass_patterns):
                    zipf.write(path, arcname=rel)
                    incl += 1; continue

                # 3. Escaneo normal
                f_findings = scan_file_for_secrets(path)
                if f_findings:
                    findings.append(f"SALTADO ({', '.join(f_findings)}): {rel}")
                    ign += 1; continue

                zipf.write(path, arcname=rel)
                incl += 1
    return incl, ign, findings

def main():
    parser = argparse.ArgumentParser(description="Empaqueta proyecto en ZIP para IA.")
    parser.add_argument("--copy", choices=["file", "path", "none"], default="file", help="Modo de copiado.")
    parser.add_argument("--output", help="Ruta del ZIP de salida.")
    parser.add_argument("folder", nargs=argparse.REMAINDER, help="Carpeta a procesar.")
    args = parser.parse_args()

    f_path = " ".join(args.folder).strip() if args.folder else "."
    root = Path(f_path).expanduser().resolve()
    if not root.exists():
        raise SystemExit(f"❌ La ruta no existe: {root}")
    if not root.is_dir():
        raise SystemExit(f"❌ La ruta no es una carpeta: {root}")

    name = root.name if root.name else "project"
    out_zip = Path(args.output).expanduser().resolve() if args.output else root.parent / f"{name}.zip"

    ignore_patterns = DEFAULT_IGNORE + load_aiignore(root)
    pass_patterns = load_aipass(root)
    print(f"Empaquetando: {root.name}...")
    
    incl, ign, findings = create_zip(root, out_zip, ignore_patterns, pass_patterns)
    for f in findings: print(f"⚠️  {f}")

    if copy_zip(out_zip, args.copy):
        st = "✅ ZIP copiado al portapapeles." if args.copy == "file" else "✅ Ruta copiada."
    else:
        st = f"❌ Error al copiar. Archivo en: {out_zip}"

    print("-" * 30 + f"\nIncluidos: {incl} | Ignorados: {ign}\n{st}\n" + "-" * 30)

if __name__ == "__main__":
    main()
