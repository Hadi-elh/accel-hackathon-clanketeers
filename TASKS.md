# TASKS — who does what, when

Three people, four hours. Fill in the names below before the day starts.

| Role | Name | Branch | Owns |
|---|---|---|---|
| A — Data | _____ | `feat/ingest` | `/ingest` |
| B — Models & eval | _____ | `feat/models` | `/models`, `/eval` |
| C — Product & pitch | _____ | `feat/app` | `/app`, deploy, slides, submission |

Read `CONTEXT.md` and `CONTRACTS.md` before touching anything. Nobody edits a folder
they don't own.

---

## T-1 day — the night before (30 min, everyone)

- [ ] Clone the repo, create your branch, install Python 3.11+
- [ ] Copy `.env.example` to `.env`, fill in keys (never commit it)
- [ ] **C:** apply `schema.sql` in the Supabase SQL editor, confirm the `vandijk` row exists
- [ ] **B:** one successful Nebius call; write the exact model IDs and per-token prices
      into `/models/PRICES.md`. Guessed prices make the whole benchmark fiction.
- [ ] **A:** hit the KOOP SRU endpoint once in the browser or with curl, just to see XML
      come back. Don't build anything yet.
- [ ] Everyone: `git pull`, confirm `CLAUDE.md` is picked up by your Claude Code session

---

## T+0:00 – 0:15 — Team sync (all three, together)

Not optional. This is what makes parallel work possible.

- [ ] Read `CONTRACTS.md` out loud, section by section. Agree or change it **now**.
- [ ] Freeze the three shapes: Notice, Company profile, Model output.
- [ ] Confirm `classify_notice()` signature. C writes the stub immediately.
- [ ] Agree merge times: **T+1:15, T+2:45, T+3:15**. C runs all merges.
- [ ] Decide who labels if A gets stuck on XML (default: A labels, B keeps building).

After this, nobody blocks anybody.

---

## Person A — Data

### T+0:15 – 0:50 · KOOP ingest

**Do**
- `/ingest/fetch.py` — query the SRU endpoint for yesterday and today
- Parse XML → the Notice shape in CONTRACTS.md §1
- Strip HTML from `body`. Plain text only.
- Write to the `notices` table (upsert on `id`)
- Save one real response to `/ingest/sample_notices.json` **as soon as you have it** —
  this unblocks B and C permanently

**Done when:** `python -m ingest.fetch --date today` prints a count and rows appear in
Supabase.

**Hard timebox:** at minute 20, if XML is still fighting you, hand-download 60 notices
from the website, shape them into `sample_notices.json` by hand or with Claude Code, commit
it, and move on. **The product must not die in an XML debugger.**

### T+0:50 – 1:15 · Prefilter

**Do**
- `/ingest/prefilter.py` — haversine distance, radius check, rubriek allowlist
- Build the rubriek allowlist by looking at real data, not by guessing
- `prefilter_stats()` returning the real funnel counts (CONTRACTS.md §4)
- Handle `lat`/`lng` = null: count as `location_unknown`, never silently drop

**Done when:** the funnel prints real numbers, e.g. `1284 → 46 → 31`.

### T+1:15 – 2:15 · Labelling (the most valuable hour of your day)

**Do**
- Pick 50 notices: **20 relevant, 20 irrelevant, 10 borderline**
- For each: `expected_decision`, `expected_category`, `expected_service`,
  `expected_evidence` (copy the exact sentence), `labeller`, `split='test'`
- Insert into `eval_items`
- If two of you disagree on a notice, it's borderline — label it and note why

**Rules:** labels are human. No model. Never relabel a test item after seeing a model's
answer — that's how you fool yourself.

**Done when:** 50 rows in `eval_items` with the 20/20/10 split.

### T+2:15 – 3:00 · Training data (only if the fine-tune is alive)

- 200–500 more notices labelled by the large model, `split='train'`
- Export to `/eval/train.jsonl` in chat format
- **Zero overlap with test items.** Check with a set difference, don't eyeball it.

### T+3:00 onward · Second pair of eyes

- Verify every number on the demo screen traces to a real query
- Click every source link in the UI
- Help C rehearse

---

## Person B — Models and eval

### T+0:15 – 0:40 · Client and schema

**Do**
- `/models/schema.json` — the structured-output schema from CONTRACTS.md §3
- `/models/client.py` — Nebius client, `classify(notice, profile, model)` returning
  `(result, meta)` where meta = model, tokens, latency_ms, cost_eur
- `/models/prompt.py` — system + user prompt, versioned (`PROMPT_VERSION = "v1"`)
- `/models/log.py` — writes `model_runs`. **Working before your second model call.**

**Done when:** one notice from `sample_notices.json` classifies and one `model_runs` row
exists with a non-zero cost.

### T+0:40 – 1:15 · Benchmark first (before the router)

**Do**
- `/eval/run.py` — run a config over all `split='test'` items, write `eval_results`
- Run `config='small'`, then `config='large'`
- `/eval/metrics.py` — precision, recall, F1, evidence accuracy, p95 latency, cost/1k
- Print the table

**Done when:** two rows of real numbers exist. **At this point you already hold judging
evidence most teams will never produce.** Tell C so the benchmark page can go live.

**Also at T+0:40:** if the fine-tune is happening, get `train.jsonl` uploaded and the job
started now. It trains while you keep working. If it's not ready by T+2:30, drop it.

### T+1:15 – 2:00 · The router

**Do**
- `/models/router.py` implementing `classify_notice()` exactly as CONTRACTS.md §4 says
- Escalation triggers: `uncertain`, confidence < 0.82, missing evidence,
  **evidence not a verbatim substring**, schema validation failure
- Retry once on parse failure → escalate → on total failure return
  `decision='uncertain'` with `error`. **Never raise.**
- Re-run the benchmark as `config='router'`, record escalation rate

**Done when:** the table has three rows and you can state the escalation percentage.

**Tell C the moment this lands** — that's C's one-line import swap.

### T+2:00 – 2:45 · Baseline and depth

- `config='baseline_closed'` — Claude over the same test set, offline
- Optional but high value: **threshold sweep**. Run the router at 0.7 / 0.8 / 0.9 and
  plot escalation rate vs F1. Turns "we picked 0.82" into "we measured where the curve
  bends."
- Cost projection: cost per notice × daily volume × 365, routed vs large-on-everything

### T+2:45 – 3:15 · Freeze and hand over

- Final table to C for the public benchmark page
- Write the three sentences C will say on stage about the numbers
- No new configs after this. Stability over curiosity.

---

## Person C — Product, infra, pitch

### T+0:15 – 0:45 · Foundations

**Do**
- Supabase live, schema applied, keys shared securely (not in the repo)
- `/app/api.py` — FastAPI with the three routes from CONTRACTS.md §4
- `/app/stub.py` — fake `classify_notice` returning a fixed result after 200 ms
- Deploy the skeleton **now**, not later. A "hello world" that's live at T+0:45 beats a
  perfect app that fails to deploy at T+3:10.

**Done when:** a public URL returns JSON from `/api/signals`.

### T+0:45 – 2:00 · The product

**Do**
- Lovable UI against your API: funnel counters at top, ranked opportunity cards, map/feed
- Card shows: match %, project type, distance, why it matched, **verbatim evidence**,
  source link
- Detail view shows the model-routing strip (small → uncertain → escalated → relevant).
  That strip is for the Nebius judge.
- Empty and error states. A scan that returns nothing must look deliberate, not broken.

**Rules:** no auth, no billing, no settings, no CRM, no chatbot. Every number from a real
query — **no hard-coded 1,284**.

### T+2:00 – 2:45 · Integration and benchmark page

- Swap the stub for B's `classify_notice`
- Full end-to-end run on real notices, real profile
- `/api/benchmark` rendering the comparison table → this is the public proof link for
  the submission form
- **Nice-to-have that's worth more than polish:** a profile switcher with a second
  company (e.g. a solar installer). Same notices, different results. That demoes the
  expansion story in 10 seconds.

### T+2:45 – 3:15 · Deploy and freeze

- Final deploy, test in **incognito on a second device**
- Supabase Pro so the project doesn't pause mid-judging
- Confirm every link works from a machine that isn't yours
- **Feature freeze.** After this, only bug fixes.

### T+3:15 – 4:00 · Submission and pitch

- [ ] Fill every form field with real numbers, no placeholders
- [ ] Slides public (Google Slides), tested in incognito — stage computer, no laptops
- [ ] All six criteria covered; a criterion you skip scores zero
- [ ] **Record a backup demo video**
- [ ] Rehearse the 5 minutes three times, out loud, with a timer

---

## Merge protocol

Three merges, run by C, five minutes each.

```bash
# each person, before the merge point
git add -A && git commit -m "wip: <what>" && git push origin feat/<yours>

# C
git checkout main && git pull
git merge feat/ingest && git merge feat/models && git merge feat/app
git push origin main

# everyone, after
git checkout feat/<yours> && git pull origin main --rebase
```

| Time | What should be on `main` |
|---|---|
| T+1:15 | Real notices, prefilter, two benchmark rows, deployed skeleton |
| T+2:45 | Router integrated, UI on real data, benchmark page live |
| T+3:15 | Final build. Nothing merges after this except bug fixes. |

Commit every 15 minutes even if it's ugly. Small commits are recoverable; one giant
commit at hour three is not.

---

## Starting a Claude Code session

Each person opens their session with this, adjusted:

> Read CLAUDE.md, CONTEXT.md and CONTRACTS.md first. I own /ingest only — do not edit
> files outside it. My task right now is: [task]. Build against the Notice shape in
> CONTRACTS.md §1. Ask before adding any dependency.

---

## Escalation rules (when something breaks)

| Situation | Do this |
|---|---|
| SRU XML unsolved at T+0:35 | Switch to cached sample. Permanently. |
| Fine-tune not finished by T+2:30 | Drop it. Three configs is a complete benchmark. |
| Model returns garbage JSON repeatedly | Lower temperature to 0, simplify schema, escalate |
| Deployment failing at T+2:50 | Demo from localhost + recorded video. Say so honestly. |
| Two people need the same file | The owner makes the change. No exceptions. |
| Someone finishes early | Label more eval items. Never start a new feature. |

---

## The one-sentence reminder

If you're choosing between a prettier interface and a real number, choose the number.
