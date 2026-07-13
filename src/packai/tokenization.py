"""Replaceable token estimators with a deterministic degraded fallback."""

from __future__ import annotations

import importlib
import math
from typing import Any

from packai.contracts import TokenEstimate, TokenEstimator


class HeuristicTokenEstimator:
    """Estimate tokens from UTF-8 bytes when a real tokenizer is unavailable."""

    name = "heuristic:utf8-bytes/4"

    def estimate(self, text: str) -> TokenEstimate:
        if not text:
            return TokenEstimate(count=0, method=self.name, degraded=True)
        count = max(1, math.ceil(len(text.encode("utf-8")) / 4))
        return TokenEstimate(count=count, method=self.name, degraded=True)


class TiktokenEstimator:
    """Count tokens with the stable o200k_base encoding."""

    name = "tiktoken:o200k_base"

    def __init__(self) -> None:
        module = importlib.import_module("tiktoken")
        self._encoding: Any = module.get_encoding("o200k_base")

    def estimate(self, text: str) -> TokenEstimate:
        count = len(self._encoding.encode(text, disallowed_special=()))
        return TokenEstimate(count=count, method=self.name, degraded=False)


class ResilientTokenEstimator:
    """Use a primary estimator and degrade per file if it fails."""

    def __init__(
        self,
        primary: TokenEstimator,
        fallback: TokenEstimator | None = None,
    ) -> None:
        self._primary = primary
        self._fallback = fallback or HeuristicTokenEstimator()
        self.name = primary.name

    def estimate(self, text: str) -> TokenEstimate:
        try:
            estimate = self._primary.estimate(text)
            if estimate.count < 0:
                raise ValueError("el estimador devolvió un conteo negativo")
            return estimate
        except Exception:
            return self._fallback.estimate(text)


def build_default_token_estimator() -> TokenEstimator:
    """Build tiktoken when available, otherwise return the safe fallback."""
    fallback = HeuristicTokenEstimator()
    try:
        return ResilientTokenEstimator(TiktokenEstimator(), fallback)
    except Exception:
        return fallback
