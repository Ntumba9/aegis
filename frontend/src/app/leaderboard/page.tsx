"use client";

import { useEffect, useState } from "react";
import { getTeamLeaderboard, getUserLeaderboard, LeaderboardEntry } from "@/lib/api";

export default function LeaderboardPage() {
  const [tab, setTab] = useState<"users" | "teams">("users");
  const [users, setUsers] = useState<LeaderboardEntry[]>([]);
  const [teams, setTeams] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getUserLeaderboard().then(setUsers).catch((e) => setError(e.message));
    getTeamLeaderboard().then(setTeams).catch(() => {});
  }, []);

  return (
    <main className="max-w-3xl mx-auto px-6 py-16">
      <h1 className="text-3xl font-bold">Leaderboard</h1>
      <p className="text-slate-400 mt-2 text-sm">
        Only server-verified challenge completions count toward points — a local, unverified
        submission never contributes here.
      </p>

      <div className="flex gap-2 mt-6">
        {(["users", "teams"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 rounded-full text-sm border ${
              tab === t ? "border-electric text-electric" : "border-slate-700 text-slate-400"
            }`}
          >
            {t === "users" ? "Individuals" : "Teams"}
          </button>
        ))}
      </div>

      {error && <p className="text-red-400 mt-6">{error}</p>}

      {tab === "users" && (
        <table className="w-full mt-8 text-sm">
          <thead className="text-slate-500 text-left">
            <tr>
              <th className="py-2">Rank</th>
              <th>Player</th>
              <th>Completed</th>
              <th>Points</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.user_id} className="border-t border-slate-800">
                <td className="py-3 font-mono text-electric">#{u.rank}</td>
                <td>{u.display_name || u.user_id.slice(0, 8)}</td>
                <td>{u.challenges_completed}</td>
                <td className="font-semibold">{u.total_points}</td>
              </tr>
            ))}
            {users.length === 0 && (
              <tr><td colSpan={4} className="py-6 text-slate-500">No completions yet.</td></tr>
            )}
          </tbody>
        </table>
      )}

      {tab === "teams" && (
        <table className="w-full mt-8 text-sm">
          <thead className="text-slate-500 text-left">
            <tr>
              <th className="py-2">Rank</th>
              <th>Team</th>
              <th>Members</th>
              <th>Points</th>
            </tr>
          </thead>
          <tbody>
            {teams.map((t: any) => (
              <tr key={t.team_id} className="border-t border-slate-800">
                <td className="py-3 font-mono text-electric">#{t.rank}</td>
                <td>{t.team_name}</td>
                <td>{t.members}</td>
                <td className="font-semibold">{t.total_points}</td>
              </tr>
            ))}
            {teams.length === 0 && (
              <tr><td colSpan={4} className="py-6 text-slate-500">No teams yet.</td></tr>
            )}
          </tbody>
        </table>
      )}
    </main>
  );
}
