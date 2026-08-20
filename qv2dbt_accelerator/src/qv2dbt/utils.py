"""Shared helpers for the generators."""
from __future__ import annotations

import re


def case_identifier(name: str, mode: str) -> str:
    name = name.strip().strip('"')
    if mode == "upper":
        return name.upper()
    if mode == "lower":
        return name.lower()
    return name


def snake(name: str) -> str:
    name = re.sub(r"[^\w]+", "_", name.strip())
    name = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
    return re.sub(r"_+", "_", name).strip("_").lower()


def sql_type_guess(field_name: str) -> str:
    """Heuristic Snowflake type for raw landing DDL (best-effort)."""
    n = field_name.lower()
    if any(k in n for k in ("date", "_dt", "dob")):
        return "DATE"
    if any(k in n for k in ("timestamp", "_ts", "datetime", "created", "updated")):
        return "TIMESTAMP_NTZ"
    if any(k in n for k in ("amount", "amt", "price", "cost", "value", "sales",
                            "revenue", "qty", "quantity", "rate", "pct")):
        return "NUMBER(38,4)"
    if n.endswith("id") or n.endswith("_key") or n in ("id", "key"):
        return "VARCHAR(100)"
    if any(k in n for k in ("flag", "is_", "has_")):
        return "BOOLEAN"
    return "VARCHAR(16777216)"
