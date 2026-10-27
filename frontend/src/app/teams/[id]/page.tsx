"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import {
  createReport,
  listTeamMembers,
  listTeamReports,
  startTeamSession,
} from "@/lib/api";

export default function TeamDetailPage() {
  const params = useParams<{ id: string }>();
  const [members, setMembers] = useState<any[]>([]);
  const [reports, setReports] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);

  const [sessionChallenge, setSessionChallenge] = useState("");
  const [sessionMode, setSessionMode] = useState<"attack" | "defense">("attack");

  const [reportTitle, setReportTitle] = useState("");
  const [reportChallenge, setReportChallenge] = useState("");
  const [reportSeverity, setReportSeverity] = useState("medium");
  const [reportDescription, setReportDescription] = useState("");

  function refresh() {
    listTeamMembers(params.id).then(setMembers).catch((e: any) => setError(e.message));
    listTeamReports(params.id).then(setReports).catch(() => {});
  }

  useEffect(refresh, [params.id]);

  async function handleStartSession() {
    if (!sessionChallenge.trim()) return;
    try {
      await startTeamSession(params.id, sessionChallenge, sessionMode);
      setSessionChallenge("");
    } catch (e: any) {
      setError(e.message);
    }
  }

  async function handleSubmitReport() {
    if (!reportTitle.trim() || !reportChallenge.trim() || !reportDescription.trim()) return;
    try {
      await createReport({
        team_id: params.id,
        challenge_id: reportChallenge,
        title: reportTitle,
        severity: reportSeverity,
        description: reportDescription,
      });
      setReportTitle("");
      setReportChallenge("");
      setReportDescription("");
      refresh();
    } catch (e: any) {
      setError(e.message);
    }
  }

  return (
    <main className="max-w-4xl mx-auto px-6 py-16 space-y-10">
      <div>
        <h1 className="text-3xl font-bold">Team Workspace</h1>
        {error && <p className="text-red-400 mt-2">{error}</p>}
      </div>

      <section>
        <h2 className="font-semibold text-lg mb-3">Members</h2>
        <div className="flex gap-2 flex-wrap">
          {members.map((m: any) => (
            <span key={m.user_id} className="border border-slate-800 rounded-full px-3 py-1 text-sm">
              {m.user_id.slice(0, 8)} — {m.role}
            </span>
          ))}
        </div>
      </section>

      <section className="border-t border-slate-800 pt-8">
        <h2 className="font-semibold text-lg mb-1">Start a testing session</h2>
        <p className="text-slate-500 text-sm mb-3">
          Attack mode: find the vulnerability. Defense mode: fix it and validate with the regression test.
        </p>
        <div className="flex gap-2">
          <input
            value={sessionChallenge}
            onChange={(e) => setSessionChallenge(e.target.value)}
            placeholder="challenge id, e.g. api1-bola-project-files"
            className="flex-1 bg-navy/60 border border-slate-700 rounded-lg px-4 py-2 outline-none focus:border-electric"
          />
          <select
            value={sessionMode}
            onChange={(e) => setSessionMode(e.target.value as "attack" | "defense")}
            className="bg-navy/60 border border-slate-700 rounded-lg px-3 py-2"
          >
            <option value="attack">Attack</option>
            <option value="defense">Defense</option>
          </select>
          <button onClick={handleStartSession} className="bg-electric text-charcoal font-semibold px-4 py-2 rounded-lg">
            Start
          </button>
        </div>
      </section>

      <section className="border-t border-slate-800 pt-8">
        <h2 className="font-semibold text-lg mb-3">File a vulnerability report</h2>
        <div className="space-y-2">
          <input
            value={reportChallenge}
            onChange={(e) => setReportChallenge(e.target.value)}
            placeholder="challenge id"
            className="w-full bg-navy/60 border border-slate-700 rounded-lg px-4 py-2 outline-none focus:border-electric"
          />
          <input
            value={reportTitle}
            onChange={(e) => setReportTitle(e.target.value)}
            placeholder="Title"
            className="w-full bg-navy/60 border border-slate-700 rounded-lg px-4 py-2 outline-none focus:border-electric"
          />
          <select
            value={reportSeverity}
            onChange={(e) => setReportSeverity(e.target.value)}
            className="bg-navy/60 border border-slate-700 rounded-lg px-3 py-2"
          >
            {["low", "medium", "high", "critical"].map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
          <textarea
            value={reportDescription}
            onChange={(e) => setReportDescription(e.target.value)}
            placeholder="Description, impact, reproduction steps"
            className="w-full bg-navy/60 border border-slate-700 rounded-lg px-4 py-2 outline-none focus:border-electric"
            rows={3}
          />
          <button onClick={handleSubmitReport} className="bg-electric text-charcoal font-semibold px-4 py-2 rounded-lg">
            Submit report
          </button>
        </div>
      </section>

      <section className="border-t border-slate-800 pt-8">
        <h2 className="font-semibold text-lg mb-3">Reports & remediation</h2>
        <div className="space-y-2">
          {reports.map((r: any) => (
            <div key={r.id} className="border border-slate-800 rounded-lg px-4 py-3">
              <div className="flex justify-between">
                <span className="font-semibold">{r.title}</span>
                <span className="text-xs uppercase text-amber-400">{r.severity}</span>
              </div>
              <p className="text-slate-400 text-sm mt-1">{r.description}</p>
              <p className="text-xs text-slate-500 mt-2">
                {r.challenge_id} — status: {r.remediation_status}
              </p>
            </div>
          ))}
          {reports.length === 0 && <p className="text-slate-500 text-sm">No reports yet.</p>}
        </div>
      </section>
    </main>
  );
}
