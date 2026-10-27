"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { createOrg, listMyOrgs, Org } from "@/lib/api";

export default function OrgsPage() {
  const [orgs, setOrgs] = useState<Org[]>([]);
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);

  function refresh() {
    listMyOrgs().then(setOrgs).catch((e) => setError(e.message));
  }

  useEffect(refresh, []);

  async function handleCreate() {
    if (!name.trim()) return;
    try {
      await createOrg(name);
      setName("");
      refresh();
    } catch (e: any) {
      setError(e.message);
    }
  }

  return (
    <main className="max-w-3xl mx-auto px-6 py-16">
      <h1 className="text-3xl font-bold">Organizations</h1>
      <p className="text-slate-400 mt-2 text-sm">
        Your SaaS tenants — projects, documents, API keys, and security operations live here.
      </p>

      <div className="flex gap-2 mt-6">
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Organization name"
          className="flex-1 bg-navy/60 border border-slate-700 rounded-lg px-4 py-2 outline-none focus:border-electric"
        />
        <button onClick={handleCreate} className="bg-electric text-charcoal font-semibold px-4 py-2 rounded-lg">
          Create
        </button>
      </div>

      {error && <p className="text-red-400 mt-4">{error}</p>}

      <div className="grid md:grid-cols-2 gap-4 mt-8">
        {orgs.map((o) => (
          <Link
            key={o.id}
            href={`/orgs/${o.id}`}
            className="border border-slate-800 bg-navy/40 rounded-xl p-5 hover:border-electric"
          >
            <p className="font-semibold">{o.name}</p>
            <p className="text-xs text-slate-500 mt-1">Open dashboard →</p>
          </Link>
        ))}
        {orgs.length === 0 && <p className="text-slate-500 text-sm">No organizations yet.</p>}
      </div>
    </main>
  );
}
