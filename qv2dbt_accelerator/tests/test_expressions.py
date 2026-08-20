import pytest

from qv2dbt.config import load_config
from qv2dbt.expressions import ExpressionTranslator


@pytest.fixture(scope="module")
def tr():
    return ExpressionTranslator(load_config())


def test_if_to_case(tr):
    out, _ = tr.translate("if(Discontinued = 1, 'Y', 'N')")
    assert out == "CASE WHEN Discontinued = 1 THEN 'Y' ELSE 'N' END"


def test_concat_operator(tr):
    out, _ = tr.translate("FirstName & ' ' & LastName")
    assert "||" in out and "&" not in out


def test_nested_functions(tr):
    out, _ = tr.translate("Num(UnitPrice) * Num(Quantity)")
    assert out == "TO_NUMBER(UnitPrice) * TO_NUMBER(Quantity)"


def test_date_with_format(tr):
    out, _ = tr.translate("Date(OrderDate, 'YYYY-MM-DD')")
    assert out == "TO_DATE(OrderDate, 'YYYY-MM-DD')"


def test_bracket_identifier(tr):
    out, _ = tr.translate("[Therapeutic Area]")
    assert out == '"Therapeutic Area"'


def test_applymap_becomes_macro(tr):
    out, warns = tr.translate("ApplyMap('CountryMap', CountryCode, 'Unknown')")
    assert "apply_map('CountryMap'" in out
    assert any("ApplyMap" in w for w in warns)


def test_unknown_function_flagged(tr):
    out, warns = tr.translate("Peek('X', -1)")
    assert "TODO review" in out
    assert warns
