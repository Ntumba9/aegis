alter table challenges enable row level security;
alter table user_progress enable row level security;
alter table verification_attempts enable row level security;
alter table achievements enable row level security;
alter table user_achievements enable row level security;
alter table teams enable row level security;
alter table team_members enable row level security;
alter table team_sessions enable row level security;
alter table vulnerability_reports enable row level security;
alter table retests enable row level security;
alter table classrooms enable row level security;
alter table classroom_students enable row level security;
alter table classroom_assignments enable row level security;

-- Challenges and achievements are public read (catalog browsing requires no auth).
create policy challenges_public_read on challenges for select using (is_published);
create policy achievements_public_read on achievements for select using (true);

-- Progress and verification attempts: a user only ever sees their own.
-- INSERT/UPDATE intentionally has no policy for the authenticated role —
-- only the backend's service-role key (which bypasses RLS) may write these,
-- enforcing "never trust a client-submitted success flag" at the DB layer.
create policy progress_self_select on user_progress
  for select using (user_id = auth.uid());
create policy verification_self_select on verification_attempts
  for select using (user_id = auth.uid());

create policy user_achievements_self_select on user_achievements
  for select using (user_id = auth.uid());

create or replace function is_team_member(target_team uuid)
returns boolean language sql security definer set search_path = public as $$
  select exists (select 1 from team_members where team_id = target_team and user_id = auth.uid());
$$;

create policy teams_member_select on teams
  for select using (is_team_member(id) or created_by = auth.uid());
create policy teams_creator_insert on teams
  for insert with check (created_by = auth.uid());

create policy team_members_select on team_members
  for select using (is_team_member(team_id));
create policy team_members_self_insert on team_members
  for insert with check (user_id = auth.uid());

create policy team_sessions_member_select on team_sessions
  for select using (is_team_member(team_id));
create policy team_sessions_member_insert on team_sessions
  for insert with check (is_team_member(team_id));

create policy vuln_reports_team_select on vulnerability_reports
  for select using (team_id is null or is_team_member(team_id));
create policy vuln_reports_reporter_insert on vulnerability_reports
  for insert with check (reporter_id = auth.uid());
create policy vuln_reports_team_update on vulnerability_reports
  for update using (team_id is null or is_team_member(team_id));

create policy retests_report_select on retests
  for select using (
    exists (select 1 from vulnerability_reports r where r.id = retests.report_id
            and (r.team_id is null or is_team_member(r.team_id)))
  );
create policy retests_tester_insert on retests
  for insert with check (tester_id = auth.uid());

create or replace function is_classroom_instructor(target_classroom uuid)
returns boolean language sql security definer set search_path = public as $$
  select exists (select 1 from classrooms where id = target_classroom and instructor_id = auth.uid());
$$;

create policy classrooms_instructor_all on classrooms
  for all using (instructor_id = auth.uid());
create policy classrooms_student_select on classrooms
  for select using (
    exists (select 1 from classroom_students cs where cs.classroom_id = classrooms.id and cs.student_id = auth.uid())
  );

create policy classroom_students_instructor_all on classroom_students
  for all using (is_classroom_instructor(classroom_id));
create policy classroom_students_self_select on classroom_students
  for select using (student_id = auth.uid());

create policy classroom_assignments_instructor_all on classroom_assignments
  for all using (is_classroom_instructor(classroom_id));
create policy classroom_assignments_student_select on classroom_assignments
  for select using (
    exists (select 1 from classroom_students cs where cs.classroom_id = classroom_assignments.classroom_id and cs.student_id = auth.uid())
  );
