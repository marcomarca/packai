"""Git adapter used to build optional last-commit context."""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path

from packai.contracts import GitContextResult
from packai.policy import build_git_exclude_pathspecs

GitRunner = Callable[[Path, list[str]], str | None]


def run_git_command(root: Path, args: list[str]) -> str | None:
    """Run Git with deterministic UTF-8 decoding and no shell."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    return result.stdout.strip()


def build_git_context(
    root: Path,
    exclude_dirs: Sequence[str] = (),
    *,
    runner: GitRunner = run_git_command,
) -> GitContextResult:
    """Build a presentation-neutral result for the latest committed diff."""
    inside = runner(root, ["rev-parse", "--is-inside-work-tree"])
    if inside != "true":
        return GitContextResult(None, "no es un repositorio Git")

    full_hash = runner(root, ["rev-parse", "HEAD"])
    if full_hash is None:
        return GitContextResult(None, "no hay commits disponibles")

    short_hash = runner(root, ["rev-parse", "--short", "HEAD"])
    subject = runner(root, ["log", "-1", "--pretty=%s"])
    body = runner(root, ["log", "-1", "--pretty=%b"])
    date = runner(root, ["log", "-1", "--date=iso-strict", "--pretty=%ad"])
    repo_root = runner(root, ["rev-parse", "--show-toplevel"])

    if short_hash is None or subject is None or date is None or repo_root is None:
        return GitContextResult(None, "no hay commits disponibles")

    env_excludes = [
        ":(exclude).env",
        ":(exclude).env.*",
        ":(exclude)**/.env",
        ":(exclude)**/.env.*",
    ]
    pathspecs = ["--", ".", *env_excludes, *build_git_exclude_pathspecs(tuple(exclude_dirs))]
    changed = runner(
        root,
        ["show", "--name-status", "--format=", "--find-renames", "HEAD", *pathspecs],
    )
    stat = runner(root, ["show", "--stat", "--format=", "--find-renames", "HEAD", *pathspecs])
    diff = runner(
        root,
        [
            "show",
            "--format=",
            "--patch",
            "--find-renames",
            "--find-copies",
            "--no-ext-diff",
            "--no-color",
            "HEAD",
            *pathspecs,
        ],
    )

    if changed is None or stat is None or diff is None:
        return GitContextResult(None, "no hay commits disponibles")

    body = body or "(sin cuerpo de commit)"
    changed = changed or "(sin archivos reportados)"
    stat = stat or "(sin estadísticas)"
    diff = diff or "(sin diff textual)"

    markdown = f"""## Resumen

- Modo: `last-commit`
- Repositorio: `{Path(repo_root).name}`
- Commit: `{full_hash}`
- Commit corto: `{short_hash}`
- Fecha: `{date}`
- Subject: `{subject}`

## Cuerpo del commit

{body}

## Archivos cambiados

```text
{changed}
```

## Estadísticas

```text
{stat}
```

## Diff del último commit

```diff
{diff}
```
"""
    return GitContextResult(markdown)


class SubprocessGitContextProvider:
    """Production implementation of the Git context port."""

    def build(self, root: Path, exclude_dirs: Sequence[str] = ()) -> GitContextResult:
        return build_git_context(root, exclude_dirs)


def get_git_commit_info(root: Path) -> tuple[str | None, str | None]:
    """Return the last commit subject and short hash for archive naming."""
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--pretty=%s|%h"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None, None

    data = result.stdout.strip()
    if "|" in data:
        subject, short_hash = data.rsplit("|", 1)
        return subject, short_hash
    return data, None
