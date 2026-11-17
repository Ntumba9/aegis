"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Challenge, getChallenge, submitChallenge } from "@/lib/api";

export default function ChallengeDetailPage() {
  const params = useParams<{ id: string }>();
  const [challenge, setChallenge] = useState<Challenge | null>(null);
  const [showHints, setShowHints] = useState(false);
  const [evidence, setEvidence] = useState("");
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getChallenge(params.id).then(setChallenge).catch((e) => setError(e.message));
  }, [params.id]);

  async function handleSubmit() {
    setError(null);
    setResult(null);
    try {
      const res = await submitChallenge(params.id, { flag: evidence, secret: evidence });
      setResult(
        res.passed
          ? `✅ Passed — ${res.verification_mode}, ${res.points_awarded} points awarded`
          : `❌ Not yet — ${res.evidence_summary}`
      );
    } catch (e: any) {
      setError(e.message);
    }
  }

  if (error && !challenge) return <main className="max-w-3xl mx-auto px-6 py-16 text-red-400">{error}</main>;
  if (!challenge) return <main className="max-w-3xl mx-auto px-6 py-16 text-slate-400">Loading...</main>;

  return (
    <main className="max-w-3xl mx-auto px-6 py-16 space-y-8">
      <div>
        <span className="font-mono text-xs text-electric">{challenge.owasp_category}</span>
        <h1 className="text-3xl font-bold mt-2">{challenge.title}</h1>
        <p className="text-slate-400 mt-3">{challenge.summary}</p>
      </div>

      <section>
        <h2 className="font-semibold text-lg">Authorized testing scope</h2>
        <p className="text-amber-300 text-sm mt-2 border border-amber-900/50 bg-amber-950/20 rounded-lg p-4">
          {challenge.authorized_scope}
        </p>
      </section>

      <section>
        <h2 className="font-semibold text-lg">Learning objectives</h2>
        <ul className="list-disc list-inside text-slate-400 mt-2 space-y-1">
          {challenge.learning_objectives.map((o) => <li key={o}>{o}</li>)}
        </ul>
      </section>

      <section>
        <h2 className="font-semibold text-lg">Local lab setup</h2>
        <pre className="bg-navy/60 border border-slate-800 rounded-lg p-4 text-sm overflow-x-auto mt-2">
{`git clone <repo-url> && cd aegis
cp .env.lab.example .env.lab
docker compose up -d lab-db lab-internal-mock lab-api
pip install asyncpg
python3 lab/scripts/seed.py`}
        </pre>
        <p className="text-slate-500 text-sm mt-2">
          Required services: {challenge.required_services.join(", ")}. The lab listens on
          http://localhost:8100, bound to 127.0.0.1 only.
        </p>
      </section>

      <section>
        <button onClick={() => setShowHints(!showHints)} className="text-electric text-sm underline">
          {showHints ? "Hide hints" : "Show hints"}
        </button>
        {showHints && (
          <ul className="list-disc list-inside text-slate-400 mt-2 space-y-1">
            {challenge.hints.map((h) => <li key={h}>{h}</li>)}
          </ul>
        )}
      </section>

      <section className="border-t border-slate-800 pt-8">
        <h2 className="font-semibold text-lg">Submit your evidence</h2>
        <p className="text-slate-500 text-sm mt-1">
          Paste the flag/secret you recovered from your local lab. This is checked against the lab
          database server-side — not trusted blindly.
        </p>
        <input
          value={evidence}
          onChange={(e) => setEvidence(e.target.value)}
          placeholder="AEGIS{...}"
          className="w-full bg-navy/60 border border-slate-700 rounded-lg px-4 py-3 mt-3 outline-none focus:border-electric"
        />
        <button
          onClick={handleSubmit}
          className="bg-electric text-charcoal font-semibold px-6 py-3 rounded-lg mt-3"
        >
          Verify
        </button>
        {result && <p className="mt-3">{result}</p>}
        {error && <p className="text-red-400 mt-3">{error}</p>}
      </section>
    </main>
  );
}
