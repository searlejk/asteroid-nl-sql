# Sample questions: one that worked, one that didn't

Both are real outputs from the app. They use the single-domain few-shot strategy (the app's default), with the local Qwen2.5-Coder-3B model, run on 2026-10-13. The full logs are in [responses/](responses/).

## A question it did well on

**Question:** When will Apophis pass Earth, and how close will it get?

**SQL it generated:**
```sql
SELECT ca.full_name, ca.approach_time, ca.dist_km, ca.dist_ld, ca.velocity_kms
FROM close_approaches ca JOIN asteroids a ON a.designation = ca.designation
WHERE a.name = 'Apophis' AND ca.approach_date >= date('now')
ORDER BY ca.approach_time LIMIT 1;
```

**Raw result:** `[('99942 Apophis (2004 MN4)', '2029-04-13 21:46', 38011.45916295157, 0.0988851695186045, 7.42253895678452)]`

**Friendly response:** Apophis will pass Earth on April 13, 2029. It will be about 38,011 kilometers (about 0.09889 lunar distances) away from Earth at that time.

**Why it worked:** this needs a join, because the name "Apophis" is in `asteroids` and the flybys are in `close_approaches`. It also needs a "from today on" filter and the right ordering to get the *next* pass. The model got all three. The answer matches NASA's published figure for the 2029 flyby, which brings Apophis closer than geostationary satellites. One of the single-domain examples showed the model the same name-to-flyby join for a different asteroid (Bennu), and that clearly helped. Zero-shot and cross-domain both got this question wrong.

## A question it tripped up on

**Question:** How many near-Earth asteroids are there?

**SQL it generated:**
```sql
SELECT COUNT(*) AS hazardous_asteroids FROM asteroids WHERE is_pha = 1;
```

**Raw result:** `[(2550,)]`

**Friendly response:** There are 2,550 near-Earth asteroids.

**What went wrong:** the correct query is `WHERE is_neo = 1`, which gives **42,732**. The model instead copied one of its single-domain examples almost word for word ("How many potentially hazardous asteroids are there?"). So it counted the 2,550 *potentially hazardous* asteroids, a much smaller group. The column alias even says `hazardous_asteroids`. The friendly-response step then reported that number as "near-Earth asteroids", hiding the mistake.

This is an easy question, and the zero-shot and cross-domain strategies both got it right. The examples that help with hard questions made this easy one worse, because the model pattern-matched on the most similar example instead of reading the question. It's a lot like the dog-show example in the class sample post: the query ran fine, but the user got a confident, wrong answer. The app's checks don't catch it, because 2,550 really is in the results. They verify that an answer's numbers come from the data, not that the query asked the right thing.
