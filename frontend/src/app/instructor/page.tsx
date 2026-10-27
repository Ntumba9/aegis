"use client";

import { useEffect, useState } from "react";
import {
  createAssignment,
  createClassroom,
  createClassroomInvite,
  getClassroomProgress,
  listMyClassrooms,
} from "@/lib/api";

export default function InstructorPage() {
  const [classrooms, setClassrooms] = useState<any[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [progress, setProgress] = useState<any[]>([]);
  const [inviteToken, setInviteToken] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [challengeId, setChallengeId] = useState("");
  const [error, setError] = useState<string | null>(null);

  function refreshClassrooms() {
    listMyClassrooms().then(setClassrooms).catch((e: any) => setError(e.message));
  }

  useEffect(refreshClassrooms, []);

  useEffect(() => {
    if (selected) getClassroomProgress(selected).then(setProgress).catch(() => setProgress([]));
  }, [selected]);

  async function handleCreateClassroom() {
    if (!name.trim()) return;
    try {
      await createClassroom(name);
      setName("");
      refreshClassrooms();
    } catch (e: any) {
      setError(e.message);
    }
  }

  async function handleInvite() {
    if (!selected) return;
    const res = await createClassroomInvite(selected);
    setInviteToken((res as any).invite_token);
  }

  async function handleAssign() {
    if (!selected || !challengeId.trim()) return;
    await createAssignment(selected, challengeId);
    setChallengeId("");
  }

  return (
    <main className="max-w-4xl mx-auto px-6 py-16 space-y-10">
      <div>
        <h1 className="text-3xl font-bold">Instructor Dashboard</h1>
        <p className="text-slate-400 mt-2 text-sm">
          Creating a classroom makes you its instructor — no separate role required.
        </p>
        {error && <p className="text-red-400 mt-2">{error}</p>}
      </div>

      <section>
        <div className="flex gap-2">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Classroom name"
            className="flex-1 bg-navy/60 border border-slate-700 rounded-lg px-4 py-2 outline-none focus:border-electric"
          />
          <button onClick={handleCreateClassroom} className="bg-electric text-charcoal font-semibold px-4 py-2 rounded-lg">
            Create classroom
          </button>
        </div>

        <div className="flex gap-2 flex-wrap mt-4">
          {classrooms.map((c: any) => (
            <button
              key={c.id}
              onClick={() => setSelected(c.id)}
              className={`px-4 py-2 rounded-full text-sm border ${
                selected === c.id ? "border-electric text-electric" : "border-slate-700 text-slate-400"
              }`}
            >
              {c.name}
            </button>
          ))}
        </div>
      </section>

      {selected && (
        <>
          <section className="border-t border-slate-800 pt-8">
            <h2 className="font-semibold text-lg mb-3">Invite students</h2>
            <button onClick={handleInvite} className="bg-electric text-charcoal font-semibold px-4 py-2 rounded-lg">
              Generate invite token
            </button>
            {inviteToken && (
              <p className="text-sm mt-3 font-mono bg-navy/60 border border-slate-800 rounded-lg p-3">
                {inviteToken}
              </p>
            )}
          </section>

          <section className="border-t border-slate-800 pt-8">
            <h2 className="font-semibold text-lg mb-3">Assign a challenge</h2>
            <div className="flex gap-2">
              <input
                value={challengeId}
                onChange={(e) => setChallengeId(e.target.value)}
                placeholder="challenge id, e.g. api3-bopla-role-escalation"
                className="flex-1 bg-navy/60 border border-slate-700 rounded-lg px-4 py-2 outline-none focus:border-electric"
              />
              <button onClick={handleAssign} className="bg-electric text-charcoal font-semibold px-4 py-2 rounded-lg">
                Assign
              </button>
            </div>
          </section>

          <section className="border-t border-slate-800 pt-8">
            <h2 className="font-semibold text-lg mb-3">Completion report</h2>
            <table className="w-full text-sm">
              <thead className="text-slate-500 text-left">
                <tr><th className="py-2">Student</th><th>Challenge</th><th>Status</th><th>Points</th></tr>
              </thead>
              <tbody>
                {progress.map((p: any, i: number) => (
                  <tr key={i} className="border-t border-slate-800">
                    <td className="py-2">{p.student_id.slice(0, 8)}</td>
                    <td className="font-mono text-xs">{p.challenge_id}</td>
                    <td className={p.status === "completed" ? "text-emerald-400" : "text-slate-500"}>
                      {p.status}
                    </td>
                    <td>{p.points_awarded}</td>
                  </tr>
                ))}
                {progress.length === 0 && (
                  <tr><td colSpan={4} className="py-6 text-slate-500">No students or assignments yet.</td></tr>
                )}
              </tbody>
            </table>
          </section>
        </>
      )}
    </main>
  );
}
