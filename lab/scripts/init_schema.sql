-- Schema for the isolated lab-db. Synthetic data only; this database is
-- never the production Supabase instance and holds no real user data.

create table if not exists bola_projects (
  id serial primary key,
  owner_id int not null,
  name text not null,
  description text not null  -- carries the per-challenge flag for victim projects
);

create table if not exists bola_victim_projects (
  challenge_id text primary key,
  project_id int not null references bola_projects(id),
  flag text not null
);

create table if not exists ssrf_internal_secrets (
  challenge_id text primary key,
  secret text not null
);

-- Generic flag table used by the simpler challenges below: each challenge
-- stores one expected flag here; backend verify() reads it and compares
-- against the user's submission.
create table if not exists challenge_flags (
  challenge_id text primary key,
  flag text not null
);

-- API2 Broken Authentication: predictable, non-expiring session tokens.
create table if not exists lab_sessions (
  token text primary key,
  username text not null,
  mode text not null check (mode in ('vulnerable', 'hardened')),
  created_at timestamptz not null default now()
);
create sequence if not exists lab_sessions_vuln_seq;

-- API3 BOPLA / API5 BFLA / API9: lab users with a mutable role column.
create table if not exists lab_users (
  id int primary key,
  username text unique not null,
  display_name text,
  role text not null default 'user' check (role in ('user', 'admin'))
);

-- API4 Unrestricted Resource Consumption: a large synthetic dataset with
-- one sensitive row near the end, only reachable with an uncapped limit.
create table if not exists sensitive_records (
  id serial primary key,
  payload text not null
);

-- API6 Sensitive Business Flows: wallets + coupon redemption tracking.
create table if not exists wallets (
  username text primary key,
  balance int not null default 0
);
create table if not exists coupon_redemptions (
  username text not null,
  code text not null,
  redeemed_at timestamptz not null default now(),
  primary key (username, code)
);
