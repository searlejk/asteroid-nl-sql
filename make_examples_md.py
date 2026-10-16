"""Turn the latest experiment run (responses/response_*_<stamp>.json) into responses/ALL_RESULTS.md.

    python3 make_examples_md.py               # newest run
    python3 make_examples_md.py 20261013_160132
"""
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RESP = os.path.join(HERE, "responses")


def main():
    files = glob.glob(os.path.join(RESP, "response_*_*.json"))
    stamps = sorted({re.search(r"_(\d{8}_\d{6})\.json$", f).group(1) for f in files})
    if not stamps:
        sys.exit("no responses/ files yet: run python3 run_experiments.py first")
    stamp = sys.argv[1] if len(sys.argv) > 1 else stamps[-1]
    runs = [json.load(open(f)) for f in sorted(glob.glob(os.path.join(RESP, f"response_*_{stamp}.json")))]
    order = ["zero_shot", "single_domain", "cross_domain"]
    runs.sort(key=lambda r: order.index(r["strategy"]) if r["strategy"] in order else 99)

    model = runs[0]["model"]
    out = [f"# Example questions, SQL and answers", "",
           f"Model: **{model}** · run `{stamp}` · repair step: {'on' if runs[0]['repair'] else 'off'}", "",
           "✅ = generated SQL returns the same answer as a hand-written gold query (execution accuracy), "
           "❌ = different answer, ⚠️ = SQL error, 📝 = open-ended, judged by hand.", ""]
    for i, q in enumerate(runs[0]["questionResults"]):
        out += [f"## {i + 1}. {q['question']}", ""]
        if q.get("gold_sql"):
            out += ["<details><summary>Gold SQL</summary>", "", "```sql", q["gold_sql"], "```", "</details>", ""]
        for run in runs:
            r = run["questionResults"][i]
            mark = "⚠️" if r["error"] != "None" else {True: "✅", False: "❌", None: "📝"}[r["execution_match"]]
            out += [f"**{run['strategy']}** {mark}", "", "```sql", (r["sql"] or "").strip(), "```"]
            if r["error"] != "None":
                out += [f"Error: `{r['error']}`", ""]
            else:
                raw = r["queryRawResponse"]
                out += [f"Raw result: `{raw[:200]}{'…' if len(raw) > 200 else ''}`", ""]
            if r.get("rejected_answer"):
                out += [f"Model's answer, rejected by the grounding check ({'; '.join(r['grounding_problems'])}):", "",
                        f"> ~~{r['rejected_answer'].strip()}~~", "", "Shown instead:", ""]
            out += [f"> {(r['friendlyResponse'] or '').strip().replace(chr(10), chr(10) + '> ')}", ""]
    path = os.path.join(RESP, "ALL_RESULTS.md")
    with open(path, "w") as f:
        f.write("\n".join(out))
    print("wrote", path)


if __name__ == "__main__":
    main()
