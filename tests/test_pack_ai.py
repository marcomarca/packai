import os
import zipfile
from pathlib import Path
import pytest
from pack_ai import create_zip, scan_file_for_secrets, should_ignore_path, copy_zip

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
    secret_file.write_text("API_KEY='sk-12345678901234567890123456789012'", encoding="utf-8")
    
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
    # Usamos un secreto que dispare el escáner con total seguridad
    env_ex.write_text("OPENAI_KEY=sk-12345678901234567890123456789012", encoding="utf-8")
    
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
    assert should_ignore_path("foo/backups/old.py", patterns) == True
    assert should_ignore_path("backups/old.py", patterns) == True
    assert should_ignore_path("src/backups/old.py", patterns) == True
    assert should_ignore_path("important_backups/old.py", patterns) == False

def test_copy_zip_modes():
    """Verifica los retornos de estado de copy_zip."""
    # No necesitamos un zip real para el modo 'none'
    assert copy_zip(Path("dummy.zip"), "none") == "none"
