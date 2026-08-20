"""Configuration loading with deep-merge overrides.

Supports both YAML (when PyYAML is installed) and JSON fallback
for environments like Streamlit in Snowflake where PyYAML may
not be available.
"""
from __future__ import annotations

import json
import os

try:
    import yaml
    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False

# Look for config: JSON first (always works), then YAML if available
_PKG_DIR = os.path.dirname(os.path.abspath(__file__))
_BUNDLED_JSON = os.path.join(_PKG_DIR, "default_config.json")
_BUNDLED_YAML = os.path.join(_PKG_DIR, "default_config.yml")
_REPO = os.path.join(os.path.dirname(os.path.dirname(_PKG_DIR)), "config", "default_config.yml")

if os.path.isfile(_BUNDLED_JSON):
    _DEFAULT = _BUNDLED_JSON
    _DEFAULT_FORMAT = "json"
elif os.path.isfile(_BUNDLED_YAML):
    _DEFAULT = _BUNDLED_YAML
    _DEFAULT_FORMAT = "yaml"
elif os.path.isfile(_REPO):
    _DEFAULT = _REPO
    _DEFAULT_FORMAT = "yaml"
else:
    _DEFAULT = None
    _DEFAULT_FORMAT = None


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _load_file(path: str) -> dict:
    """Load a config file (JSON or YAML) based on extension."""
    with open(path, encoding="utf-8") as fh:
        if path.endswith(".json"):
            return json.load(fh)
        elif _HAS_YAML:
            return yaml.safe_load(fh)
        else:
            raise ImportError(
                f"Cannot load YAML file '{path}' — PyYAML not installed. "
                f"Use the .json config or install PyYAML."
            )


def load_config(override_path: str | None = None) -> dict:
    if _DEFAULT is None:
        raise FileNotFoundError(
            "No default config found. Expected default_config.json or "
            "default_config.yml next to the qv2dbt package."
        )
    cfg = _load_file(_DEFAULT)
    if override_path:
        cfg = _deep_merge(cfg, _load_file(override_path) or {})
    return cfg
