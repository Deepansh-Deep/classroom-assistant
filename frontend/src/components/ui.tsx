"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { BellRing, BookOpen, GraduationCap, LayoutDashboard, LogOut, MessageCircleQuestion } from "lucide-react";
import { api, BAND, token, type Factors, type Score, type User } from "@/lib/api";

export function Card({ children, className = "", style }: { children: ReactNode; className?: string; style?: React.CSSProperties }) {
  return <div style={style} className={`rounded-2xl border border-white/[.07] bg-white/[.03] p-5 backdrop-blur animate-rise ${className}`}>{children}</div>;
}

export function Badge({ band }: { band: Score["band"] }) {
  const b = BAND[band];
  return <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ${b.cls}`}>{b.label}</span>;
}

export function Ring({ value, size = 64 }: { value: number | null; size?: number }) {
  const [v, setV] = useState(0);
  useEffect(() => { const id = requestAnimationFrame(() => setV(value ?? 0)); return () => cancelAnimationFrame(id); }, [value]);
  const r = size / 2 - 6, c = 2 * Math.PI * r;
  const color = value == null ? "#6b7186" : value >= 75 ? "#34d399" : value >= 55 ? "#fbbf24" : "#fb7185";
  return (
    <svg width={size} height={size} className="shrink-0 -rotate-90">
      <circle cx={size / 2} cy={size / 2} r={r} stroke="rgba(255,255,255,.08)" strokeWidth={6} fill="none" />
      <circle cx={size / 2} cy={size / 2} r={r} stroke={color} strokeWidth={6} fill="none" strokeLinecap="round"
        strokeDasharray={c} strokeDashoffset={c - (c * v) / 100} style={{ transition: "stroke-dashoffset 1.1s cubic-bezier(.2,.8,.2,1)" }} />
      <text x="50%" y="50%" textAnchor="middle" dominantBaseline="central" className="rotate-90 origin-center fill-white font-display"
        fontSize={size / 3.6} fontWeight={600}>{value == null ? "–" : Math.round(value)}</text>
    </svg>
  );
}

const LABELS: Record<keyof Factors, string> = { completion: "Completion", timeliness: "On time", consistency: "Consistency", grades: "Grades" };
export function FactorBars({ factors }: { factors: Factors }) {
  return (
    <div className="space-y-2.5">
      {(Object.keys(LABELS) as (keyof Factors)[]).map((k) => (
        <div key={k}>
          <div className="mb-1 flex justify-between text-xs text-ink-300"><span>{LABELS[k]}</span><span>{factors[k] == null ? "n/a" : `${Math.round(factors[k]!)}%`}</span></div>
          <div className="h-1.5 overflow-hidden rounded-full bg-white/[.06]">
            <div className="h-full rounded-full bg-gradient-to-r from-violet-400 to-sky-400 transition-[width] duration-1000" style={{ width: `${factors[k] ?? 0}%` }} />
          </div>
        </div>
      ))}
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="py-8 text-center text-sm text-ink-500">{children}</p>;
}

export function useMe() {
  const [me, setMe] = useState<User | null>(null);
  const router = useRouter();
  useEffect(() => {
    if (!token.get()) { router.replace("/"); return; }
    api<User>("/me").then(setMe).catch(() => router.replace("/"));
  }, [router]);
  return me;
}

export function Shell({ children }: { children: ReactNode }) {
  const me = useMe();
  const path = usePathname();
  const router = useRouter();
  const nav = [
    { href: "/dashboard/", label: "Dashboard", icon: LayoutDashboard },
    { href: "/courses/", label: "Courses", icon: BookOpen },
    { href: "/ask/", label: "Ask", icon: MessageCircleQuestion },
    ...(me?.role === "student" ? [{ href: "/reminders/", label: "Reminders", icon: BellRing }] : []),
  ];
  return (
    <div className="min-h-screen">
      <div className="pointer-events-none fixed inset-0 -z-10 bg-[radial-gradient(60rem_40rem_at_10%_-10%,rgba(139,92,246,.18),transparent),radial-gradient(50rem_30rem_at_110%_10%,rgba(14,165,233,.14),transparent)]" />
      <header className="sticky top-0 z-20 border-b border-white/[.06] bg-ink-950/70 backdrop-blur-xl">
        <div className="mx-auto flex max-w-6xl items-center gap-6 px-5 py-3">
          <Link href="/dashboard/" className="flex items-center gap-2 font-display text-lg font-semibold">
            <GraduationCap className="h-6 w-6 text-violet-400" /> Classroom<span className="text-violet-400">.</span>
          </Link>
          <nav className="flex gap-1 overflow-x-auto">
            {nav.map(({ href, label, icon: Icon }) => (
              <Link key={href} href={href} className={`flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-sm transition ${path?.startsWith(href.slice(0, -1)) ? "bg-white text-ink-950" : "text-ink-300 hover:bg-white/5 hover:text-white"}`}>
                <Icon className="h-4 w-4" /> <span className="hidden sm:inline">{label}</span>
              </Link>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-3 text-sm">
            {me && <span className="hidden text-ink-300 md:inline">{me.name} · <span className="capitalize">{me.role}</span>{me.is_demo && <span className="ml-2 rounded-full bg-violet-500/15 px-2 py-0.5 text-xs text-violet-300">demo</span>}</span>}
            <button onClick={() => { token.clear(); router.replace("/"); }} className="rounded-full p-2 text-ink-300 hover:bg-white/5 hover:text-white" title="Sign out"><LogOut className="h-4 w-4" /></button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-5 py-8">{me ? children : <Empty>Loading…</Empty>}</main>
    </div>
  );
}
