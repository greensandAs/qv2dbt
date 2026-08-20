"""Stage 4: enrich the parsed IR with translated Snowflake SQL.

Runs the expression translator over every field, WHERE and GROUP BY, and
finalises each table's dbt layer (marts are chosen by name pattern from the
config). After this pass the IR carries everything the generators need.
"""
from __future__ import annotations

import fnmatch

from .expressions import ExpressionTranslator
from .models import QvScript


class Transformer:
    def __init__(self, config: dict):
        self.config = config
        self.translator = ExpressionTranslator(config)
        self.mart_patterns = (
            (config.get("layers") or {}).get("mart_name_patterns") or []
        )

    def run(self, script: QvScript) -> QvScript:
        for table in script.tables:
            for f in table.fields:
                f.sf_expr, warns = self.translator.translate(f.source_expr)
                f.warnings.extend(warns)
            if table.where_raw:
                table.where_sf, warns = self.translator.translate(table.where_raw)
                table.warnings.extend(warns)
            self._finalise_layer(table)
        return script

    def _finalise_layer(self, table) -> None:
        name = table.name.lower()
        for pat in self.mart_patterns:
            if fnmatch.fnmatch(name, pat.lower()):
                table.layer = "mart"
                return
