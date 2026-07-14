"""Configuration boundary with backwards-compatible local overrides."""

try:
    import config_pack_ai

    INCLUDE_ENV_EXAMPLE = bool(getattr(config_pack_ai, "INCLUDE_ENV_EXAMPLE", True))
    INCLUDE_LOCKFILES = bool(getattr(config_pack_ai, "INCLUDE_LOCKFILES", True))
except ImportError:
    INCLUDE_ENV_EXAMPLE = True
    INCLUDE_LOCKFILES = True
