"""Download NASA/JPL asteroid data and build data/asteroids.db (SQLite).

Sources (all public NASA/JPL Solar System Dynamics APIs, no key needed):
  - SBDB Query API   https://ssd-api.jpl.nasa.gov/sbdb_query.api  every known asteroid
  - Close Approach   https://ssd-api.jpl.nasa.gov/cad.api         Earth flybys 1900-2200
  - Sentry           https://ssd-api.jpl.nasa.gov/sentry.api      impact-risk watch list

Usage:  python3 build_db.py            (full catalogue, ~1.6M asteroids, a few minutes)
        python3 build_db.py --neo-only (near-Earth asteroids only, ~30 s)

The finished file is chmod 444 (read-only on disk). The query server additionally
opens it in SQLite read-only mode, so nothing the app runs can change the data.
"""
import argparse
import math
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "data", "asteroids.db")

SBDB_URL = "https://ssd-api.jpl.nasa.gov/sbdb_query.api"
CAD_URL = "https://ssd-api.jpl.nasa.gov/cad.api"
SENTRY_URL = "https://ssd-api.jpl.nasa.gov/sentry.api"

AU_KM = 149_597_870.7
LD_KM = 384_400.0  # mean Earth-Moon distance
DEFAULT_ALBEDO = 0.14  # used only to estimate size when no measurement exists

SBDB_FIELDS = ["spkid", "full_name", "pdes", "name", "neo", "pha", "H", "diameter", "albedo",
               "rot_per", "e", "a", "q", "ad", "i", "per_y", "moid", "class",
               "first_obs", "last_obs", "n_obs_used", "kind"]

ORBIT_CLASSES = [
    ("IEO", "Atira", "Orbit entirely inside Earth's orbit (near-Earth)"),
    ("ATE", "Aten", "Earth-crossing, semi-major axis smaller than Earth's (near-Earth)"),
    ("APO", "Apollo", "Earth-crossing, semi-major axis larger than Earth's (near-Earth)"),
    ("AMO", "Amor", "Approaches but does not cross Earth's orbit (near-Earth)"),
    ("MCA", "Mars-crosser", "Crosses the orbit of Mars"),
    ("IMB", "Inner main belt", "Inner part of the main asteroid belt"),
    ("MBA", "Main belt", "Main asteroid belt between Mars and Jupiter"),
    ("OMB", "Outer main belt", "Outer part of the main asteroid belt"),
    ("TJN", "Jupiter trojan", "Shares Jupiter's orbit"),
    ("CEN", "Centaur", "Between Jupiter and Neptune"),
    ("TNO", "Trans-Neptunian object", "Beyond Neptune"),
    ("PAA", "Parabolic asteroid", "Parabolic orbit"),
    ("HYA", "Hyperbolic asteroid", "Hyperbolic orbit (not bound to the Sun)"),
    ("AST", "Other asteroid", "Asteroid orbit not matching any defined class"),
]

SCHEMA_PATH = os.path.join(HERE, "schema.sql")  # shared with the LLM prompts

INDEXES = """
CREATE INDEX ix_ast_des   ON asteroids(designation);
CREATE INDEX ix_ast_name  ON asteroids(name COLLATE NOCASE);
CREATE INDEX ix_ast_neo   ON asteroids(is_neo);
CREATE INDEX ix_ast_pha   ON asteroids(is_pha);
CREATE INDEX ix_ast_class ON asteroids(orbit_class);
CREATE INDEX ix_ast_moid  ON asteroids(moid_au);
CREATE INDEX ix_ast_diam  ON asteroids(diameter_est_km);
CREATE INDEX ix_ast_h     ON asteroids(abs_magnitude_h);
CREATE INDEX ix_ca_des    ON close_approaches(designation);
CREATE INDEX ix_ca_time   ON close_approaches(approach_time);
CREATE INDEX ix_ca_dist   ON close_approaches(dist_km);
"""


def num(v, cast=float):
    if v is None or v == "":
        return None
    try:
        return cast(v)
    except (TypeError, ValueError):
        return None


def get_json(url, params, tries=5):
    for attempt in range(tries):
        try:
            r = requests.get(url, params=params, timeout=900)
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, ValueError) as e:
            if attempt == tries - 1:
                raise
            wait = 5 * (attempt + 1)
            print(f"  request failed ({e}); retrying in {wait}s", flush=True)
            time.sleep(wait)


def estimate_diameter(h, albedo):
    if h is None:
        return None
    return 1329.0 / math.sqrt(albedo or DEFAULT_ALBEDO) * 10 ** (-h / 5)


def load_asteroids(con, neo_only, page=50_000):
    params = {"fields": ",".join(SBDB_FIELDS), "sb-kind": "a", "limit": page}
    if neo_only:
        params["sb-group"] = "neo"
    offset, total, seen = 0, None, 0
    while total is None or offset < total:
        params["limit-from"] = offset
        t = time.time()
        js = get_json(SBDB_URL, params)
        total = int(js["count"])
        idx = {f: i for i, f in enumerate(js["fields"])}
        rows = []
        for d in js["data"]:
            g = lambda f: d[idx[f]]
            h, diam, alb = num(g("H")), num(g("diameter")), num(g("albedo"))
            moid = num(g("moid"))
            rows.append((
                int(g("spkid")), g("pdes"), g("name"), (g("full_name") or "").strip(),
                1 if g("kind") == "an" else 0,
                1 if g("neo") == "Y" else 0, 1 if g("pha") == "Y" else 0,
                g("class"), h, diam,
                diam if diam is not None else estimate_diameter(h, alb),
                alb, num(g("rot_per")), num(g("e")), num(g("a")), num(g("q")), num(g("ad")),
                num(g("i")), num(g("per_y")), moid,
                moid * AU_KM if moid is not None else None,
                moid * AU_KM / LD_KM if moid is not None else None,
                g("first_obs"), g("last_obs"), num(g("n_obs_used"), int),
            ))
        con.executemany(f"INSERT OR REPLACE INTO asteroids VALUES ({','.join('?' * 25)})", rows)
        seen += len(rows)
        offset += page
        print(f"  asteroids {min(offset, total):>9,}/{total:,}  ({time.time() - t:.1f}s)", flush=True)
        if not js["data"]:
            break
    return total


def km(au):
    au = num(au)
    return au * AU_KM if au is not None else None


def cad_time_iso(cd):
    # "2026-Jan-01 15:44" -> "2026-01-01 15:44"
    return datetime.strptime(cd, "%Y-%b-%d %H:%M").strftime("%Y-%m-%d %H:%M")


def load_close_approaches(con, date_min="1900-01-01", date_max="2200-12-31", dist_max_au=0.2):
    js = get_json(CAD_URL, {"date-min": date_min, "date-max": date_max, "dist-max": dist_max_au,
                            "kind": "a", "neo": "false", "fullname": "true"})
    idx = {f: i for i, f in enumerate(js["fields"])}
    rows = []
    for d in js["data"]:
        g = lambda f: d[idx[f]]
        t = cad_time_iso(g("cd"))
        dist = num(g("dist"))
        rows.append((g("des"), (g("fullname") or "").strip(), t, t[:10], dist, dist * AU_KM, dist * AU_KM / LD_KM,
                     km(g("dist_min")), km(g("dist_max")), num(g("v_rel")), num(g("h"))))
    con.executemany("INSERT INTO close_approaches (designation, full_name, approach_time, approach_date, dist_au,"
                    " dist_km, dist_ld, dist_min_km, dist_max_km, velocity_kms, abs_magnitude_h)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)
    print(f"  close approaches {len(rows):,}", flush=True)
    return len(rows)


def load_sentry(con):
    js = get_json(SENTRY_URL, {})
    rows = []
    for d in js["data"]:
        rng = (d.get("range") or "").split("-")
        rows.append((d["des"], (d.get("fullname") or "").strip(), num(d.get("ip")), num(d.get("n_imp"), int),
                     num(rng[0], int) if rng else None, num(rng[-1], int) if rng else None,
                     num(d.get("ps_cum")), num(d.get("ps_max")), num(d.get("ts_max"), int),
                     num(d.get("diameter")), num(d.get("v_inf")), num(d.get("h")), d.get("last_obs")))
    con.executemany(f"INSERT OR REPLACE INTO impact_risk VALUES ({','.join('?' * 13)})", rows)
    print(f"  impact-risk objects {len(rows):,}", flush=True)
    return len(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--neo-only", action="store_true", help="only near-Earth asteroids (much faster)")
    args = ap.parse_args()

    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    tmp = DB_PATH + ".building"
    if os.path.exists(tmp):
        os.remove(tmp)
    con = sqlite3.connect(tmp)
    with open(SCHEMA_PATH) as f:
        con.executescript(f.read())
    con.executemany("INSERT INTO orbit_classes VALUES (?,?,?)", ORBIT_CLASSES)

    t0 = time.time()
    print("Fetching asteroid catalogue from JPL SBDB...", flush=True)
    n_ast = load_asteroids(con, args.neo_only)
    print("Fetching Earth close approaches (1900-2200, within 0.2 au)...", flush=True)
    n_ca = load_close_approaches(con)
    print("Fetching Sentry impact-risk list...", flush=True)
    n_sentry = load_sentry(con)

    info = {
        "fetched_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "catalogue": "near-Earth asteroids only" if args.neo_only else "all known asteroids",
        "asteroid_count": str(n_ast),
        "close_approach_range": "1900-01-01 to 2200-12-31, within 0.2 au (~77.8 lunar distances)",
        "close_approach_count": str(n_ca),
        "impact_risk_count": str(n_sentry),
        "sources": "NASA/JPL SSD APIs: sbdb_query.api, cad.api, sentry.api",
    }
    con.executemany("INSERT INTO dataset_info VALUES (?,?)", info.items())
    print("Indexing...", flush=True)
    con.executescript(INDEXES)
    con.commit()
    con.execute("ANALYZE")
    con.commit()
    con.close()

    if os.path.exists(DB_PATH):
        os.chmod(DB_PATH, 0o644)
    os.replace(tmp, DB_PATH)
    os.chmod(DB_PATH, 0o444)  # read-only on disk
    print(f"Done in {time.time() - t0:.0f}s -> {DB_PATH} ({os.path.getsize(DB_PATH) / 1e6:.0f} MB)")


if __name__ == "__main__":
    sys.exit(main())
