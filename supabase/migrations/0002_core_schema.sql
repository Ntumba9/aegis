-- Core multi-tenant SaaS schema: profiles, organizations, membership,
-- projects/tasks, documents, api keys, webhooks, and request logs.

create table profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  full_name text,
  avatar_url text,
  created_at timestamptz not null default now()
);

create table organizations (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  created_at timestamptz not null default now()
);

create table memberships (
  org_id uuid not null references organizations(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  role text not null check (role in ('owner', 'admin', 'employee')),
  created_at timestamptz not null default now(),
  primary key (org_id, user_id)
);
create index idx_memberships_user on memberships(user_id);

create table invitations (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references organizations(id) on delete cascade,
  email text not null,
  role text not null check (role in ('admin', 'employee')),
  token text not null unique,
  status text not null default 'pending' check (status in ('pending', 'accepted', 'revoked')),
  created_by uuid not null references auth.users(id),
  created_at timestamptz not null default now()
);
create index idx_invitations_org on invitations(org_id);

create table projects (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references organizations(id) on delete cascade,
  name text not null,
  description text,
  created_by uuid not null references auth.users(id),
  created_at timestamptz not null default now()
);
create index idx_projects_org on projects(org_id);

create table tasks (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references projects(id) on delete cascade,
  title text not null,
  description text,
  assignee_id uuid references auth.users(id),
  status text not null default 'todo' check (status in ('todo', 'in_progress', 'done')),
  created_by uuid not null references auth.users(id),
  created_at timestamptz not null default now()
);
create index idx_tasks_project on tasks(project_id);

create table documents (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references organizations(id) on delete cascade,
  project_id uuid references projects(id) on delete cascade,
  storage_path text not null,
  filename text not null,
  content_type text not null,
  size_bytes bigint not null check (size_bytes >= 0),
  uploaded_by uuid not null references auth.users(id),
  created_at timestamptz not null default now()
);
create index idx_documents_org on documents(org_id);

create table api_keys (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references organizations(id) on delete cascade,
  name text not null,
  key_hash text not null unique,
  scopes text[] not null default array['read'],
  last_used_at timestamptz,
  revoked_at timestamptz,
  created_by uuid not null references auth.users(id),
  created_at timestamptz not null default now()
);
create index idx_api_keys_org on api_keys(org_id);

create table webhooks (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references organizations(id) on delete cascade,
  target_url text not null,
  signing_secret text not null,
  event_types text[] not null,
  is_active boolean not null default true,
  created_by uuid not null references auth.users(id),
  created_at timestamptz not null default now()
);
create index idx_webhooks_org on webhooks(org_id);

create table webhook_deliveries (
  id uuid primary key default gen_random_uuid(),
  webhook_id uuid not null references webhooks(id) on delete cascade,
  event_type text not null,
  payload jsonb not null,
  status text not null default 'pending' check (status in ('pending', 'delivered', 'failed')),
  attempt_count int not null default 0,
  last_attempted_at timestamptz,
  created_at timestamptz not null default now()
);
create index idx_webhook_deliveries_webhook on webhook_deliveries(webhook_id);

create table request_logs (
  id uuid primary key default gen_random_uuid(),
  org_id uuid references organizations(id) on delete cascade,
  api_key_id uuid references api_keys(id) on delete set null,
  method text not null,
  path text not null,
  status_code int not null,
  latency_ms int not null,
  created_at timestamptz not null default now()
);
create index idx_request_logs_org_time on request_logs(org_id, created_at desc);
