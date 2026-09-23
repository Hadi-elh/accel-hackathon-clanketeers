# ReguLine

**Turning the daily flood of Dutch government publications into company-specific commercial signals.**

Built for AI Innovate Amsterdam (AISO × Accel), Future Founders track — team Clanketeers.

---

## The problem

Dutch authorities publish over a thousand official notices every day: permits granted,
buildings being transformed, charging points approved, zoning changed. It is free, public,
and effectively unreadable — written for legal compliance, not for sales.

Those notices are announcements that a company is about to spend money. A 28-person
electrical installer in Amsterdam would like to know about the four nearby projects that
might need them. Nobody has time to read a thousand Dutch bureaucratic notices to find them.

## What ReguLine does

Reads the entire stream and returns only the notices that matter to **one specific
company**, each with the verbatim sentence that proves it and a link to the official source.

```
1,284 notices published today
     46 within this company's service radius
      7 matched their business
      3 high-fit project signals
```

We call the output a **project signal**, never a guaranteed lead. A permit proves activity
is happening; it doesn't prove the applicant still needs an installer.

> **The data is free. The judgement is the product.**

## Why open models

At thousands of documents a day, cost per document *is* the business. Running a frontier
model on everything destroys the margin.

```
KOOP SRU (official Dutch publications, CC0)
        │
        ▼
DETERMINISTIC PREFILTER              ← no model calls
date · geo radius · rubriek
        │
        ▼
SMALL OPEN MODEL (Nebius Token Factory)
decision · confidence · evidence · project type
        │
   ┌────┴────┐
confident   uncertain / no evidence / invalid schema
   │             │
   │             ▼
   │      LARGE MODEL (Nebius Token Factory)
   └────┬────────┘
        ▼
  signals → API → UI (feed + map)
```

**Core thesis: reasoning tokens should be spent in proportion to uncertainty.** We measure
exactly what that saves against a hand-labelled evaluation set — precision, recall, F1,
p95 latency, cost per 1,000 notices, and escalation rate.

Not used: RAG, vector search, agent loops, LLM-as-judge. The task outputs a discrete label,
so exact matching against human labels is the correct evaluation method.

## Repo layout

| Path | What it is |
|---|---|
| `PLAYBOOK.md` | Full build and pitch plan — business case, benchmark design, slides, submission drafts |
| `TASKS.md` | Hour-by-hour task breakdown per person, merge protocol, escalation rules |
| `CONTEXT.md` | Short version: what we're building, the demo customer, the timeline |
| `CONTRACTS.md` | **Frozen** data shapes and function signatures — read before writing code |
| `CLAUDE.md` | Repo rules, picked up automatically by Claude Code |
| `schema.sql` | Supabase schema, applied once |
| `ingest/` | KOOP SRU fetch, XML parsing, deterministic prefilter |
| `models/` | Nebius client, prompts, output schema, routing logic |
| `eval/` | Benchmark runner and metrics |
| `app/` | FastAPI service and UI |

## Setup

```bash
git clone https://github.com/emrewhiting/accel-hackathon-clanketeers.git
cd accel-hackathon-clanketeers
cp .env.example .env        # fill in your keys — never commit this
```

Required environment variables:

| Variable | Used for |
|---|---|
| `NEBIUS_API_KEY` | All production inference |
| `SUPABASE_URL`, `SUPABASE_KEY` | Data, telemetry, eval results |
| `ANTHROPIC_API_KEY` | Offline benchmark baseline only — never in the product path |

Then apply `schema.sql` in the Supabase SQL editor.

## Working conventions

- **Folder ownership:** `ingest/` → A, `models/` + `eval/` → B, `app/` → C. Don't edit a
  folder you don't own; ask the owner instead.
- **Branches:** `feat/ingest`, `feat/models`, `feat/app`. Nothing is pushed directly to
  `main` — merges happen at three fixed checkpoints.
- **Shared files** (`CONTRACTS.md`, `schema.sql`, `CONTEXT.md`, `CLAUDE.md`) change only in
  a team sync.

```bash
git checkout -b feat/<yours>
git pull origin main --rebase     # before starting new work
```

## Non-negotiables

1. Every number in the demo comes from a real query. Nothing hard-coded.
2. Ground-truth labels are human. No model defines truth.
3. Training data and test data never overlap.
4. Every model call is logged to `model_runs` from request #1.
5. `evidence` must be a verbatim substring of the notice, or we escalate.
6. Business signals, not citizen profiling. No automated outreach. A human decides.

## Data source

Officiële Bekendmakingen (Staatscourant, Staatsblad, gemeenteblad, provincieblad,
waterschapsblad), published by KOOP under a CC0 licence and queried through the SRU
interface. Public, reusable, no scraping of anything the government didn't publish
deliberately.

## Licence

MIT.
