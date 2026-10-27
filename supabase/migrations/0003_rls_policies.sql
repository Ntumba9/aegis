-- Row Level Security: defense in depth behind the API's own authorization
-- checks. Every tenant-scoped table is locked down to members of the
-- owning organization; role escalation only happens via the service-role
-- key from the backend, never directly from the client.

alter table profiles enable row level security;
alter table organizations enable row level security;
alter table memberships enable row level security;
alter table invitations enable row level security;
alter table projects enable row level security;
alter table tasks enable row level security;
alter table documents enable row level security;
alter table api_keys enable row level security;
alter table webhooks enable row level security;
alter table webhook_deliveries enable row level security;
alter table request_logs enable row level security;

create or replace function is_org_member(target_org uuid)
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

create or replace function org_role(target_org uuid)
returns text
language sql
security definer
set search_path = public
as $$
  select role from memberships
  where org_id = target_org and user_id = auth.uid();
$$;

create policy profiles_self_select on profiles
  for select using (id = auth.uid());
create policy profiles_self_update on profiles
  for update using (id = auth.uid());

create policy orgs_member_select on organizations
  for select using (is_org_member(id));

create policy memberships_member_select on memberships
  for select using (is_org_member(org_id));
create policy memberships_admin_write on memberships
  for all using (org_role(org_id) in ('owner', 'admin'));

create policy invitations_admin_all on invitations
  for all using (org_role(org_id) in ('owner', 'admin'));

create policy projects_member_select on projects
  for select using (is_org_member(org_id));
create policy projects_admin_write on projects
  for insert with check (org_role(org_id) in ('owner', 'admin'));
create policy projects_admin_update on projects
  for update using (org_role(org_id) in ('owner', 'admin'));
create policy projects_admin_delete on projects
  for delete using (org_role(org_id) in ('owner', 'admin'));

create policy tasks_member_select on tasks
  for select using (
    exists (select 1 from projects p where p.id = tasks.project_id and is_org_member(p.org_id))
  );
create policy tasks_member_write on tasks
  for insert with check (
    exists (select 1 from projects p where p.id = tasks.project_id and is_org_member(p.org_id))
  );

create policy documents_member_select on documents
  for select using (is_org_member(org_id));
create policy documents_member_insert on documents
  for insert with check (is_org_member(org_id));

create policy api_keys_admin_all on api_keys
  for all using (org_role(org_id) in ('owner', 'admin'));

create policy webhooks_admin_all on webhooks
  for all using (org_role(org_id) in ('owner', 'admin'));

create policy webhook_deliveries_admin_select on webhook_deliveries
  for select using (
    exists (select 1 from webhooks w where w.id = webhook_deliveries.webhook_id and org_role(w.org_id) in ('owner', 'admin'))
  );

create policy request_logs_admin_select on request_logs
  for select using (org_role(org_id) in ('owner', 'admin'));
