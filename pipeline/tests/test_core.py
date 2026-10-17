import duckdb
import pytest

from nces_pipeline import schema
from nces_pipeline.ccd_build import FLAG_SQL, col_expr, num_value
from nces_pipeline.ccd_topics import TOPICS, bootstrap
from nces_pipeline.config import State
from nces_pipeline.parquet import write_parquet
from nces_pipeline.rawio import ensure_utf8, header_of
from nces_pipeline.stage import state_filter

STATE = State("Testland", "TL", "99", (0, 0, 1, 1), (0, 0), 5, "T")


def test_schema_drift_lists_new_and_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(schema, "SCHEMAS", tmp_path)
    d = tmp_path / "ccd" / "t"
    d.mkdir(parents=True)
    (d / "2020.yml").write_text(
        "source: ccd\ntopic: t\nyear: 2020\ncolumns:\n  A: {name: a}\n  B: {name: b}\n  Z: {ignore: true, reason: x}\n"
    )
    monkeypatch.setattr(schema, "map_path", lambda s, t, y: tmp_path / s / t / f"{y}.yml")
    cm = schema.load_map("ccd", "t", 2020)
    schema.check_header(cm, ["A", "B", "Z"])  # ok
    with pytest.raises(schema.SchemaDrift) as e:
        schema.check_header(cm, ["A", "Bb", "Z", "NEW"])
    msg = str(e.value)
    assert "NEW" in msg and "Bb" in msg and "MISSING" in msg


def test_ignore_requires_reason(tmp_path, monkeypatch):
    p = tmp_path / "2020.yml"
    p.write_text("source: ccd\ntopic: t\nyear: 2020\ncolumns:\n  A: {ignore: true}\n")
    monkeypatch.setattr(schema, "map_path", lambda s, t, y: p)
    with pytest.raises(schema.SchemaDrift):
        schema.load_map("ccd", "t", 2020)


def test_sentinels_become_null_with_flags():
    con = duckdb.connect()
    rows = {"12": ("12", "reported"), "0": ("0", "reported"), "-1": (None, "missing"), "-2": (None, "not_applicable"),
            "-3": (None, "suppressed"), "-9": (None, "not_meeting_standards"), "M": (None, "missing"),
            "N": (None, "not_applicable"), "x": (None, "unknown_other"), "12.00": ("12", "reported")}
    for raw, (val, flag) in rows.items():
        s = f"'{raw}'"
        v, f = con.execute(f"SELECT {num_value(s, 'INTEGER')}, {FLAG_SQL.format(s=s)}").fetchone()
        assert (None if v is None else str(v)) == val, raw
        assert f == flag, raw
    v, f = con.execute(f"SELECT {num_value('NULL', 'INTEGER')}, {FLAG_SQL.format(s='NULL')}").fetchone()
    assert v is None and f is None


def test_signed_columns_keep_negative_values():
    con = duckdb.connect()
    con.execute("CREATE TABLE r(\"LON\" VARCHAR)")
    con.execute("INSERT INTO r VALUES ('-111.5')")
    expr = col_expr("LON", {"name": "lon", "type": "DOUBLE", "signed": True})
    assert con.execute(f"SELECT {expr} FROM r").fetchone()[0] == -111.5


def test_ids_keep_leading_zeros():
    con = duckdb.connect()
    con.execute('CREATE TABLE r("NCESSCH" VARCHAR)')
    con.execute("INSERT INTO r VALUES ('10000500870 ')")
    expr = col_expr("NCESSCH", {"name": "ncessch", "type": "VARCHAR"})
    assert con.execute(f"SELECT {expr} FROM r").fetchone()[0] == "010000500870"


def test_state_filter_prefers_fips_and_pads():
    sql = state_filter(["FIPST", "ST", "X"], STATE)
    assert "'99'" in sql and "lpad" in sql
    assert "'TL'" in state_filter(["ST"], STATE)
    with pytest.raises(SystemExit):
        state_filter(["NOPE"], STATE)


def test_parquet_is_deterministic(tmp_path):
    con = duckdb.connect()
    con.execute("CREATE TABLE t AS SELECT range AS a, md5(range::varchar) AS b FROM range(5000)")
    p = tmp_path / "x.parquet"
    write_parquet(con, "SELECT * FROM t", p, ["a"])
    first = p.read_bytes()
    con2 = duckdb.connect()
    con2.execute("CREATE TABLE t AS SELECT range AS a, md5(range::varchar) AS b FROM range(4999, -1, -1)")
    write_parquet(con2, "SELECT * FROM t", p, ["a"])
    assert p.read_bytes() == first


def test_wide_membership_bootstrap_unpivots_every_count_column():
    cols = ["NCESSCH", "LEAID", "PK", "G01", "TOTAL", "MEMBER", "AMPKM", "WHKGF", "AM", "AMALM", "ISMEMPUP"]
    cm, unp = bootstrap(TOPICS["membership"], 2014, cols)
    assert not [c for c, s in cm.items() if s.get("todo")]
    by = {u["source"]: u for u in unp}
    assert by["AMPKM"]["race"] == "American Indian or Alaska Native" and by["AMPKM"]["sex"] == "Male"
    assert by["WHKGF"]["grade"] == "Kindergarten"
    assert by["MEMBER"]["total_indicator"] == "Education Unit Total"
    assert cm["ISMEMPUP"]["ignore"] and cm["ISMEMPUP"]["reason"]


def test_ensure_utf8_transcodes_cp1252(tmp_path):
    p = tmp_path / "a.csv"
    p.write_bytes("A,B\n1,’x\n".encode("cp1252"))
    out = ensure_utf8(p)
    assert out != p and "’x" in out.read_text(encoding="utf-8")
    assert header_of(p) == ["A", "B"]
    q = tmp_path / "b.csv"
    q.write_text("A,B\n1,’x\n", encoding="utf-8")
    assert ensure_utf8(q) == q
