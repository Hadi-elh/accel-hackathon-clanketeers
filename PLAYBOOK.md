# ReguLine — Build & Pitch Playbook

**AI Innovate Amsterdam (AISO × Accel) — Future Founders track**
Single source of truth for the day. Read sections 0–3 before the event. Follow section 10 during it.

---

## 0. The 60-second version

Every day Dutch authorities publish roughly a thousand-plus official notices: permits granted, buildings being transformed, charging points approved, zoning changed. It is free, public, and unreadable — it is written for legal compliance, not for sales.

A 28-person electrical installer in Amsterdam does not want 1,400 government notices. They want the four that mean *someone near me is about to need what I sell*.

ReguLine reads the whole stream and returns only the notices that matter to one specific company, with the sentence that proves it and a link to the official source.

The economics only work because of model choice. At thousands of documents per day, running a frontier model on everything destroys the margin. We run a small open model on Nebius Token Factory for the easy calls, escalate only uncertain cases to a large model, and measure exactly what that saves.

**Pitch one-liner: the data is free — the judgement is the product.**

**Company one-liner (use this, not "leads for installers"): public document streams are huge, free and useless without judgement. We turn them into qualified, company-specific commercial signals — starting with Dutch permits.**

---

## 1. What we are being judged on

| Criterion | Weight | What wins it |
|---|---|---|
| Product and user value | 25% | Works end to end on real public data for one named customer |
| Problem and company potential | 20% | Proven willingness to pay + a mechanism for why we win over time |
| Measurable model advantage | 20% | Hand-labelled eval, 3+ configs, precision/recall/F1/cost/latency |
| Technical execution & Token Factory use | 20% | Deterministic prefilter, routing, structured outputs, retries, telemetry |
| Demo clarity | 10% | The funnel: 1,284 notices → 3 opportunities |
| Responsible design | 5% | Business signals not citizen profiling, evidence, human in the loop |

### Realistic score projection (if we execute)

- Product/user value: **19–21 / 25** — capped because no real customer is in the room.
- Problem/company potential: **11–14 / 20 by default**, **16–18 with the positioning in §3**. This is where we either fix it or lose it.
- Measurable model advantage: **17–19 / 20** — our strongest. Volume makes cost-per-document the actual P&L, so the benchmark is a business artefact, not an academic one.
- Technical execution: **16–18 / 20** — full marks need reliability *shown*, not claimed.
- Demo clarity: **6–9 / 10** — permits are dry; the funnel contrast is the whole game.
- Responsible design: **4–5 / 5** — cheap points, one slide.

**Total: ~73–86.** Top-8 pitch slot in most rooms, winnable if the demo lands and the company framing is right.

### Submission fields (from the form)

1. Live product link (optional on paper — treat as required)
2. What did you build and what problem does it solve
3. Models and Token Factory use
4. Measurable model advantage — **with a public link to proof**
5. Responsible design
6. Pitch slides — public link, opened on the stage computer, test in incognito. **A criterion you skip scores zero.** 5 minutes including live demo.

Consequences: the eval must end up on a public URL, the product must be hosted early, slides must be public (Google Slides, not a local PDF or a login-gated Figma).

---

## 2. The product

### 2.1 Definition

> ReguLine watches every new Dutch government notice and tells a local SME which ones signal a potential customer or project for their specific business, why it matters, and where the evidence came from.

Call the output a **project signal**, never a guaranteed lead. A permit proves something is happening. It does not prove the applicant still needs an installer. Existing products in this market make the same distinction — copying that honesty is a credibility win, not a weakness.

### 2.2 The demo customer (fixed, concrete, one only)

| Attribute | Value |
|---|---|
| Company | Van Dijk Techniek (fictional, labelled as such) |
| Size | 28 employees |
| Base | Amsterdam |
| Service radius | 35 km |
| Services | Commercial electrical installation, EV charging, access control, commercial lighting |
| Wants | Office renovations, warehouses, retail, hospitality, multi-unit residential |
| Does not want | Single-home dakkapellen, tree permits, private gardens, events |
| Project size | €10k–€250k |
| Buyer | Owner / commercial director / sales manager |

Configured once. Runs continuously. That recurring-value property is what fixes the "would they actually open this daily?" problem — **it is a push product**. Value arrives as an alert; frequency of use is how often something worth having is delivered, not how often someone logs in.

### 2.3 Job to be done

Answers exactly: *"What happened in my market today that might create business for me?"*

Not "what permits were published?" and definitely not "would you like to chat with an AI about permits?" The LLM should be invisible in the UX. The user sees opportunities.

### 2.4 The one screen

```
┌───────────────────────────────────────────────────────────────┐
│ REGULINE                                     Van Dijk ⚡   │
├───────────────────────────────────────────────────────────────┤
│  TODAY                                                        │
│                                                               │
│  1,284 official notices scanned                               │
│     46 within your region                                     │
│      7 matched your business                                  │
│      3 high-priority project signals                          │
│                                                               │
│  ┌───────────────────────────────────────────────────────┐    │
│  │ 92% MATCH                                             │    │
│  │ Commercial property transformation                    │    │
│  │ Amsterdam-Zuid · 4.8 km                               │    │
│  │                                                       │    │
│  │ WHY THIS MATCHES                                      │    │
│  │ Large commercial renovation within your service area, │    │
│  │ likely to require electrical infrastructure work.     │    │
│  │                                                       │    │
│  │ Evidence: "...transformeren en uitbreiden van het     │    │
│  │ bestaande bedrijfspand..."                            │    │
│  │ Source: Gemeenteblad Amsterdam · today                │    │
│  │ [View official source]                     [Save]     │    │
│  └───────────────────────────────────────────────────────┘    │
│                          MAP                                  │
└───────────────────────────────────────────────────────────────┘
```

**Every number on that screen must come from a real query. Do not hard-code "1,284".** If a judge asks where the number came from and it is fake, the whole submission loses trust.

### 2.5 Detail card (include the model-routing strip — it is for the judges)

```
PROJECT SIGNAL — Commercial property renovation        Match: HIGH

Why ReguLine surfaced this
  ✓ Commercial property      ✓ Significant renovation
  ✓ Within 35 km             ✓ Matches electrical installation services

Evidence   "...transformeren en uitbreiden van het bestaande bedrijfspand..."
Source     Gemeenteblad Amsterdam · 23 September 2026 · [official link]

Model decision
  Small model → uncertain → escalated → reasoning model → RELEVANT
```

---

## 3. Business case (this is the 20% we must not lose)

### 3.1 The market exists and already pays

Permit-derived lead products are already sold in the Netherlands on recurring subscriptions (Kansradar, Slicegraph, Bouwberichten, DutchSignals and similar). **Verify the current price points yourself before quoting them on stage** — the figures circulating are roughly €49–€99/month entry tiers.

This is good news, not bad: it proves willingness to pay. Never say "nobody is doing this." Say "people already pay for the raw version; we sell the judgement layer."

### 3.2 Positioning table

| Existing category | ReguLine |
|---|---|
| Generic industry filters | Company-specific semantic fit |
| Keyword configuration | Natural-language business profile |
| Every item processed identically | Cost-aware model routing |
| Opaque scoring | Evidence-backed reasoning, quoted sentence |
| Generic "AI-powered" claim | Published precision/recall/cost benchmark |
| Hidden unit economics | Open-model economics quantified |
| Static vendor model | Feedback-driven per-customer adapters |

### 3.3 The scale-up story — do it in this order

Vertical-expansion talk ("later we do insurance") is what every team says. It answers *where else could you sell* while dodging *why do you win, and why does it get harder to beat you over time*. Three moves make it land:

**1. Expand sideways before outward.** The same permit stream already serves solar installers, HVAC, roofers, contractors, property developers. Same pipeline, same data, new profile. This is demoable today: swap the profile, same notices, different output. Do that live if there is time — it is worth more than any slide.

**2. The engine is the company, not the vertical.** Permits are the first stream, not the product. Adding a stream should be config, not a rebuild. If we can honestly say *"adding a second source took us 40 minutes"*, expansion becomes believable rather than aspirational.

**3. Name the compounding asset.** Every save / dismiss / "this was useless" is a labelled example of what a real company considers commercially relevant. Those corrections fine-tune that customer's model. The product gets more accurate per customer over time, and a competitor starting fresh has the same free feed and none of the judgement.

> **The strongest sentence in the pitch:** "The feed is a commodity. Our customers' corrections are not — every dismissal trains their model, and a competitor starting today has the same public data and none of our judgement."

This is also why the fine-tuning work is not a benchmark trick — it is the moat, demonstrated.

### 3.4 Market sizing — do it honestly

**Do not** write `1.6M SMEs × €100 = €1.9B TAM`. It is lazy and a VC will dock you for it.

Do say: tens of thousands of installation and contracting firms in the Netherlands alone; lead generation is already a budget line they pay for; the same public-notice infrastructure exists in every EU member state, so the expansion path is geographic as well as vertical.

### 3.5 Pricing hypothesis (label it as a hypothesis)

| Plan | Scope |
|---|---|
| €49/mo | One territory, one service profile |
| €99/mo | Larger territory, several service categories |
| €249+/mo | Teams, CRM export, real-time alerts, enrichment |

Framed as "a pricing hypothesis informed by what comparable products charge today", not as validated prices.

### 3.6 Long-term vision (mention in one sentence, do not build)

Today: permit → opportunity. Tomorrow: any public event → commercial signal — planning decisions, environmental approvals, subsidies, procurement, licences, corporate filings. *An intent-data layer for the physical economy.*

---

## 4. Data source

- **What:** Officiële Bekendmakingen — Staatscourant, Staatsblad, gemeenteblad, provincieblad, waterschapsblad.
- **Owner:** KOOP. **Licence:** CC0 1.0. Public, reusable, no negotiation needed.
- **Interface:** SRU 2.0. Two endpoints seen in the wild — verify which works on the day:
  - `https://repository.overheid.nl/sru`
  - `https://zoek.officielebekendmakingen.nl/sru/Search?version=1.2&operation=searchRetrieve&x-connection=oep&startRecord=1&maximumRecords=10&query=...`
- **Format:** XML. Docs are in Dutch. Budget for friction.
- **Useful metadata exposed:** municipality, postcode, publication date, document type/rubriek, geometry/coordinates (radius search supported), reaction/objection deadline, links to HTML/XML/PDF representations.
- **Volume:** commonly cited as ~1,000–2,000 notices/day. **Do not quote this on stage unless you verify it — better, count it from your own query and quote your own number.**

**Rule: never spend model tokens on something the metadata already answers.** Geography, date, municipality, publication category are deterministic. The model answers only: what project is this, what commercial activity does it imply, does it match this company, which sentence proves it.

---

## 5. Architecture

```
            OFFICIAL DUTCH PUBLICATIONS (KOOP SRU)
                            │
                            ▼
                DETERMINISTIC PREFILTER
                date · geo radius · rubriek
                            │
                            ▼
                   SMALL OPEN MODEL  (Token Factory)
                   project type · service match
                   property type · evidence · decision
                            │
                 ┌──────────┴──────────┐
            confident                uncertain / no evidence
                 │                    / schema invalid
                 │                          │
                 │                          ▼
                 │              LARGE REASONING MODEL (Token Factory)
                 │              adjudicate · verify evidence
                 │                          │
                 └──────────┬───────────────┘
                            ▼
                  STRUCTURED OPPORTUNITY  →  Supabase
                            │
                    ┌───────┴───────┐
                   MAP             FEED
```

**Thesis to say out loud:** *reasoning tokens should be spent in proportion to uncertainty.* That reads as engineering maturity; "we used multiple agents" does not.

### 5.1 Models

| Role | Candidate |
|---|---|
| High-volume classifier | a small open model (e.g. `openai/gpt-oss-20b` class) |
| Escalation / adjudicator | a large open model from the same family (e.g. `openai/gpt-oss-120b` class) |
| Offline baseline only | a closed frontier model (Anthropic credits) |

Same family for both tiers gives a clean story: *how much intelligence does one government notice actually need?* **Confirm exact model IDs from the Nebius starter kit PDF the night before.** Do not lose 40 minutes fighting for one specific model — if the approved list differs, swap and move on.

Token Factory facts that matter here: OpenAI-compatible API, 60+ open models, structured JSON outputs, function calling, LoRA/full fine-tuning with one-click deployment, batch/async inference, zero-retention mode, EU data residency (Finland/France).

---

## 6. The model task

### 6.1 Input — company profile

```json
{
  "services": [
    "commercial electrical installations",
    "EV charging infrastructure",
    "access control systems",
    "commercial lighting"
  ],
  "preferred_property_types": ["office", "warehouse", "retail", "hospitality", "multi-unit residential"],
  "excluded_project_types": ["single-family minor renovation", "tree removal", "events", "private gardens"],
  "radius_km": 35
}
```

### 6.2 Output schema (enforce with structured outputs)

```json
{
  "decision": "relevant | irrelevant | uncertain",
  "confidence": 0.93,
  "project_type": "commercial renovation",
  "property_type": "office",
  "matched_services": ["commercial electrical installations"],
  "project_stage": "permit_application",
  "evidence": "transformatie en uitbreiding van het bedrijfspand",
  "reason": "Substantial modification of a commercial property inside the service area."
}
```

`uncertain` is load-bearing: it is simultaneously the honest answer and the routing trigger.

`evidence` must be a **verbatim substring of the notice**. Validate that in code — if it is not a substring, treat it as a hallucination and escalate. That single check is worth mentioning to the technical judges.

### 6.3 Prompt skeleton

```
You classify Dutch government publications for one company.

COMPANY PROFILE:
{profile_json}

NOTICE (verbatim):
{notice_text}

Decide whether this publication signals a potential project for this company.
Rules:
- A permit is a signal of activity, not a guaranteed sale.
- "evidence" MUST be copied verbatim from the notice text.
- If the notice is ambiguous or evidence is weak, answer "uncertain".
- Answer ONLY with the JSON schema provided.
```

Keep the prompt identical across models so the comparison is fair. Log the prompt version with every run.

### 6.4 Routing logic

LLM self-reported confidence is not calibrated. Use multiple triggers:

```python
needs_escalation = (
    result.decision == "uncertain"
    or result.confidence < 0.82
    or not result.evidence
    or result.evidence not in notice_text      # hallucinated quote
    or schema_validation_failed
)
```

And prefilter *before* any model call: outside the radius → no call. Irrelevant rubriek → no call. That is what makes the cost story real.

---

## 7. Data model (Supabase)

```sql
create table company_profiles (
  id uuid primary key default gen_random_uuid(),
  name text,
  services jsonb,
  excluded_project_types jsonb,
  preferred_property_types jsonb,
  lat double precision,
  lng double precision,
  radius_km int
);

create table notices (
  id text primary key,              -- KOOP identifier
  source_url text,
  title text,
  body text,
  published_on date,
  municipality text,
  rubriek text,
  lat double precision,
  lng double precision,
  fetched_at timestamptz default now()
);

create table signals (
  id uuid primary key default gen_random_uuid(),
  notice_id text references notices(id),
  profile_id uuid references company_profiles(id),
  decision text,                    -- relevant | irrelevant | uncertain
  confidence numeric,
  project_type text,
  property_type text,
  matched_services jsonb,
  evidence text,
  reason text,
  escalated boolean default false,
  created_at timestamptz default now()
);

create table model_runs (
  id uuid primary key default gen_random_uuid(),
  notice_id text,
  profile_id uuid,
  model text not null,
  stage text,                       -- 'small' | 'large' | 'baseline'
  prompt_version text,
  input_tokens int,
  output_tokens int,
  latency_ms int,
  cost_eur numeric,
  ok boolean,
  error text,
  created_at timestamptz default now()
);

create table eval_items (
  notice_id text primary key references notices(id),
  expected_decision text,           -- human label
  expected_category text,
  expected_service text,
  expected_evidence text,
  labeller text,
  split text default 'test'         -- 'test' | 'train'
);

create table eval_results (
  id uuid primary key default gen_random_uuid(),
  notice_id text references eval_items(notice_id),
  config text,                      -- '20b' | '120b' | 'router' | 'baseline' | 'finetuned'
  prediction text,
  correct boolean,
  latency_ms int,
  cost_eur numeric,
  run_at timestamptz default now()
);
```

**`model_runs` is judging evidence.** Log from request #1. Measurement bolted on at 16:00 is measurement that does not exist.

---

## 8. The benchmark (20% of the score lives here)

### 8.1 Set size and composition

40–60 notices, hand-labelled. Not 150 — we have four hours. Reading a notice and deciding relevant/irrelevant takes about 10 seconds; 50 items is ~10 minutes split across the team.

Compose deliberately, because a random sample is mostly irrelevant and a model that always says "irrelevant" would score 94%:

- 20 relevant
- 20 irrelevant
- 10 borderline / hard

Separately, keep a **real-distribution sample** (e.g. one full day unfiltered) purely for the cost projection and the funnel numbers.

### 8.2 Ground truth rules

- Labels are **human**. Not Claude, not the 120B, not another AI judge.
- A closed model may help *inspect disagreements*; it never *defines* truth.
- Model-generated labels are acceptable for fine-tune **training** data only — that is distillation, and we say so openly.
- Training data and test data never overlap. Tag `split` in the table so it cannot happen by accident.

### 8.3 Metrics — report all of them

| Metric | Why |
|---|---|
| Precision `TP/(TP+FP)` | Salespeople hate garbage leads |
| Recall `TP/(TP+FN)` | A missed project is a lost sale |
| F1 | Single comparable number |
| Evidence accuracy | Did it quote the sentence that actually supports the call |
| Cost per 1,000 notices | The entire Token Factory story |
| p50 / p95 latency | Infrastructure execution |
| Escalation rate | e.g. "only 18% needed the large model" |

**Say the asymmetry out loud:** missing a relevant project costs a sale; a false positive costs 30 seconds of a salesperson's attention. So we tune the escalation threshold for recall and accept some precision loss. Stating which error matters more is what separates a real eval from a table of numbers.

### 8.4 The comparison table (all values ACTUAL, no placeholders)

| Configuration | Precision | Recall | F1 | p95 latency | Cost / 1k |
|---|---|---|---|---|---|
| Small model only | | | | | |
| Large model only | | | | | |
| **ReguLine router** | | | | | |
| Closed baseline (offline) | | | | | |
| Fine-tuned small (stretch) | | | | | |

**We do not need to beat the closed model on accuracy.** The winning result is: *matched the large model's F1 while sending only ~20% of documents to it, at a fraction of the cost.*

### 8.5 Funnel + cost projection

```
1,500 notices/day
   ↓ geo prefilter
 320 in radius
   ↓ rubriek filter
 180 plausible categories
   ↓ small model
 180 small-model calls
   ↓ escalation
  28 large-model calls
```

Then: `cost per notice × daily volume × 365` for the routed system vs `1,500 × large model`. That converts an architecture choice into a P&L line, which is exactly what the Nebius and Accel judges want to see.

---

## 9. Fine-tuning (stretch goal — start early, do not depend on it)

### 9.1 What it means, plainly

Instead of explaining the job in a prompt every time, show the model a few hundred examples of the job done right. You get back your own private version of the model that already knows the task. A small model that is mediocre out of the box can beat a much larger one at this one narrow job, at a fraction of the cost per document. That is only possible because the weights are open.

### 9.2 Steps

1. **Collect examples** — 200–500 notices with answers. Model-generated labels are fine here (`split='train'`).
2. **Format as JSONL** — one line per example: user message = notice + profile, assistant message = correct JSON.
3. **Upload the file** to Token Factory (OpenAI-compatible file upload).
4. **Start the job** — one API call: base model, training file, `lora: true`.
5. **Poll until done** — unpredictable. This is the risk.
6. **Deploy** — one click / one call, returns a new model name.
7. **Use it** — same endpoint, different model string.
8. **Evaluate** on the untouched test set and add a row to the table.

### 9.3 Rules

- Kick it off **before lunch**, build the product while it trains.
- If it has not landed by the UI phase, drop it. The benchmark still stands on three configs.
- Never train and evaluate on the same notices. Judges will ask.

---

## 10. The four-hour plan

Do not reverse this order.

### T+0:00 – 0:35 — Data and labels
- Person A: KOOP SRU returning real notices → `notices` table. **If XML is still fighting you at minute 20, cache a real sample locally and move on.** The product must not die in an XML debugger.
- Person B: finalise the company profile, start labelling into `eval_items` (target 40–50).
- Person C: Supabase project up, schema applied, keys in the repo `.env`.
- Person D: FastAPI skeleton + Nebius client + `model_runs` logging helper.

### T+0:35 – 1:15 — Benchmark first
- Run the small model over every eval item. Then the large model. Log decision, correctness, latency, tokens, cost.
- Compute precision, recall, F1 per config.
- **At this point we already hold judging evidence most teams will never produce.**
- In parallel: kick off the fine-tune job if the training file is ready.

### T+1:15 – 2:00 — The router
- Structured outputs + schema validation + evidence-substring check + confidence threshold + escalation + retry/fallback.
- Re-run the benchmark as `config='router'`. Record escalation rate.

### T+2:00 – 2:45 — Demo product only
- Profile at top, scan button, opportunity cards, map or feed, funnel counters from real queries.
- **No** auth, billing, onboarding, settings, CRM.

### T+2:45 – 3:15 — Deploy and freeze
- Hosted UI + hosted API + **public benchmark page**.
- Test in incognito on a second device. After this point, stability beats features.

### T+3:15 – 4:00 — Submission and pitch
- Fill every form field with real numbers.
- Slides public, tested in incognito.
- **Record a backup demo video.**
- Rehearse the run-through three times.

### Standing rule
If forced to choose between a beautiful interactive map and 40 labelled notices with real precision/recall/cost — **choose the benchmark, then ship an ugly map.** The organisers said it themselves: a rough measurement with real numbers beats a polished claim with none.

---

## 11. Backend surface

Three routes. That is enough.

```
POST /api/scan        # profile in → fetch, prefilter, classify, store
GET  /api/signals     # ranked opportunities for a profile
GET  /api/benchmark   # current benchmark table (also the public proof link)
```

### Reliability rules (this is the "shown, not claimed" part)

- Every model output is schema-validated.
- JSON parse fails → retry once → fallback to large model → `status = processing_error`. **Never let one malformed output kill a scan.**
- Every signal must carry: decision, evidence, source URL, model used.
- Missing or non-substring evidence → escalate, never publish.
- Timeouts and rate limits: catch, log to `model_runs.error`, continue.

---

## 12. Reference snippets

Adapt, do not paste blindly. Verify model IDs and base URL against the starter kit.

### 12.1 Token Factory client

```python
import os, time, json
from openai import OpenAI

client = OpenAI(
    base_url="https://api.tokenfactory.nebius.com/v1",   # verify in starter kit
    api_key=os.environ["NEBIUS_API_KEY"],
)

SMALL = "openai/gpt-oss-20b"      # verify
LARGE = "openai/gpt-oss-120b"     # verify

PRICES_EUR_PER_MTOK = {           # fill from the dashboard, do not guess
    SMALL: {"in": 0.0, "out": 0.0},
    LARGE: {"in": 0.0, "out": 0.0},
}

def classify(notice_text: str, profile: dict, model: str, schema: dict):
    t0 = time.perf_counter()
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(notice_text, profile)},
        ],
        response_format={"type": "json_schema", "json_schema": schema},
        temperature=0,
    )
    latency_ms = int((time.perf_counter() - t0) * 1000)
    usage = resp.usage
    p = PRICES_EUR_PER_MTOK[model]
    cost = (usage.prompt_tokens * p["in"] + usage.completion_tokens * p["out"]) / 1_000_000
    return json.loads(resp.choices[0].message.content), {
        "model": model,
        "input_tokens": usage.prompt_tokens,
        "output_tokens": usage.completion_tokens,
        "latency_ms": latency_ms,
        "cost_eur": cost,
    }
```

### 12.2 Router

```python
CONF_THRESHOLD = 0.82

def route(notice, profile):
    result, meta = classify(notice["body"], profile, SMALL, SCHEMA)
    log_model_run(notice, profile, stage="small", **meta)

    escalate = (
        result["decision"] == "uncertain"
        or result.get("confidence", 0) < CONF_THRESHOLD
        or not result.get("evidence")
        or result["evidence"] not in notice["body"]
    )
    if escalate:
        result, meta = classify(notice["body"], profile, LARGE, SCHEMA)
        log_model_run(notice, profile, stage="large", **meta)
        result["escalated"] = True
    else:
        result["escalated"] = False
    return result
```

### 12.3 Deterministic prefilter

```python
from math import radians, sin, cos, asin, sqrt

def km(lat1, lng1, lat2, lng2):
    dlat, dlng = radians(lat2 - lat1), radians(lng2 - lng1)
    a = sin(dlat/2)**2 + cos(radians(lat1))*cos(radians(lat2))*sin(dlng/2)**2
    return 2 * 6371 * asin(sqrt(a))

def prefilter(notices, profile, allowed_rubrieken):
    kept = []
    for n in notices:
        if n["rubriek"] not in allowed_rubrieken:
            continue
        if n["lat"] and km(profile["lat"], profile["lng"], n["lat"], n["lng"]) > profile["radius_km"]:
            continue
        kept.append(n)
    return kept
```

### 12.4 Eval runner

```python
def run_eval(config_name, predict_fn, items):
    for item in items:                      # items where split == 'test'
        notice = get_notice(item["notice_id"])
        pred, meta = predict_fn(notice)
        save_eval_result(
            notice_id=item["notice_id"],
            config=config_name,
            prediction=pred["decision"],
            correct=(pred["decision"] == item["expected_decision"]),
            latency_ms=meta["latency_ms"],
            cost_eur=meta["cost_eur"],
        )

def prf(config_name):
    rows = fetch_eval_results(config_name)
    tp = sum(r.prediction == "relevant" and r.expected == "relevant" for r in rows)
    fp = sum(r.prediction == "relevant" and r.expected != "relevant" for r in rows)
    fn = sum(r.prediction != "relevant" and r.expected == "relevant" for r in rows)
    precision = tp / (tp + fp) if tp + fp else 0
    recall = tp / (tp + fn) if tp + fn else 0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0
    return precision, recall, f1
```

---

## 13. Tools: what we use and what we ignore

| Tool | Use |
|---|---|
| Nebius Token Factory | All production inference. Required and central. |
| Supabase | Postgres, storage, run logging. Pro credits stop project pausing mid-judging. |
| FastAPI | The service |
| Lovable | UI, last 45 minutes |
| Vercel | Frontend hosting if needed |
| Anthropic credits | **Offline baseline only.** Disclosed on the form. Never in the product path. |
| Tavily | Optional enrichment *after* a high-fit signal is found — company site, project context. Never in core classification. Never enrich private residential applicants. |
| ElevenLabs / n8n / Modal | Not used. Bolting on sponsor tools for show is visible and costs credibility. |
| Miro | Planning only |

---

## 14. Do not build

- A chatbot
- Authentication (unless hosting forces it)
- CRM sync, Stripe, email campaigns
- The whole of the Netherlands plus ten industries
- A beautiful map before a working benchmark
- A fine-tune before a benchmark exists
- Fake contacts, invented project values, hard-coded funnel numbers

---

## 15. Responsible design (full 5% for ~20 minutes of work)

Principles, and say them plainly:

1. **Business signals, not citizen surveillance.** Suppress personal names; do not build profiles of natural persons from residential permits.
2. **No automatic outreach.** The system surfaces; a human decides whether to contact anyone.
3. **Evidence always preserved.** Every recommendation links to the original official publication.
4. **Uncertainty is visible.** Low confidence is flagged for review, not presented as fact.
5. **No overclaiming.** A permit is a project signal, never a guaranteed buyer.
6. **Infrastructure.** Nebius offers zero-retention inference and EU processing locations (Finland, France) — worth stating even though the notices themselves are public.

---

## 16. The two questions we will be asked

### "Why not just use ChatGPT?"

> ChatGPT can analyse one notice after a human finds it and explains their company. ReguLine continuously processes the entire national stream, filters deterministically on geography and category, and routes by uncertainty. On our hand-labelled set, our routed Token Factory pipeline hit **[F1]** at **[€ per 1,000 notices]**, escalating only **[X]%** of cases. And because the models are open, the classification layer adapts to each customer's feedback instead of depending on one closed general model forever.

### "Why Nebius?"

> Not because the rules said so. Our business model is processing thousands of low-value documents continuously, so cost per document *is* the margin. Token Factory lets us serve a small open model for most decisions and selectively route the hard ones to a larger model through the same API — and lets us fine-tune the small one on customer feedback. That model choice directly determines our cost per opportunity.

---

## 17. Pitch — 5 minutes

| Time | Content |
|---|---|
| 0:00–0:35 | Problem |
| 0:35–0:55 | Customer and pain |
| 0:55–2:10 | **Live demo** |
| 2:10–2:55 | Architecture / Token Factory |
| 2:55–3:40 | Real benchmark |
| 3:40–4:15 | Business model, moat, market |
| 4:15–4:35 | Responsible design |
| 4:35–5:00 | Close / buffer |

### Slides

1. **"Your next customer may have already told the government they're about to spend."** — daily notice volume (our own counted number). Local businesses have no time to read it.
2. **ReguLine** — the funnel: `1,284 → 46 → 7 → 3`. Then launch the demo.
3. **Architecture** — metadata → small model → confidence routing → large model only when needed.
4. **The benchmark** — the big table with real numbers. Probably the single most important slide.
5. **Company** — existing products already charge recurring fees; our moat is customer correction data; sideways expansion first, then new streams.
6. **Responsible design** — businesses not private citizens; evidence on every signal; human decides.

### Stage script

> Every day, Dutch governments publish [OUR COUNTED NUMBER] official notices. Buried in them are signals that businesses are about to build, expand, renovate and invest. For a local installer that could be their next customer — but nobody has time to read it.
>
> We built ReguLine. Our example customer is a commercial electrical installer in Amsterdam. They tell us what they sell and how far they travel.
>
> [DEMO] Today we scanned [N] publications. [X] were in their region. ReguLine surfaced [Y] project signals. Here's one. It matched because [REASON] — and here's the exact sentence that proves it, plus the official source. We're not claiming this company is definitely buying. We're saying something commercially relevant just happened and this installer should know.
>
> Underneath: government metadata handles geography deterministically. A small open model on Nebius Token Factory handles the majority of notices. If it's uncertain, can't produce evidence, or fails our schema check, we escalate to a larger reasoning model. This matters because it's a high-volume product — running the biggest model on everything would be wasteful.
>
> So we measured it. We hand-labelled [N] real notices. Small model: [X]. Large model: [Y]. Our routed system: [Z] — while sending only [P]% to the expensive model and cutting cost [Q]%. Raw benchmark is public at this link.
>
> Businesses already pay monthly subscriptions for permit-derived project data, so the willingness to pay is proven. Our difference is the judgement layer — and every time a customer dismisses a signal, that's a training example that sharpens their model. The feed is a commodity; the judgement compounds.
>
> We start with installation companies. The same engine points at any public stream — what changed today that creates an opportunity for my business?
>
> ReguLine doesn't contact anyone automatically, doesn't present a permit as a guaranteed buyer, and focuses on business activity rather than private citizens. Every signal traces back to its official source.
>
> **From thousands of public notices to the few opportunities your business actually needs to see.**

---

## 18. Submission drafts (replace every bracket with real values)

### What did you build, and what problem does it solve?

> Small local businesses miss commercial opportunities hidden inside public government information. Every day Dutch authorities publish large numbers of permits, planning decisions and other official notices, but an installer or construction SME has no time to read them and work out which ones matter.
>
> ReguLine turns that stream into company-specific commercial signals. A business defines what it sells and where it operates. ReguLine monitors new official publications, filters them geographically, and identifies which developments match that company's services. Instead of hundreds of notices the user receives a short ranked list, each with the reason for the match, a confidence level, the exact supporting sentence, and a link to the official source.
>
> Our first customer profile is a 28-person commercial electrical installer in Amsterdam with a 35 km service radius. Discovering one relevant project early is worth far more than the monthly software cost, and existing permit-data products already sell on recurring subscriptions — the willingness to pay is proven. Longer term, the same engine converts any public event stream into company-specific commercial intelligence, and every customer correction trains that customer's own model.

### Models and Token Factory use

> ReguLine uses [SMALL MODEL] on Nebius Token Factory as its high-volume classification layer: project type, service match, structured JSON with relevance, confidence and verbatim supporting evidence.
>
> Easy cases stop there. Cases marked uncertain, below our confidence threshold, missing evidence, or failing schema/evidence validation are routed to [LARGE MODEL] on Token Factory for adjudication.
>
> Every inference call logs model, input/output tokens, latency and estimated cost. Government metadata handles deterministic attributes such as geography and publication category, so model capacity is spent only on semantic decisions. [If applicable: we additionally fine-tuned [SMALL MODEL] with LoRA on [N] examples and deployed it on Token Factory.]
>
> All production inference uses open models. [CLOSED MODEL] was used only as an offline benchmark baseline and is not part of the product.

### Measurable model advantage

> We hand-labelled [N] real Dutch official notices against a fixed commercial-installer profile (20 relevant / 20 irrelevant / 10 borderline) and evaluated every configuration on the identical set. Labels are human; no model defined ground truth.
>
> [SMALL MODEL]: precision [P], recall [R], F1 [F], €[C] per 1,000 classifications, p95 [L] ms.
> [LARGE MODEL]: precision [P], recall [R], F1 [F], €[C] per 1,000, p95 [L] ms.
> ReguLine router: precision [P], recall [R], F1 [F], escalating only [X]% of notices — [Y]% lower cost than running the large model on everything, at p95 [L] ms.
> [Fine-tuned [SMALL MODEL]: precision [P], recall [R], F1 [F], €[C] per 1,000.]
>
> We optimise the escalation threshold for recall, because a missed project is a lost sale while a false positive costs a salesperson seconds.
>
> Benchmark and raw results: [PUBLIC LINK]

### Responsible design

> ReguLine treats government publications as project signals, not guaranteed leads. Every recommendation links to the original official source, and uncertain classifications are surfaced as uncertain rather than presented as fact. We focus on business and project activity rather than profiling private individuals, suppress personal names, and never contact anyone automatically — a human decides whether a signal is worth following up. Production inference runs on EU-hosted, zero-retention infrastructure.

---

## 19. Risk register

| Risk | Mitigation |
|---|---|
| SRU XML eats the morning | 20-minute timebox, then use a cached real sample |
| Fine-tune queue is slow | Stretch goal only, launched before lunch, droppable |
| Eval set is unbalanced → fake accuracy | Forced 20/20/10 composition |
| Train/test leakage | `split` column, separate tables, never relabel test items |
| "This already exists" | Lead with existing paid products as proof of demand; pitch the judgement layer, not the feed |
| Demo feels small | Live profile swap: same notices, different company, different results |
| Model returns malformed JSON on stage | Retry → fallback → error state, never a crash |
| Hosted app sleeps before judging | Supabase Pro, deploy early, keep it warm |
| Live demo dies | Recorded backup video |

---

## 20. Night-before checklist

- [ ] Nebius key works; one successful call; **exact model IDs and prices noted from the starter kit**
- [ ] Anthropic credits redeemed (baseline only)
- [ ] Supabase project created, credits applied, schema ready to apply
- [ ] Lovable account ready
- [ ] Repo created, env installed, `.env.example` committed
- [ ] SRU endpoint spiked once; a sample response cached locally
- [ ] Company profile JSON written
- [ ] Roles assigned (data / models / eval / UI+pitch)
- [ ] Slides deck created and set to public
- [ ] Hard spend cap in code (`MAX_SPEND_EUR`) wired to `model_runs.cost_eur`
- [ ] Extension plug, hotspot, power bank

---

## 21. If the judges remember one thing

**User:** government data says what happened; ReguLine says why it matters to *your* business.

**Nebius:** we don't run the biggest model on everything — we measured exactly how much reasoning each decision needs.

**Accel:** companies already pay for this data; better model economics plus proprietary relevance feedback turn a commodity feed into vertical commercial intelligence.
