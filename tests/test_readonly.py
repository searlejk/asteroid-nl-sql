"""Prove generated SQL cannot modify the database.   python3 tests/test_readonly.py"""
import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db  # noqa: E402

ATTACKS = [
    "DELETE FROM asteroids",
    "DROP TABLE asteroids",
    "UPDATE asteroids SET name = 'x' WHERE spkid = 20000001",
    "INSERT INTO orbit_classes VALUES ('ZZZ', 'x', 'y')",
    "CREATE TABLE t (x)",
    "PRAGMA query_only = OFF",
    "ATTACH DATABASE '/tmp/x.db' AS x",
    "VACUUM",
    "SELECT 1; DELETE FROM asteroids",
    "WITH x AS (SELECT 1) DELETE FROM asteroids",
    "/* sneaky */ DELETE FROM asteroids",
    "SELECT load_extension('evil')",
    "REPLACE INTO dataset_info VALUES ('k', 'v')",
]


def digest():
    with open(db.DB_PATH, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def main():
    before = digest()
    failures = 0
    for sql in ATTACKS:
        try:
            db.run_query(sql)
            print(f"FAIL (ran!)  {sql}")
            failures += 1
        except Exception as e:
            print(f"blocked      {sql:<55} -> {type(e).__name__}: {str(e)[:60]}")
    ok = db.run_query("SELECT COUNT(*) FROM asteroids WHERE is_neo = 1")
    print(f"\nnormal SELECT still works: {ok['rows'][0][0]:,} near-Earth asteroids")
    cte = db.run_query("WITH RECURSIVE n(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM n WHERE x < 5) SELECT SUM(x) FROM n")
    print(f"recursive CTE still works: {cte['rows'][0][0]}")
    try:
        db.run_query("WITH RECURSIVE n(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM n) SELECT MAX(x) FROM n", timeout_s=1)
        print("FAIL runaway query was not stopped"); failures += 1
    except db.QueryRejected as e:
        print(f"runaway query stopped:     {e}")
    assert digest() == before, "database file changed!"
    print("database file unchanged (sha256 identical)")
    print("ALL PASSED" if not failures else f"{failures} FAILURES")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
