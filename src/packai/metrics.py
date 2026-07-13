"""In-memory archive metrics shared by CLI and future graphical clients."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from packai.contracts import FileTokenMetrics, PackMetrics, TokenEstimator
from packai.tokenization import HeuristicTokenEstimator, ResilientTokenEstimator


@dataclass(frozen=True, slots=True)
class MetricsEntry:
    """Exact bytes selected for the ZIP plus their analysis classification."""

    relative_path: str
    data: bytes
    text_encoding: str | None


class ArchiveMetricsAnalyzer:
    """Calculate metrics from the same immutable bytes written to the ZIP."""

    def __init__(self, estimator: TokenEstimator) -> None:
        self._estimator = ResilientTokenEstimator(estimator, HeuristicTokenEstimator())

    def analyze(self, entries: Sequence[MetricsEntry], *, top_n: int) -> PackMetrics:
        text_files = 0
        binary_files = 0
        estimated_tokens = 0
        token_files: list[FileTokenMetrics] = []
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

        token_files.sort(key=lambda item: (-item.token_count, item.relative_path))
        largest = tuple(token_files[:top_n]) if top_n else ()
        tokenizer = "+".join(sorted(methods)) if methods else self._estimator.name

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
        )
