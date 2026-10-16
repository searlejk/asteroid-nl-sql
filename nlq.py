"""Natural language -> SQL -> results -> natural language.

Prompting strategies follow Chang & Fosler-Lussier 2023, "How to Prompt LLMs for
Text-to-SQL: A Study in Zero-shot, Single-domain, and Cross-domain Settings"
(https://arxiv.org/abs/2305.11853). Every strategy gets the schema as CREATE TABLE
statements plus a few rows of table content (the paper's best representation);
they differ only in the demonstrations:
  zero_shot      no examples
  single_domain  question/SQL examples written for THIS asteroid database
  cross_domain   question/SQL examples from OTHER databases (dog show, flights)
"""
import json
import os
import re
import time
from datetime import date, datetime

import db
import grounding

HERE = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(HERE, "logs", "queries.jsonl")
MAX_ROWS_TO_LLM = 25

SQL_SYSTEM = """You translate questions about a NASA asteroid database into one SQLite SELECT query.
Rules:
- Output only the SQL inside a ```sql code block. One statement. Read-only: SELECT or WITH only.
- Use only tables and columns from the schema. Flags are 1/0. Dates are ISO text, so compare them as strings or with date().
- Today's date is {today}; in SQL use date('now') for "today", "upcoming", "next", "this year".
- For size questions use diameter_est_km. For "potentially hazardous" use is_pha = 1. For "near-Earth" use is_neo = 1.
- "Closest approach", "fly by", "pass within X of Earth" -> the close_approaches table (actual flybys).
  "Orbit comes within" or MOID -> asteroids.moid_*. Close approaches cover 1900-2200 only.
- Convert distance units to the matching column (km -> dist_km, lunar distances / "the Moon's distance" -> dist_ld, au -> dist_au).
  "Closer than the Moon" means dist_ld < 1. 1 million km is 1000000.
- Column locations: moid_* columns exist only in asteroids; dist_*, approach_date and velocity_kms only in close_approaches.
  Use the nominal dist_* columns (not dist_min_km/dist_max_km) unless the question is about uncertainty.
- Year of a flyby: substr(approach_date, 1, 4). "Ever"/"has passed" means approach_date <= date('now'); "will" means >= date('now').
- When counting asteroids from close_approaches, use COUNT(DISTINCT designation).
- When listing asteroids, include full_name and the columns that answer the question; add LIMIT 25 unless the user asks for more.
- Look up named asteroids with name = 'Apophis' (case-sensitive proper name) or designation.
- The tables DO answer questions about: asteroid counts, names, sizes, orbits and classes (asteroids); flybys and
  how close/fast/when (close_approaches); "will/could an asteroid hit Earth", impact chances and impact years,
  including future years (impact_risk). Write a real query for those.
- Questions that are not about this data (today's weekday or time, weather, news, general knowledge) must not be
  answered with SQLite functions alone; treat them as unanswerable.
- The database has NO mass/weight, density, composition, discoverer, temperature or images. If answering needs data
  that is not in the schema, do NOT substitute other columns. Output exactly:
  SELECT 'UNANSWERABLE' AS status, '<the missing data, e.g. asteroid masses>' AS reason;"""

ZERO_SHOT_EXAMPLES = []

SINGLE_DOMAIN_EXAMPLES = [
    ("How many potentially hazardous asteroids are there?",
     "SELECT COUNT(*) AS hazardous_asteroids FROM asteroids WHERE is_pha = 1;"),
    ("What are the 5 largest near-Earth asteroids?",
     "SELECT full_name, diameter_est_km FROM asteroids WHERE is_neo = 1\nORDER BY diameter_est_km DESC LIMIT 5;"),
    ("Which asteroids will pass closer than the Moon in 2027?",
     "SELECT full_name, approach_time, dist_km, dist_ld, velocity_kms FROM close_approaches\n"
     "WHERE approach_date BETWEEN '2027-01-01' AND '2027-12-31' AND dist_ld < 1\nORDER BY dist_km;"),
    ("When is Bennu's next close approach to Earth?",
     "SELECT ca.full_name, ca.approach_time, ca.dist_km, ca.dist_ld, ca.velocity_kms\n"
     "FROM close_approaches ca JOIN asteroids a ON a.designation = ca.designation\n"
     "WHERE a.name = 'Bennu' AND ca.approach_date >= date('now')\nORDER BY ca.approach_time LIMIT 1;"),
    ("How many near-Earth asteroids are in each orbit class?",
     "SELECT oc.name AS orbit_class, COUNT(*) AS asteroids FROM asteroids a\n"
     "JOIN orbit_classes oc ON oc.code = a.orbit_class\nWHERE a.is_neo = 1 GROUP BY oc.name ORDER BY asteroids DESC;"),
    ("How many different asteroids came within 1 million km of Earth during the 1990s?",
     "SELECT COUNT(DISTINCT designation) AS asteroids FROM close_approaches\n"
     "WHERE approach_date BETWEEN '1990-01-01' AND '1999-12-31' AND dist_km < 1000000;"),
    ("Could an asteroid hit Earth in 2040?",
     "SELECT full_name, impact_probability, first_year, last_year, diameter_km FROM impact_risk\n"
     "WHERE 2040 BETWEEN first_year AND last_year ORDER BY impact_probability DESC LIMIT 25;"),
    ("Which 3 asteroids on the impact risk list are the biggest?",
     "SELECT full_name, diameter_km, impact_probability, first_year, last_year FROM impact_risk\n"
     "ORDER BY diameter_km DESC LIMIT 3;"),
]

# Demonstrations from unrelated databases, each shown with its own schema (cross-domain setting).
CROSS_DOMAIN_DBS = [
    ("""CREATE TABLE person (person_id INTEGER PRIMARY KEY, name VARCHAR(20) NOT NULL);
CREATE TABLE dog (dog_id INTEGER PRIMARY KEY, name VARCHAR(35), breed VARCHAR(35), birth_date DATE);
CREATE TABLE award (award_id INTEGER PRIMARY KEY, dog_id INTEGER NOT NULL REFERENCES dog(dog_id),
                    event_date DATE, award_name VARCHAR(25) NOT NULL);
CREATE TABLE person_dog (dog_id INTEGER REFERENCES dog(dog_id), person_id INTEGER REFERENCES person(person_id));""",
     [("Which are the most awarded dogs?",
       "SELECT d.name, COUNT(a.award_id) AS awards FROM dog d JOIN award a ON a.dog_id = d.dog_id\n"
       "GROUP BY d.dog_id ORDER BY awards DESC LIMIT 25;"),
      ("How many dogs were born after 2020?",
       "SELECT COUNT(*) AS dogs FROM dog WHERE birth_date > '2020-12-31';")]),
    ("""CREATE TABLE airport (code TEXT PRIMARY KEY, city TEXT, country TEXT);
CREATE TABLE flight (flight_id INTEGER PRIMARY KEY, origin TEXT REFERENCES airport(code),
                     destination TEXT REFERENCES airport(code), departure_time TEXT, distance_km REAL);""",
     [("What are the 3 longest flights leaving Paris after today?",
       "SELECT f.flight_id, f.destination, f.departure_time, f.distance_km FROM flight f\n"
       "JOIN airport a ON a.code = f.origin WHERE a.city = 'Paris' AND f.departure_time >= date('now')\n"
       "ORDER BY f.distance_km DESC LIMIT 3;"),
      ("How many different cities have flights shorter than 500 km?",
       "SELECT COUNT(DISTINCT a.city) AS cities FROM flight f JOIN airport a ON a.code = f.origin\n"
       "WHERE f.distance_km < 500;")]),
]

STRATEGIES = {
    "zero_shot": "Zero-shot: schema + sample rows, no examples",
    "single_domain": "Single-domain few-shot: 8 example questions on this asteroid database",
    "cross_domain": "Cross-domain few-shot: examples from other databases (dog show, flights)",
}
DEFAULT_STRATEGY = "single_domain"

UNANSWERABLE_SQL = re.compile(r"\s*SELECT\s+'UNANSWERABLE'", flags=re.I)

SECOND_LOOK = ("Double-check before giving up. The tables cover asteroid counts, names, sizes, orbits and classes "
               "(asteroids); Earth flybys with dates, distances and speeds, past and future (close_approaches); and "
               "which asteroids could hit Earth, with probabilities and possible impact years (impact_risk). If any "
               "table can answer the question, write that SELECT query in a ```sql block. Only if none can, repeat "
               "the UNANSWERABLE query.")

OUT_OF_SCOPE = ("I can only answer from the NASA asteroid data in this database, and it doesn't contain that. "
                "It covers asteroid sizes, orbits, Earth flybys (1900-2200) and impact risk, but not things like "
                "mass, composition, who discovered them, or today's date. Try a question about one of those, "
                "for example \"What is the largest asteroid?\"")

ANSWER_SYSTEM = """You turn SQL query results from a NASA asteroid database into a short, friendly, accurate answer.
- Answer the user's question directly in 1-4 sentences.
- If the result has more than 5 rows, FIRST say how many there are in total (row_count), then name the top few
  (at most 5) with their key numbers. Never imply the few you name are all of them.
- Use ONLY the numbers, names and dates in the results below. Do not add anything from your own knowledge: no
  facts about asteroids, no dates or weekdays, no comparisons to other objects. If the results don't contain
  something the question asks, say the data doesn't include it.
- Format numbers readably: thousands separators, sensible rounding (e.g. 1,234,567 km; 0.42 lunar distances; 1.3 km wide).
  When a distance in km is given, also say it in lunar distances if available (1 LD = 384,400 km, the Earth-Moon distance).
- If the results were truncated, say you are showing the first rows.
- If the query measured something slightly different from what was asked (e.g. orbit distance vs an actual flyby,
  or a limited date range), say so briefly. Do not mention SQL, tables or column names.
- Describe what was actually counted or listed, judging from the query and column names. If that differs from what
  the user asked (e.g. they asked about near-Earth asteroids but the query counted hazardous ones), say so plainly.
- If the result cannot actually answer the question (e.g. it asked for a weight but the column is a sum of diameters),
  say the data can't answer it instead of reporting the number.
- Copy numbers exactly from the results. Do not do your own arithmetic beyond simple unit conversions.
Domain facts:
- The impact_risk (Sentry) list holds asteroids that CANNOT YET BE RULED OUT as impactors. These are possibilities with
  tiny probabilities, not predicted collisions. Never say an asteroid is "on a collision course". Give probabilities
  as "about 1 in N" (N = 1/probability) and note that more observations usually rule impacts out.
- "Potentially hazardous" is a size-and-orbit category, not a prediction of impact.
- JPL's asteroid catalogue also includes dwarf planets such as Ceres, Pluto and Eris."""

_cache = {}


def _schema_block():
    if "schema" not in _cache:
        _cache["schema"] = db.schema_sql() + "\n\n" + db.sample_rows()
    return _cache["schema"]


def build_sql_messages(question, strategy):
    system = SQL_SYSTEM.format(today=date.today().isoformat())
    parts = []
    if strategy == "cross_domain":
        for schema, examples in CROSS_DOMAIN_DBS:
            ex = "\n\n".join(f"Question: {q}\n```sql\n{s}\n```" for q, s in examples)
            parts.append(f"Example database:\n{schema}\n\n{ex}")
        parts.append("Now the real database.")
    parts.append(_schema_block())
    if strategy == "single_domain":
        ex = "\n\n".join(f"Question: {q}\n```sql\n{s}\n```" for q, s in SINGLE_DOMAIN_EXAMPLES)
        parts.append("Examples for this database:\n\n" + ex)
    elif strategy not in ("zero_shot", "cross_domain"):
        raise ValueError(f"unknown strategy {strategy!r}")
    parts.append(f"Question: {question}")
    return [{"role": "system", "content": system}, {"role": "user", "content": "\n\n".join(parts)}]


def extract_sql(text):
    """Pull the SQL out of a model reply (fenced block preferred, else from the first SELECT/WITH)."""
    m = re.search(r"```(?:sql|sqlite)?\s*\n?(.*?)```", text, flags=re.S | re.I)
    if m:
        sql = m.group(1)
    else:
        m = re.search(r"\b(SELECT|WITH)\b.*", text, flags=re.S | re.I)
        sql = m.group(0) if m else text
    sql = sql.strip()
    # keep only the first statement
    if ";" in sql:
        sql = sql[: sql.index(";") + 1]
    return sql.strip()


def _table_columns():
    if "columns" not in _cache:
        cols = {}
        for m in re.finditer(r"CREATE TABLE (\w+) \((.*?)\n\);", db.schema_sql(), flags=re.S):
            for line in m.group(2).splitlines():
                name = line.split("--")[0].strip().split(" ")[0]
                if name:
                    cols.setdefault(name, []).append(m.group(1))
        _cache["columns"] = cols
    return _cache["columns"]


def _column_hint(error):
    """For 'no such column: x', tell the model which table really has x (small models often pick the wrong table)."""
    m = re.search(r"no such column: (?:\w+\.)?(\w+)", error)
    if not m:
        return ""
    tables = _table_columns().get(m.group(1))
    if tables:
        return f"Hint: column {m.group(1)} exists only in table(s): {', '.join(tables)}.\n"
    return f"Hint: there is no column named {m.group(1)} in any table.\n"


def _rows_for_prompt(res):
    rows = res["rows"][:MAX_ROWS_TO_LLM]
    def fmt(v):
        if isinstance(v, float):  # 4 significant figures: small models copy digits verbatim
            return round(v) if abs(v) >= 10_000 else float(f"{v:.4g}")
        return v
    return [dict(zip(res["columns"], [fmt(v) for v in r])) for r in rows]


def build_answer_messages(question, sql, res):
    shown = len(res["rows"])
    payload = {
        "question": question,
        "sql_query_used": sql,
        "columns": res["columns"],
        "row_count": f"{shown}{'+ (truncated)' if res['truncated'] else ''}",
        "rows": _rows_for_prompt(res),
    }
    if shown > MAX_ROWS_TO_LLM:
        payload["note"] = f"Only the first {MAX_ROWS_TO_LLM} of {shown} rows are shown here."
    # Only the question, the SQL and the rows: anything else here (e.g. today's date) is something the
    # model can turn into an answer that isn't from the dataset.
    content = json.dumps(payload, indent=1, default=str)
    return [{"role": "system", "content": ANSWER_SYSTEM}, {"role": "user", "content": content}]


def ask(provider, question, strategy=DEFAULT_STRATEGY, repair=True, answer=True):
    """Full pipeline. Returns a dict that is safe to JSON-serialise."""
    t0 = time.monotonic()
    out = {"question": question, "strategy": strategy, "model": provider.name, "sql": None,
           "columns": [], "rows": [], "truncated": False, "answer": None, "error": None,
           "attempts": [], "timings_ms": {}}
    messages = build_sql_messages(question, strategy)
    res = None
    for attempt in range(2 if repair else 1):
        t = time.monotonic()
        reply = provider.chat(messages, max_tokens=500)
        sql = extract_sql(reply)
        out["timings_ms"][f"sql_llm_{attempt + 1}"] = round((time.monotonic() - t) * 1000)
        out["sql"] = sql
        if UNANSWERABLE_SQL.match(sql):
            # Small models over-use the escape hatch, so ask for a second look once before accepting it.
            if repair and attempt == 0:
                out["attempts"].append({"sql": sql, "error": "model said unanswerable; asked to double-check"})
                messages = messages + [
                    {"role": "assistant", "content": f"```sql\n{sql}\n```"},
                    {"role": "user", "content": SECOND_LOOK},
                ]
                continue
            # The model chose "unanswerable"; no need to run it (and its free-text reason may not even parse).
            out["attempts"].append({"sql": sql, "error": None})
            res = {"columns": ["status", "reason"], "rows": [["UNANSWERABLE", None]], "truncated": False,
                   "ms": 0.0, "tables": []}
            break
        try:
            res = db.run_query(sql)
            out["attempts"].append({"sql": sql, "error": None})
            break
        except Exception as e:  # sqlite error or QueryRejected
            err = f"{type(e).__name__}: {e}"
            out["attempts"].append({"sql": sql, "error": err})
            hint = _column_hint(str(e))
            messages = messages + [
                {"role": "assistant", "content": f"```sql\n{sql}\n```"},
                {"role": "user", "content": f"That query failed with: {err}\n{hint}Return a corrected single SQLite "
                                            f"SELECT query in a ```sql block, using only the schema above."},
            ]
    if res is None:
        out["error"] = out["attempts"][-1]["error"]
        out["answer"] = ("Sorry, I couldn't turn that into a working database query. "
                         "Try rephrasing it, for example with a specific distance, date or asteroid name.")
    else:
        out["timings_ms"]["sql_exec"] = res["ms"]
        out.update(columns=res["columns"], rows=res["rows"], truncated=res["truncated"])
        out["tables_read"] = res["tables"]
        # Fixed wording (not the model's) whenever the data can't support an answer.
        if _is_unanswerable(res) or not res["tables"]:
            # not res["tables"]: the query read no data table (e.g. SELECT strftime('%A', 'now')),
            # so whatever it returns is not from the dataset.
            out["unanswerable"] = True
            out["answer"] = OUT_OF_SCOPE
        elif all(v is None for row in res["rows"] for v in row):
            out["answer"] = "The database returned no data for that question, so I don't have an answer."
        elif answer:
            t = time.monotonic()
            draft = trim_repetition(
                provider.chat(build_answer_messages(question, out["sql"], res), max_tokens=400).strip())
            out["timings_ms"]["answer_llm"] = round((time.monotonic() - t) * 1000)
            problems = grounding.check(draft, res, question)
            out["grounding_problems"] = problems
            if problems:
                out["rejected_answer"] = draft
                out["answer"] = (grounding.plain_answer(res) + "\n\n(The model's wording included details that "
                                 "aren't in the data, so the raw result is shown instead.)")
            else:
                out["answer"] = draft
    out["timings_ms"]["total"] = round((time.monotonic() - t0) * 1000)
    _log(out)
    return out


def _is_unanswerable(res):
    return bool(res["rows"]) and res["columns"][:1] == ["status"] and str(res["rows"][0][0]).upper() == "UNANSWERABLE"


def trim_repetition(text, min_repeats=6):
    """Cut a degenerate loop like ',000,000,000,...' that small models sometimes fall into."""
    m = re.search(r"(.{1,12}?)\1{%d,}" % min_repeats, text, flags=re.S)
    if not m:
        return text
    cut = text.rfind(" ", 0, m.start())  # back up to a word boundary so no half-number is left
    return text[: max(cut, 0)].rstrip(" ,.;") + " [answer cut off: the model started repeating itself]"


def _log(out):
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    rec = {k: v for k, v in out.items() if k != "rows"}
    rec["rows_preview"] = out["rows"][:5]
    rec["time"] = datetime.now().isoformat(timespec="seconds")
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(rec, default=str) + "\n")


if __name__ == "__main__":
    import argparse
    import llm
    ap = argparse.ArgumentParser(description="Ask the asteroid database a question from the terminal.")
    ap.add_argument("question", nargs="+")
    ap.add_argument("--strategy", default=DEFAULT_STRATEGY, choices=list(STRATEGIES))
    a = ap.parse_args()
    r = ask(llm.make_provider(), " ".join(a.question), a.strategy)
    print(f"[{r['model']} / {r['strategy']}]\nSQL:\n{r['sql']}\n")
    if r["error"]:
        print("Error:", r["error"])
    else:
        print("Columns:", r["columns"])
        for row in r["rows"][:10]:
            print("  ", row)
    print("\nAnswer:", r["answer"])
    print("Timings (ms):", r["timings_ms"])
