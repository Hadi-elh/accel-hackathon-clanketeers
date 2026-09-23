# ReguLine — project context

Read this first. Full detail lives in `PLAYBOOK.md`.

## What we are building

Dutch authorities publish 1,000+ official notices every day (permits, zoning decisions,
building transformations). It is free, public, and unreadable — written for legal
compliance, not for sales.

ReguLine reads the whole stream and returns only the notices that matter to **one specific
company**, with the verbatim sentence that proves it and a link to the official source.

**Pitch line:** the data is free, the judgement is the product.

## The demo customer (fixed — do not change)

Van Dijk Techniek (fictional, labelled as such in the demo):

- 28 employees, based in Amsterdam, 35 km service radius
- Services: commercial electrical installation, EV charging, access control, commercial lighting
- Wants: office renovations, warehouses, retail, hospitality, multi-unit residential
- Does not want: single-home dakkapellen, tree permits, private gardens, events
- Project size: €10k–€250k

## Architecture

```
KOOP SRU (official Dutch publications, CC0)
        │
        ▼
DETERMINISTIC PREFILTER          <- no model calls here
date · geo radius · rubriek
        │
        ▼
SMALL OPEN MODEL (Nebius Token Factory)
decision · confidence · evidence · project type · matched services
        │
   ┌────┴────┐
confident   uncertain / no evidence / invalid schema
   │             │
   │             ▼
   │      LARGE MODEL (Nebius Token Factory)
   │      adjudicate · verify evidence
   └────┬────────┘
        ▼
  signals table  →  API  →  UI (feed + map)
```

**Core thesis:** reasoning tokens should be spent in proportion to uncertainty.

## Models

Confirm exact IDs and prices against the Nebius dashboard / starter kit before use.

| Role | Candidate | Notes |
|---|---|---|
| Small classifier | Nemotron 3 Nano 30B A3B | cheapest tier, high volume |
| Large adjudicator | gpt-oss-120b | escalation only |
| Expensive baseline (eval row only) | a large reasoning model (DeepSeek V4 Pro / Qwen3.5 397B class) | shows what "big model on everything" costs |
| Offline closed baseline | Claude (Anthropic credits) | eval only, never in product path |

Not used: embeddings, RAG, vision, agents, LLM-as-judge. The task outputs a discrete
label, so exact matching against human labels is the correct evaluation.

## Ownership

| Folder | Owner | Deliverable |
|---|---|---|
| `/ingest` | A | KOOP fetch, XML parse, prefilter, `notices` rows |
| `/models`, `/eval` | B | Nebius client, router, benchmark, comparison table |
| `/app` | C | Supabase, FastAPI, UI, hosting, slides, submission |

Shared files (`CONTRACTS.md`, `schema.sql`, `CLAUDE.md`, `CONTEXT.md`) change only in a
team sync, never unilaterally.

## Timeline

| Time | Focus |
|---|---|
| 0:00–0:35 | Data + labels. A: SRU. B: client skeleton. C: Supabase + schema |
| 0:35–1:15 | **Benchmark first.** Small model then large model over the eval set |
| 1:15–2:00 | Router: validation, evidence check, escalation, retries |
| 2:00–2:45 | Demo product only. No auth, billing, CRM, settings |
| 2:45–3:15 | Deploy + public benchmark page. Freeze features |
| 3:15–4:00 | Submission fields, slides, backup demo video, rehearse 3x |

**Standing rule:** if forced to choose between a beautiful map and a real benchmark,
choose the benchmark and ship an ugly map.

## Non-negotiables

1. Every number shown in the demo comes from a real query. Nothing hard-coded.
2. Ground-truth labels are human. No model defines truth.
3. Training data and test data never overlap.
4. Every model call is logged to `model_runs` from request #1.
5. `evidence` must be a verbatim substring of the notice, or we escalate.
6. Output is a "project signal", never a "guaranteed lead".
