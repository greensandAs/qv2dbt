import os

import pytest

from qv2dbt.control import find_control_blocks
from qv2dbt.preprocessor import strip_comments
from qv2dbt.pipeline import run_migration

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STRESS = os.path.join(ROOT, "samples", "stress_test.qvs")


def test_control_blocks_detected():
    cbs = find_control_blocks(strip_comments(open(STRESS).read()))
    kinds = sorted(b.kind for b in cbs)
    assert kinds == ["call", "for", "if", "sub"]
    sub = next(b for b in cbs if b.kind == "sub")
    assert "END SUB" in sub.body.upper()
    assert sub.guidance


@pytest.fixture(scope="module")
def result(tmp_path_factory):
    return run_migration(STRESS, str(tmp_path_factory.mktemp("out")))


def test_sql_views_generated(result):
    assert os.path.exists(result["sql_views_combined"])
    sql = open(result["sql_views_combined"], encoding="utf-8").read()
    assert "create or replace view" in sql
    # physical refs, no dbt jinja / macros
    assert "{{" not in sql and "}}" not in sql
    assert "LUNDBECK_UKIE." in sql


def test_apply_map_inlined_in_views(result):
    view = os.path.join(result["sql_views_dir"], "views", "stg_customers.sql")
    sql = open(view, encoding="utf-8").read()
    assert "coalesce((select" in sql.lower()
    assert "MAP_COUNTRY_MAP" in sql


def test_control_stubs_written(result):
    assert result["control_blocks"] == 4
    stubs = open(result["control_stubs"], encoding="utf-8").read()
    assert "Manual Conversion Stubs" in stubs
    assert "```qlik" in stubs


def test_mart_view_has_aggregation(result):
    view = os.path.join(result["sql_views_dir"], "views", "mart_sales_fact.sql")
    sql = open(view, encoding="utf-8").read()
    assert "group by" in sql.lower()
    assert "MEDIAN(" in sql.upper()  # from expanded function map
