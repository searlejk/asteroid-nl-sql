# Example questions, SQL and answers

Model: **local qwen2.5-coder-3b-instruct-q4_k_m.gguf** · run `20261013_165225` · repair step: off

✅ = generated SQL returns the same answer as a hand-written gold query (execution accuracy), ❌ = different answer, ⚠️ = SQL error, 📝 = open-ended, judged by hand.

## 1. How many asteroids are there?

<details><summary>Gold SQL</summary>

```sql
SELECT COUNT(*) FROM asteroids
```
</details>

**zero_shot** ✅

```sql
SELECT COUNT(*) AS asteroid_count FROM asteroids;
```
Raw result: `[(1573578,)]`

> There are 1,573,578 asteroids in the database.

**single_domain** ✅

```sql
SELECT COUNT(*) AS total_asteroids FROM asteroids;
```
Raw result: `[(1573578,)]`

> There are 1,573,578 asteroids in the database.

**cross_domain** ✅

```sql
SELECT COUNT(*) AS asteroid_count FROM asteroids;
```
Raw result: `[(1573578,)]`

> There are 1,573,578 asteroids in the database.

## 2. How many near-Earth asteroids are there?

<details><summary>Gold SQL</summary>

```sql
SELECT COUNT(*) FROM asteroids WHERE is_neo = 1
```
</details>

**zero_shot** ✅

```sql
SELECT COUNT(*) FROM asteroids WHERE is_neo = 1;
```
Raw result: `[(42732,)]`

> There are 42,732 near-Earth asteroids.

**single_domain** ❌

```sql
SELECT COUNT(*) AS hazardous_asteroids FROM asteroids WHERE is_pha = 1;
```
Raw result: `[(2550,)]`

> There are 2,550 near-Earth asteroids.

**cross_domain** ✅

```sql
SELECT COUNT(*) AS near_earth_asteroids FROM asteroids WHERE is_neo = 1;
```
Raw result: `[(42732,)]`

> There are 42,732 near-Earth asteroids.

## 3. How many asteroids will come within 1 million km of Earth in the next 10 years?

<details><summary>Gold SQL</summary>

```sql
SELECT COUNT(DISTINCT designation) FROM close_approaches WHERE approach_date BETWEEN date('now') AND date('now', '+10 years') AND dist_km < 1000000
```
</details>

**zero_shot** ⚠️

```sql
SELECT COUNT(DISTINCT designation) FROM close_approaches WHERE dist_km > 1000000 AND approach_date >= date('now') + INTERVAL '10 years';
```
Error: `OperationalError: near "'10 years'": syntax error`

> Sorry, I couldn't turn that into a working database query. Try rephrasing it, for example with a specific distance, date or asteroid name.

**single_domain** ✅

```sql
SELECT COUNT(DISTINCT designation) AS asteroids FROM close_approaches
WHERE approach_date BETWEEN date('now') AND date('now', '+10 years') AND dist_km < 1000000;
```
Raw result: `[(56,)]`

> There will be 56 asteroids that come within 1 million km of Earth in the next 10 years.

**cross_domain** ✅

```sql
SELECT COUNT(DISTINCT designation) FROM close_approaches WHERE dist_km < 1000000 AND approach_date >= date('now') AND approach_date <= date('now', '+10 years');
```
Raw result: `[(56,)]`

> There are 56 asteroids that will come within 1 million km of Earth in the next 10 years.

## 4. What is the closest an asteroid will come to Earth in the next year?

<details><summary>Gold SQL</summary>

```sql
SELECT dist_km FROM close_approaches WHERE approach_date BETWEEN date('now') AND date('now', '+1 year') ORDER BY dist_km LIMIT 1
```
</details>

**zero_shot** ❌

```sql
SELECT DISTINCT designation, approach_date FROM close_approaches WHERE approach_date >= date('now') AND approach_date < date('now', '+1 year')
ORDER BY dist_au ASC LIMIT 1;
```
Raw result: `[('2026 TP6', '2026-10-15')]`

> The closest an asteroid will come to Earth in the next year is 2026 TP6, which will approach on October 15, 2026.

**single_domain** ✅

```sql
SELECT ca.full_name, ca.approach_time, ca.dist_km, ca.dist_ld, ca.velocity_kms
FROM close_approaches ca JOIN asteroids a ON a.designation = ca.designation
WHERE ca.approach_date >= date('now') AND ca.approach_date < date('now', '+1 year')
ORDER BY ca.dist_km ASC LIMIT 1;
```
Raw result: `[('(2026 TP6)', '2026-10-15 00:01', 218957.62845064938, 0.5696088149080369, 10.286211071684)]`

> The closest an asteroid will come to Earth in the next year is (2026 TP6), which will approach on October 15, 2026. It will be about 218,958 km away, or approximately 0.57 lunar distances from Earth.

**cross_domain** ⚠️

```sql
SELECT c.full_name, c.dist_au, c.dist_km, c.dist_ld FROM close_approaches c
WHERE c.approach_date >= date('now') AND c.approach_date < date('now', '+1 year')
ORDER BY c.moid_au ASC LIMIT 1;
```
Error: `OperationalError: no such column: c.moid_au`

> Sorry, I couldn't turn that into a working database query. Try rephrasing it, for example with a specific distance, date or asteroid name.

## 5. When will Apophis pass Earth, and how close will it get?

<details><summary>Gold SQL</summary>

```sql
SELECT ca.dist_km FROM close_approaches ca JOIN asteroids a ON a.designation = ca.designation WHERE a.name = 'Apophis' AND ca.approach_date >= date('now') ORDER BY ca.approach_time LIMIT 1
```
</details>

**zero_shot** ❌

```sql
SELECT 
    c.approach_date AS "Closest Approach Date",
    c.dist_au AS "Distance from Earth (AU)",
    c.dist_ld AS "Distance from Earth (Lunar Distances)"
FROM 
    close_approaches c
JOIN 
    asteroids a ON c.designation = a.designation
WHERE 
    a.name = 'Apophis';
```
Raw result: `[('1907-04-13', 0.0286132572302756, 11.135489998544768), ('1914-11-06', 0.163107867004413, 63.47708012039274), ('1915-01-28', 0.122134946686818, 47.53155037046304), ('1922-12-19', 0.115350960684972, 4…`

Model's answer, rejected by the grounding check (date 2044-04-13 is not in the results):

> ~~Apophis will pass Earth on April 13, 2044, at a distance of about 8.03 AU (31.25 lunar distances).~~

Shown instead:

> The database returned 28 rows. First rows:
> • Closest Approach Date: 1907-04-13, Distance from Earth (AU): 0.02861, Distance from Earth (Lunar Distances): 11.14
> • Closest Approach Date: 1914-11-06, Distance from Earth (AU): 0.1631, Distance from Earth (Lunar Distances): 63.48
> • Closest Approach Date: 1915-01-28, Distance from Earth (AU): 0.1221, Distance from Earth (Lunar Distances): 47.53
> • Closest Approach Date: 1922-12-19, Distance from Earth (AU): 0.1154, Distance from Earth (Lunar Distances): 44.89
> • Closest Approach Date: 1924-04-13, Distance from Earth (AU): 0.1079, Distance from Earth (Lunar Distances): 41.98
> …and 23 more (see the results table).
> 
> (The model's wording included details that aren't in the data, so the raw result is shown instead.)

**single_domain** ✅

```sql
SELECT ca.full_name, ca.approach_time, ca.dist_km, ca.dist_ld, ca.velocity_kms
FROM close_approaches ca JOIN asteroids a ON a.designation = ca.designation
WHERE a.name = 'Apophis' AND ca.approach_date >= date('now')
ORDER BY ca.approach_time LIMIT 1;
```
Raw result: `[('99942 Apophis (2004 MN4)', '2029-04-13 21:46', 38011.45916295157, 0.0988851695186045, 7.42253895678452)]`

> Apophis will pass Earth on April 13, 2029. It will be about 38,011 kilometers (about 0.09889 lunar distances) away from Earth at that time.

**cross_domain** ❌

```sql
SELECT ca.approach_date, ca.dist_ld FROM close_approaches ca
JOIN asteroids a ON ca.designation = a.designation
WHERE a.name = 'Apophis' AND ca.approach_date >= date('now')
ORDER BY ca.approach_date ASC LIMIT 1;
```
Raw result: `[('2029-04-13', 0.0988851695186045)]`

> Apophis will pass Earth on April 13, 2029. It will be about 0.09889 lunar distances away from Earth at that time.

## 6. Which asteroid has the highest chance of hitting Earth?

<details><summary>Gold SQL</summary>

```sql
SELECT full_name FROM impact_risk ORDER BY impact_probability DESC LIMIT 1
```
</details>

**zero_shot** ✅

```sql
SELECT designation, full_name, impact_probability FROM impact_risk ORDER BY impact_probability DESC LIMIT 1;
```
Raw result: `[('2010 RF12', '(2010 RF12)', 0.102637259069)]`

> The asteroid with the highest chance of hitting Earth is 2010 RF12, with an impact probability of about 1 in 9.

**single_domain** ✅

```sql
SELECT full_name, impact_probability, first_year, last_year FROM impact_risk ORDER BY impact_probability DESC LIMIT 1;
```
Raw result: `[('(2010 RF12)', 0.102637259069, 2095, 2122)]`

> The asteroid with the highest chance of hitting Earth is (2010 RF12), with a 1 in 9.76 probability of impact between 2095 and 2122.

**cross_domain** ✅

```sql
SELECT designation, full_name, impact_probability FROM impact_risk ORDER BY impact_probability DESC LIMIT 1;
```
Raw result: `[('2010 RF12', '(2010 RF12)', 0.102637259069)]`

> The asteroid with the highest chance of hitting Earth is 2010 RF12, with an impact probability of about 1 in 9.

## 7. How many potentially hazardous asteroids are bigger than 1 km?

<details><summary>Gold SQL</summary>

```sql
SELECT COUNT(*) FROM asteroids WHERE is_pha = 1 AND diameter_est_km > 1
```
</details>

**zero_shot** ✅

```sql
SELECT COUNT(*) AS count FROM asteroids WHERE is_pha = 1 AND diameter_est_km > 1;
```
Raw result: `[(156,)]`

> There are 156 potentially hazardous asteroids bigger than 1 km.

**single_domain** ✅

```sql
SELECT COUNT(*) AS hazardous_asteroids FROM asteroids WHERE is_pha = 1 AND diameter_est_km > 1;
```
Raw result: `[(156,)]`

> There are 156 potentially hazardous asteroids bigger than 1 km.

**cross_domain** ✅

```sql
SELECT COUNT(*) AS potentially_hazardous_asteroids FROM asteroids WHERE is_pha = 1 AND diameter_est_km > 1;
```
Raw result: `[(156,)]`

> There are 156 potentially hazardous asteroids bigger than 1 km.

## 8. What is the largest asteroid?

<details><summary>Gold SQL</summary>

```sql
SELECT full_name FROM asteroids ORDER BY diameter_est_km DESC LIMIT 1
```
</details>

**zero_shot** ✅

```sql
SELECT full_name, diameter_est_km FROM asteroids ORDER BY diameter_est_km DESC LIMIT 1;
```
Raw result: `[('136199 Eris (2003 UB313)', 6345.428620404627)]`

> The largest asteroid is 136199 Eris (2003 UB313), with an estimated diameter of 6,345 km.

**single_domain** ✅

```sql
SELECT full_name, diameter_est_km FROM asteroids ORDER BY diameter_est_km DESC LIMIT 1;
```
Raw result: `[('136199 Eris (2003 UB313)', 6345.428620404627)]`

> The largest asteroid is 136199 Eris (2003 UB313), with an estimated diameter of 6,345 km.

**cross_domain** ✅

```sql
SELECT full_name, diameter_est_km FROM asteroids ORDER BY diameter_est_km DESC LIMIT 1;
```
Raw result: `[('136199 Eris (2003 UB313)', 6345.428620404627)]`

> The largest asteroid is 136199 Eris (2003 UB313), with an estimated diameter of 6,345 km.

## 9. Which asteroids passed closer than the Moon in 2025?

<details><summary>Gold SQL</summary>

```sql
SELECT full_name FROM close_approaches WHERE approach_date BETWEEN '2025-01-01' AND '2025-12-31' AND dist_ld < 1
```
</details>

**zero_shot** ❌

```sql
SELECT designation, full_name, dist_ld FROM close_approaches WHERE approach_date LIKE '2025%' AND dist_ld < 1 ORDER BY dist_ld ASC LIMIT 25;
```
Raw result: `[('2025 UC11', '(2025 UC11)', 0.017167496998414213), ('2025 TF', '(2025 TF)', 0.017639096773634316), ('2025 BP6', '(2025 BP6)', 0.02526522407998759), ('2025 OS', '(2025 OS)', 0.027206273926983066), ('…`

> There are 25 asteroids that passed closer than the Moon in 2025. The closest was 2025 UC11, which came within about 0.017 LD of the Moon.

**single_domain** ✅

```sql
SELECT ca.full_name, ca.approach_time, ca.dist_km, ca.dist_ld, ca.velocity_kms
FROM close_approaches ca JOIN asteroids a ON a.designation = ca.designation
WHERE ca.approach_date BETWEEN '2025-01-01' AND '2025-12-31' AND ca.dist_ld < 1
ORDER BY ca.dist_km;
```
Raw result: `[('(2025 UC11)', '2025-10-30 12:11', 6599.185846190423, 0.017167496998414213, 11.3649293026491), ('(2025 TF)', '2025-10-01 00:49', 6780.468799785031, 0.017639096773634316, 20.8761143006887), ('(2025 B…`

> There were 189 asteroids that passed closer than the Moon in 2025. The closest asteroid was (2025 UC11) with a distance of 6,599 km or 0.01717 lunar distances.

**cross_domain** ✅

```sql
SELECT a.designation, a.full_name, ca.dist_ld FROM asteroids a JOIN close_approaches ca ON a.designation = ca.designation
WHERE ca.approach_date LIKE '2025%' AND ca.dist_ld < 1;
```
Raw result: `[('2025 AC', '(2025 AC)', 0.36477988277905565), ('2025 AB', '(2025 AB)', 0.39835419283693424), ('2025 AZ3', '(2025 AZ3)', 0.5937194654325026), ('2025 BA1', '(2025 BA1)', 0.7158148662373167), ('2025 BD…`

> There were 189 asteroids that passed closer than the Moon in 2025. The top few are:
> - (2025 AC) with a distance of 0.3648 lunar distances
> - (2025 AB) with a distance of 0.3984 lunar distances
> - (2025 AZ3) with a distance of 0.5937 lunar distances
> - (2025 BA1) with a distance of 0.7158 lunar distances
> - (2025 BD) with a distance of 0.6258 lunar distances

## 10. How many asteroids have names?

<details><summary>Gold SQL</summary>

```sql
SELECT COUNT(*) FROM asteroids WHERE name IS NOT NULL
```
</details>

**zero_shot** ✅

```sql
SELECT COUNT(DISTINCT name) FROM asteroids WHERE name IS NOT NULL;
```
Raw result: `[(26567,)]`

> There are 26,567 asteroids with names in the database.

**single_domain** ✅

```sql
SELECT COUNT(*) AS asteroids_with_names FROM asteroids WHERE name IS NOT NULL;
```
Raw result: `[(26567,)]`

> There are 26,567 asteroids with names in the database.

**cross_domain** ✅

```sql
SELECT COUNT(DISTINCT name) FROM asteroids WHERE name IS NOT NULL;
```
Raw result: `[(26567,)]`

> There are 26,567 asteroids with names in the database.

## 11. What percentage of near-Earth asteroids are potentially hazardous?

<details><summary>Gold SQL</summary>

```sql
SELECT 100.0 * SUM(is_pha) / COUNT(*) FROM asteroids WHERE is_neo = 1
```
</details>

**zero_shot** ✅

```sql
SELECT CAST(SUM(CASE WHEN is_pha = 1 THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(*) FROM asteroids WHERE is_neo = 1;
```
Raw result: `[(5.967424880651502,)]`

> 5.97% of near-Earth asteroids are potentially hazardous.

**single_domain** ✅

```sql
SELECT CAST(SUM(CASE WHEN is_pha = 1 THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(*) FROM asteroids WHERE is_neo = 1;
```
Raw result: `[(5.967424880651502,)]`

> 5.97% of near-Earth asteroids are potentially hazardous.

**cross_domain** ✅

```sql
SELECT CAST(SUM(CASE WHEN is_pha = 1 THEN 1 ELSE 0 END) AS REAL) * 100 / COUNT(*) FROM asteroids WHERE is_neo = 1;
```
Raw result: `[(5.967424880651502,)]`

> 5.97% of near-Earth asteroids are potentially hazardous.

## 12. Which upcoming year will have the most asteroid flybys closer than the Moon?

<details><summary>Gold SQL</summary>

```sql
SELECT substr(approach_date, 1, 4) FROM close_approaches WHERE dist_ld < 1 AND approach_date >= date('now') GROUP BY 1 ORDER BY COUNT(*) DESC LIMIT 1
```
</details>

**zero_shot** ⚠️

```sql
SELECT T2.year, COUNT(DISTINCT T1.designation) AS flyby_count
FROM close_approaches AS T1
JOIN (
    SELECT DISTINCT approach_date, YEAR(approach_date) AS year
    FROM close_approaches
    WHERE dist_ld < 1 AND approach_date > date('now')
) AS T2 ON T1.approach_date = T2.approach_date
GROUP BY T2.year
ORDER BY flyby_count DESC
LIMIT 1;
```
Error: `OperationalError: no such function: YEAR`

> Sorry, I couldn't turn that into a working database query. Try rephrasing it, for example with a specific distance, date or asteroid name.

**single_domain** ❌

```sql
SELECT ca.approach_date, COUNT(*) AS flybys FROM close_approaches ca
WHERE ca.dist_ld < 1 AND ca.approach_date >= date('now')
GROUP BY ca.approach_date ORDER BY flybys DESC LIMIT 1;
```
Raw result: `[('2189-11-18', 1)]`

> In 2189, there will be 1 asteroid flyby closer than the Moon.

**cross_domain** ⚠️

```sql
SELECT T2.approach_date, COUNT(T1.designation) AS flybys FROM close_approaches AS T1
JOIN asteroids AS T2 ON T1.designation = T2.designation
WHERE T1.dist_ld < 1 AND T1.approach_date > date('now')
GROUP BY T2.approach_date ORDER BY flybys DESC LIMIT 1;
```
Error: `OperationalError: no such column: T2.approach_date`

> Sorry, I couldn't turn that into a working database query. Try rephrasing it, for example with a specific distance, date or asteroid name.

## 13. What is the fastest an asteroid has ever flown past Earth?

<details><summary>Gold SQL</summary>

```sql
SELECT MAX(velocity_kms) FROM close_approaches WHERE approach_date <= date('now')
```
</details>

**zero_shot** ✅

```sql
SELECT MAX(velocity_kms) AS max_velocity FROM close_approaches;
```
Raw result: `[(67.3744736543721,)]`

> The fastest asteroid ever to fly past Earth has been recorded at 67.37 km/s.

**single_domain** ✅

```sql
SELECT full_name, velocity_kms FROM close_approaches ORDER BY velocity_kms DESC LIMIT 1;
```
Raw result: `[('(2020 BZ12)', 67.3744736543721)]`

> The fastest asteroid to fly past Earth has been (2020 BZ12), which flew at a velocity of 67.37 km/s.

**cross_domain** ✅

```sql
SELECT MAX(velocity_kms) AS max_velocity FROM close_approaches;
```
Raw result: `[(67.3744736543721,)]`

> The fastest asteroid ever to fly past Earth has been recorded at 67.37 km/s.

## 14. How many asteroids have orbits that come within 0.05 au of Earth's orbit?

<details><summary>Gold SQL</summary>

```sql
SELECT COUNT(*) FROM asteroids WHERE moid_au <= 0.05
```
</details>

**zero_shot** ⚠️

```sql
SELECT COUNT(DISTINCT designation) FROM close_approaches WHERE moid_au <= 0.05;
```
Error: `OperationalError: no such column: moid_au`

> Sorry, I couldn't turn that into a working database query. Try rephrasing it, for example with a specific distance, date or asteroid name.

**single_domain** ⚠️

```sql
SELECT COUNT(DISTINCT designation) AS asteroids FROM close_approaches WHERE moid_au <= 0.05;
```
Error: `OperationalError: no such column: moid_au`

> Sorry, I couldn't turn that into a working database query. Try rephrasing it, for example with a specific distance, date or asteroid name.

**cross_domain** ⚠️

```sql
SELECT COUNT(DISTINCT designation) FROM close_approaches WHERE moid_au <= 0.05;
```
Error: `OperationalError: no such column: moid_au`

> Sorry, I couldn't turn that into a working database query. Try rephrasing it, for example with a specific distance, date or asteroid name.

## 15. Is any asteroid going to hit Earth?

**zero_shot** 📝

```sql
SELECT 'UNANSWERABLE' AS status, 'No data available for future impact probabilities.' AS reason;
```
Raw result: `[('UNANSWERABLE', None)]`

> I can only answer from the NASA asteroid data in this database, and it doesn't contain that. It covers asteroid sizes, orbits, Earth flybys (1900-2200) and impact risk, but not things like mass, composition, who discovered them, or today's date. Try a question about one of those, for example "What is the largest asteroid?"

**single_domain** 📝

```sql
SELECT 'UNANSWERABLE' AS status, 'No data available for future impact predictions.' AS reason;
```
Raw result: `[('UNANSWERABLE', None)]`

> I can only answer from the NASA asteroid data in this database, and it doesn't contain that. It covers asteroid sizes, orbits, Earth flybys (1900-2200) and impact risk, but not things like mass, composition, who discovered them, or today's date. Try a question about one of those, for example "What is the largest asteroid?"

**cross_domain** 📝

```sql
SELECT 'UNANSWERABLE' AS status, 'No data available for future impact risk predictions.' AS reason;
```
Raw result: `[('UNANSWERABLE', None)]`

> I can only answer from the NASA asteroid data in this database, and it doesn't contain that. It covers asteroid sizes, orbits, Earth flybys (1900-2200) and impact risk, but not things like mass, composition, who discovered them, or today's date. Try a question about one of those, for example "What is the largest asteroid?"

## 16. Will we have a problem with any of the biggest near-Earth asteroids?

**zero_shot** 📝

```sql
SELECT 'UNANSWERABLE' AS status, 'No data available for future impact probabilities.' AS reason;
```
Raw result: `[('UNANSWERABLE', None)]`

> I can only answer from the NASA asteroid data in this database, and it doesn't contain that. It covers asteroid sizes, orbits, Earth flybys (1900-2200) and impact risk, but not things like mass, composition, who discovered them, or today's date. Try a question about one of those, for example "What is the largest asteroid?"

**single_domain** 📝

```sql
SELECT 'UNANSWERABLE' AS status, 'No data available for future impact risk assessment.' AS reason;
```
Raw result: `[('UNANSWERABLE', None)]`

> I can only answer from the NASA asteroid data in this database, and it doesn't contain that. It covers asteroid sizes, orbits, Earth flybys (1900-2200) and impact risk, but not things like mass, composition, who discovered them, or today's date. Try a question about one of those, for example "What is the largest asteroid?"

**cross_domain** 📝

```sql
SELECT 'UNANSWERABLE' AS status, 'No data available for future impact probabilities.' AS reason;
```
Raw result: `[('UNANSWERABLE', None)]`

> I can only answer from the NASA asteroid data in this database, and it doesn't contain that. It covers asteroid sizes, orbits, Earth flybys (1900-2200) and impact risk, but not things like mass, composition, who discovered them, or today's date. Try a question about one of those, for example "What is the largest asteroid?"

## 17. How many elephants does the heaviest asteroid weigh?

**zero_shot** 📝

```sql
SELECT 'UNANSWERABLE' AS status, 'Asteroids do not have mass or weight.' AS reason;
```
Raw result: `[('UNANSWERABLE', None)]`

> I can only answer from the NASA asteroid data in this database, and it doesn't contain that. It covers asteroid sizes, orbits, Earth flybys (1900-2200) and impact risk, but not things like mass, composition, who discovered them, or today's date. Try a question about one of those, for example "What is the largest asteroid?"

**single_domain** 📝

```sql
SELECT 'UNANSWERABLE' AS status, 'mass data is not available in the schema' AS reason;
```
Raw result: `[('UNANSWERABLE', None)]`

> I can only answer from the NASA asteroid data in this database, and it doesn't contain that. It covers asteroid sizes, orbits, Earth flybys (1900-2200) and impact risk, but not things like mass, composition, who discovered them, or today's date. Try a question about one of those, for example "What is the largest asteroid?"

**cross_domain** 📝

```sql
SELECT 'UNANSWERABLE' AS status, 'mass data not available in the schema' AS reason;
```
Raw result: `[('UNANSWERABLE', None)]`

> I can only answer from the NASA asteroid data in this database, and it doesn't contain that. It covers asteroid sizes, orbits, Earth flybys (1900-2200) and impact risk, but not things like mass, composition, who discovered them, or today's date. Try a question about one of those, for example "What is the largest asteroid?"

## 18. What day of the week is it today?

**zero_shot** 📝

```sql
SELECT 'UNANSWERABLE' AS status, 'Today\'s weekday is not available in this database.' AS reason
```
Raw result: `[('UNANSWERABLE', None)]`

> I can only answer from the NASA asteroid data in this database, and it doesn't contain that. It covers asteroid sizes, orbits, Earth flybys (1900-2200) and impact risk, but not things like mass, composition, who discovered them, or today's date. Try a question about one of those, for example "What is the largest asteroid?"

**single_domain** 📝

```sql
SELECT 'UNANSWERABLE' AS status, 'Today's weekday is not available in this database.' AS reason;
```
Raw result: `[('UNANSWERABLE', None)]`

> I can only answer from the NASA asteroid data in this database, and it doesn't contain that. It covers asteroid sizes, orbits, Earth flybys (1900-2200) and impact risk, but not things like mass, composition, who discovered them, or today's date. Try a question about one of those, for example "What is the largest asteroid?"

**cross_domain** 📝

```sql
SELECT 'UNANSWERABLE' AS status, 'Today's weekday is not available in this database.' AS reason;
```
Raw result: `[('UNANSWERABLE', None)]`

> I can only answer from the NASA asteroid data in this database, and it doesn't contain that. It covers asteroid sizes, orbits, Earth flybys (1900-2200) and impact risk, but not things like mass, composition, who discovered them, or today's date. Try a question about one of those, for example "What is the largest asteroid?"
