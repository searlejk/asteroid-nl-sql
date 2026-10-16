"""Run every question in questions.json through every prompting strategy and log the results.

    python3 run_experiments.py                      # all strategies, provider from config.json
    python3 run_experiments.py --strategies zero_shot single_domain
    python3 run_experiments.py --repair             # allow one self-repair after a SQL error

Writes, like the class example:
    responses/response_<strategy>_<timestamp>.json   prompt, and per question: sql, raw result, friendly answer, error
    responses/summary_<timestamp>.md                 execution-accuracy table comparing strategies

"Execution match" (the paper's execution accuracy, made a little lenient): the generated query
returns the same number of rows as the gold query, and every gold column's values appear as some
column of the generated result (extra columns like full_name are fine; floats compared to 3 sig. figs).
"""
import argparse
import json
import os
import time
from collections import Counter

import db
import llm
import nlq

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "responses")


def _norm(v):
    if isinstance(v, float):
        return float(f"{v:.3g}")
    if isinstance(v, str):
        return v.strip().lower()
    return v


def execution_match(gold_sql, pred):
    if pred.get("error") or not pred.get("columns"):
        return False
    gold = db.run_query(gold_sql)
    if len(gold["rows"]) != len(pred["rows"]):
        return False
    ordered = "order by" in gold_sql.lower()
    pred_cols = [[_norm(r[i]) for r in pred["rows"]] for i in range(len(pred["columns"]))]
    for gi in range(len(gold["columns"])):
        gcol = [_norm(r[gi]) for r in gold["rows"]]
        if ordered:
            ok = any(pc == gcol for pc in pred_cols)
        else:
            ok = any(Counter(map(str, pc)) == Counter(map(str, gcol)) for pc in pred_cols)
        if not ok:
            return False
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--strategies", nargs="+", default=list(nlq.STRATEGIES), choices=list(nlq.STRATEGIES))
    ap.add_argument("--repair", action="store_true", help="allow one SQL repair attempt after an error")
    ap.add_argument("--questions", default=os.path.join(HERE, "questions.json"))
    args = ap.parse_args()

    with open(args.questions) as f:
        questions = json.load(f)
    provider = llm.make_provider()
    os.makedirs(OUT_DIR, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    print(f"Model: {provider.name}   repair: {args.repair}   questions: {len(questions)}")

    table = {}
    for strategy in args.strategies:
        print("#" * 72 + f"\nStrategy: {strategy}")
        results = []
        for q in questions:
            r = nlq.ask(provider, q["question"], strategy, repair=args.repair)
            match = execution_match(q["gold"], r) if q.get("gold") else None
            table[(strategy, q["question"])] = (match, r)
            print(f"- {q['question']}\n  SQL: {(r['sql'] or '').replace(chr(10), ' ')}\n"
                  f"  {'ERROR ' + r['error'] if r['error'] else 'rows=' + str(len(r['rows']))}"
                  f"   match={match}\n  Answer: {r['answer']}\n")
            results.append({
                "question": q["question"],
                "sql": r["sql"],
                "queryRawResponse": str([tuple(x) for x in r["rows"][:20]]),
                "friendlyResponse": r["answer"],
                "error": r["error"] or "None",
                "gold_sql": q.get("gold"),
                "execution_match": match,
                "attempts": r["attempts"],
                "tables_read": r.get("tables_read"),
                "grounding_problems": r.get("grounding_problems"),
                "rejected_answer": r.get("rejected_answer"),
                "timings_ms": r["timings_ms"],
            })
        prompt_prefix = nlq.build_sql_messages("<question>", strategy)
        with open(os.path.join(OUT_DIR, f"response_{strategy}_{stamp}.json"), "w") as f:
            json.dump({"strategy": strategy, "model": provider.name, "repair": args.repair,
                       "prompt_prefix": prompt_prefix, "questionResults": results}, f, indent=2, default=str)

    # summary
    lines = [f"# Strategy comparison ({provider.name}, {stamp}, repair={args.repair})", "",
             "| Question | " + " | ".join(args.strategies) + " |",
             "|---|" + "---|" * len(args.strategies)]
    totals = Counter()
    graded = sum(1 for q in questions if q.get("gold"))
    for q in questions:
        cells = []
        for s in args.strategies:
            match, r = table[(s, q["question"])]
            if r["error"]:
                cells.append("error")
            elif match is None:
                cells.append("(manual)")
            else:
                cells.append("✅" if match else "❌")
                totals[s] += bool(match)
        lines.append(f"| {q['question']} | " + " | ".join(cells) + " |")
    lines.append("| **Execution accuracy** | " +
                 " | ".join(f"**{totals[s]}/{graded}**" for s in args.strategies) + " |")
    lines += ["", f"Tokens used: {provider.usage}"]
    summary = "\n".join(lines)
    with open(os.path.join(OUT_DIR, f"summary_{stamp}.md"), "w") as f:
        f.write(summary + "\n")
    print(summary)


if __name__ == "__main__":
    main()
