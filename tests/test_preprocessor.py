from qv2dbt.preprocessor import preprocess, split_statements, strip_comments


def test_strip_comments():
    txt = "LOAD a // inline\n, b /* block */ , c;\nREM note;\n"
    out = strip_comments(txt)
    assert "inline" not in out
    assert "block" not in out
    assert "REM" not in out


def test_split_ignores_semicolons_in_brackets():
    txt = "LOAD * INLINE [\na; b\nc; d\n];\nLOAD x FROM y.qvd;"
    stmts = split_statements(txt)
    assert len(stmts) == 2


def test_variable_capture_and_expansion():
    txt = "SET vPath = 'lib://x/';\nLOAD a FROM [$(vPath)f.qvd];"
    stmts, vars_ = preprocess(txt)
    assert vars_[0].name == "vPath"
    # $(vPath) expanded into the LOAD statement
    assert "lib://x/f.qvd" in stmts[1].raw
