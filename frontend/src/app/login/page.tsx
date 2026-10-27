"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { getSupabaseBrowserClient } from "@/lib/supabase";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mode, setMode] = useState<"signin" | "signup" | "forgot">("signin");
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setInfo(null);
    setLoading(true);
    const supabase = getSupabaseBrowserClient();

    if (mode === "forgot") {
      const { error } = await supabase.auth.resetPasswordForEmail(email, {
        redirectTo: `${window.location.origin}/reset-password`,
      });
      setLoading(false);
      if (error) {
        setError(error.message);
        return;
      }
      setInfo("Check your email for a password reset link.");
      return;
    }

    const { error } = mode === "signin"
      ? await supabase.auth.signInWithPassword({ email, password })
      : await supabase.auth.signUp({ email, password });
    setLoading(false);
    if (error) {
      setError(error.message);
      return;
    }
    router.push("/challenges");
  }

  const titles = { signin: "Sign in", signup: "Create account", forgot: "Reset your password" };

  return (
    <main className="max-w-md mx-auto px-6 py-24">
      <h1 className="text-2xl font-bold">{titles[mode]}</h1>
      <form onSubmit={handleSubmit} className="mt-6 space-y-4">
        <input
          type="email"
          required
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="w-full bg-navy/60 border border-slate-700 rounded-lg px-4 py-3 outline-none focus:border-electric"
        />
        {mode !== "forgot" && (
          <input
            type="password"
            required
            minLength={8}
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full bg-navy/60 border border-slate-700 rounded-lg px-4 py-3 outline-none focus:border-electric"
          />
        )}
        {error && <p className="text-red-400 text-sm">{error}</p>}
        {info && <p className="text-emerald-400 text-sm">{info}</p>}
        <button
          type="submit"
          disabled={loading}
          className="w-full bg-electric text-charcoal font-semibold py-3 rounded-lg disabled:opacity-50"
        >
          {loading ? "Working..." : mode === "signin" ? "Sign in" : mode === "signup" ? "Sign up" : "Send reset link"}
        </button>
      </form>

      <div className="flex flex-col gap-2 mt-4">
        {mode !== "signin" && (
          <button onClick={() => setMode("signin")} className="text-slate-400 text-sm underline text-left">
            Back to sign in
          </button>
        )}
        {mode === "signin" && (
          <>
            <button onClick={() => setMode("signup")} className="text-slate-400 text-sm underline text-left">
              Need an account? Sign up
            </button>
            <button onClick={() => setMode("forgot")} className="text-slate-400 text-sm underline text-left">
              Forgot your password?
            </button>
          </>
        )}
      </div>
    </main>
  );
}
