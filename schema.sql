-- ReguLine schema. Applied once by owner C in the Supabase SQL editor.
-- Do not modify without a team sync (see CONTRACTS.md).

create extension if not exists "pgcrypto";

-- ---------------------------------------------------------------- profiles
create table if not exists company_profiles (
  id                       text primary key,        -- 'vandijk'
  name                     text not null,
  lat                      double precision not null,
  lng                      double precision not null,
  radius_km                int not null default 35,
  services                 jsonb not null default '[]',
  preferred_property_types jsonb not null default '[]',
  excluded_project_types   jsonb not null default '[]',
  created_at               timestamptz default now()
);

-- ---------------------------------------------------------------- notices
create table if not exists notices (
  id            text primary key,                   -- KOOP identifier
  source_url    text,
  title         text,
  body          text,
  published_on  date,
  municipality  text,
  rubriek       text,
  lat           double precision,                   -- nullable
  lng           double precision,                   -- nullable
  fetched_at    timestamptz default now()
);

create index if not exists notices_published_idx on notices (published_on);

-- ---------------------------------------------------------------- signals
create table if not exists signals (
  id               uuid primary key default gen_random_uuid(),
  notice_id        text references notices(id) on delete cascade,
  profile_id       text references company_profiles(id) on delete cascade,
  decision         text not null,                   -- relevant | irrelevant | uncertain
  confidence       numeric,
  project_type     text,
  property_type    text,
  project_stage    text,
  matched_services jsonb default '[]',
  evidence         text,
  reason           text,
  escalated        boolean default false,
  model_used       text,
  error            text,
  created_at       timestamptz default now(),
  unique (notice_id, profile_id)
);

create index if not exists signals_profile_decision_idx
  on signals (profile_id, decision, confidence desc);

-- ------------------------------------------------------------- telemetry
-- Judging evidence. Log EVERY model call from request #1.
create table if not exists model_runs (
  id             uuid primary key default gen_random_uuid(),
  notice_id      text,
  profile_id     text,
  model          text not null,
  stage          text,                              -- small | large | baseline | finetuned
  prompt_version text,
  input_tokens   int,
  output_tokens  int,
  latency_ms     int,
  cost_eur       numeric,
  ok             boolean default true,
  error          text,
  created_at     timestamptz default now()
);

create index if not exists model_runs_model_idx on model_runs (model, created_at);

-- ----------------------------------------------------------------- scans
-- One row per POST /api/scan run. Owner: C (/app's scan orchestrator is
-- the only writer -- see CONTRACTS.md).
create table if not exists scan_runs (
  id               uuid primary key default gen_random_uuid(),
  profile_id       text references company_profiles(id) on delete cascade,
  scan_date        date,
  started_at       timestamptz default now(),
  finished_at      timestamptz,
  status           text not null default 'running',  -- running | done | failed
  error            text,
  fetched          int,
  kept             int,
  prefilter_stats  jsonb,        -- full ingest.prefilter.prefilter_stats_for_date() dict
  rule_rejected    int,
  ai_analysed      int,
  escalated        int,
  uncertain        int,
  no_text          int,          -- rows with error='empty_or_short_body'
  relevant         int,
  cost_eur         numeric,
  prompt_version   text,
  rules_version    text
);

create index if not exists scan_runs_profile_date_idx
  on scan_runs (profile_id, scan_date desc);

-- ------------------------------------------------------------------ eval
create table if not exists eval_items (
  notice_id         text primary key references notices(id) on delete cascade,
  expected_decision text not null,                  -- human label, never model-generated
  expected_category text,
  expected_service  text,
  expected_evidence text,
  labeller          text,
  split             text not null default 'test',   -- test | train
  created_at        timestamptz default now()
);

create table if not exists eval_results (
  id         uuid primary key default gen_random_uuid(),
  notice_id  text references eval_items(notice_id) on delete cascade,
  config     text not null,                         -- small|large|router|baseline_closed|finetuned
  prediction text,
  correct    boolean,
  escalated  boolean default false,
  latency_ms int,
  cost_eur   numeric,
  run_at     timestamptz default now()
);

create index if not exists eval_results_config_idx on eval_results (config);

-- ------------------------------------------------------- convenience view
-- Powers the public benchmark page and the pitch table.
create or replace view benchmark_summary as
select
  config,
  count(*)                                          as items,
  round(avg(case when correct then 1 else 0 end)::numeric, 3) as accuracy,
  round(avg(case when escalated then 1 else 0 end)::numeric, 3) as escalation_rate,
  percentile_cont(0.95) within group (order by latency_ms)      as p95_latency_ms,
  round(sum(cost_eur) / nullif(count(*), 0) * 1000, 4)          as cost_eur_per_1k
from eval_results
group by config;

-- Seed the demo profile.
insert into company_profiles (id, name, lat, lng, radius_km, services,
                              preferred_property_types, excluded_project_types)
values (
  'vandijk', 'Van Dijk Techniek', 52.3702, 4.8952, 35,
  '["commercial electrical installations","EV charging infrastructure","access control systems","commercial lighting"]',
  '["office","warehouse","retail","hospitality","multi-unit residential"]',
  '["single-family minor renovation","tree removal","events","private gardens"]'
)
on conflict (id) do nothing;
