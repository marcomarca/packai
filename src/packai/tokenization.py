"""Replaceable token estimators with an offline, deterministic primary implementation."""

from __future__ import annotations

import base64
import hashlib
import importlib
import math
from functools import lru_cache
from importlib import resources
from typing import Any, cast

from packai.contracts import TokenEstimate, TokenEstimator

_O200K_DATA_SHA256 = "446a9538cb6c348e3516120d7c08b09f57c36495e2acfffe59a5bf8b0cfb1a2d"
_O200K_PATTERN = "|".join(
    [
        r"""[^\r\n\p{L}\p{N}]?[\p{Lu}\p{Lt}\p{Lm}\p{Lo}\p{M}]*[\p{Ll}\p{Lm}\p{Lo}\p{M}]+(?i:'s|'t|'re|'ve|'m|'ll|'d)?""",
        r"""[^\r\n\p{L}\p{N}]?[\p{Lu}\p{Lt}\p{Lm}\p{Lo}\p{M}]+[\p{Ll}\p{Lm}\p{Lo}\p{M}]*(?i:'s|'t|'re|'ve|'m|'ll|'d)?""",
        r"""\p{N}{1,3}""",
        r""" ?[^\s\p{L}\p{N}]+[\r\n/]*""",
        r"""\s*[\r\n]+""",
        r"""\s+(?!\S)""",
        r"""\s+""",
    ]
)
_O200K_SPECIAL_TOKENS = {
    "<|endoftext|>": 199999,
    "<|endofprompt|>": 200018,
}


class HeuristicTokenEstimator:
    """Estimate tokens from UTF-8 bytes when a real tokenizer is unavailable."""

    name = "heuristic:utf8-bytes/4"

    def estimate(self, text: str) -> TokenEstimate:
        if not text:
            return TokenEstimate(count=0, method=self.name, degraded=True)
        count = max(1, math.ceil(len(text.encode("utf-8")) / 4))
        return TokenEstimate(count=count, method=self.name, degraded=True)


class TiktokenEstimator:
    """Count tokens with a bundled, hash-verified ``o200k_base`` vocabulary.

    The vocabulary is a package resource, so initialization performs no network
    access and does not depend on tiktoken's process cache. ``encoding_data`` is
    injectable only to make integrity and fallback behavior directly testable.
    """

    name = "tiktoken:o200k_base"

    def __init__(self, *, encoding_data: bytes | None = None) -> None:
        module = importlib.import_module("tiktoken")
        data = encoding_data if encoding_data is not None else _read_bundled_encoding_data()
        mergeable_ranks = _parse_verified_o200k_data(data)
        encoding_type = cast(Any, module).Encoding
        self._encoding: Any = encoding_type(
            name="o200k_base",
            pat_str=_O200K_PATTERN,
            mergeable_ranks=mergeable_ranks,
            special_tokens=_O200K_SPECIAL_TOKENS,
        )

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


def _read_bundled_encoding_data() -> bytes:
    resource = resources.files("packai.data").joinpath("o200k_base.tiktoken")
    return resource.read_bytes()


def _parse_verified_o200k_data(data: bytes) -> dict[bytes, int]:
    # Git puede materializar recursos textuales con CRLF en Windows. El formato
    # tiktoken es una secuencia de registros ASCII separados por líneas, por lo
    # que la integridad se verifica sobre una representación canónica LF sin
    # alterar los tokens ni los rangos.
    canonical_data = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    digest = hashlib.sha256(canonical_data).hexdigest()
    if digest != _O200K_DATA_SHA256:
        raise ValueError(
            "El vocabulario o200k_base incluido está ausente o corrupto "
            f"(SHA-256 esperado: {_O200K_DATA_SHA256}; recibido: {digest})."
        )

    ranks: dict[bytes, int] = {}
    try:
        for line in canonical_data.splitlines():
            if not line:
                continue
            encoded_token, raw_rank = line.split()
            ranks[base64.b64decode(encoded_token, validate=True)] = int(raw_rank)
    except (ValueError, TypeError) as exc:
        raise ValueError("El vocabulario o200k_base incluido no tiene un formato válido.") from exc

    if len(ranks) != 199_998:
        raise ValueError(
            "El vocabulario o200k_base incluido está incompleto "
            f"({len(ranks):,} entradas; se esperaban 199,998)."
        )
    return ranks


@lru_cache(maxsize=1)
def build_default_token_estimator() -> TokenEstimator:
    """Build the exact offline estimator, otherwise return the safe fallback."""
    fallback = HeuristicTokenEstimator()
    try:
        return ResilientTokenEstimator(TiktokenEstimator(), fallback)
    except Exception:
        return fallback
