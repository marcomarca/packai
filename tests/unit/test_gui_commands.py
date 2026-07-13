from __future__ import annotations

from pathlib import Path

from packai.gui.commands import build_commands
from packai.gui.contracts import GuiLaunchOptions


def test_gui_commands_reproduce_selection_without_output_override(
    tmp_path: Path,
    monkeypatch,
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    monkeypatch.chdir(root)
    options = GuiLaunchOptions(
        root=root,
        force=True,
        include_git_context=True,
        include_env_example=False,
        token_top=10,
        copy_mode="none",
    )

    commands = build_commands(options, ("generated", "tests/fixtures"))

    assert commands["pack"].startswith("packai .")
    assert commands["gui"].startswith("packai gui .")
    for command in commands.values():
        assert "-e generated" in command
        assert "-e tests/fixtures" in command
        assert "--force" in command
        assert " -g" in command
        assert "--no-env-example" in command
        assert "--token-top 10" in command
        assert "--copy none" in command
        assert "--output" not in command
