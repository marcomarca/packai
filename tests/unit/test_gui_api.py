from __future__ import annotations

import zipfile
from pathlib import Path

from packai.gui.api import GuiBridge
from packai.gui.contracts import GuiLaunchOptions


def _payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "exclude_paths": [],
        "force": False,
        "include_git_context": False,
        "include_env_example": True,
        "include_lockfiles": True,
        "token_top": 3,
        "copy_mode": "none",
    }
    payload.update(overrides)
    return payload


def test_gui_bridge_initializes_tree_and_metrics(tmp_path: Path) -> None:
    root = tmp_path / "project"
    (root / "src").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "src" / "main.py").write_text("print('ok')", encoding="utf-8")
    (root / "tests" / "test_main.py").write_text("def test_ok(): pass", encoding="utf-8")
    bridge = GuiBridge(GuiLaunchOptions(root=root, copy_mode="none"))

    response = bridge.initialize()

    assert response["ok"] is True
    assert {node["name"] for node in response["tree"]} == {"src", "tests"}
    tree_by_name = {node["name"]: node for node in response["tree"]}
    assert tree_by_name["src"]["total_size_bytes"] == len("print('ok')")
    assert tree_by_name["tests"]["total_size_bytes"] == len("def test_ok(): pass")
    preview = response["preview"]
    assert preview["metrics"]["included_files"] == 2
    assert preview["metrics"]["code_files"] == 2
    assert preview["metrics"]["code_lines"] == 2
    assert preview["metrics"]["language_code_lines"] == [
        {"language": "Python", "files": 2, "code_lines": 2}
    ]
    assert response["commands"]["pack"].startswith("packai ")


def test_gui_bridge_preview_applies_folder_exclusions_and_updates_command(tmp_path: Path) -> None:
    root = tmp_path / "project"
    (root / "src").mkdir(parents=True)
    (root / "generated").mkdir()
    (root / "src" / "main.py").write_text("print('ok')", encoding="utf-8")
    (root / "generated" / "client.py").write_text("x = 1", encoding="utf-8")
    bridge = GuiBridge(GuiLaunchOptions(root=root, copy_mode="none"))

    response = bridge.preview(_payload(exclude_paths=["generated"]))

    assert response["ok"] is True
    assert response["excluded_paths"] == ["generated"]
    assert response["preview"]["metrics"]["included_files"] == 1
    assert "-e generated" in response["commands"]["pack"]


def test_gui_bridge_pack_rescans_and_creates_default_zip(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / "main.py").write_text("print('first')", encoding="utf-8")
    bridge = GuiBridge(GuiLaunchOptions(root=root, copy_mode="none"))
    bridge.initialize()
    (root / "new.py").write_text("print('new')", encoding="utf-8")
    (root / "generated").mkdir()
    (root / "generated" / "client.py").write_text("x = 1", encoding="utf-8")

    response = bridge.pack(_payload())

    assert response["ok"] is True
    assert response["copy_status"] == "none"
    output = Path(response["output_zip"])
    assert output.parent == root.parent
    with zipfile.ZipFile(output) as archive:
        assert set(archive.namelist()) == {"main.py", "new.py", "generated/client.py"}
    assert {node["name"] for node in response["tree"]} == {"generated"}
    assert response["preview"]["metrics"]["zip_size"] == output.stat().st_size


def test_gui_bridge_force_changes_secret_inclusion_without_persisting_state(tmp_path: Path) -> None:
    root = tmp_path / "project"
    secure = root / "secure"
    secure.mkdir(parents=True)
    (secure / "config.py").write_text(
        'OPENAI_API_KEY = "sk-' + "Ab3Cd4Ef5Gh6Ij7Kl8Mn9Op0Qr1St2Uv" + '"',
        encoding="utf-8",
    )
    bridge = GuiBridge(GuiLaunchOptions(root=root, copy_mode="none"))

    safe = bridge.preview(_payload(force=False))
    forced = bridge.preview(_payload(force=True))

    assert safe["preview"]["metrics"]["included_files"] == 0
    assert safe["preview"]["findings"][0]["forced"] is False
    assert forced["preview"]["metrics"]["included_files"] == 1
    assert forced["preview"]["findings"][0]["forced"] is True


def test_gui_bridge_drops_stale_exclusions_after_folder_is_removed(tmp_path: Path) -> None:
    root = tmp_path / "project"
    stale = root / "generated"
    stale.mkdir(parents=True)
    bridge = GuiBridge(GuiLaunchOptions(root=root, exclude_paths=("generated",), copy_mode="none"))
    stale.rmdir()

    response = bridge.refresh(_payload(exclude_paths=["generated"]))

    assert response["ok"] is True
    assert response["excluded_paths"] == []


def test_gui_bridge_toggles_lockfiles_and_renders_reproducible_command(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / "uv.lock").write_text("version = 1", encoding="utf-8")
    (root / "main.py").write_text("print('ok')", encoding="utf-8")
    bridge = GuiBridge(GuiLaunchOptions(root=root, copy_mode="none"))

    included = bridge.preview(_payload(include_lockfiles=True))
    excluded = bridge.preview(_payload(include_lockfiles=False))

    assert included["preview"]["metrics"]["included_files"] == 2
    assert excluded["preview"]["metrics"]["included_files"] == 1
    assert excluded["options"]["include_lockfiles"] is False
    assert "--no-lockfiles" in excluded["commands"]["pack"]

    packed = bridge.pack(_payload(include_lockfiles=False))
    with zipfile.ZipFile(Path(packed["output_zip"])) as archive:
        assert archive.namelist() == ["main.py"]
