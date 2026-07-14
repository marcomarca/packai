"""In-memory archive metrics shared by CLI, GUI, and API clients."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import PurePosixPath

from packai.contracts import (
    FileTokenMetrics,
    LanguageCodeMetrics,
    PackMetrics,
    TokenEstimator,
)
from packai.tokenization import HeuristicTokenEstimator, ResilientTokenEstimator


@dataclass(frozen=True, slots=True)
class MetricsEntry:
    """Exact bytes selected for the ZIP plus their analysis classification."""

    relative_path: str
    data: bytes
    text_encoding: str | None


_LANGUAGE_BY_SUFFIX = {
    ".asm": "Assembly",
    ".bash": "Shell",
    ".c": "C",
    ".cc": "C++",
    ".clj": "Clojure",
    ".cljc": "Clojure",
    ".cljs": "Clojure",
    ".cmake": "CMake",
    ".coffee": "CoffeeScript",
    ".cpp": "C++",
    ".cs": "C#",
    ".css": "CSS",
    ".cxx": "C++",
    ".dart": "Dart",
    ".edn": "Clojure",
    ".eex": "Elixir",
    ".elm": "Elm",
    ".erl": "Erlang",
    ".ex": "Elixir",
    ".exs": "Elixir",
    ".fish": "Shell",
    ".fs": "F#",
    ".fsi": "F#",
    ".fsx": "F#",
    ".go": "Go",
    ".gql": "GraphQL",
    ".gradle": "Gradle",
    ".graphql": "GraphQL",
    ".groovy": "Groovy",
    ".h": "C/C++ Header",
    ".hcl": "HCL",
    ".hh": "C/C++ Header",
    ".hpp": "C/C++ Header",
    ".hrl": "Erlang",
    ".hs": "Haskell",
    ".htm": "HTML",
    ".html": "HTML",
    ".hxx": "C/C++ Header",
    ".java": "Java",
    ".js": "JavaScript",
    ".json": "JSON",
    ".jsx": "JavaScript",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".less": "Less",
    ".lhs": "Haskell",
    ".lua": "Lua",
    ".m": "Objective-C",
    ".mjs": "JavaScript",
    ".mm": "Objective-C++",
    ".nim": "Nim",
    ".pas": "Pascal",
    ".php": "PHP",
    ".pl": "Perl",
    ".pm": "Perl",
    ".proto": "Protocol Buffers",
    ".ps1": "PowerShell",
    ".psd1": "PowerShell",
    ".psm1": "PowerShell",
    ".py": "Python",
    ".pyw": "Python",
    ".r": "R",
    ".rb": "Ruby",
    ".rs": "Rust",
    ".sass": "Sass",
    ".scala": "Scala",
    ".sc": "Scala",
    ".scss": "SCSS",
    ".sh": "Shell",
    ".sol": "Solidity",
    ".sql": "SQL",
    ".svelte": "Svelte",
    ".swift": "Swift",
    ".tf": "Terraform",
    ".tfvars": "Terraform",
    ".toml": "TOML",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".v": "V",
    ".vb": "Visual Basic",
    ".vue": "Vue",
    ".xml": "XML",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".zig": "Zig",
    ".zsh": "Shell",
}

_LANGUAGE_BY_FILENAME = {
    "cmakelists.txt": "CMake",
    "dockerfile": "Dockerfile",
    "gemfile": "Ruby",
    "jenkinsfile": "Groovy",
    "makefile": "Makefile",
    "rakefile": "Ruby",
}

_SHEBANG_LANGUAGES = (
    ("python", "Python"),
    ("node", "JavaScript"),
    ("deno", "TypeScript"),
    ("ruby", "Ruby"),
    ("perl", "Perl"),
    ("php", "PHP"),
    ("pwsh", "PowerShell"),
    ("powershell", "PowerShell"),
    ("bash", "Shell"),
    ("zsh", "Shell"),
    ("fish", "Shell"),
    ("sh", "Shell"),
)


class ArchiveMetricsAnalyzer:
    """Calculate metrics from the same immutable bytes written to the ZIP."""

    def __init__(self, estimator: TokenEstimator) -> None:
        self._estimator = ResilientTokenEstimator(estimator, HeuristicTokenEstimator())

    def analyze(self, entries: Sequence[MetricsEntry], *, top_n: int) -> PackMetrics:
        text_files = 0
        binary_files = 0
        estimated_tokens = 0
        code_files = 0
        code_lines = 0
        token_files: list[FileTokenMetrics] = []
        language_totals: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        methods: set[str] = set()
        degraded = False

        for entry in entries:
            if entry.text_encoding is None:
                binary_files += 1
                continue

            text_files += 1
            text = entry.data.decode(entry.text_encoding, errors="strict")
            estimate = self._estimator.estimate(text)
            methods.add(estimate.method)
            degraded = degraded or estimate.degraded
            estimated_tokens += estimate.count
            token_files.append(
                FileTokenMetrics(
                    relative_path=entry.relative_path,
                    token_count=estimate.count,
                    uncompressed_size=len(entry.data),
                )
            )

            language = detect_source_language(entry.relative_path, text)
            if language is not None:
                lines = count_physical_code_lines(text)
                code_files += 1
                code_lines += lines
                language_totals[language][0] += 1
                language_totals[language][1] += lines

        token_files.sort(key=lambda item: (-item.token_count, item.relative_path))
        largest = tuple(token_files[:top_n]) if top_n else ()
        tokenizer = "+".join(sorted(methods)) if methods else self._estimator.name
        by_language = tuple(
            LanguageCodeMetrics(language=language, files=files, code_lines=lines)
            for language, (files, lines) in sorted(
                language_totals.items(),
                key=lambda item: (-item[1][1], item[0]),
            )
        )

        return PackMetrics(
            included_files=len(entries),
            text_files=text_files,
            binary_files=binary_files,
            uncompressed_size=sum(len(entry.data) for entry in entries),
            zip_size=None,
            estimated_tokens=estimated_tokens,
            largest_token_files=largest,
            tokenizer=tokenizer,
            degraded=degraded,
            complete=True,
            warnings=(),
            code_files=code_files,
            code_lines=code_lines,
            language_code_lines=by_language,
        )


def count_physical_code_lines(text: str) -> int:
    """Count non-empty physical lines; comments are intentionally included."""
    return sum(1 for line in text.splitlines() if line.strip())


def detect_source_language(relative_path: str, text: str) -> str | None:
    """Detect common source and declarative languages without parsing content."""
    path = PurePosixPath(relative_path)
    filename = path.name.lower()
    language = _LANGUAGE_BY_FILENAME.get(filename)
    if language is not None:
        return language

    language = _LANGUAGE_BY_SUFFIX.get(path.suffix.lower())
    if language is not None:
        return language

    first_line = text.splitlines()[0].lower() if text.splitlines() else ""
    if first_line.startswith("#!"):
        for marker, detected in _SHEBANG_LANGUAGES:
            if marker in first_line:
                return detected
    return None
