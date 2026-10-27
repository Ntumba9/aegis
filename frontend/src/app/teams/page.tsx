"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { createTeam, listMyTeams, Team } from "@/lib/api";

export default function TeamsPage() {
  const [teams, setTeams] = useState<Team[]>([]);
  const [name, setName] = useState("");
  const [mode, setMode] = useState("mixed");
  const [error, setError] = useState<string | null>(null);

  function refresh() {
    listMyTeams().then(setTeams).catch((e) => setError(e.message));
  }

  useEffect(refresh, []);

  async function handleCreate() {
    if (!name.trim()) return;
    try {
      await createTeam(name, mode);
      setName("");
      refresh();
    } catch (e: any) {
      setError(e.message);
    }
  }

  return (
    <main className="max-w-3xl mx-auto px-6 py-16">
      <h1 className="text-3xl font-bold">Teams</h1>
      <p className="text-slate-400 mt-2 text-sm">
        Red teams attack, blue teams defend — a mixed team does both on the same challenges.
      </p>

      <div className="flex gap-2 mt-6">
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Team name"
          className="flex-1 bg-navy/60 border border-slate-700 rounded-lg px-4 py-2 outline-none focus:border-electric"
        />
        <select
          value={mode}
          onChange={(e) => setMode(e.target.value)}
          className="bg-navy/60 border border-slate-700 rounded-lg px-3 py-2"
        >
          <option value="mixed">Mixed</option>
          <option value="red">Red</option>
          <option value="blue">Blue</option>
        </select>
        <button onClick={handleCreate} className="bg-electric text-charcoal font-semibold px-4 py-2 rounded-lg">
          Create
        </button>
      </div>

      {error && <p className="text-red-400 mt-4">{error}</p>}

      <div className="grid md:grid-cols-2 gap-4 mt-8">
        {teams.map((t) => (
          <Link
            key={t.id}
            href={`/teams/${t.id}`}
            className="border border-slate-800 bg-navy/40 rounded-xl p-5 hover:border-electric"
          >
            <p className="font-semibold">{t.name}</p>
            <p className="text-xs uppercase text-slate-500 mt-1">{t.mode}</p>
          </Link>
        ))}
        {teams.length === 0 && <p className="text-slate-500 text-sm">You're not on a team yet.</p>}
      </div>
    </main>
  );
}
