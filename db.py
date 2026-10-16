"""Read-only access to data/asteroids.db.

Defense in depth, so a generated query can never change the data:
  1. the file is opened with SQLite's mode=ro (the OS-level handle is read-only)
  2. PRAGMA query_only = ON
  3. an authorizer that only allows SELECT / READ / FUNCTION / RECURSIVE actions
     (blocks INSERT, UPDATE, DELETE, DROP, CREATE, ATTACH, PRAGMA, ...)
  4. the statement must be a single SELECT or WITH query
plus a time limit and a row cap so a runaway query can't hang the server.
The database file itself is also chmod 444 by build_db.py.
"""
import os
import re
import sqlite3
import time

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "data", "asteroids.db")
SCHEMA_PATH = os.path.join(HERE, "schema.sql")

MAX_ROWS = 1000
TIMEOUT_S = 15

_ALLOWED_ACTIONS = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION,
                    getattr(sqlite3, "SQLITE_RECURSIVE", 33)}
_BLOCKED_FUNCTIONS = {"load_extension", "readfile", "writefile", "edit", "fts3_tokenizer"}


class QueryRejected(Exception):
    """The SQL was refused before or during execution (not read-only, too slow, ...)."""


def _authorizer(action, arg1, arg2, db_name, trigger):
    if action not in _ALLOWED_ACTIONS:
        return sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_FUNCTION and (arg2 or "").lower() in _BLOCKED_FUNCTIONS:
        return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK


def _strip_comments(sql):
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.S)
    return re.sub(r"--[^\n]*", " ", sql)


def check_read_only(sql):
    """Cheap first gate; the authorizer is the real enforcement."""
    body = _strip_comments(sql).strip().rstrip(";").strip()
    if not body:
        raise QueryRejected("Empty query.")
    first = body.split(None, 1)[0].upper()
    if first not in ("SELECT", "WITH"):
        raise QueryRejected(f"Only SELECT queries are allowed (got {first}).")
    return body


def connect(tables_read=None):
    """Read-only connection. If tables_read (a set) is given, every data table the query reads is added to it."""
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f"{DB_PATH} not found. Run: python3 build_db.py")
    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, check_same_thread=False)
    con.execute("PRAGMA query_only = ON")

    def auth(action, arg1, arg2, db_name, trigger):
        verdict = _authorizer(action, arg1, arg2, db_name, trigger)
        if (verdict == sqlite3.SQLITE_OK and action == sqlite3.SQLITE_READ and tables_read is not None
                and arg1 and not arg1.startswith("sqlite_")):
            tables_read.add(arg1)
        return verdict

    con.set_authorizer(auth)
    return con


def run_query(sql, max_rows=MAX_ROWS, timeout_s=TIMEOUT_S):
    """Run one read-only query. Returns dict(columns, rows, truncated, ms, tables).

    `tables` lists the data tables the query actually read. Empty means the answer did not come from the
    dataset at all (e.g. SELECT strftime(...) or SELECT 'some text'), which callers should refuse to present."""
    body = check_read_only(sql)
    tables = set()
    con = connect(tables)
    deadline = time.monotonic() + timeout_s
    con.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 10_000)
    t = time.monotonic()
    try:
        cur = con.execute(body)
        cols = [d[0] for d in cur.description or []]
        rows = cur.fetchmany(max_rows + 1)
    except sqlite3.DatabaseError as e:
        msg = str(e)
        if "interrupted" in msg:
            raise QueryRejected(f"Query took longer than {timeout_s}s and was stopped.") from e
        if "not authorized" in msg or "readonly" in msg:
            raise QueryRejected(f"Blocked: the database is read-only ({msg}).") from e
        raise
    finally:
        con.close()
    truncated = len(rows) > max_rows
    return {"columns": cols, "rows": [list(r) for r in rows[:max_rows]], "truncated": truncated,
            "ms": round((time.monotonic() - t) * 1000, 1), "tables": sorted(tables)}


def schema_sql():
    with open(SCHEMA_PATH) as f:
        return f.read().strip()


def sample_rows(n=3):
    """A few example rows per table, as CREATE-TABLE-plus-content prompts in the paper use."""
    con = connect()
    out = []
    try:
        for table, cols in [
            ("asteroids", "designation, name, full_name, is_neo, is_pha, orbit_class, diameter_est_km, moid_ld"),
            ("close_approaches", "designation, full_name, approach_time, dist_km, dist_ld, velocity_kms"),
            ("impact_risk", "designation, impact_probability, first_year, last_year, palermo_scale_cum, diameter_km"),
            ("orbit_classes", "code, name"),
        ]:
            where = {"asteroids": "WHERE name IN ('Eros','Apophis','Bennu')",
                     "close_approaches": "WHERE designation = '99942' ORDER BY dist_km",
                     "impact_risk": "ORDER BY palermo_scale_cum DESC",
                     "orbit_classes": ""}[table]
            cur = con.execute(f"SELECT {cols} FROM {table} {where} LIMIT {n}")
            names = [d[0] for d in cur.description]
            lines = [" | ".join(names)] + [" | ".join("NULL" if v is None else str(v) for v in r) for r in cur]
            out.append(f"/* {n} example rows from {table}:\n" + "\n".join(lines) + "\n*/")
    finally:
        con.close()
    return "\n".join(out)


def dataset_info():
    res = run_query("SELECT key, value FROM dataset_info")
    return {k: v for k, v in res["rows"]}
