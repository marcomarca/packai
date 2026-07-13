from __future__ import annotations

from pathlib import Path

from packai.gui.tree import FolderNode, scan_folder_tree


def _by_name(nodes: tuple[FolderNode, ...]) -> dict[str, FolderNode]:
    return {node.name: node for node in nodes}


def test_folder_tree_keeps_policy_directories_visible_but_disabled(tmp_path: Path) -> None:
    root = tmp_path / "project"
    (root / "src" / "packai").mkdir(parents=True)
    (root / "src" / "main.py").write_text("print('ok')", encoding="utf-8")
    (root / ".git" / "objects" / "aa").mkdir(parents=True)
    (root / "node_modules" / "large-package").mkdir(parents=True)
    (root / "generated" / "nested").mkdir(parents=True)
    (root / ".ignore2packai").write_text("generated/\n", encoding="utf-8")

    nodes = _by_name(scan_folder_tree(root, include_env_example=True))

    assert nodes["src"].disabled is False
    assert nodes["src"].direct_file_count == 1
    assert [child.name for child in nodes["src"].children] == ["packai"]

    assert nodes[".git"].disabled is True
    assert nodes[".git"].children == ()
    assert nodes["node_modules"].disabled is True
    assert nodes["node_modules"].children == ()
    assert nodes["generated"].disabled is True
    assert nodes["generated"].disabled_reason == "Ignorado por la política del proyecto"


def test_folder_tree_never_exposes_files_as_selectable_nodes(tmp_path: Path) -> None:
    root = tmp_path / "project"
    folder = root / "docs"
    folder.mkdir(parents=True)
    (folder / "guide.md").write_text("guide", encoding="utf-8")

    nodes = scan_folder_tree(root, include_env_example=True)

    assert len(nodes) == 1
    assert nodes[0].name == "docs"
    assert nodes[0].direct_file_count == 1
    assert nodes[0].children == ()
