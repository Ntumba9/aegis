"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { downloadSecurityEventsCsv, getSecurityEvents, getSecurityMetrics } from "@/lib/api";

export default function SecurityOpsPage() {
  const params = useParams<{ id: string }>();
  const [metrics, setMetrics] = useState<any | null>(null);
  const [events, setEvents] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getSecurityMetrics(params.id).then(setMetrics).catch((e: any) => setError(e.message));
    getSecurityEvents(params.id).then(setEvents).catch(() => {});
  }, [params.id]);

  const severityColor: Record<string, string> = {
    info: "text-slate-400",
    warning: "text-amber-400",
    high: "text-orange-400",
    critical: "text-red-400",
  };

  return (
    <main className="max-w-4xl mx-auto px-6 py-16 space-y-10">
      <div>
        <h1 className="text-3xl font-bold">Security Operations</h1>
        <p className="text-slate-400 mt-2 text-sm">
          Every number here comes from real request/event logs — nothing is fabricated. Admin/owner only.
        </p>
        {error && <p className="text-red-400 mt-2">{error}</p>}
        <button
          onClick={() => downloadSecurityEventsCsv(params.id).catch((e: any) => setError(e.message))}
          className="mt-4 border border-slate-700 hover:border-slate-500 rounded-lg px-4 py-2 text-sm"
        >
          Export events as CSV
        </button>
      </div>

      {metrics && (
        <section className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { label: "Requests (24h)", value: metrics.total_requests },
            { label: "Auth failures", value: metrics.auth_failures },
            { label: "Authz denials", value: metrics.authorization_denials },
            { label: "Rate-limit hits", value: metrics.rate_limit_violations },
          ].map((m) => (
            <div key={m.label} className="border border-slate-800 bg-navy/40 rounded-xl p-4">
              <p className="text-slate-500 text-xs">{m.label}</p>
              <p className="text-2xl font-bold mt-1">{m.value}</p>
            </div>
          ))}
        </section>
      )}

      {metrics && metrics.alerts > 0 && (
        <div className="border border-red-900/50 bg-red-950/20 rounded-lg p-4 text-red-300 text-sm">
          {metrics.alerts} high/critical-severity alert{metrics.alerts === 1 ? "" : "s"} in the last {metrics.window_hours}h.
        </div>
      )}

      <section>
        <h2 className="font-semibold text-lg mb-3">Recent security events</h2>
        <div className="space-y-2">
          {events.map((e: any) => (
            <div key={e.id} className="flex justify-between items-center border border-slate-800 rounded-lg px-4 py-3 text-sm">
              <span className="font-mono">{e.event_type}</span>
              <span className={`uppercase text-xs ${severityColor[e.severity] || "text-slate-400"}`}>
                {e.severity}
              </span>
              <span className="text-slate-500 text-xs">{new Date(e.created_at).toLocaleString()}</span>
            </div>
          ))}
          {events.length === 0 && <p className="text-slate-500 text-sm">No events recorded yet.</p>}
        </div>
      </section>
    </main>
  );
}
