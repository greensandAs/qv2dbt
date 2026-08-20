import os

import pytest

from qv2dbt.config import load_config
from qv2dbt.parser import parse_fields, parse_script
from qv2dbt.transformer import Transformer

SAMPLE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "samples", "sales_pipeline.qvs")


@pytest.fixture(scope="module")
def script():
    with open(SAMPLE, encoding="utf-8") as fh:
        s = parse_script(fh.read(), "sales_pipeline.qvs")
    # Layer refinement (mart pattern matching) happens in the transformer.
    Transformer(load_config()).run(s)
    return s


def test_parse_fields_alias():
    fields = parse_fields("ProductID, Num(UnitPrice) as UnitPrice")
    assert fields[0].alias == "ProductID"
    assert fields[0].is_passthrough
    assert fields[1].alias == "UnitPrice"
    assert not fields[1].is_passthrough


def test_tables_detected(script):
    names = {t.name for t in script.tables}
    assert {"Products", "SalesRaw", "SalesEnriched", "sales_fact"} <= names


def test_mapping_detected(script):
    assert any(m.name == "CountryMap" for m in script.maps)


def test_source_detected(script):
    idents = {s.identifier for s in script.sources}
    assert any("products" in i for i in idents)


def test_layers(script):
    products = script.table_by_name("Products")
    fact = script.table_by_name("sales_fact")
    assert products.layer == "staging"
    assert fact.layer == "mart"


def test_join_recorded(script):
    enriched = script.table_by_name("SalesEnriched")
    assert enriched.joins, "LEFT JOIN onto SalesEnriched should be recorded"


def test_dropped_table(script):
    assert "SalesPY" in script.dropped_tables
