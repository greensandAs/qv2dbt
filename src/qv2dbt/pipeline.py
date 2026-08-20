"""End-to-end orchestration: .qvs in -> Snowflake DDL + dbt project + report."""
from __future__ import annotations

import json
import os

from .config import load_config
from .generators import (
    control_stubs,
    dbt_models,
    dbt_scaffold,
    lineage_out,
    report,
    snowflake_ddl,
    sql_views,
    sttm,
)
from .lineage import build_lineage
from .parser import parse_script
from .qvf_extractor import extract_script, is_binary_qlik
from .transformer import Transformer


def run_migration(qvs_path: str, out_dir: str,
                  config_override: str | None = None) -> dict:
    config = load_config(config_override)
    script_name = os.path.basename(qvs_path)
    extracted_path = None

    # Accept binary Qlik apps (.qvf/.qvw) directly: pull out the load script.
    if is_binary_qlik(qvs_path):
        text = extract_script(qvs_path)
        os.makedirs(out_dir, exist_ok=True)
        base = os.path.splitext(script_name)[0]
        extracted_path = os.path.join(out_dir, base + "_extracted.qvs")
        with open(extracted_path, "w", encoding="utf-8") as fh:
            fh.write(text)
        script_name = base + ".qvs"
    else:
        with open(qvs_path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()

    # Stages 1-4: parse then translate.
    script = parse_script(text, script_name)
    Transformer(config).run(script)

    # Generators.
    models = dbt_models.DbtModelGenerator(config).generate(script)

    os.makedirs(out_dir, exist_ok=True)
    dbt_dir = os.path.join(out_dir, "dbt_project")

    ddl = snowflake_ddl.generate(script, config)
    ddl_path = os.path.join(out_dir, "snowflake_raw_ddl.sql")
    with open(ddl_path, "w", encoding="utf-8") as fh:
        fh.write(ddl)
    # Copy DDL into the dbt project too, for convenience.
    os.makedirs(dbt_dir, exist_ok=True)
    with open(os.path.join(dbt_dir, "snowflake_raw_ddl.sql"), "w",
              encoding="utf-8") as fh:
        fh.write(ddl)

    scaffold_files = dbt_scaffold.generate(script, models, config, dbt_dir)

    md, data = report.build(script, models, config)
    report_md = os.path.join(out_dir, "migration_report.md")
    report_json = os.path.join(out_dir, "migration_report.json")
    with open(report_md, "w", encoding="utf-8") as fh:
        fh.write(md)
    with open(report_json, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)

    # Source-to-Target Mapping + lineage.
    lineage = build_lineage(script)
    sttm_dir = os.path.join(out_dir, "sttm_and_lineage")
    os.makedirs(sttm_dir, exist_ok=True)
    sttm_xlsx = os.path.join(sttm_dir, "STTM.xlsx")
    sttm_yaml = os.path.join(sttm_dir, "STTM.yaml")
    sttm.generate(script, lineage, sttm_xlsx, sttm_yaml)
    lineage_paths = {
        "json": os.path.join(sttm_dir, "lineage.json"),
        "mmd": os.path.join(sttm_dir, "lineage.mmd"),
        "md": os.path.join(sttm_dir, "lineage.md"),
        "html": os.path.join(sttm_dir, "lineage_explorer.html"),
    }
    lineage_out.generate(script, lineage, lineage_paths)

    # Plain Snowflake SQL views/selects per target (non-dbt path).
    sql_dir = os.path.join(out_dir, "sql_views")
    sql_info = sql_views.generate(script, config, sql_dir)

    # Manual-conversion stubs for control flow.
    stubs_path = os.path.join(out_dir, "manual_conversion_stubs.md")
    n_stubs = control_stubs.generate(script, stubs_path)

    return {
        "script": script_name,
        "extracted_script": extracted_path,
        "snowflake_ddl": ddl_path,
        "sql_views_dir": sql_dir,
        "sql_views_combined": sql_info["combined"],
        "control_stubs": stubs_path,
        "control_blocks": n_stubs,
        "sttm_xlsx": sttm_xlsx,
        "sttm_yaml": sttm_yaml,
        "lineage_json": lineage_paths["json"],
        "lineage_mermaid": lineage_paths["mmd"],
        "lineage_md": lineage_paths["md"],
        "lineage_html": lineage_paths["html"],
        "dbt_project": dbt_dir,
        "dbt_files": scaffold_files,
        "report_md": report_md,
        "report_json": report_json,
        "summary": data["summary"],
    }
