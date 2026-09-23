# ReguLine — read before doing anything

Product and architecture: `CONTEXT.md`.
Data shapes and function signatures: `CONTRACTS.md`.
Database: `schema.sql`.

This is a 4-hour hackathon build with three people working in parallel on separate
branches. Scope discipline matters more than elegance.

## Folder ownership — do not cross it

| Folder | Owner |
|---|---|
| `/ingest` | A |
| `/models`, `/eval` | B |
| `/app` | C |

Only edit files in the folder you own. If you need a change elsewhere, say so in chat
instead of editing. Never edit `CONTRACTS.md`, `schema.sql`, `CONTEXT.md` or this file
without an explicit instruction from the user — three people depend on them.

## Hard rules

1. **Never invent data.** Every number in the UI comes from a real query. No hard-coded
   funnel counts, no placeholder metrics, no fabricated company names or contacts.
2. **Log every model call** to `model_runs`: model, stage, tokens, latency_ms, cost_eur.
   Logging is not an afterthought; a call that isn't logged doesn't exist.
3. **Validate every model output** against `/models/schema.json`. `evidence` must be a
   verbatim substring of `notice.body`. If not, escalate — never publish it.
4. **Never let one bad response kill a scan.** Parse failure → retry once → escalate to
   the large model → record `decision='uncertain'` with an `error`. Keep going.
5. **Ground truth is human.** Do not generate or overwrite `eval_items` rows where
   `split='test'`. Model-generated labels are allowed only for `split='train'`.
6. **No leakage.** Anything used for fine-tuning is `split='train'` and never evaluated on.

## Do not build

Chatbots, authentication, CRM sync, billing, email sending, settings pages, RAG, vector
search, embeddings, agent loops, LLM-as-judge. The task outputs a discrete label, so
exact matching against human labels is the correct evaluation method.

No new dependencies without asking. Stack is Python, FastAPI, Supabase, and the Nebius
OpenAI-compatible SDK.

## Style

Small testable functions. Type hints. No clever abstractions — someone else reads this
at hour three under pressure. Prefer one obvious file over three tidy ones.

## Git

Work on your own branch (`feat/ingest`, `feat/models`, `feat/app`). Commit roughly every
15 minutes. Never push to `main` — merges happen at three fixed points, run by C.
Before starting new work: `git pull origin main --rebase`.
