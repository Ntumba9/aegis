-- Persisted classroom invite tokens (previously an in-process dict in
-- app/api/classrooms.py: lost on restart, never expired, not shared across
-- workers). Only the SHA-256 of the token is stored; the plaintext is shown
-- once, to the instructor, when the invite is created.

create table classroom_invites (
  id uuid primary key default gen_random_uuid(),
  classroom_id uuid not null references classrooms(id) on delete cascade,
  token_hash text not null unique,   -- sha256 hex; the plaintext is shown once
  created_by uuid not null references auth.users(id),
  expires_at timestamptz not null,
  used_at timestamptz,
  used_by uuid references auth.users(id),
  created_at timestamptz not null default now()
);
create index idx_classroom_invites_classroom on classroom_invites(classroom_id);

-- RLS on with NO policies: the `authenticated` role (PostgREST) can read or
-- write nothing here. Only the backend's own service-role connection touches
-- this table, like the INSERT side of security_events / user_achievements.
alter table classroom_invites enable row level security;
