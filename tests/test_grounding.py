"""Answers with facts not in the query results must be caught.   python3 tests/test_grounding.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import grounding  # noqa: E402


def R(cols, rows):
    return {"columns": cols, "rows": rows, "truncated": False}


# (label, should_flag, answer, result, question): the "bad" answers are real outputs from the 3B model
CASES = [
    ("weekday from NULL", True, "Today is Wednesday.",
     R(["day_of_week"], [[None]]), "what day of the week is it today"),
    ("elephants from a sum of diameters", True,
     "The heaviest asteroid weighs about 332,033,780,600 kg, which is about 55 billion elephants.",
     R(["total_weight"], [[3320337805.9022083]]), "how many elephants does the heaviest asteroid weigh?"),
    ("invented threshold", True, "There are 2221 asteroids with a probability of impact greater than 0.2.",
     R(["potential_impacts"], [[2221]]), "Is any asteroid going to hit Earth?"),
    ("invented years", True, "Yes. 1000+ asteroids could hit within the next 1900-2200 years.",
     R(["designation"], [["2011 TO"], ["2012 BA102"]]), "Is any asteroid going to hit Earth?"),
    ("date pieced together from two rows", True,
     "Apophis will pass Earth on April 13, 2044, at a distance of about 8.03 AU (31.25 lunar distances).",
     R(["approach_date", "dist_au", "dist_ld"],
       [["2029-04-13", 0.000254, 0.098885], ["2044-08-24", 0.080299, 31.249], ["1915-01-28", 0.122135, 47.53]]),
     "When will Apophis pass Earth, and how close will it get?"),
    ("Apophis", False,
     "Apophis will pass Earth on April 13, 2029, about 38,011 km (0.09889 lunar distances) away at 7.423 km/s.",
     R(["full_name", "approach_time", "dist_km", "dist_ld", "velocity_kms"],
       [["99942 Apophis (2004 MN4)", "2029-04-13 21:46", 38011.459, 0.098885, 7.4225]]),
     "When will Apophis pass Earth, and how close will it get?"),
    ("list total + closest", False,
     "There were 189 asteroids that passed closer than the Moon in 2025. The closest was (2025 UC11) at 6599 km.",
     R(["full_name", "dist_km"], [["(2025 UC11)", 6599.19]] + [["x", 1.0]] * 188),
     "Which asteroids passed closer than the Moon in 2025?"),
    ("percent", False, "About 5.97% of near-Earth asteroids are potentially hazardous.",
     R(["pct"], [[5.9674]]), "What percentage of near-Earth asteroids are potentially hazardous?"),
    ("fraction to percent", False, "About 6% of near-Earth asteroids are hazardous.",
     R(["frac"], [[0.0597]]), "What share of near-Earth asteroids are hazardous?"),
    ("AU value off by 100x (real 3B output)", True, "Its closest pass is about 8.03 AU from Earth.",
     R(["dist_au", "dist_ld"], [[0.080299, 31.249], [0.122135, 47.53]]), "How close will it get?"),
    ("1 in N", False, "(2010 RF12) has about a 1 in 10 chance (10.26%) of impact in 2095.",
     R(["full_name", "impact_probability", "first_year"], [["(2010 RF12)", 0.10264, 2095]]),
     "Which asteroid has the highest chance of hitting Earth?"),
    ("1 in N rounded down", False, "2010 RF12 has an impact probability of about 1 in 9.",
     R(["designation", "impact_probability"], [["2010 RF12", 0.102637]]), "Which asteroid is most likely to hit Earth?"),
    ("number from question", False, "285 asteroids will come within 1 million km of Earth in the next 10 years.",
     R(["n"], [[285]]), "How many asteroids will come within 1 million km of Earth in the next 10 years?"),
    ("km to lunar distances", False, "It passed 1,200,000 km away, about 3.1 lunar distances.",
     R(["dist_km"], [[1200000.0]]), "How close did it pass?"),
]


def main():
    failures = 0
    for label, should_flag, answer, res, question in CASES:
        problems = grounding.check(answer, res, question)
        ok = bool(problems) == should_flag
        failures += not ok
        print(f"{'ok  ' if ok else 'FAIL'} {'flagged' if problems else 'passed '}  {label:36} {problems}")
    print("ALL PASSED" if not failures else f"{failures} FAILURES")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
