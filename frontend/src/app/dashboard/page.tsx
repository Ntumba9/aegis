"use client";

import { useEffect, useState } from "react";
import { listAchievements, myAchievements, myProgress } from "@/lib/api";

export default function DashboardPage() {
  const [progress, setProgress] = useState<any[]>([]);
  const [achievements, setAchievements] = useState<any[]>([]);
  const [earned, setEarned] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    myProgress().then(setProgress).catch((e) => setError(e.message));
    listAchievements().then(setAchievements).catch(() => {});
    myAchievements().then(setEarned).catch(() => {});
  }, []);

  const earnedIds = new Set(earned.map((e: any) => e.achievement_id));
  const totalPoints = progress.reduce((sum, p) => sum + (p.points_awarded || 0), 0);
  const completedCount = progress.filter((p) => p.status === "completed").length;

  return (
    <main className="max-w-4xl mx-auto px-6 py-16">
      <h1 className="text-3xl font-bold">Your Progress</h1>
      {error && <p className="text-red-400 mt-4">{error}</p>}

      <div className="grid grid-cols-2 gap-4 mt-6">
        <div className="border border-slate-800 bg-navy/40 rounded-xl p-5">
          <p className="text-slate-500 text-sm">Challenges completed</p>
          <p className="text-3xl font-bold mt-1">{completedCount}</p>
        </div>
        <div className="border border-slate-800 bg-navy/40 rounded-xl p-5">
          <p className="text-slate-500 text-sm">Server-verified points</p>
          <p className="text-3xl font-bold mt-1 text-electric">{totalPoints}</p>
        </div>
      </div>

      <section className="mt-10">
        <h2 className="font-semibold text-lg mb-3">Challenge history</h2>
        <div className="space-y-2">
          {progress.map((p) => (
            <div
              key={p.challenge_id}
              className="flex justify-between items-center border border-slate-800 rounded-lg px-4 py-3 text-sm"
            >
              <span className="font-mono">{p.challenge_id}</span>
              <span className="text-slate-500">{p.verification_mode || "—"}</span>
              <span
                className={
                  p.status === "completed" ? "text-emerald-400" : "text-slate-500"
                }
              >
                {p.status}
              </span>
              <span className="font-semibold">{p.points_awarded} pts</span>
            </div>
          ))}
          {progress.length === 0 && <p className="text-slate-500 text-sm">No attempts yet.</p>}
        </div>
      </section>

      <section className="mt-10">
        <h2 className="font-semibold text-lg mb-3">Achievements</h2>
        <div className="grid md:grid-cols-3 gap-4">
          {achievements.map((a) => {
            const unlocked = earnedIds.has(a.id);
            return (
              <div
                key={a.id}
                className={`border rounded-xl p-4 ${
                  unlocked ? "border-electric bg-electric/10" : "border-slate-800 opacity-50"
                }`}
              >
                <p className="font-semibold">{a.title}</p>
                <p className="text-slate-400 text-xs mt-1">{a.description}</p>
                {!unlocked && <p className="text-xs text-slate-600 mt-2">Locked</p>}
              </div>
            );
          })}
        </div>
      </section>
    </main>
  );
}
