"""Command-line entrypoint for the qv2dbt accelerator.

Usage:
    python -m qv2dbt <script.qvs> [-o OUTPUT_DIR] [-c config_overrides.yml]
"""
from __future__ import annotations

import argparse
import os
import sys

from .pipeline import run_migration


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="qv2dbt",
        description="Migrate a QlikView load script (.qvs) to Snowflake DDL, "
                    "a dbt project, and a migration report.")
    ap.add_argument("qvs", help="Path to a QlikView .qvs script OR a binary "
                                "Qlik app (.qvf/.qvw); the script is extracted "
                                "automatically from binary apps.")
    ap.add_argument("-o", "--out", default="./qv2dbt_output",
                    help="Output directory (default: ./qv2dbt_output)")
    ap.add_argument("-c", "--config", default=None,
                    help="Optional YAML config overrides")
    args = ap.parse_args(argv)

    result = run_migration(args.qvs, args.out, args.config)
    s = result["summary"]
    print(f"\n  qv2dbt - migrated '{result['script']}'")
    if result.get("extracted_script"):
        print(f"  (script extracted from binary Qlik app)")
    print(f"  {'-'*52}")
    print(f"  QlikView tables .......... {s['tables']}")
    print(f"  dbt models generated ..... {s['models_generated']}")
    print(f"  Mapping tables ........... {s['mapping_tables']}")
    print(f"  External sources ......... {s['external_sources']}")
    print(f"  Auto-translatable ........ {s['auto_translatable_pct']}%")
    print(f"  Fields needing review .... {s['fields_needing_review']}")
    print(f"  {'-'*52}")
    print(f"  Snowflake DDL: {result['snowflake_ddl']}")
    print(f"  dbt project:   {result['dbt_project']}")
    print(f"  Report (md):   {result['report_md']}")
    print(f"  Report (json): {result['report_json']}")
    print(f"  STTM (xlsx):   {result['sttm_xlsx']}")
    print(f"  STTM (yaml):   {result['sttm_yaml']}")
    print(f"  Lineage (html):{result['lineage_html']}")
    print(f"  Lineage (json/mmd/md): {os.path.dirname(result['lineage_json'])}")
    print(f"  SQL views:     {result['sql_views_combined']}")
    print(f"  Control stubs: {result['control_stubs']} "
          f"({result['control_blocks']} block(s))\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
