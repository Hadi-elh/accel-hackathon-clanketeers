# CONTRACTS — frozen interfaces

These shapes are agreed at T+0:15 and **do not change** without a team sync.
Build against them. Do not wait for someone else's code.

---

## 1. Notice

Produced by `/ingest`, consumed by `/models` and `/app`.

```json
{
  "id": "gmb-2026-412887",
  "source_url": "https://zoek.officielebekendmakingen.nl/gmb-2026-412887.html",
  "title": "Aanvraag omgevingsvergunning, transformatie bedrijfspand",
  "body": "Burgemeester en wethouders maken bekend dat een aanvraag is ontvangen voor het transformeren en uitbreiden van het bestaande bedrijfspand aan de ...",
  "published_on": "2026-09-23",
  "municipality": "Amsterdam",
  "rubriek": "omgevingsvergunning",
  "lat": 52.3421,
  "lng": 4.8712
}
```

Rules:
- `id` is the KOOP identifier, unique, used as primary key.
- `body` is plain text, not HTML. Strip markup in `/ingest`.
- `lat`/`lng` may be `null`. Downstream must handle that (treat as "unknown location",
  do not silently drop — count it in the funnel as `location_unknown`).

**Fallback:** if SRU is not working by T+0:20, `/ingest/sample_notices.json` contains a
real cached list in exactly this shape. Everyone builds against that file regardless.

---

## 2. Company profile

```json
{
  "id": "vandijk",
  "name": "Van Dijk Techniek",
  "lat": 52.3702,
  "lng": 4.8952,
  "radius_km": 35,
  "services": [
    "commercial electrical installations",
    "EV charging infrastructure",
    "access control systems",
    "commercial lighting"
  ],
  "preferred_property_types": ["office", "warehouse", "retail", "hospitality", "multi-unit residential"],
  "excluded_project_types": ["single-family minor renovation", "tree removal", "events", "private gardens"]
}
```

Stored in `/app/profiles/vandijk.json` and in the `company_profiles` table.

---

## 3. Model output

Returned by the classifier, enforced with structured outputs.

```json
{
  "decision": "relevant",
  "confidence": 0.93,
  "project_type": "commercial renovation",
  "property_type": "office",
  "matched_services": ["commercial electrical installations"],
  "project_stage": "permit_application",
  "evidence": "transformeren en uitbreiden van het bestaande bedrijfspand",
  "reason": "Substantial modification of a commercial property inside the service area."
}
```

Allowed values:

- `decision`: `"relevant" | "irrelevant" | "uncertain"`
- `confidence`: float 0.0–1.0
- `project_stage`: `"permit_application" | "permit_granted" | "zoning" | "other"`
- `evidence`: **verbatim substring of `notice.body`**. If it is not a substring, the
  result is invalid and must be escalated.
- `matched_services`: subset of the profile's `services`, may be empty.

JSON schema lives at `/models/schema.json`. Single source of truth for the API call.

**Rule-based decisions:** `/models/rules.py` may reject a notice for free, with no model
call. Stored in `signals` with `model_used = 'rules:rN'` (rN = `rules.RULES_VERSION`) and
**no corresponding `model_runs` row** — rules never call a model, so nothing to log.
Their `confidence` is a declared constant (`rules.RULE_CONFIDENCE`), not a measured
probability.

**Confidence is never user-facing.** `confidence` (model or rule) exists for routing and
eval only. No UI may render it as a percentage or score — see the product boundary.

---

## 4. Function signatures

These are the only cross-folder dependencies. Everything else is internal.

```python
# /ingest/fetch.py  — owner A
def fetch_notices(date: str, profile: dict) -> list[dict]:
    """Fetch + prefilter. Returns Notice dicts (section 1).
    Prefilter drops: wrong rubriek, outside radius_km. Never calls a model."""

def prefilter_stats() -> dict:
    """Funnel counters for the UI, across the whole notices table (no date filter).
    All real, never hard-coded.
    {"fetched": 1284, "in_region": 46, "plausible_rubriek": 31, "location_unknown": 3,
     "location_unknown_kept": 3, "dropped_by_municipality": 0}"""

def prefilter_stats_for_date(target_date: str, profile: dict | None = None) -> dict:
    """Same funnel, scoped to one scan date. Adds "date" and "geo_inferred_in_region".
    This is the dict C stores verbatim into scan_runs.prefilter_stats (jsonb)."""
```

`kept == plausible_rubriek + location_unknown_kept` always holds — A asserts this
identity. `fetched`, `plausible_rubriek`, `location_unknown_kept` are stable contract
keys; every other key in the funnel dict (`in_region`, `location_unknown`,
`dropped_by_municipality`, `geo_inferred_in_region`, ...) is diagnostic and may change
without a sync.

```python
# /models/router.py  — owner B
def classify_notice(notice: dict, profile: dict) -> dict:
    """Returns the model output (section 3) plus:
       'escalated': bool, 'model_used': str, 'latency_ms': int, 'cost_eur': float
    Handles validation, retry, escalation and logging internally.
    Never raises: on total failure returns decision='uncertain' with
    'error': '<reason>'."""
```

```python
# /app/api.py  — owner C
POST /api/scan       body: {"profile_id": "vandijk", "date": "2026-09-23"}
GET  /api/signals    query: ?profile_id=vandijk        -> ranked signals + funnel stats
GET  /api/benchmark                                     -> current comparison table
```

**Stub rule:** until B ships, C uses a stub `classify_notice` that returns a fixed
"relevant" result after a 200 ms sleep. When B's version lands, C changes one import.
No integration crunch at hour three.

**`scan_runs` table:** one row per `POST /api/scan` call. **`/app`'s scan orchestrator
is the only writer** — A and B never insert into it. Written from `fetch_notices()`'s
count, `prefilter_stats_for_date()` (stored whole, in `prefilter_stats` jsonb), and the
resulting `signals` rows for that scan (`rule_rejected`, `ai_analysed`, `escalated`,
`uncertain`, `relevant` are counts; `no_text` counts rows with
`error='empty_or_short_body'`). `cost_eur` is the sum of that scan's `model_runs.cost_eur`,
or `null` if any contributing row has a `null` cost. See `schema.sql` for columns.

---

## 5. Eval contract

```json
{
  "notice_id": "gmb-2026-412887",
  "expected_decision": "relevant",
  "expected_category": "renovation",
  "expected_service": "electrical",
  "expected_evidence": "transformeren en uitbreiden van het bestaande bedrijfspand",
  "labeller": "hadi",
  "split": "test"
}
```

Set composition, fixed: **20 relevant, 20 irrelevant, 10 borderline.** A random sample
would be ~95% irrelevant and a model that always says "irrelevant" would score 95%.

`split` is `"test"` (human-labelled, never trained on) or `"train"` (fine-tune only,
may be model-generated).

Config names used in `eval_results.config`, exactly these strings:
`"small"`, `"large"`, `"router"`, `"baseline_closed"`, `"baseline_open"`.
(`"finetuned"` is dropped: Nemotron 3 Nano has no LoRA fine-tuning on Nebius — see
`/models/PRICES.md`.)

**Borderline flag:** `eval_items`/`eval_results` have no borderline column. The flag
lives in `/eval/borderline.txt` — one `notice_id` per line, optional. Absent from the
file means "not borderline", not "unknown."

**Cost currency:** always EUR. Every `cost_eur` column (`model_runs`, `eval_results`,
`scan_runs`) is converted from Nebius's USD list price at the ECB reference rate
recorded in `/models/PRICES.md`. Never store USD directly; a missing price gives
`cost_eur = null`, never a guessed number.
