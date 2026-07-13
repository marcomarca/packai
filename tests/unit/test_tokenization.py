from __future__ import annotations

from unittest.mock import patch

import pytest

from packai.contracts import TokenEstimate
from packai.tokenization import (
    HeuristicTokenEstimator,
    ResilientTokenEstimator,
    TiktokenEstimator,
    build_default_token_estimator,
)


def test_bundled_tiktoken_estimator_counts_offline() -> None:
    estimator = TiktokenEstimator()

    estimate = estimator.estimate("hello world")

    assert estimate.count == 2
    assert estimate.method == "tiktoken:o200k_base"
    assert estimate.degraded is False


def test_tiktoken_rejects_corrupted_bundled_vocabulary() -> None:
    with pytest.raises(ValueError, match="ausente o corrupto"):
        TiktokenEstimator(encoding_data=b"corrupted")


def test_default_estimator_falls_back_when_exact_estimator_cannot_initialize() -> None:
    build_default_token_estimator.cache_clear()
    with patch(
        "packai.tokenization.TiktokenEstimator",
        side_effect=ValueError("missing resource"),
    ):
        estimator = build_default_token_estimator()

    assert isinstance(estimator, HeuristicTokenEstimator)
    build_default_token_estimator.cache_clear()


def test_resilient_estimator_degrades_when_primary_fails_per_file() -> None:
    class BrokenEstimator:
        name = "broken"

        def estimate(self, text: str) -> TokenEstimate:
            raise RuntimeError(text)

    estimator = ResilientTokenEstimator(BrokenEstimator())

    estimate = estimator.estimate("abcd")

    assert estimate.count == 1
    assert estimate.degraded is True
    assert estimate.method == "heuristic:utf8-bytes/4"
