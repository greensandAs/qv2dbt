"""OpenLineage event generator.

Converts the internal :class:`Lineage` graph into a list of OpenLineage
``RunEvent`` dicts (one COMPLETE event per table).  The output conforms to
the OpenLineage spec v2-0-2 and can be ingested by Marquez, Atlan, DataHub,
or Snowflake Horizon.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from ..lineage import Lineage
from ..models import QvScript

_SCHEMA_URL = (
    "https://openlineage.io/spec/2-0-2/OpenLineage.json"
    "#/$defs/RunEvent"
)
_COL_LINEAGE_SCHEMA = (
    "https://openlineage.io/spec/facets/1-1-0/ColumnLineageDatasetFacet.json"
    "#/$defs/ColumnLineageDatasetFacet"
)
_PRODUCER = "https://github.com/qv2dbt"

_MAPPING_TYPE_TO_OL = {
    "direct": "DIRECT",
    "derived": "INDIRECT",
    "aggregate": "INDIRECT",
    "lookup": "INDIRECT",
    "constant": "INDIRECT",
    "join": "INDIRECT",
}


def _namespace_for_source(meta: dict) -> str:
    locator = meta.get("locator", "")
    kind = meta.get("kind", "")
    if "://" in locator:
        prefix = locator.split("://")[0]
        return f"qvd://{prefix}"
    if kind == "sql":
        return "db://source"
    return f"file://{kind}"


def _target_namespace(config: dict) -> str:
    db = config.get("target", {}).get("database", "SNOWFLAKE")
    return f"snowflake://{db}"


def _build_column_lineage_facet(
    table_name: str, lin: Lineage, target_ns: str
) -> dict[str, Any] | None:
    cols = lin.for_table(table_name)
    if not cols:
        return None
    fields: dict[str, Any] = {}
    for cm in cols:
        input_fields = []
        for dep in cm.direct_deps:
            if dep.external:
                src_key = dep.upstream
                src_meta = lin.sources.get(src_key, {})
                ns = _namespace_for_source(src_meta)
                ds_name = src_key.replace("source:", "")
            else:
                ns = target_ns
                ds_name = dep.upstream
            input_fields.append({
                "namespace": ns,
                "name": ds_name,
                "field": dep.column,
            })
        fields[cm.column] = {
            "inputFields": input_fields,
            "transformationDescription": cm.snowflake_sql or cm.qlik_expr,
            "transformationType": _MAPPING_TYPE_TO_OL.get(
                cm.mapping_type, "INDIRECT"
            ),
        }
    return {
        "_producer": _PRODUCER,
        "_schemaURL": _COL_LINEAGE_SCHEMA,
        "fields": fields,
    }


def build_events(
    script: QvScript, lin: Lineage, config: dict
) -> list[dict[str, Any]]:
    """Return one OpenLineage RunEvent per table in the script."""
    target_ns = _target_namespace(config)
    now = datetime.now(timezone.utc).isoformat()
    run_id = str(uuid.uuid4())
    events: list[dict[str, Any]] = []

    for table_name, meta in lin.tables.items():
        # Collect input datasets (upstream nodes for this table).
        inputs: list[dict[str, Any]] = []
        seen_inputs: set[str] = set()
        for upstream, downstream in lin.table_edges:
            if downstream != table_name:
                continue
            if upstream in seen_inputs:
                continue
            seen_inputs.add(upstream)

            if upstream in lin.sources:
                src_meta = lin.sources[upstream]
                ns = _namespace_for_source(src_meta)
                ds_name = upstream.replace("source:", "")
            else:
                ns = target_ns
                ds_name = upstream
            inputs.append({"namespace": ns, "name": ds_name})

        # Build output dataset with columnLineage facet.
        col_facet = _build_column_lineage_facet(table_name, lin, target_ns)
        output_facets: dict[str, Any] = {}
        if col_facet:
            output_facets["columnLineage"] = col_facet

        output = {
            "namespace": target_ns,
            "name": table_name,
            "facets": output_facets,
        }

        events.append({
            "eventType": "COMPLETE",
            "eventTime": now,
            "producer": _PRODUCER,
            "schemaURL": _SCHEMA_URL,
            "run": {"runId": run_id},
            "job": {
                "namespace": f"qv2dbt:{script.name}",
                "name": table_name,
                "facets": {
                    "jobType": {
                        "_producer": _PRODUCER,
                        "_schemaURL": (
                            "https://openlineage.io/spec/facets/2-0-2/"
                            "JobTypeJobFacet.json#/$defs/JobTypeJobFacet"
                        ),
                        "processingType": "BATCH",
                        "integration": "qv2dbt",
                        "jobType": "TASK",
                    }
                },
            },
            "inputs": inputs,
            "outputs": [output],
        })

    return events


def write_events(
    script: QvScript, lin: Lineage, config: dict, path: str
) -> list[dict[str, Any]]:
    events = build_events(script, lin, config)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(events, fh, indent=2)
    return events
