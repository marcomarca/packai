"""Content classification without changing the bytes written to an archive."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

ContentKind = Literal["text", "binary_asset", "unsupported_binary", "executable"]

# Binary formats that are useful context for multimodal AI review. Unknown binary
# formats remain excluded by default. SVG is intentionally treated as text because
# it can contain source code, scripts, and secrets.
SUPPORTED_BINARY_ASSET_EXTENSIONS = frozenset(
    {
        ".avif",
        ".bmp",
        ".gif",
        ".heic",
        ".heif",
        ".ico",
        ".jpeg",
        ".jpg",
        ".pdf",
        ".png",
        ".tif",
        ".tiff",
        ".webp",
    }
)

_EXECUTABLE_MAGICS = (
    b"MZ",  # Windows PE
    b"\x7fELF",  # Linux/Unix ELF
    b"\xca\xfe\xba\xbe",  # Java class / Mach-O universal
    b"\xfe\xed\xfa\xce",  # Mach-O 32-bit
    b"\xce\xfa\xed\xfe",
    b"\xfe\xed\xfa\xcf",  # Mach-O 64-bit
    b"\xcf\xfa\xed\xfe",
    b"\x00asm",  # WebAssembly
)


@dataclass(frozen=True, slots=True)
class ContentClassification:
    """Classification plus the decoding required only for analysis."""

    kind: ContentKind
    text: str | None = None
    encoding: str | None = None


def classify_content(path: Path, data: bytes) -> ContentClassification:
    """Classify bytes conservatively while preserving the original payload.

    Text decoding is used only for secret scanning and token estimation. The
    archive writer always receives ``data`` unchanged.
    """
    if _has_executable_magic(data):
        return ContentClassification("executable")

    suffix = path.suffix.lower()
    if suffix in SUPPORTED_BINARY_ASSET_EXTENSIONS:
        if _matches_binary_asset_signature(suffix, data):
            return ContentClassification("binary_asset")
        # Do not trust a convenient extension when the content is another binary.
        decoded = decode_text(data)
        if decoded is not None:
            text, encoding = decoded
            return ContentClassification("text", text=text, encoding=encoding)
        return ContentClassification("unsupported_binary")

    decoded = decode_text(data)
    if decoded is not None:
        text, encoding = decoded
        return ContentClassification("text", text=text, encoding=encoding)
    return ContentClassification("unsupported_binary")


def decode_text(data: bytes) -> tuple[str, str] | None:
    """Decode common text encodings using strict, deterministic rules."""
    if not data:
        return "", "utf-8"

    bom_candidates = (
        (b"\x00\x00\xfe\xff", "utf-32"),
        (b"\xff\xfe\x00\x00", "utf-32"),
        (b"\xef\xbb\xbf", "utf-8-sig"),
        (b"\xfe\xff", "utf-16"),
        (b"\xff\xfe", "utf-16"),
    )
    for bom, encoding in bom_candidates:
        if data.startswith(bom):
            try:
                return data.decode(encoding, errors="strict"), encoding
            except UnicodeDecodeError:
                return None

    # NUL bytes outside a recognized Unicode BOM are a strong binary signal.
    if b"\x00" in data[:8192]:
        return None

    try:
        return data.decode("utf-8", errors="strict"), "utf-8"
    except UnicodeDecodeError:
        pass

    if _binary_control_ratio(data[:8192]) > 0.05:
        return None

    # cp1252 covers common legacy Western text while avoiding latin-1 control
    # characters that make arbitrary binary data look like valid text.
    try:
        return data.decode("cp1252", errors="strict"), "cp1252"
    except UnicodeDecodeError:
        return None


def _has_executable_magic(data: bytes) -> bool:
    return any(data.startswith(magic) for magic in _EXECUTABLE_MAGICS)


def _matches_binary_asset_signature(suffix: str, data: bytes) -> bool:
    if suffix == ".pdf":
        return b"%PDF-" in data[:1024]
    if suffix == ".png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    if suffix in {".jpg", ".jpeg"}:
        return data.startswith(b"\xff\xd8\xff")
    if suffix == ".gif":
        return data.startswith((b"GIF87a", b"GIF89a"))
    if suffix == ".webp":
        return len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WEBP"
    if suffix == ".bmp":
        return data.startswith(b"BM")
    if suffix in {".tif", ".tiff"}:
        return data.startswith((b"II*\x00", b"MM\x00*"))
    if suffix == ".ico":
        return data.startswith(b"\x00\x00\x01\x00")
    if suffix == ".avif":
        return _has_isobmff_brand(data, {b"avif", b"avis"})
    if suffix in {".heic", ".heif"}:
        return _has_isobmff_brand(data, {b"heic", b"heix", b"hevc", b"hevx", b"mif1", b"msf1"})
    return False


def _has_isobmff_brand(data: bytes, brands: set[bytes]) -> bool:
    return len(data) >= 12 and data[4:8] == b"ftyp" and any(brand in data[8:32] for brand in brands)


def _binary_control_ratio(sample: bytes) -> float:
    if not sample:
        return 0.0
    allowed_controls = {9, 10, 12, 13}
    controls = sum(byte < 32 and byte not in allowed_controls for byte in sample)
    return controls / len(sample)
