"""Generate a complete, runnable dbt project around the generated models.

Writes: dbt_project.yml, packages.yml, a profiles.yml template, sources.yml,
per-layer schema.yml, the apply_map macro, mapping-table models, and every
model SQL file placed under models/<layer>/.
"""
from __future__ import annotations

import os

from ..models import LoadKind, QvScript
from ..utils import snake
from .dbt_models import ModelFile


def _write(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)


def generate(script: QvScript, models: list[ModelFile], config: dict,
             out_dir: str) -> list[str]:
    tgt = config["target"]
    naming = config["naming"]
    project = "lundbeck_qv_migration"
    written: list[str] = []

    def emit(rel: str, content: str) -> None:
        p = os.path.join(out_dir, rel)
        _write(p, content)
        written.append(p)

    # -- dbt_project.yml ------------------------------------------------------
    emit("dbt_project.yml", f"""\
name: '{project}'
version: '1.0.0'
config-version: 2
profile: '{project}'

model-paths: ["models"]
macro-paths: ["macros"]
seed-paths: ["seeds"]

models:
  {project}:
    staging:
      +materialized: view
      +schema: {tgt['staging_schema'].lower()}
    intermediate:
      +materialized: view
      +schema: {tgt['staging_schema'].lower()}
    marts:
      +materialized: table
      +schema: {tgt['mart_schema'].lower()}
""")

    # -- packages.yml ---------------------------------------------------------
    emit("packages.yml", "packages:\n"
                         "  - package: dbt-labs/dbt_utils\n"
                         "    version: [\">=1.0.0\", \"<2.0.0\"]\n")

    # -- profiles template ----------------------------------------------------
    emit("profiles.template.yml", f"""\
# Copy to ~/.dbt/profiles.yml and fill in credentials.
{project}:
  target: dev
  outputs:
    dev:
      type: snowflake
      account: "<your_account>"
      user: "<your_user>"
      authenticator: externalbrowser
      role: "<your_role>"
      database: {tgt['database']}
      warehouse: "<your_wh>"
      schema: {tgt['staging_schema'].lower()}
      threads: 4
""")

    # -- apply_map macro ------------------------------------------------------
    emit("macros/apply_map.sql", """\
{# Resolves a QlikView ApplyMap() against a generated mapping model.
   Usage (emitted by the accelerator):
     {{ apply_map('MapName', "<key_sql>", "<default_sql>") }}
#}
{% macro apply_map(map_name, key_sql, default_sql='null') %}
    coalesce(
        (
            select mapped_value
            from {{ ref('map_' ~ map_name | lower) }}
            where mapped_key = {{ key_sql }}
            limit 1
        ),
        {{ default_sql }}
    )
{% endmacro %}
""")

    # -- sources.yml ----------------------------------------------------------
    src_lines = ["version: 2", "", "sources:",
                 f"  - name: {naming['source_name']}",
                 f"    database: {tgt['database']}",
                 f"    schema: {tgt['raw_schema'].lower()}",
                 "    description: >",
                 "      Raw QlikView-sourced tables (QVD/file/SQL extracts) "
                 "landed in Snowflake.",
                 "    tables:"]
    if script.sources:
        for s in script.sources:
            src_lines.append(f"      - name: {s.identifier}")
            src_lines.append(f"        description: 'Origin: {s.locator}'")
    else:
        src_lines.append("      []")
    emit("models/staging/_sources.yml", "\n".join(src_lines) + "\n")

    # -- mapping-table models -------------------------------------------------
    for m in script.maps:
        model_name = f"map_{snake(m.name)}"
        if m.source:
            frm = f"{{{{ ref('{_guess_ref(script, m.source)}') }}}}"
        else:
            frm = "-- TODO: source of mapping table"
        emit(f"models/staging/{model_name}.sql", f"""\
-- Mapping table migrated from QlikView MAPPING LOAD '{m.name}'.
-- Used by the apply_map() macro to resolve ApplyMap() calls.
{{{{ config(materialized='table') }}}}

select
    {m.key_expr or 'key'} as mapped_key,
    {m.value_expr or 'value'} as mapped_value
from {frm}
""")

    # -- model files by layer -------------------------------------------------
    layer_dir = {"staging": "staging", "intermediate": "intermediate",
                 "mart": "marts"}
    per_layer: dict[str, list[ModelFile]] = {"staging": [], "intermediate": [],
                                             "mart": []}
    for mf in models:
        d = layer_dir.get(mf.layer, "intermediate")
        emit(f"models/{d}/{mf.name}.sql", mf.sql)
        per_layer.setdefault(mf.layer, []).append(mf)

    # -- schema.yml per layer -------------------------------------------------
    for layer, dirname in layer_dir.items():
        mfs = per_layer.get(layer) or []
        if not mfs:
            continue
        lines = ["version: 2", "", "models:"]
        for mf in mfs:
            lines.append(f"  - name: {mf.name}")
            if mf.warnings:
                lines.append("    description: >")
                lines.append("      AUTO-MIGRATED. Review notes: "
                             + "; ".join(w.replace(':', '-') for w in mf.warnings[:5]))
            else:
                lines.append("    description: 'Auto-migrated from QlikView.'")
            if mf.columns:
                lines.append("    columns:")
                for c in mf.columns:
                    lines.append(f"      - name: {c}")
        emit(f"models/{dirname}/_{dirname}__models.yml", "\n".join(lines) + "\n")

    # -- README for the generated project ------------------------------------
    emit("README.md", f"""\
# {project}

dbt project auto-generated by the **qv2dbt accelerator** from
`{script.name}`.

## Layout
- `models/staging/` - one model per QlikView source LOAD (+ mapping tables)
- `models/intermediate/` - RESIDENT / JOIN-built tables
- `models/marts/` - final fact/dim/report tables
- `macros/apply_map.sql` - resolves QlikView `ApplyMap()`

## Getting started
1. Run the RAW landing DDL (`snowflake_raw_ddl.sql`) in Snowflake.
2. Load QVD/file extracts into the RAW tables.
3. `cp profiles.template.yml ~/.dbt/profiles.yml` and add credentials.
4. `dbt deps && dbt build`.

> Every model header lists `WARNING:` lines for constructs that need a human
> review. Search the project for `TODO review` before go-live.
""")

    return written


def _guess_ref(script: QvScript, name: str) -> str:
    from ..utils import snake as _s
    t = script.table_by_name(name)
    if t:
        prefix = {"staging": "stg_", "intermediate": "int_",
                  "mart": "mart_"}.get(t.layer, "")
        return f"{prefix}{_s(t.name)}"
    return _s(name)
