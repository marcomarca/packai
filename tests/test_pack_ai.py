import os
import zipfile
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock
from pack_ai import (
    build_default_zip_stem,
    build_git_context_markdown,
    build_parser,
    create_zip,
    get_git_commit_info,
    GIT_CONTEXT_FILENAME,
    scan_file_for_secrets,
    should_ignore_path,
    copy_git_context_to_clipboard,
    copy_zip,
    sanitize_filename,
)

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

def test_aipass_excluded_even_with_force(temp_project):
    """Verifica que .aipass no se incluya ni con --force."""
    (temp_project / ".aipass").write_text("secret.py", encoding="utf-8")
    (temp_project / "code.py").write_text("print('hello')", encoding="utf-8")

    zip_path = temp_project.parent / "test.zip"
    create_zip(temp_project, zip_path, [], [], True, force=True)

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

def test_env_example_excluded_with_no_env_example(temp_project):
    env_ex = temp_project / ".env.example"
    env_ex.write_text("DB_HOST=localhost", encoding="utf-8")

    zip_path = temp_project.parent / "test.zip"
    incl, ign, findings = create_zip(temp_project, zip_path, [], [], False)

    assert incl == 0
    with zipfile.ZipFile(zip_path, "r") as z:
        assert ".env.example" not in z.namelist()

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

def test_hidden_dot_directories_are_strictly_ignored(temp_project):
    """Verifica que carpetas ocultas genéricas se excluyan globalmente."""
    assert should_ignore_path(".tmp/", []) == "strict"
    assert should_ignore_path(".tmp/cache.py", []) == "strict"
    assert should_ignore_path("src/.uv-python/", []) == "strict"
    assert should_ignore_path("src/.uv-python/bin/python", []) == "strict"
    assert should_ignore_path(".cache/data.json", []) == "strict"

def test_dot_files_are_not_ignored_by_hidden_directory_rule(temp_project):
    """Verifica que la regla de carpetas ocultas no afecte archivos con punto."""
    assert should_ignore_path(".python-version", []) is None
    assert should_ignore_path(".env.example", []) is None

def test_allowed_dot_directories_are_not_globally_ignored(temp_project):
    """Verifica excepciones de carpetas ocultas que si aportan contexto."""
    assert should_ignore_path(".github/workflows/ci.yml", []) is None

def test_hidden_dot_directory_excluded_from_zip(temp_project):
    """Verifica que os.walk no entre a carpetas ocultas excluidas."""
    hidden_dir = temp_project / ".tmp"
    hidden_dir.mkdir()
    (hidden_dir / "cache.py").write_text("print('cache')", encoding="utf-8")
    (temp_project / ".python-version").write_text("3.12", encoding="utf-8")
    (temp_project / "code.py").write_text("print('hello')", encoding="utf-8")

    zip_path = temp_project.parent / "test_hidden_dirs.zip"
    incl, ign, findings = create_zip(temp_project, zip_path, [], [], True)

    assert incl == 2
    assert findings == []
    with zipfile.ZipFile(zip_path, "r") as z:
        names = z.namelist()
        assert "code.py" in names
        assert ".python-version" in names
        assert ".tmp/cache.py" not in names

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

def test_default_zip_stem_uses_project_and_hash_without_subject(temp_project):
    long_subject = "feat: " + "very-long-subject-" * 20

    with patch("pack_ai.get_git_commit_info", return_value=(long_subject, "b8c7cd4")):
        stem = build_default_zip_stem(temp_project)

    assert stem == "test_project-b8c7cd4"
    assert "very-long-subject" not in stem

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

def test_git_context_not_included_by_default(temp_project):
    (temp_project / "code.py").write_text("print('hello')", encoding="utf-8")
    zip_path = temp_project.parent / "test.zip"

    with patch("pack_ai.build_git_context_markdown") as mock_build:
        create_zip(temp_project, zip_path, [], [], True, include_git_context=False)

    mock_build.assert_not_called()
    with zipfile.ZipFile(zip_path, "r") as z:
        assert GIT_CONTEXT_FILENAME not in z.namelist()

def test_git_context_included_with_g(temp_project):
    (temp_project / "code.py").write_text("print('hello')", encoding="utf-8")
    zip_path = temp_project.parent / "test.zip"
    markdown = "```diff\n+print('hello')\n```"

    with patch("pack_ai.build_git_context_markdown", return_value=(markdown, None)):
        create_zip(temp_project, zip_path, [], [], True, include_git_context=True)

    with zipfile.ZipFile(zip_path, "r") as z:
        assert GIT_CONTEXT_FILENAME in z.namelist()
        assert "+print('hello')" in z.read(GIT_CONTEXT_FILENAME).decode("utf-8")

def test_git_context_secret_excluded_without_force(temp_project):
    (temp_project / "code.py").write_text("print('hello')", encoding="utf-8")
    zip_path = temp_project.parent / "test.zip"
    markdown = "OPENAI_KEY=sk-12345678901234567890123456789012"

    with patch("pack_ai.build_git_context_markdown", return_value=(markdown, None)):
        incl, ign, findings = create_zip(temp_project, zip_path, [], [], True, force=False, include_git_context=True)

    with zipfile.ZipFile(zip_path, "r") as z:
        assert GIT_CONTEXT_FILENAME not in z.namelist()
    assert any(f["reason"] == "git_context_secret_found" and f["forced"] is False for f in findings)

def test_git_context_secret_included_with_force(temp_project):
    (temp_project / "code.py").write_text("print('hello')", encoding="utf-8")
    zip_path = temp_project.parent / "test.zip"
    markdown = "OPENAI_KEY=sk-12345678901234567890123456789012"

    with patch("pack_ai.build_git_context_markdown", return_value=(markdown, None)):
        incl, ign, findings = create_zip(temp_project, zip_path, [], [], True, force=True, include_git_context=True)

    with zipfile.ZipFile(zip_path, "r") as z:
        assert GIT_CONTEXT_FILENAME in z.namelist()
    assert any(f["reason"] == "git_context_secret_found" and f["forced"] is True for f in findings)

def test_git_context_collision_is_not_overwritten(temp_project):
    (temp_project / GIT_CONTEXT_FILENAME).write_text("REAL FILE", encoding="utf-8")
    zip_path = temp_project.parent / "test.zip"

    with patch("pack_ai.build_git_context_markdown", return_value=("GENERATED FILE", None)):
        create_zip(temp_project, zip_path, [], [], True, include_git_context=True)

    with zipfile.ZipFile(zip_path, "r") as z:
        names = z.namelist()
        assert names.count(GIT_CONTEXT_FILENAME) == 1
        content = z.read(GIT_CONTEXT_FILENAME).decode("utf-8")
        assert content == "REAL FILE"
        assert "GENERATED FILE" not in content

def test_build_git_context_markdown_not_repo():
    with patch("pack_ai.run_git_command", return_value="false"):
        markdown, reason = build_git_context_markdown(Path("."))

    assert markdown is None
    assert "no es un repositorio Git" in reason

def test_build_git_context_markdown_contains_expected_sections():
    values = {
        ("rev-parse", "--is-inside-work-tree"): "true",
        ("rev-parse", "HEAD"): "abcdef1234567890",
        ("rev-parse", "--short", "HEAD"): "abcdef1",
        ("log", "-1", "--pretty=%s"): "feat: demo",
        ("log", "-1", "--pretty=%b"): "body",
        ("log", "-1", "--pretty=%an <%ae>"): "Ada <ada@example.com>",
        ("log", "-1", "--date=iso-strict", "--pretty=%ad"): "2026-06-01T12:00:00+00:00",
        ("rev-parse", "--show-toplevel"): "/tmp/repo",
    }

    def fake_git(root, args):
        key = tuple(args)
        if key in values:
            return values[key]
        if "--name-status" in args:
            return "M\tcode.py"
        if "--stat" in args:
            return " code.py | 2 +-"
        if "--patch" in args:
            return "diff --git a/code.py b/code.py\n@@ -1 +1 @@\n-old\n+new"
        return None

    with patch("pack_ai.run_git_command", side_effect=fake_git):
        markdown, reason = build_git_context_markdown(Path("."))

    assert reason is None
    for section in [
        "# AI Git Context",
        "## Resumen",
        "## Cuerpo del commit",
        "## Archivos cambiados",
        "## Estadísticas",
        "## Diff del último commit",
        "diff --git",
        "@@",
        "+new",
        "-old",
    ]:
        assert section in markdown

def test_env_excluded_without_force(temp_project):
    (temp_project / ".env").write_text("TOKEN=abc", encoding="utf-8")
    zip_path = temp_project.parent / "test.zip"

    create_zip(temp_project, zip_path, [], [], True, force=False)

    with zipfile.ZipFile(zip_path, "r") as z:
        assert ".env" not in z.namelist()

def test_env_excluded_even_with_force(temp_project):
    (temp_project / ".env").write_text("TOKEN=abc", encoding="utf-8")
    zip_path = temp_project.parent / "test.zip"

    create_zip(temp_project, zip_path, [], [], True, force=True)

    with zipfile.ZipFile(zip_path, "r") as z:
        assert ".env" not in z.namelist()

def test_env_variants_excluded_even_with_force(temp_project):
    (temp_project / ".env.local").write_text("TOKEN=abc", encoding="utf-8")
    (temp_project / ".env.production").write_text("TOKEN=abc", encoding="utf-8")
    nested = temp_project / "nested"
    nested.mkdir()
    (nested / ".env").write_text("TOKEN=abc", encoding="utf-8")
    (nested / ".env.local").write_text("TOKEN=abc", encoding="utf-8")
    zip_path = temp_project.parent / "test.zip"

    create_zip(temp_project, zip_path, [], [], True, force=True)

    with zipfile.ZipFile(zip_path, "r") as z:
        names = z.namelist()
        assert ".env.local" not in names
        assert ".env.production" not in names
        assert "nested/.env" not in names
        assert "nested/.env.local" not in names

def test_git_context_uses_env_exclude_pathspecs():
    calls = []

    def fake_git(root, args):
        calls.append(args)
        if args == ["rev-parse", "--is-inside-work-tree"]:
            return "true"
        if args[:1] == ["rev-parse"] or args[:1] == ["log"]:
            return "value"
        return ""

    with patch("pack_ai.run_git_command", side_effect=fake_git):
        build_git_context_markdown(Path("."))

    env_pathspecs = {":(exclude).env", ":(exclude).env.*", ":(exclude)**/.env", ":(exclude)**/.env.*"}
    git_show_calls = [args for args in calls if args[:1] == ["show"]]
    assert len(git_show_calls) == 3
    for args in git_show_calls:
        assert env_pathspecs.issubset(set(args))

def test_git_context_does_not_include_env_diff():
    def fake_git(root, args):
        if args == ["rev-parse", "--is-inside-work-tree"]:
            return "true"
        if args[:1] == ["rev-parse"] or args[:1] == ["log"]:
            return "value"
        if "--name-status" in args:
            return "M\tcode.py"
        if "--stat" in args:
            return " code.py | 1 +"
        if "--patch" in args:
            return "diff --git a/code.py b/code.py\n@@ -1 +1 @@\n-old\n+new"
        return ""

    with patch("pack_ai.run_git_command", side_effect=fake_git):
        markdown, reason = build_git_context_markdown(Path("."))

    assert reason is None
    assert ".env" not in markdown
    assert "API_KEY=" not in markdown
    assert "SECRET=" not in markdown
    assert "TOKEN=" not in markdown

def test_argparse_combined_gf():
    args = build_parser().parse_args([".", "-gf"])

    assert args.include_git_context is True
    assert args.force is True


def test_argparse_commit_clipboard():
    args = build_parser().parse_args([".", "-c"])

    assert args.copy_git_context is True

def test_argparse_combined_cf():
    args = build_parser().parse_args([".", "-cf"])

    assert args.copy_git_context is True
    assert args.force is True

def test_copy_git_context_to_clipboard_success():
    markdown = "# AI Git Context\n\n```diff\n+ok\n```"

    with patch("pack_ai.build_git_context_markdown", return_value=(markdown, None)), \
         patch("pack_ai.copy_text_to_clipboard", return_value=True) as mock_copy:
        status, findings = copy_git_context_to_clipboard(Path("."), force=False)

    assert status == "copied"
    assert findings == []
    mock_copy.assert_called_once_with(markdown)

def test_copy_git_context_to_clipboard_blocks_secret_without_force():
    markdown = "OPENAI_KEY=sk-12345678901234567890123456789012"

    with patch("pack_ai.build_git_context_markdown", return_value=(markdown, None)), \
         patch("pack_ai.copy_text_to_clipboard") as mock_copy:
        status, findings = copy_git_context_to_clipboard(Path("."), force=False)

    assert status == "blocked_secret"
    assert len(findings) == 1
    assert findings[0]["reason"] == "git_context_secret_found"
    assert findings[0]["forced"] is False
    mock_copy.assert_not_called()

def test_copy_git_context_to_clipboard_allows_secret_with_force():
    markdown = "OPENAI_KEY=sk-12345678901234567890123456789012"

    with patch("pack_ai.build_git_context_markdown", return_value=(markdown, None)), \
         patch("pack_ai.copy_text_to_clipboard", return_value=True) as mock_copy:
        status, findings = copy_git_context_to_clipboard(Path("."), force=True)

    assert status == "copied"
    assert len(findings) == 1
    assert findings[0]["forced"] is True
    mock_copy.assert_called_once_with(markdown)
