-- AEGIS Labs public training platform: challenge catalog, progress,
-- teams, security reports, and classrooms. Runs in the SAME production
-- Supabase project as the main app (these are platform/community tables,
-- not lab target data) but never stores lab exploit payloads here.

create table challenges (
  id text primary key,                 -- e.g. 'api1-bola-project-files'
  owasp_category text not null check (owasp_category in (
    'API1-BOLA','API2-BROKEN-AUTH','API3-BOPLA','API4-RESOURCE-CONSUMPTION',
    'API5-BFLA','API6-SENSITIVE-FLOWS','API7-SSRF','API8-MISCONFIGURATION',
    'API9-INVENTORY','API10-UNSAFE-CONSUMPTION'
  )),
  title text not null,
  difficulty text not null check (difficulty in ('beginner','intermediate','advanced')),
  summary text not null,
  learning_objectives text[] not null default '{}',
  prerequisites text[] not null default '{}',
  authorized_scope text not null,       -- what the user is authorized to test, spelled out
  required_services text[] not null,    -- docker-compose service names
  hints text[] not null default '{}',
  remediation_markdown text not null,
  points int not null default 100,
  is_published boolean not null default true,
  created_at timestamptz not null default now()
);

create table user_progress (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  challenge_id text not null references challenges(id) on delete cascade,
  status text not null default 'in_progress' check (status in ('in_progress','completed','reset')),
  verification_mode text check (verification_mode in ('server_verified','local_unverified')),
  points_awarded int not null default 0,
  completed_at timestamptz,
  created_at timestamptz not null default now(),
  unique (user_id, challenge_id)
);
create index idx_progress_user on user_progress(user_id);
create index idx_progress_challenge on user_progress(challenge_id);

-- Verification attempts are logged separately from progress so completion
-- can never be achieved by writing directly to user_progress from the
-- client: only the backend's verification service may upsert there.
create table verification_attempts (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  challenge_id text not null references challenges(id) on delete cascade,
  outcome text not null check (outcome in ('passed','failed')),
  evidence_summary text,     -- short, non-sensitive description; never raw payloads
  verified_by text not null check (verified_by in ('server','local_cli')),
  created_at timestamptz not null default now()
);
create index idx_verification_user_challenge on verification_attempts(user_id, challenge_id);
create index idx_verification_rate_limit on verification_attempts(user_id, created_at desc);

create table achievements (
  id text primary key,
  title text not null,
  description text not null,
  icon text not null
);

create table user_achievements (
  user_id uuid not null references auth.users(id) on delete cascade,
  achievement_id text not null references achievements(id) on delete cascade,
  earned_at timestamptz not null default now(),
  primary key (user_id, achievement_id)
);

create table teams (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  mode text not null default 'mixed' check (mode in ('red','blue','mixed')),
  created_by uuid not null references auth.users(id),
  created_at timestamptz not null default now()
);

create table team_members (
  team_id uuid not null references teams(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  role text not null default 'member' check (role in ('lead','member')),
  joined_at timestamptz not null default now(),
  primary key (team_id, user_id)
);

create table team_sessions (
  id uuid primary key default gen_random_uuid(),
  team_id uuid not null references teams(id) on delete cascade,
  challenge_id text not null references challenges(id),
  mode text not null check (mode in ('attack','defense')),
  started_at timestamptz not null default now(),
  ended_at timestamptz
);

create table vulnerability_reports (
  id uuid primary key default gen_random_uuid(),
  team_id uuid references teams(id) on delete set null,
  reporter_id uuid not null references auth.users(id),
  challenge_id text not null references challenges(id),
  title text not null,
  severity text not null check (severity in ('low','medium','high','critical')),
  description text not null,
  remediation_status text not null default 'open' check (remediation_status in ('open','in_progress','fixed','wont_fix')),
  assignee_id uuid references auth.users(id),
  created_at timestamptz not null default now()
);
create index idx_vuln_reports_team on vulnerability_reports(team_id);

create table retests (
  id uuid primary key default gen_random_uuid(),
  report_id uuid not null references vulnerability_reports(id) on delete cascade,
  tester_id uuid not null references auth.users(id),
  result text not null check (result in ('still_vulnerable','fixed')),
  notes text,
  created_at timestamptz not null default now()
);

create table classrooms (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  instructor_id uuid not null references auth.users(id),
  created_at timestamptz not null default now()
);

create table classroom_students (
  classroom_id uuid not null references classrooms(id) on delete cascade,
  student_id uuid not null references auth.users(id) on delete cascade,
  joined_at timestamptz not null default now(),
  primary key (classroom_id, student_id)
);

create table classroom_assignments (
  id uuid primary key default gen_random_uuid(),
  classroom_id uuid not null references classrooms(id) on delete cascade,
  challenge_id text not null references challenges(id),
  due_at timestamptz,
  created_at timestamptz not null default now()
);
