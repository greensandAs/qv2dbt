import json
import os

import pytest

from qv2dbt.config import load_config
from qv2dbt.generators.openlineage import build_events
from qv2dbt.lineage import build_lineage
from qv2dbt.parser import parse_script
from qv2dbt.pipeline import run_migration
from qv2dbt.transformer import Transformer

SAMPLE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "samples", "sales_pipeline.qvs")


@pytest.fixture(scope="module")
def ol_events():
    with open(SAMPLE, encoding="utf-8") as fh:
        s = parse_script(fh.read(), "sales_pipeline.qvs")
    cfg = load_config()
    Transformer(cfg).run(s)
    lin = build_lineage(s)
    return build_events(s, lin, cfg)


def test_events_are_list(ol_events):
    assert isinstance(ol_events, list)
    assert len(ol_events) > 0


def test_event_structure(ol_events):
    for ev in ol_events:
        assert ev["eventType"] == "COMPLETE"
        assert ev["schemaURL"].startswith("https://openlineage.io/spec/")
        assert "run" in ev and "runId" in ev["run"]
        assert "job" in ev and "namespace" in ev["job"] and "name" in ev["job"]
        assert "inputs" in ev and isinstance(ev["inputs"], list)
        assert "outputs" in ev and isinstance(ev["outputs"], list)
        assert len(ev["outputs"]) == 1


def test_job_namespace_contains_script(ol_events):
    for ev in ol_events:
        assert "sales_pipeline.qvs" in ev["job"]["namespace"]


def test_inputs_have_namespace_and_name(ol_events):
    for ev in ol_events:
        for inp in ev["inputs"]:
            assert "namespace" in inp
            assert "name" in inp
            assert inp["name"] != ""


def test_column_lineage_facet_present_on_tables(ol_events):
    facet_found = False
    for ev in ol_events:
        out = ev["outputs"][0]
        if "columnLineage" in out.get("facets", {}):
            facet_found = True
            cl = out["facets"]["columnLineage"]
            assert "fields" in cl
            assert cl["_schemaURL"].startswith("https://openlineage.io/spec/")
            for col_name, col_info in cl["fields"].items():
                assert "inputFields" in col_info
                assert "transformationType" in col_info
                assert col_info["transformationType"] in ("DIRECT", "INDIRECT")
    assert facet_found, "No columnLineage facet found in any event"


def test_mart_has_column_lineage(ol_events):
    mart_events = [e for e in ol_events if "fact" in e["job"]["name"].lower()
                   or "mart" in e["job"]["name"].lower()]
    assert len(mart_events) > 0
    for ev in mart_events:
        cl = ev["outputs"][0]["facets"].get("columnLineage")
        assert cl is not None, f"Mart {ev['job']['name']} has no columnLineage"
        assert len(cl["fields"]) > 0


def test_pipeline_emits_openlineage(tmp_path):
    res = run_migration(SAMPLE, str(tmp_path))
    assert "openlineage_json" in res
    assert os.path.exists(res["openlineage_json"])
    with open(res["openlineage_json"]) as fh:
        data = json.load(fh)
    assert isinstance(data, list)
    assert len(data) > 0
