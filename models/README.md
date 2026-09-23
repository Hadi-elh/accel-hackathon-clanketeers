# /models — ReguLine classification layer (owner: B)

**If this document and `/CONTRACTS.md` disagree, `/CONTRACTS.md` is the absolute source of truth.**

All paths are relative to the repository root. Python imports use the package form
(`/models/router.py` is imported as `models.router`). Run every command from the repo root.

## What this folder does

ReguLine is signal discovery, not a recommendation engine. The only question this folder answers is:
does this official publication describe activity that matches the company's configured monitoring
profile (services, monitored property types, exclusions)? It never judges whether the company should
pursue it, whether it is a good lead, or whether it is feasible; a human decides that. `relevant`
means "matches the monitoring profile", nothing more. `confidence` is internal (routing, eval) and
must never be shown to users as a percentage. Example profile: the electrical installer Van Dijk Techniek. Free keyword rules decide the obvious cases,
a small open model on Nebius Token Factory handles the bulk, and a large model is called only
when the small one is uncertain or produces invalid output. Every model call is logged.

```
notice -> /models/rules.py -> /models/client.py (small)
       -> /models/client.py (large, only on a trigger) -> /models/router.py returns one result
```

Input shape (`/CONTRACTS.md` §1):

```json
{"id": "c", "title": "Aanvraag",
 "body": "Er is een aanvraag ontvangen voor het transformeren en uitbreiden van het bestaande bedrijfspand aan de Kade 7.",
 "published_on": "2026-09-23", "municipality": "Amsterdam", "rubriek": "omgevingsvergunning",
 "lat": 52.34, "lng": 4.87}
```

## Files

### `/models/schema.json` — output contract as JSON Schema

The 8 required fields from `/CONTRACTS.md` §3: `decision`, `confidence`, `project_type`,
`property_type`, `matched_services`, `project_stage`, `evidence`, `reason`. Sent to Nebius as the
structured-output schema. Enums for `decision` and `project_stage`, `confidence` in 0–1, no extra
keys. `matched_services` is left open in the file; `/models/client.py` injects the profile's
`services` as its enum at request time.

```json
{"decision": "relevant", "confidence": 0.9, "project_type": "commercial renovation",
 "property_type": "office", "matched_services": ["commercial electrical installations"],
 "project_stage": "permit_application",
 "evidence": "transformeren en uitbreiden van het bestaande bedrijfspand",
 "reason": "Renovation of an office, a monitored property type, related to configured electrical installation services."}
```

### `/models/prompt.py` — versioned prompt

`build_messages(notice, profile) -> [system, user]`.

- System: the company's monitoring profile plus decision rules, framed as profile matching, not
  lead scoring. `property_type` must copy a monitored property type exactly when one applies, so
  the UI can show transparent criteria (e.g. property type in the profile, services matched). When torn between relevant and irrelevant the model
  must say `uncertain`. Evidence is required for every decision, copied verbatim in Dutch from the
  body; for irrelevant notices it is the span that rules the notice out (e.g. "kappen van een boom").
  Dutch stage hints ("aanvraag ontvangen" -> `permit_application`, "verleend" -> `permit_granted`).
- User: title, municipality, rubriek, date, body (capped at `MAX_BODY_CHARS = 6000`).
- `PROMPT_VERSION = "v2"` is logged on every call. Bump it on any edit.
- Tune the prompt only on notices that are not in the test split.

### `/models/log.py` — telemetry

`log_run(notice_id, profile_id, meta)` inserts one row into the Supabase `model_runs` table per
model call. If Supabase fails it appends to `/models/runs.local.jsonl`. Never raises.

```json
{"notice_id": "c", "profile_id": "vandijk", "model": "<nebius-model-id>", "stage": "small",
 "prompt_version": "v2", "input_tokens": 1000, "output_tokens": 200, "latency_ms": 850,
 "cost_eur": 0.0000972, "ok": true, "error": null}
```

### `/models/client.py` — one model call

`classify(notice, profile, model_alias) -> (result | None, meta)`. One logical call, never raises,
no retry or escalation (that belongs to `/models/router.py`).

Aliases in `MODELS`:

| alias | model | purpose |
|---|---|---|
| `small` | Nemotron 3 Nano, thinking off | product path |
| `small_think` | same model, default reasoning | measurement only |
| `large` | gpt-oss-120b, `reasoning_effort` medium | escalation |
| `baseline_open` | large reasoning model | eval row |
| `finetuned` | LoRA of small | eval row |
| `baseline_closed` | Claude | eval only, never in the product path |

Model IDs and prices are placeholders filled from the Nebius dashboard. A missing price gives
`cost_eur = None`, never a guessed number.

Call sequence:

1. Request strict `json_schema` output.
2. On HTTP 400, probe to find the cause. If the model rejects even a trivial schema, downgrade to
   `json_object`, then no format. If only our `extra_body` fails, raise
   `ConfigRejected: extra_body rejected`. If only our schema fails, raise
   `ConfigRejected: schema rejected`. `ConfigRejected` never downgrades.
3. Parse JSON (tolerates `<think>` blocks and code fences), drop extra keys.
4. `validate()`: required keys, enums, confidence range, `matched_services` subset of the profile,
   `evidence` a verbatim substring of `notice.body` (whitespace collapsed, edge quotes and "..."
   stripped, at least 12 characters).
5. Cost from token counts. `output_tokens` includes hidden reasoning tokens.

```json
{"model": "<id>", "stage": "small", "mode": "json_schema", "input_tokens": 1000,
 "output_tokens": 200, "reasoning_tokens": null, "reasoning_chars": 0, "latency_ms": 850,
 "cost_eur": 0.0000972, "finish_reason": "stop", "ok": false,
 "error": "evidence_not_verbatim", "errors": ["evidence_not_verbatim"], "raw": "..."}
```

Reasoning audit (runs `small`, `small_think`, `large` on 5 notices, prints averages):

```bash
python -m models.client ingest/sample_notices.json 5
```

### `/models/rules.py` — free deterministic triage

`triage(notice, profile) -> Triage(reject, rule, positive_hits)`.

1. Reject obvious non-projects: tree felling, dormers, events, market stalls, driveways, traffic
   decisions, moorings. Fires only when the notice contains no commercial keyword. Some rules apply
   only if the profile's `excluded_project_types` lists that type. Evidence is the matching sentence
   sliced from the body, so it is verbatim by construction.
2. Positive keywords (bedrijfspand, kantoor, appartementen, laadpaal, nieuwbouw, ...) never accept
   anything. They only make `/models/router.py` escalate when the small model says irrelevant.

- "...aanvraag ontvangen voor het kappen van een boom aan de Lindengracht 12" -> rejected by
  `tree_felling`, no model call.
- "nieuwbouw van 40 appartementen en het kappen van 3 bomen" -> not rejected, hits
  `["appartementen", "nieuwbouw"]`, goes to the model.
- "kapvergunning ... ter inzage tijdens kantooruren" -> rejected; "kantooruren" is not "kantoor".

### `/models/router.py` — product entry point

`classify_notice(notice, profile, *, threshold=0.82, trace=None) -> dict`, matching
`/CONTRACTS.md` §4. Never raises. `threshold` can be set with the `ROUTER_THRESHOLD` env var.

1. Rules. A reject returns immediately at cost 0.
2. Small model. One retry on `parse_failed` or network errors; no retry on `truncated` or
   `ConfigRejected`.
3. Escalate to the large model if any trigger fires: invalid output, `decision == "uncertain"`,
   `confidence < threshold`, or small says irrelevant while rules found commercial keywords
   (`rule_conflict`).
4. Large valid -> return it with `escalated: true`. Large fails or gives invalid evidence ->
   `decision: "uncertain"` with `error`. Surfaced for review, never published.

Returns the 8 contract fields plus `escalated`, `model_used`, `cost_eur` (sum of all calls),
`error`, `latency_ms` (wall clock including retries). The optional `trace` dict receives
`decided_by` (`rules` | `small` | `large` | `fallback`), `triggers`, `rule`, `positive_hits`, and
every call's meta.

Rules path:

```json
{"decision": "irrelevant", "confidence": 0.95, "project_type": "tree removal",
 "property_type": "unknown", "matched_services": [], "project_stage": "permit_application",
 "evidence": "Burgemeester en wethouders hebben een aanvraag ontvangen voor het kappen van een boom aan de Lindengracht 12",
 "reason": "Rule r2/tree_felling: tree removal is excluded in this monitoring profile.",
 "escalated": false, "model_used": "rules:r2", "cost_eur": 0.0, "error": null, "latency_ms": 0}
```

Escalation path: office notice, small says `irrelevant` at 0.97, trigger
`rule_conflict:bedrijfspand,transformeren`, large says `relevant` -> `escalated: true`,
`model_used` = large ID, `cost_eur` = small + large.

Failure path:

```json
{"decision": "uncertain", "confidence": 0.0, "evidence": "",
 "reason": "Automatic classification failed; needs human review.",
 "error": "escalation_failed: evidence_not_verbatim", "escalated": true}
```

### `/models/selftest_router.py` — offline regression

```bash
python -m models.selftest_router
```

Replaces the model call with scripted responses and runs 16 router scenarios: rule rejects, mixed
trees + apartments, rule conflict, low confidence, retries, truncation, paraphrased evidence, large
also failing, total outage, a tree-care profile, threshold override, rules crash. Needs no API keys.
Re-run after any change to `/models/rules.py` or `/models/router.py`.

## Human setup (an AI cannot do these)

1. Fill `MODELS` IDs and prices in `/models/client.py` from the Nebius dashboard and copy them into
   `/models/PRICES.md`. Set `USD_TO_EUR`, or rename the cost column to `cost_usd` at the team sync.
2. Confirm the base URL against the Nebius starter kit; override with `NEBIUS_BASE_URL` if needed.
3. Environment: `NEBIUS_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY`, optionally `ANTHROPIC_API_KEY`.
4. Run the reasoning audit and check the Nebius dashboard usage against summed tokens in
   `model_runs`.

## TODO for the AI / Next steps

Rules that apply to every task below:

- Edit only files under `/models` and `/eval`. Never edit `/CONTRACTS.md`, `/schema.sql`,
  `/CONTEXT.md` or `/CLAUDE.md`. No new dependencies.
- Never write or modify `eval_items` rows with `split = 'test'`.
- `eval_results.config` must be one of: `"small"`, `"large"`, `"router"`, `"baseline_closed"`,
  `"finetuned"` (plus `"baseline_open"` only once `/CONTRACTS.md` lists it).

**Task 1. When you ingest this repository, your first task is to write `/eval/run.py` exactly
matching the interfaces above.**

- CLI: `python -m eval.run --config <config> [--threshold 0.82]`.
- Load `eval_items` where `split = 'test'` joined with `notices`, and the `vandijk` profile from
  `company_profiles`.
- `small`, `large`, `baseline_closed`, `finetuned`, `baseline_open`: call
  `models.client.classify(notice, profile, config)`.
- `router`: call `models.router.classify_notice(notice, profile, threshold=..., trace=trace)`.
- Per item, insert into `eval_results`: `notice_id`, `config`, `prediction` (the decision),
  `correct`, `escalated`, `latency_ms`, `cost_eur`. `correct` = the prediction mapped to binary
  (`relevant` and `uncertain` count as positive, `irrelevant` as negative) equals
  `expected_decision`. `expected_decision` is always `relevant` or `irrelevant`.
- Also append one JSON line per item to `/eval/runs/<config>.jsonl` containing the full result,
  full meta or trace (including `confidence`, `decided_by`, `triggers`), and the expected label.
  Never crash the run on one item.

**Task 2. Write `/eval/metrics.py`.**

- Positive = predicted `relevant` or `uncertain`. Report precision and recall separately, plus F1,
  accuracy on the borderline-flagged subset, evidence accuracy, p95 latency, cost per 1k notices,
  and escalation rate.
- `/schema.sql` has no borderline column. Use whatever storage `/CONTRACTS.md` specifies for the
  borderline flag; if it specifies none, skip the borderline metric and say so. Do not invent one.
- Evidence accuracy: correct if the predicted evidence contains the expected evidence or vice
  versa, after whitespace normalization and lowercasing. Only for items with `expected_evidence`.
- Score the decision only. Category and service are diagnostic, not scored.

**Task 3. Offline router replay in `/eval/metrics.py` (zero API calls).**

- From `/eval/runs/small.jsonl` and `/eval/runs/large.jsonl`, simulate the router at thresholds
  0.7, 0.8 and 0.9, with and without `/models/rules.py`, using the same triggers as
  `models.router.escalation_triggers`. Output one row per variant with F1, recall, precision,
  escalation rate, and cost per 1k.
- Plot a histogram of small-model `confidence` values.

Do not build: RAG, embeddings, agent loops, LLM-as-judge.
