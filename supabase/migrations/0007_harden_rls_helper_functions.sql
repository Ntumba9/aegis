-- Supabase's security advisor flagged is_org_member/org_role/is_team_member/
-- is_classroom_instructor as directly callable by anon/authenticated via
-- PostgREST's auto-exposed /rest/v1/rpc/<fn> routes, since PostgREST exposes
-- every function in the `public` schema by default. These were only ever
-- meant to be called from inside RLS policies, not as a public API surface.
-- Fix: move them to a `private` schema (not in PostgREST's exposed schema
-- list), which blocks the RPC auto-exposure while RLS policies — which
-- reference functions by schema-qualified name at the query-plan level, not
-- through PostgREST's HTTP routing — keep working identically.
--
-- Applied directly to the live project during deployment; captured here so
-- the migration history in this repo matches the actual deployed schema.

create schema if not exists private;

create or replace function private.is_org_member(target_org uuid)
returns boolean
language sql
security definer
set search_path = public
as $$
  select exists (
    select 1 from memberships
    where org_id = target_org and user_id = auth.uid()
  );
$$;

create or replace function private.org_role(target_org uuid)
returns text
language sql
security definer
set search_path = public
as $$
  select role from memberships
  where org_id = target_org and user_id = auth.uid();
$$;

create or replace function private.is_team_member(target_team uuid)
returns boolean language sql security definer set search_path = public as $$
  select exists (select 1 from team_members where team_id = target_team and user_id = auth.uid());
$$;

create or replace function private.is_classroom_instructor(target_classroom uuid)
returns boolean language sql security definer set search_path = public as $$
  select exists (select 1 from classrooms where id = target_classroom and instructor_id = auth.uid());
$$;

-- Repoint every policy at the private-schema versions.
alter policy orgs_member_select on organizations
  using (private.is_org_member(id));

alter policy memberships_member_select on memberships
  using (private.is_org_member(org_id));
alter policy memberships_admin_write on memberships
  using (private.org_role(org_id) in ('owner', 'admin'));

alter policy invitations_admin_all on invitations
  using (private.org_role(org_id) in ('owner', 'admin'));

alter policy projects_member_select on projects
  using (private.is_org_member(org_id));
alter policy projects_admin_write on projects
  with check (private.org_role(org_id) in ('owner', 'admin'));
alter policy projects_admin_update on projects
  using (private.org_role(org_id) in ('owner', 'admin'));
alter policy projects_admin_delete on projects
  using (private.org_role(org_id) in ('owner', 'admin'));

alter policy tasks_member_select on tasks
  using (
    exists (select 1 from projects p where p.id = tasks.project_id and private.is_org_member(p.org_id))
  );
alter policy tasks_member_write on tasks
  with check (
    exists (select 1 from projects p where p.id = tasks.project_id and private.is_org_member(p.org_id))
  );

alter policy documents_member_select on documents
  using (private.is_org_member(org_id));
alter policy documents_member_insert on documents
  with check (private.is_org_member(org_id));

alter policy api_keys_admin_all on api_keys
  using (private.org_role(org_id) in ('owner', 'admin'));

alter policy webhooks_admin_all on webhooks
  using (private.org_role(org_id) in ('owner', 'admin'));

alter policy webhook_deliveries_admin_select on webhook_deliveries
  using (
    exists (select 1 from webhooks w where w.id = webhook_deliveries.webhook_id and private.org_role(w.org_id) in ('owner', 'admin'))
  );

alter policy request_logs_admin_select on request_logs
  using (private.org_role(org_id) in ('owner', 'admin'));

alter policy teams_member_select on teams
  using (private.is_team_member(id) or created_by = auth.uid());

alter policy team_members_select on team_members
  using (private.is_team_member(team_id));

alter policy team_sessions_member_select on team_sessions
  using (private.is_team_member(team_id));
alter policy team_sessions_member_insert on team_sessions
  with check (private.is_team_member(team_id));

alter policy vuln_reports_team_select on vulnerability_reports
  using (team_id is null or private.is_team_member(team_id));
alter policy vuln_reports_team_update on vulnerability_reports
  using (team_id is null or private.is_team_member(team_id));

alter policy retests_report_select on retests
  using (
    exists (select 1 from vulnerability_reports r where r.id = retests.report_id
            and (r.team_id is null or private.is_team_member(r.team_id)))
  );

alter policy classroom_students_instructor_all on classroom_students
  using (private.is_classroom_instructor(classroom_id));

alter policy classroom_assignments_instructor_all on classroom_assignments
  using (private.is_classroom_instructor(classroom_id));

alter policy security_events_admin_select on security_events
  using (org_id is not null and private.org_role(org_id) in ('owner', 'admin'));

-- Now safe to drop the old public-schema versions — nothing references them.
drop function if exists public.is_org_member(uuid);
drop function if exists public.org_role(uuid);
drop function if exists public.is_team_member(uuid);
drop function if exists public.is_classroom_instructor(uuid);
