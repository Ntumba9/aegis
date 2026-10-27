"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { getSupabaseBrowserClient } from "@/lib/supabase";

export default function ResetPasswordPage() {
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    const supabase = getSupabaseBrowserClient();
    // The recovery link Supabase emailed already established a session
    // (via the URL fragment) by the time this page loads, so updateUser
    // works without a separate sign-in step.
    const { error } = await supabase.auth.updateUser({ password });
    setLoading(false);
    if (error) {
      setError(error.message);
      return;
    }
    router.push("/challenges");
  }

  return (
    <main className="max-w-md mx-auto px-6 py-24">
      <h1 className="text-2xl font-bold">Set a new password</h1>
      <form onSubmit={handleSubmit} className="mt-6 space-y-4">
        <input
          type="password"
          required
          minLength={8}
          placeholder="New password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="w-full bg-navy/60 border border-slate-700 rounded-lg px-4 py-3 outline-none focus:border-electric"
        />
        {error && <p className="text-red-400 text-sm">{error}</p>}
        <button
          type="submit"
          disabled={loading}
          className="w-full bg-electric text-charcoal font-semibold py-3 rounded-lg disabled:opacity-50"
        >
          {loading ? "Working..." : "Update password"}
        </button>
      </form>
    </main>
  );
}
