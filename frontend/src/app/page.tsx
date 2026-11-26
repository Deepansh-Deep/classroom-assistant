"use client";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { BellRing, GraduationCap, LineChart, MessageCircleQuestion, School, UserRound } from "lucide-react";
import { api, token, type User } from "../lib/api";

type Health = { demo_mode: boolean; google_login: boolean; llm: boolean };

const FEATURES = [
  { icon: LineChart, title: "Progress you can explain", text: "Scores built from completion, punctuality, consistency and grades. Every number links back to actual submissions." },
  { icon: BellRing, title: "Reminders that stop", text: "48h, 24h and 2h nudges for unfinished work. Each one fires once, and none fire after you submit." },
  { icon: MessageCircleQuestion, title: "Ask your course", text: "\"When is the mid-term?\" answered from announcements and materials, with the source shown. No source, no answer." },
];

export default function Landing() {
  const router = useRouter();
  const [health, setHealth] = useState<Health | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (token.get()) router.replace("/dashboard/");
    api<Health>("/health").then(setHealth).catch(() => setErr("The API isn't reachable. Is the backend running?"));
  }, [router]);

  async function demo(role: "teacher" | "student") {
    setBusy(role); setErr("");
    try {
      const r = await api<{ token: string; user: User }>("/auth/demo", { method: "POST", body: JSON.stringify({ role }) });
      token.set(r.token);
      router.push("/dashboard/");
    } catch (e: any) { setErr(e.message); setBusy(null); }
  }

  async function google() {
    setBusy("google");
    try { window.location.href = (await api<{ url: string }>("/auth/google")).url; }
    catch (e: any) { setErr(e.message); setBusy(null); }
  }

  return (
    <div className="relative min-h-screen overflow-hidden">
      <div className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute -left-40 -top-40 h-[36rem] w-[36rem] animate-pulse rounded-full bg-violet-600/25 blur-3xl" />
        <div className="absolute -right-40 top-20 h-[30rem] w-[30rem] rounded-full bg-sky-500/20 blur-3xl" />
        <div className="absolute bottom-0 left-1/3 h-[24rem] w-[24rem] rounded-full bg-fuchsia-600/10 blur-3xl" />
      </div>

      <header className="mx-auto flex max-w-6xl items-center gap-2 px-6 py-6 font-display text-lg font-semibold">
        <GraduationCap className="h-6 w-6 text-violet-400" /> Classroom<span className="text-violet-400">.</span>
      </header>

      <section className="mx-auto max-w-4xl px-6 pb-16 pt-10 text-center">
        <p className="mb-5 inline-block rounded-full border border-white/10 bg-white/5 px-4 py-1 text-xs text-ink-300 animate-rise">For Google Classroom · teachers and students</p>
        <h1 className="font-display text-4xl font-bold leading-[1.05] tracking-tight sm:text-6xl animate-rise" style={{ animationDelay: "60ms" }}>
          Know who's falling behind<br />
          <span className="bg-gradient-to-r from-violet-400 via-fuchsia-300 to-sky-400 bg-clip-text text-transparent">before the deadline does.</span>
        </h1>
        <p className="mx-auto mt-6 max-w-2xl text-lg text-ink-300 animate-rise" style={{ animationDelay: "120ms" }}>
          Classroom Assistant reads your courses, flags missing and late work, explains each student's progress in plain English, and answers questions from course material.
        </p>

        <div className="mt-10 flex flex-col items-center justify-center gap-3 sm:flex-row animate-rise" style={{ animationDelay: "180ms" }}>
          <button onClick={() => demo("teacher")} disabled={!!busy || !health?.demo_mode}
            className="group flex items-center gap-2 rounded-full bg-white px-6 py-3 font-medium text-ink-950 shadow-[0_0_40px_-8px_rgba(167,139,250,.7)] transition hover:scale-[1.03] disabled:opacity-50">
            <School className="h-4 w-4" /> {busy === "teacher" ? "Opening…" : "Try as a teacher"}
          </button>
          <button onClick={() => demo("student")} disabled={!!busy || !health?.demo_mode}
            className="flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-6 py-3 font-medium transition hover:bg-white/10 disabled:opacity-50">
            <UserRound className="h-4 w-4" /> {busy === "student" ? "Opening…" : "Try as a student"}
          </button>
          {health?.google_login && (
            <button onClick={google} disabled={!!busy} className="rounded-full px-6 py-3 text-sm text-ink-300 underline-offset-4 hover:underline">
              Sign in with Google Classroom
            </button>
          )}
        </div>
        <p className="mt-4 text-xs text-ink-500">The demo uses a fictional class of 12 students across 3 courses. No sign-up.</p>
        {err && <p className="mt-4 text-sm text-rose-300">{err}</p>}
      </section>

      <section className="mx-auto grid max-w-6xl gap-4 px-6 pb-24 md:grid-cols-3">
        {FEATURES.map(({ icon: Icon, title, text }, i) => (
          <div key={title} className="rounded-2xl border border-white/[.07] bg-white/[.03] p-6 backdrop-blur transition hover:-translate-y-1 hover:border-violet-400/30 animate-rise" style={{ animationDelay: `${240 + i * 80}ms` }}>
            <Icon className="mb-4 h-6 w-6 text-violet-300" />
            <h3 className="mb-2 font-display text-lg font-semibold">{title}</h3>
            <p className="text-sm leading-relaxed text-ink-300">{text}</p>
          </div>
        ))}
      </section>
    </div>
  );
}
