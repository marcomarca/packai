from __future__ import annotations

from pathlib import Path

from packai import cli
from packai.gui.contracts import GuiLaunchOptions


def test_gui_command_dispatches_without_changing_legacy_parser(
    tmp_path: Path,
    monkeypatch,
) -> None:
    root = tmp_path / "project"
    excluded = root / "generated"
    excluded.mkdir(parents=True)
    captured: list[GuiLaunchOptions] = []

    monkeypatch.setattr(
        "packai.gui.launcher.launch_gui", lambda options: captured.append(options) or 17
    )

    status = cli.main(
        [
            "gui",
            str(root),
            "-e",
            "generated",
            "--force",
            "-g",
            "--copy",
            "none",
            "--token-top",
            "10",
        ]
    )

    assert status == 17
    assert captured == [
        GuiLaunchOptions(
            root=root.resolve(),
            exclude_paths=("generated",),
            force=True,
            include_git_context=True,
            include_env_example=True,
            token_top=10,
            copy_mode="none",
        )
    ]
    assert cli.build_parser().parse_args([str(root)]).folder == str(root)
