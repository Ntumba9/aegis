import Link from "next/link";

export default function LandingPage() {
  return (
    <main className="max-w-5xl mx-auto px-6 py-24">
      <p className="text-electric font-mono text-sm tracking-widest uppercase">AEGIS</p>
      <h1 className="text-4xl md:text-6xl font-bold mt-3 leading-tight">
        Build. Break. <span className="text-electric">Defend.</span>
      </h1>
      <p className="text-slate-400 mt-6 max-w-2xl text-lg">
        An open-source, multi-tenant SaaS platform paired with a hands-on OWASP
        API Security Top 10 laboratory — attack real vulnerable services,
        fix them, and verify your fix with automated tests.
      </p>
      <div className="flex gap-4 mt-10">
        <Link
          href="/challenges"
          className="bg-electric text-charcoal font-semibold px-6 py-3 rounded-lg hover:opacity-90"
        >
          Browse Challenges
        </Link>
        <Link
          href="/login"
          className="border border-slate-700 px-6 py-3 rounded-lg hover:border-electric"
        >
          Sign in
        </Link>
      </div>

      <nav className="flex gap-6 mt-6 text-sm text-slate-400 flex-wrap">
        <Link href="/dashboard" className="hover:text-electric">Progress & Achievements</Link>
        <Link href="/leaderboard" className="hover:text-electric">Leaderboard</Link>
        <Link href="/teams" className="hover:text-electric">Teams</Link>
        <Link href="/instructor" className="hover:text-electric">Instructor</Link>
        <Link href="/orgs" className="hover:text-electric">Organizations</Link>
      </nav>

      <section className="grid md:grid-cols-3 gap-6 mt-24">
        {[
          { title: "10 OWASP Categories", body: "BOLA, broken auth, SSRF, BFLA and more — each with a vulnerable and hardened implementation." },
          { title: "Server-verified progress", body: "Completions are checked against lab state server-side, not a client-submitted flag." },
          { title: "Red Team / Blue Team", body: "Form a team, assign remediation, retest the fix — attack and defense modes on the same challenge." },
        ].map((f) => (
          <div key={f.title} className="border border-slate-800 rounded-xl p-6 bg-navy/40">
            <h3 className="font-semibold text-lg">{f.title}</h3>
            <p className="text-slate-400 mt-2 text-sm">{f.body}</p>
          </div>
        ))}
      </section>
    </main>
  );
}
