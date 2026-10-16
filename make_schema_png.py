"""Draw schema.png from schema.sql with Graphviz (brew install graphviz).   python3 make_schema_png.py"""
import html
import os
import re
import subprocess

import db

HERE = os.path.dirname(os.path.abspath(__file__))
# (child table, child column, parent table, parent column, label, marker at child end, marker at parent end)
# Crow's-foot markers: crow = many, tee = exactly one, teeodot = zero or one.
LINKS = [
    ("close_approaches", "designation", "asteroids", "designation", "an asteroid has many flybys", "crow", "tee"),
    ("impact_risk", "designation", "asteroids", "designation", "an asteroid has 0 or 1 risk entry", "teeodot", "tee"),
    ("asteroids", "orbit_class", "orbit_classes", "code", "many asteroids per class", "crow", "tee"),
]


def parse(sql):
    tables = {}
    for m in re.finditer(r"CREATE TABLE (\w+) \((.*?)\n\);", sql, flags=re.S):
        cols = []
        for line in m.group(2).splitlines():
            line = line.split("--")[0].strip().rstrip(",")
            if line:
                parts = line.split()
                cols.append((parts[0], parts[1], "PRIMARY KEY" in line))
        tables[m.group(1)] = cols
    return tables


def row_counts(tables):
    try:
        return {t: db.run_query(f"SELECT COUNT(*) FROM {t}")["rows"][0][0] for t in tables}
    except Exception:  # database not built yet: draw without counts
        return {}


def main():
    with open(os.path.join(HERE, "schema.sql")) as f:
        tables = parse(f.read())
    counts = row_counts(tables)
    fk = {(a, b) for a, b, *_ in LINKS}
    out = ['digraph schema {',
           'graph [rankdir=LR, bgcolor="white", pad=0.4, nodesep=0.6, ranksep=1.4, fontname="Helvetica", '
           'labelloc=t, fontsize=22, label=<<b>NASA/JPL asteroid database</b><br/>'
           '<font point-size="13" color="#6a6f7a">SQLite, opened read-only · 🔑 primary key · ↗ foreign key · '
           'crow\'s foot = many, bar = one, circle = optional</font><br/> >];',
           'node [shape=plain, fontname="Helvetica"];',
           'edge [fontname="Helvetica", fontsize=11, color="#6a6f7a", fontcolor="#6a6f7a", dir=both, penwidth=1.3, '
           'arrowsize=1.1];']
    for t, cols in tables.items():
        n = f'<br/><font point-size="10" color="#f6e3d6">{counts[t]:,} rows</font>' if t in counts else ""
        rows = [f'<tr><td bgcolor="#c2622d" colspan="2"><font color="white"><b>{t}</b></font>{n}</td></tr>']
        for name, typ, pk in cols:
            tag = " 🔑" if pk else (" ↗" if (t, name) in fk else "")
            rows.append(f'<tr><td align="left" port="{name}">{html.escape(name)}{tag}</td>'
                        f'<td align="left" port="{name}_r"><font color="#8a8f99">{typ}</font></td></tr>')
        out.append(f'{t} [label=<<table border="0" cellborder="1" cellspacing="0" cellpadding="5" color="#d0cdc6">'
                   + "".join(rows) + "</table>>];")
    for a, ac, b, bc, label, child_end, parent_end in LINKS:
        out.append(f'{a}:{ac}_r:e -> {b}:{bc}:w [label="{label}", arrowtail={child_end}, arrowhead={parent_end}];')
    out.append("}")
    dot = "\n".join(out)
    png = os.path.join(HERE, "schema.png")
    subprocess.run(["dot", "-Tpng", "-Gdpi=150", "-o", png], input=dot.encode(), check=True)
    print("wrote", png)


if __name__ == "__main__":
    main()
