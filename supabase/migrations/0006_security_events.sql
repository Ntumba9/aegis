-- Security events: the single source the Blue Team dashboard reads from
-- (auth failures, authorization denials, rate-limit violations, and
-- anything else app/core/audit.py or the request-logging middleware
-- decides is worth recording). "Alerts" are simply events at
-- high/critical severity — not a separate table, to avoid two sources of
-- truth for the same data.

create table security_events (
  id uuid primary key default gen_random_uuid(),
  org_id uuid references organizations(id) on delete cascade,
  actor_id uuid references auth.users(id) on delete set null,
  event_type text not null,
  severity text not null default 'info' check (severity in ('info', 'warning', 'high', 'critical')),
  metadata jsonb not null default '{}',
  created_at timestamptz not null default now()
);
create index idx_security_events_org_time on security_events(org_id, created_at desc);
create index idx_security_events_type on security_events(event_type);

alter table security_events enable row level security;

-- Only org admins/owners can read their org's events; there is no INSERT
-- policy for the `authenticated` role at all — only the backend's own
-- service-role connection writes here, exactly like user_achievements.
create policy security_events_admin_select on security_events
  for select using (org_id is not null and org_role(org_id) in ('owner', 'admin'));
