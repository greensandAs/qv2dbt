import os

import pytest

from qv2dbt.config import load_config
from qv2dbt.lineage import build_lineage, extract_columns
from qv2dbt.parser import parse_script
from qv2dbt.pipeline import run_migration
from qv2dbt.transformer import Transformer

SAMPLE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "samples", "sales_pipeline.qvs")


@pytest.fixture(scope="module")
def lineage():
    with open(SAMPLE, encoding="utf-8") as fh:
        s = parse_script(fh.read(), "sales_pipeline.qvs")
    Transformer(load_config()).run(s)
    return build_lineage(s)


def test_extract_columns_ignores_funcs_and_literals():
    cols = extract_columns("Num(UnitPrice) * Num(Quantity)")
    assert set(cols) == {"UnitPrice", "Quantity"}
    assert extract_columns("if(x=1,'Y','N')") == ["x"]


def test_column_traces_to_source(lineage):
    fact = {c.column: c for c in lineage.for_table("sales_fact")}
    rev = fact["TotalRevenue"]
    assert rev.mapping_type == "aggregate"
    srcs = {f"{a}.{b}" for a, b in rev.ultimate_sources}
    assert "sales_2026.UnitPrice" in srcs and "sales_2026.Quantity" in srcs


def test_join_column_traces_through_join(lineage):
    fact = {c.column: c for c in lineage.for_table("sales_fact")}
    ta = fact["TherapeuticArea"]
    assert any(a == "products" for a, _ in ta.ultimate_sources)


def test_lookup_classified(lineage):
    raw = {c.column: c for c in lineage.for_table("SalesRaw")}
    assert raw["Country"].mapping_type == "lookup"


def test_pipeline_emits_sttm_and_lineage(tmp_path):
    res = run_migration(SAMPLE, str(tmp_path))
    for key in ("sttm_xlsx", "sttm_yaml", "lineage_json", "lineage_mermaid",
                "lineage_md", "lineage_html"):
        assert os.path.exists(res[key]), key
    # xlsx has the expected sheets
    import openpyxl
    wb = openpyxl.load_workbook(res["sttm_xlsx"])
    assert {"Target Inventory", "Source Inventory", "STTM"} <= set(wb.sheetnames)
    # html is self-contained (embeds the data + no external script src)
    html = open(res["lineage_html"], encoding="utf-8").read()
    assert "const DATA =" in html and "<script src=" not in html
