-- Minimal stand-in for the parts of a real Supabase project that our
-- migrations assume exist: the `auth` schema, `auth.users`, `auth.uid()`,
-- and an `authenticated` role that RLS policies are written against.
-- Applied ONLY in CI/local integration testing against a plain
-- `postgres:16` container — never run this against a real Supabase
-- project, which already provides all of this natively.

create extension if not exists pgcrypto;

create schema if not exists auth;

create table if not exists auth.users (
  id uuid primary key default gen_random_uuid(),
  email text
);

-- Real Supabase sets `request.jwt.claim.sub` via PostgREST per-request;
-- tests set it explicitly with `set_config` before each query to simulate
-- "being" a given authenticated user.
create or replace function auth.uid() returns uuid
language sql stable
as $$
  select nullif(current_setting('request.jwt.claim.sub', true), '')::uuid;
$$;

do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'authenticated') then
    create role authenticated;
  end if;
end
$$;

grant usage on schema public to authenticated;
grant usage on schema auth to authenticated;
