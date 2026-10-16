"""Check that a model-written answer only states facts that are in the query results.

The answer LLM is told to use only the data, but small models still fill gaps from their own
"knowledge" (e.g. answering "Wednesday" when the query returned NULL). So every number and weekday
in the answer must be traceable to the results (or the user's question); otherwise the caller
shows the raw result instead of the model's wording.

A number counts as traceable if it matches a result value within 2% or within the rounding of the
digits shown, either directly or after a simple conversion the answer prompt allows
(km <-> lunar distances, km <-> au, km <-> m, fraction <-> percent, probability -> "1 in N").
"""
import math
import re

LD_KM = 384_400.0
AU_KM = 149_597_870.7
SCALE = {"thousand": 1e3, "million": 1e6, "billion": 1e9, "trillion": 1e12, "quadrillion": 1e15}
WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")

_NUM = re.compile(r"(?<![\w.])(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?(?:\s*(thousand|million|billion|trillion|quadrillion))?"
                  r"(\s*(?:%|percent))?", flags=re.I)


MONTHS = ("january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
          "november", "december")
_M = "(" + "|".join(MONTHS) + ")"
_DATE_MDY = re.compile(_M + r"\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})", flags=re.I)   # April 13, 2029
_DATE_DMY = re.compile(r"(\d{1,2})(?:st|nd|rd|th)?\s+" + _M + r",?\s+(\d{4})", flags=re.I)  # 13 April 2029
_DATE_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")

PLAIN_TOL = 0.02     # relative tolerance for numbers copied from the results (rounding of shown digits also OK)
ONE_IN_N_TOL = 0.05  # "about 1 in 10" for 0.1026 is normal rounding


def _numbers(text, with_kind=False):
    """Yield (value, decimals_shown[, kind]) for every number in text, e.g. '1.2 million' -> (1.2e6, 1).
    kind is 'pct' for '5.97%', 'inv' for the N in '1 in N', else 'plain'."""
    for m in _NUM.finditer(text or ""):
        whole, frac, scale = m.group(1).replace(",", ""), m.group(2) or "", m.group(3)
        value = float(whole + frac)
        decimals = len(frac) - 1 if frac else 0
        kind = "pct" if m.group(4) else ("inv" if re.search(r"\b1\s+in\s+(?:about\s+)?$", text[:m.start()], re.I)
                                         else "plain")
        found = [(value, decimals)] + ([(value * SCALE[scale.lower()], None)] if scale else [])
        for v, d in found:
            yield (v, d, kind) if with_kind else (v, d)


def _allowed(res, question):
    """Values an answer may state: {'plain': ..., 'pct': ..., 'inv': ...}. Conversions are only allowed where
    the answer's wording asks for them, so a made-up number is unlikely to match something by accident."""
    plain, pct, inv = {float(len(res["rows"])), 1000.0}, set(), set()
    for row in res["rows"]:
        for v in row:
            if isinstance(v, bool) or v is None:
                continue
            if isinstance(v, (int, float)):
                b = abs(float(v))
                plain.update({b, b / LD_KM, b * LD_KM, b / AU_KM, b * AU_KM, b * 1000, b / 1000})
                pct.update({b * 100, b / 100})
                if 0 < b < 1:
                    inv.add(1 / b)  # probability -> "1 in N"
            else:
                plain.update(v for v, _ in _numbers(str(v)))  # dates, designations like "2025 UC11"
    plain.update(v for v, _ in _numbers(question))
    return {"plain": plain, "pct": pct | plain, "inv": inv}


def _matches(a, decimals, b, tol=PLAIN_TOL):
    if b == 0:
        return a == 0
    if abs(a - b) / abs(b) <= tol:
        return True
    return decimals is not None and abs(a - b) <= 0.5 * 10 ** (-decimals)


def _dates_in(text):
    out = set()
    for mon, day, year in _DATE_MDY.findall(text):
        out.add(f"{year}-{MONTHS.index(mon.lower()) + 1:02d}-{int(day):02d}")
    for day, mon, year in _DATE_DMY.findall(text):
        out.add(f"{year}-{MONTHS.index(mon.lower()) + 1:02d}-{int(day):02d}")
    out.update(f"{y}-{m}-{d}" for y, m, d in _DATE_ISO.findall(text))
    return out


def check(answer, res, question):
    """Return a list of problems (empty list = every number, date and weekday in the answer is backed by the data)."""
    problems = []
    allowed = _allowed(res, question)
    seen = set()
    for a, dec, kind in _numbers(answer, with_kind=True):
        if (a, kind) in seen:
            continue
        seen.add((a, kind))
        if kind != "inv" and dec == 0 and a == int(a) and 0 <= a <= 10:
            continue  # list numbering, "top 5", the "1" in "1 in N" (whole numbers only: 8.03 is not 8)
        if kind == "inv":
            # "1 in 9" or "1 in 10" for 1/0.1026 = 9.74 are both fair roundings
            ok = any(_matches(a, None, b, ONE_IN_N_TOL) or math.floor(b) <= a <= math.ceil(b) for b in allowed["inv"])
        else:
            ok = any(_matches(a, dec, b) for b in allowed[kind])
        if not ok:
            problems.append(f"number {a:g} is not in the results")
    # A scaled number ("1.2 million") is fine if either reading matched; drop the unscaled-reading complaint.
    problems = _drop_scale_duplicates(answer, problems, allowed["plain"])

    source_text = " ".join(str(v) for row in res["rows"] for v in row if isinstance(v, str)) + " " + question
    # Whole dates must match a whole date in the results (not a day from one row and a year from another).
    result_dates = _dates_in(source_text)
    for d in sorted(_dates_in(answer) - result_dates):
        problems.append(f"date {d} is not in the results")
    for day in WEEKDAYS:
        if re.search(rf"\b{day}\b", answer, flags=re.I) and day not in source_text.lower():
            problems.append(f"'{day.title()}' is not in the results")
    return problems


def _drop_scale_duplicates(answer, problems, allowed):
    keep = []
    for p in problems:
        val = float(p.split()[1])
        scaled_ok = False
        for m in _NUM.finditer(answer):
            if m.group(3) and float(m.group(1).replace(",", "") + (m.group(2) or "")) == val:
                big = val * SCALE[m.group(3).lower()]
                scaled_ok = any(_matches(big, None, b) for b in allowed)
        if not scaled_ok:
            keep.append(p)
    return keep


def _fmt(v):
    if v is None:
        return "no value"
    if isinstance(v, float):
        return f"{v:,.0f}" if abs(v) >= 10_000 else f"{v:,.4g}"
    if isinstance(v, int):
        return f"{v:,}"
    return str(v)


def plain_answer(res):
    """Deterministic answer straight from the rows, used when the model's wording can't be trusted."""
    cols = [c.replace("_", " ") for c in res["columns"]]
    rows = res["rows"]
    if len(rows) == 1 and len(cols) == 1:
        return f"The database returned {cols[0]}: {_fmt(rows[0][0])}."
    head = f"The database returned {len(rows):,}{'+' if res['truncated'] else ''} row{'s' if len(rows) != 1 else ''}"
    lines = [", ".join(f"{c}: {_fmt(v)}" for c, v in zip(cols, r)) for r in rows[:5]]
    more = f"\n…and {len(rows) - 5:,} more (see the results table)." if len(rows) > 5 else ""
    return head + (". First rows:\n" if len(rows) > 1 else ":\n") + "\n".join("• " + l for l in lines) + more
