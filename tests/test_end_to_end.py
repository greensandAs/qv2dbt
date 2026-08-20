import json
import os

import pytest

from qv2dbt.pipeline import run_migration

SAMPLE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "samples", "sales_pipeline.qvs")


@pytest.fixture(scope="module")
def result(tmp_path_factory):
    out = tmp_path_factory.mktemp("out")
    return run_migration(SAMPLE, str(out)), str(out)


def test_artifacts_written(result):
    res, out = result
    assert os.path.exists(res["snowflake_ddl"])
    assert os.path.exists(res["report_md"])
    assert os.path.exists(os.path.join(res["dbt_project"], "dbt_project.yml"))
    assert os.path.exists(os.path.join(res["dbt_project"], "macros",
                                       "apply_map.sql"))


def test_models_generated(result):
    res, out = result
    staging = os.path.join(res["dbt_project"], "models", "staging")
    marts = os.path.join(res["dbt_project"], "models", "marts")
    assert any(f.endswith(".sql") for f in os.listdir(staging))
    assert "mart_sales_fact.sql" in os.listdir(marts)


def test_ddl_has_create_table(result):
    res, out = result
    with open(res["snowflake_ddl"], encoding="utf-8") as fh:
        ddl = fh.read()
    assert "CREATE TABLE IF NOT EXISTS" in ddl


def test_mart_model_uses_group_by(result):
    res, out = result
    p = os.path.join(res["dbt_project"], "models", "marts", "mart_sales_fact.sql")
    with open(p, encoding="utf-8") as fh:
        sql = fh.read()
    assert "group by" in sql.lower()
    assert "SUM(" in sql.upper()


def test_report_summary(result):
    res, out = result
    with open(res["report_json"], encoding="utf-8") as fh:
        data = json.load(fh)
    assert data["summary"]["tables"] >= 4
    assert 0 <= data["summary"]["auto_translatable_pct"] <= 100
