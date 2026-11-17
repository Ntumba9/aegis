-- Server-run lab regression checks for vulnerability reports.
-- Kept in its OWN table, separate from `retests`: `retests.result` is a
-- human-declared claim (still_vulnerable / fixed). These rows are the real
-- outcome of running the lab's regression test and are never folded into it.

create table retest_lab_runs (
  id uuid primary key default gen_random_uuid(),
  report_id uuid not null references vulnerability_reports(id) on delete cascade,
  challenge_id text not null references challenges(id),
  requested_by uuid not null references auth.users(id),
  outcome text not null check (outcome in ('passed', 'failed', 'error', 'unreachable')),
  tests text[] not null,                 -- the allowlisted test file(s) that ran
  duration_ms integer not null check (duration_ms >= 0),
  summary text not null default '',      -- counts + failing test names only, never raw output
  started_at timestamptz not null default now(),
  finished_at timestamptz not null default now()
);
create index idx_retest_lab_runs_report on retest_lab_runs(report_id, started_at desc);
create index idx_retest_lab_runs_challenge on retest_lab_runs(challenge_id, finished_at desc);
create index idx_retest_lab_runs_user on retest_lab_runs(requested_by, started_at desc);

-- RLS on with NO policies: PostgREST (the `authenticated` role) can read or
-- write nothing here. Only the backend's own service-role connection does,
-- and it re-implements the team/reporter checks (app/api/lab_verification.py).
alter table retest_lab_runs enable row level security;
