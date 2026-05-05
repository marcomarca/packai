import os
import zipfile
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock
from pack_ai import create_zip, scan_file_for_secrets, should_ignore_path, copy_zip, sanitize_filename, get_git_commit_info

@pytest.fixture
def temp_project(tmp_path):
    """Crea una estructura de proyecto temporal para pruebas."""
    project = tmp_path / "test_project"
    project.mkdir()
    return project

def test_large_file_scan_no_crash(temp_project):
    """Verifica que archivos grandes no causen crash y sean reportados."""
    large_file = temp_project / "large.txt"
    large_file.write_bytes(b"a" * (1024 * 1024 + 1))
    
    findings = scan_file_for_secrets(large_file)
    assert len(findings) == 1
    assert findings[0]["type"] == "Archivo demasiado grande para escaneo"

def test_aipass_exclusion_from_zip(temp_project):
    """Verifica que .aipass no se incluya en el ZIP final."""
    (temp_project / ".aipass").write_text("dummy", encoding="utf-8")
    (temp_project / "code.py").write_text("print('hello')", encoding="utf-8")
    
    zip_path = temp_project.parent / "test.zip"
    create_zip(temp_project, zip_path, [], [], True)
    
    with zipfile.ZipFile(zip_path, "r") as z:
        names = z.namelist()
        assert "code.py" in names
        assert ".aipass" not in names

def test_aipass_bypass_scanner(temp_project):
    """Verifica que archivos en .aipass se incluyan sin ser escaneados."""
    # Archivo con secreto que normalmente sería bloqueado
    secret_file = temp_project / "secret.py"
    secret_file.write_text("API_KEY=" + "'sk" + "-12345678901234567890123456789012'", encoding="utf-8")
    
    # Añadir a .aipass
    (temp_project / ".aipass").write_text("secret.py", encoding="utf-8")
    
    zip_path = temp_project.parent / "test.zip"
    incl, ign, findings = create_zip(temp_project, zip_path, [], ["secret.py"], True)
    
    assert incl == 1
    assert len(findings) == 0
    with zipfile.ZipFile(zip_path, "r") as z:
        assert "secret.py" in z.namelist()

def test_env_example_inclusion(temp_project):
    """Verifica que .env.example se incluya si está limpio."""
    env_ex = temp_project / ".env.example"
    env_ex.write_text("DB_HOST=localhost", encoding="utf-8")
    
    zip_path = temp_project.parent / "test.zip"
    # Pasamos ignore_patterns vacíos para que solo actúen los SECRET_FILE_PATTERNS internos
    incl, ign, findings = create_zip(temp_project, zip_path, [], [], True)
    
    assert incl == 1
    with zipfile.ZipFile(zip_path, "r") as z:
        assert ".env.example" in z.namelist()

def test_env_example_exclusion_with_secret(temp_project):
    """Verifica que .env.example se excluya si tiene secretos."""
    env_ex = temp_project / ".env.example"
    # Usamos un secreto que dispare el escáner con total seguridad (concatenado para no dispararlo aquí)
    env_ex.write_text("OPENAI_KEY=" + "sk" + "-12345678901234567890123456789012", encoding="utf-8")
    
    zip_path = temp_project.parent / "test.zip"
    incl, ign, findings = create_zip(temp_project, zip_path, [], [], True)
    
    assert incl == 0
    assert len(findings) >= 1

def test_nested_directory_ignore(temp_project):
    """Verifica que patrones de carpeta como 'backups/' ignoren subcarpetas."""
    backup_dir = temp_project / "foo" / "backups"
    backup_dir.mkdir(parents=True)
    (backup_dir / "old.py").write_text("old code")
    
    patterns = ["backups/"]
    assert should_ignore_path("foo/backups/old.py", patterns) == "pattern"
    assert should_ignore_path("backups/old.py", patterns) == "pattern"
    assert should_ignore_path("src/backups/old.py", patterns) == "pattern"
    assert should_ignore_path("important_backups/old.py", patterns) is None

def test_copy_zip_modes():
    """Verifica los retornos de estado de copy_zip."""
    # No necesitamos un zip real para el modo 'none'
    assert copy_zip(Path("dummy.zip"), "none") == "none"

def test_sanitize_filename_basic():
    """Prueba sanitización básica de caracteres no permitidos."""
    assert sanitize_filename("proj-fix: aggressive filename") == "proj-fix_aggressive_filename"
    assert sanitize_filename("a:::b") == "a_b"
    assert sanitize_filename("file?name*test") == "file_name_test"

def test_sanitize_filename_unicode():
    """Prueba que los acentos y eñes se normalicen a ASCII."""
    assert sanitize_filename("cambio ñ áéíóú") == "cambio_n_aeiou"

def test_sanitize_filename_strip_underscores():
    """Prueba que se eliminen guiones bajos al inicio/final y duplicados."""
    assert sanitize_filename("___test___") == "test"
    assert sanitize_filename("a__b--c..d") == "a_b--c..d"

def test_windows_reserved_names_mitigation():
    """Verifica que nombres reservados sean mitigados con un guion bajo al inicio."""
    assert sanitize_filename("CON") == "_CON"
    assert sanitize_filename("aux.py") == "_aux.py"
    assert sanitize_filename("com1") == "_com1"
    assert sanitize_filename("LPT9") == "_LPT9"

def test_get_git_commit_info_success():
    """Verifica la obtención de info de git con mock."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            stdout="feat: test commit|abcdefg\n",
            returncode=0
        )
        subject, short_hash = get_git_commit_info(Path("."))
        assert subject == "feat: test commit"
        assert short_hash == "abcdefg"

def test_get_git_commit_info_with_pipe():
    """Verifica que mensajes con el carácter pipe '|' se procesen bien."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            stdout="feat: add | pipe test|1234567\n",
            returncode=0
        )
        subject, short_hash = get_git_commit_info(Path("."))
        assert subject == "feat: add | pipe test"
        assert short_hash == "1234567"

def test_get_git_commit_info_fail():
    """Verifica fallo al obtener info de git."""
    with patch("subprocess.run", side_effect=FileNotFoundError):
        subject, short_hash = get_git_commit_info(Path("."))
        assert subject is None
        assert short_hash is None

def test_force_inclusion_with_secret(temp_project):
    """Verifica que --force incluya archivos con secretos."""
    secret_file = temp_project / "secret.txt"
    secret_file.write_text("OPENAI_KEY=" + "sk" + "-12345678901234567890123456789012", encoding="utf-8")
    
    zip_path = temp_project.parent / "test_force.zip"
    # force=True
    incl, ign, findings = create_zip(temp_project, zip_path, [], [], True, force=True)
    
    assert incl == 1
    assert len(findings) == 1
    assert findings[0]["forced"] is True
    with zipfile.ZipFile(zip_path, "r") as z:
        assert "secret.txt" in z.namelist()

def test_strict_env_exclusion_even_with_force(temp_project):
    """Verifica que .env se excluya SIEMPRE, incluso con --force."""
    env_file = temp_project / ".env"
    env_file.write_text("DB_PASSWORD=123", encoding="utf-8")
    
    zip_path = temp_project.parent / "test_env.zip"
    # force=True
    incl, ign, findings = create_zip(temp_project, zip_path, [], [], True, force=True)
    
    assert incl == 0
    assert ign >= 1
    with zipfile.ZipFile(zip_path, "r") as z:
        assert ".env" not in z.namelist()

def test_sensitive_filename_forced(temp_project):
    """Verifica que archivos con nombres sensibles se incluyan con --force."""
    key_file = temp_project / "id_rsa.pub" # .pub is not in SECRET_FILE_PATTERNS but id_rsa is?
    # Wait, SECRET_FILE_PATTERNS has "id_rsa"
    key_file = temp_project / "id_rsa"
    key_file.write_text("ssh-rsa ...", encoding="utf-8")
    
    zip_path = temp_project.parent / "test_sensitive.zip"
    
    # Without force
    incl, ign, findings = create_zip(temp_project, zip_path, [], [], True, force=False)
    assert incl == 0
    
    # With force
    incl, ign, findings = create_zip(temp_project, zip_path, [], [], True, force=True)
    assert incl == 1
    assert any(f["reason"] == "sensitive_forced" for f in findings)
