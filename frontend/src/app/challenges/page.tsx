"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Challenge, listChallenges } from "@/lib/api";

const DIFFICULTIES = ["all", "beginner", "intermediate", "advanced"] as const;

export default function ChallengeCatalogPage() {
  const [challenges, setChallenges] = useState<Challenge[]>([]);
  const [filter, setFilter] = useState<typeof DIFFICULTIES[number]>("all");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listChallenges().then(setChallenges).catch((e) => setError(e.message));
  }, []);

  const visible = filter === "all" ? challenges : challenges.filter((c) => c.difficulty === filter);

  return (
    <main className="max-w-5xl mx-auto px-6 py-16">
      <h1 className="text-3xl font-bold">Challenge Catalog</h1>
      <p className="text-slate-400 mt-2">
        Each challenge targets your own local lab instance. See{" "}
        <Link href="/challenges" className="text-electric underline">setup instructions</Link>.
      </p>

      <div className="flex gap-2 mt-6">
        {DIFFICULTIES.map((d) => (
          <button
            key={d}
            onClick={() => setFilter(d)}
            className={`px-4 py-2 rounded-full text-sm border ${
              filter === d ? "border-electric text-electric" : "border-slate-700 text-slate-400"
            }`}
          >
            {d}
          </button>
        ))}
      </div>

      {error && <p className="text-red-400 mt-6">{error}</p>}

      <div className="grid md:grid-cols-2 gap-5 mt-8">
        {visible.map((c) => (
          <Link
            key={c.id}
            href={`/challenges/${c.id}`}
            className="border border-slate-800 bg-navy/40 rounded-xl p-6 hover:border-electric transition"
          >
            <div className="flex justify-between items-start">
              <span className="font-mono text-xs text-electric">{c.owasp_category}</span>
              <span className="text-xs uppercase text-slate-500">{c.difficulty}</span>
            </div>
            <h3 className="font-semibold text-lg mt-2">{c.title}</h3>
            <p className="text-slate-400 text-sm mt-2">{c.summary}</p>
            <p className="text-slate-500 text-xs mt-4">{c.points} points</p>
          </Link>
        ))}
      </div>
    </main>
  );
}
