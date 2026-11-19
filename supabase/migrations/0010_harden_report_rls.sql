-- Hardens RLS on vulnerability_reports and retests for reports with no team.
--
-- 0005 (repointed in 0007) used `team_id is null or is_team_member(team_id)`
-- for SELECT/UPDATE on vulnerability_reports, and the same shape via the
-- parent report for retests. `team_id is null` is true for every team-less
-- report, so ANY authenticated user could read or edit them through
-- PostgREST — the application-layer fix (reporter/assignee only) did not
-- close the direct-PostgREST path, which is the layer RLS exists for.
--
-- Team-less reports are now visible/editable by their reporter and assignee
-- only; team reports stay visible/editable to team members.

drop policy vuln_reports_team_select on vulnerability_reports;
drop policy vuln_reports_team_update on vulnerability_reports;
drop policy retests_report_select on retests;

create policy vuln_reports_select on vulnerability_reports
  for select using (
    reporter_id = auth.uid()
    or assignee_id = auth.uid()
    or (team_id is not null and private.is_team_member(team_id))
  );

create policy vuln_reports_update on vulnerability_reports
  for update using (
    reporter_id = auth.uid()
    or assignee_id = auth.uid()
    or (team_id is not null and private.is_team_member(team_id))
  );

create policy retests_report_select on retests
  for select using (
    exists (
      select 1 from vulnerability_reports r
      where r.id = retests.report_id
        and (
          r.reporter_id = auth.uid()
          or r.assignee_id = auth.uid()
          or (r.team_id is not null and private.is_team_member(r.team_id))
        )
    )
  );
