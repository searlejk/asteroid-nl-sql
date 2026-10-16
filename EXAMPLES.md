# Six more examples

These are real outputs from the app, not including the two in [SAMPLES.md](SAMPLES.md). They use the single-domain few-shot strategy (the app's default), with the local Qwen2.5-Coder-3B model, run on 2026-10-13. Every question, run through all three prompting strategies, is in [responses/ALL_RESULTS.md](responses/ALL_RESULTS.md).

| # | Question | Result |
|---|---|---|
| 1 | Which asteroids passed closer than the Moon in 2025? | ✅ correct |
| 2 | Which asteroid has the highest chance of hitting Earth? | ✅ correct (small rounding slip) |
| 3 | What percentage of near-Earth asteroids are potentially hazardous? | ✅ correct |
| 4 | How many elephants does the heaviest asteroid weigh? | ✅ correctly refused (no mass data) |
| 5 | Which upcoming year will have the most asteroid flybys closer than the Moon? | ❌ wrong answer |
| 6 | How many asteroids have orbits that come within 0.05 au of Earth's orbit? | ❌ SQL error |

---

## 1. Which asteroids passed closer than the Moon in 2025? ✅

```sql
SELECT ca.full_name, ca.approach_time, ca.dist_km, ca.dist_ld, ca.velocity_kms
FROM close_approaches ca JOIN asteroids a ON a.designation = ca.designation
WHERE ca.approach_date BETWEEN '2025-01-01' AND '2025-12-31' AND ca.dist_ld < 1
ORDER BY ca.dist_km;
```

**Raw result (first 3 of 189 rows):** `[('(2025 UC11)', '2025-10-30 12:11', 6599.19, 0.01717, 11.36), ('(2025 TF)', '2025-10-01 00:49', 6780.47, 0.01764, 20.88), ('(2025 BP6)', '2025-01-26 01:10', 9711.95, 0.02527, 21.05), …]`

**Friendly response:** There were 189 asteroids that passed closer than the Moon in 2025. The closest asteroid was (2025 UC11) with a distance of 6,599 km or 0.01717 lunar distances.

**Notes:** it translated "closer than the Moon" into `dist_ld < 1` (less than one lunar distance) and got the date range right. An earlier version of the answer prompt listed only 4 of the 189 asteroids, as if those were all of them. Adding the rule "for long lists, give the total first" fixed that. For scale, 6,599 km is measured from Earth's center, so that's only about 230 km above the surface.

## 2. Which asteroid has the highest chance of hitting Earth? ✅

```sql
SELECT full_name, impact_probability, first_year, last_year FROM impact_risk
ORDER BY impact_probability DESC LIMIT 1;
```

**Raw result:** `[('(2010 RF12)', 0.102637259069, 2095, 2122)]`

**Friendly response:** The asteroid with the highest chance of hitting Earth is (2010 RF12), with a 1 in 9.76 probability of impact between 2095 and 2122.

**Notes:** this is the right asteroid and the right years. 1 ÷ 0.1026 is 9.74, not 9.76, so the model's own arithmetic was slightly off. The app's grounding check accepts it because "1 in N" answers are allowed some rounding. The answer leaves out that 2010 RF12 is only about 7 m across, small enough to burn up in the atmosphere. The query didn't select the diameter column, so the model correctly didn't mention it.

## 3. What percentage of near-Earth asteroids are potentially hazardous? ✅

```sql
SELECT CAST(SUM(CASE WHEN is_pha = 1 THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(*)
FROM asteroids WHERE is_neo = 1;
```

**Raw result:** `[(5.967424880651502,)]`

**Friendly response:** 5.97% of near-Earth asteroids are potentially hazardous.

**Notes:** the model wrote a conditional aggregate and remembered the `CAST … AS REAL` that SQLite needs to avoid integer division. The answer is correct: 2,550 of 42,732. All three strategies got this one right.

## 4. How many elephants does the heaviest asteroid weigh? ✅ (refused)

```sql
SELECT 'UNANSWERABLE' AS status, 'mass data is not available in the schema' AS reason;
```

**Friendly response:** I can only answer from the NASA asteroid data in this database, and it doesn't contain that. It covers asteroid sizes, orbits, Earth flybys (1900-2200) and impact risk, but not things like mass, composition, who discovered them, or today's date. Try a question about one of those, for example "What is the largest asteroid?"

**Notes:** this is the right response, because NASA's catalogue has sizes but no masses. It wasn't always this way. Before I added a way to refuse, the model invented a stand-in: `SELECT SUM(diameter_est_km * 1000) AS total_weight FROM asteroids`, which adds up the diameters of all 1.5 million asteroids. The answer step then reported "332,033,780,600 kg", 100× its own query result, and got stuck repeating ",000" until it hit the length limit. Now the model can say the question is unanswerable, and the app replies with fixed text. The model's own explanation isn't shown, because those explanations sometimes contained made-up facts.

## 5. Which upcoming year will have the most asteroid flybys closer than the Moon? ❌

```sql
SELECT ca.approach_date, COUNT(*) AS flybys FROM close_approaches ca
WHERE ca.dist_ld < 1 AND ca.approach_date >= date('now')
GROUP BY ca.approach_date ORDER BY flybys DESC LIMIT 1;
```

**Raw result:** `[('2189-11-18', 1)]`

**Friendly response:** In 2189, there will be 1 asteroid flyby closer than the Moon.

**What went wrong:** it grouped by *day* (`approach_date`) instead of by *year*. So it found a day with one flyby and reported its year. The correct query groups by `substr(approach_date, 1, 4)`: **2047 and 2095 tie with 4 known flybys each**. Every number in the answer appears in the results, so the grounding check can't catch this. It's a meaning error, not a made-up number.

## 6. How many asteroids have orbits that come within 0.05 au of Earth's orbit? ❌

```sql
SELECT COUNT(DISTINCT designation) AS asteroids FROM close_approaches WHERE moid_au <= 0.05;
```

**Error:** `OperationalError: no such column: moid_au`

**Friendly response:** Sorry, I couldn't turn that into a working database query. Try rephrasing it, for example with a specific distance, date or asteroid name.

**What went wrong:** "orbits that come within" is about MOID (minimum orbit intersection distance), which is a column of `asteroids`. The model put it on the flybys table. The correct query is `SELECT COUNT(*) FROM asteroids WHERE moid_au <= 0.05`, which gives **23,101**. All three strategies made this exact mistake. In the web app the error is sent back to the model with the hint "column moid_au exists only in table(s): asteroids", but the 3B model still repeated the same query. At least it failed loudly instead of making up an answer.
