"""Configuration loading with deep-merge overrides."""
from __future__ import annotations

import os

import yaml

_DEFAULT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "config", "default_config.yml")


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config(override_path: str | None = None) -> dict:
    with open(_DEFAULT, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    if override_path:
        with open(override_path, encoding="utf-8") as fh:
            cfg = _deep_merge(cfg, yaml.safe_load(fh) or {})
    return cfg
