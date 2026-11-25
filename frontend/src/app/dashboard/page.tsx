"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { AlertTriangle, CalendarClock, CheckCircle2, Clock, Users } from "lucide-react";
import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Badge, Card, Empty, FactorBars, Ring, Shell, useMe } from "@/components/ui";
import { api, due, type Assignment, type Score } from "@/lib/api";

type TeacherDash = {
  role: "teacher";
  courses: { id: string; name: string; section: string; students: number; avg_score: number | null; completion: number | null; due_this_week: number }[];
  at_risk: { student: string; student_id: string; course: string; course_id: string; score: number; reason: string }[];
  upcoming: Assignment[];
};
type StudentDash = {
  role: "student"; due_soon: Assignment[]; missing: Assignment[];
  scores: (Score & { course_id: string; course: string })[];
  reminders: { title: string; course: string; kind: string; hours_left: number }[];
};

export default function Dashboard() {
  return <Shell><Inner /></Shell>;
}

function Inner() {
  const me = useMe();
  const [d, setD] = useState<TeacherDash | StudentDash | null>(null);
  useEffect(() => { api("/dashboard").then(setD); }, []);
  if (!d || !me) return <Empty>Loading your classroom…</Empty>;
  return (
    <>
      <h1 className="font-display text-3xl font-bold animate-rise">Hi {me.name.split(" ")[0]}</h1>
      <p className="mb-8 mt-1 text-ink-300 animate-rise">{d.role === "teacher" ? "Here's where your classes stand today." : "Here's what needs your attention."}</p>
      {d.role === "teacher" ? <Teacher d={d} /> : <Student d={d} />}
    </>
  );
}

function Stat({ icon: Icon, label, value, tone }: { icon: any; label: string; value: string | number; tone: string }) {
  return (
    <Card className="flex items-center gap-4">
      <div className={`grid h-11 w-11 place-items-center rounded-xl ${tone}`}><Icon className="h-5 w-5" /></div>
      <div><div className="font-display text-2xl font-semibold">{value}</div><div className="text-xs text-ink-300">{label}</div></div>
    </Card>
  );
}

function Teacher({ d }: { d: TeacherDash }) {
  const students = Math.max(0, ...d.courses.map((c) => c.students));
  const completions = d.courses.filter((c) => c.completion != null);
  const avgCompletion = completions.length ? Math.round(completions.reduce((s, c) => s + c.completion!, 0) / completions.length) : null;
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat icon={Users} label="Students" value={students} tone="bg-violet-500/15 text-violet-300" />
        <Stat icon={CheckCircle2} label="Work submitted (past deadlines)" value={avgCompletion == null ? "–" : `${avgCompletion}%`} tone="bg-emerald-500/15 text-emerald-300" />
        <Stat icon={CalendarClock} label="Due in the next 7 days" value={d.upcoming.length} tone="bg-sky-500/15 text-sky-300" />
        <Stat icon={AlertTriangle} label="At-risk (student × course)" value={d.at_risk.length} tone="bg-rose-500/15 text-rose-300" />
      </div>

      <div className="grid gap-6 lg:grid-cols-5">
        <Card className="lg:col-span-3">
          <h2 className="mb-4 font-display text-lg font-semibold">Courses</h2>
          <div className="space-y-3">
            {d.courses.map((c) => (
              <Link key={c.id} href={`/courses/?id=${c.id}`} className="flex items-center gap-4 rounded-xl border border-white/5 p-3 transition hover:border-violet-400/30 hover:bg-white/[.03]">
                <Ring value={c.avg_score} size={52} />
                <div className="min-w-0 flex-1">
                  <div className="truncate font-medium">{c.name}</div>
                  <div className="text-xs text-ink-300">{c.students} students · {c.completion ?? "–"}% submitted · {c.due_this_week} due this week</div>
                </div>
              </Link>
            ))}
          </div>
          <div className="mt-6 h-40">
            <ResponsiveContainer>
              <BarChart data={d.courses.map((c) => ({ name: c.name.split(" ")[0], score: c.avg_score ?? 0 }))}>
                <XAxis dataKey="name" stroke="#6b7186" fontSize={12} tickLine={false} axisLine={false} />
                <YAxis domain={[0, 100]} stroke="#6b7186" fontSize={12} tickLine={false} axisLine={false} width={28} />
                <Tooltip cursor={{ fill: "rgba(255,255,255,.03)" }} contentStyle={{ background: "#181b24", border: "1px solid #232734", borderRadius: 12 }} />
                <Bar dataKey="score" name="Average score" radius={[8, 8, 0, 0]} maxBarSize={72} isAnimationActive={false}>
                  {d.courses.map((c, i) => <Cell key={i} fill={["#a78bfa", "#38bdf8", "#f0abfc"][i % 3]} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card className="lg:col-span-2">
          <h2 className="mb-1 font-display text-lg font-semibold">Needs a conversation</h2>
          <p className="mb-4 text-xs text-ink-300">Students scoring under 55, lowest first.</p>
          {d.at_risk.length === 0 ? <Empty>Nobody is at risk right now.</Empty> : (
            <ul className="space-y-2">
              {d.at_risk.map((r) => (
                <li key={r.student_id + r.course_id}>
                  <Link href={`/courses/?id=${r.course_id}&student=${r.student_id}`} className="block rounded-xl bg-rose-500/[.06] p-3 ring-1 ring-rose-400/15 transition hover:ring-rose-400/40">
                    <div className="flex justify-between text-sm"><span className="font-medium">{r.student}</span><span className="font-display text-rose-300">{Math.round(r.score)}</span></div>
                    <div className="text-xs text-ink-300">{r.course} · {r.reason}</div>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <Card>
        <h2 className="mb-4 font-display text-lg font-semibold">Due this week</h2>
        {d.upcoming.length === 0 ? <Empty>Nothing due in the next 7 days.</Empty> : (
          <div className="grid gap-3 md:grid-cols-2">
            {d.upcoming.map((a) => (
              <div key={a.id} className="flex items-center gap-3 rounded-xl border border-white/5 p-3">
                <Clock className="h-4 w-4 shrink-0 text-sky-300" />
                <div className="min-w-0 flex-1"><div className="truncate text-sm font-medium">{a.title}</div><div className="text-xs text-ink-300">{a.course}</div></div>
                <span className="text-xs text-sky-300">{due(a.hours_left)}</span>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}

function Student({ d }: { d: StudentDash }) {
  return (
    <div className="space-y-6">
      {d.reminders.length > 0 && (
        <div className="flex items-start gap-3 rounded-2xl border border-amber-400/20 bg-amber-400/[.06] p-4 animate-rise">
          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-300" />
          <div className="text-sm">{d.reminders.map((r) => (
            <div key={r.title}><b>{r.title}</b> <span className="text-ink-300">({r.course})</span> {r.kind === "overdue" ? "is overdue" : `is due in ${Math.round(r.hours_left)}h`}.</div>
          ))}</div>
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-3">
        {d.scores.map((s, i) => (
          <Card key={s.course_id} style={{ animationDelay: `${i * 70}ms` }}>
            <div className="mb-4 flex items-center gap-4">
              <Ring value={s.score} />
              <div className="min-w-0"><div className="truncate font-medium">{s.course}</div><Badge band={s.band} /></div>
            </div>
            <FactorBars factors={s.factors} />
            <div className="mt-4 rounded-xl bg-violet-500/[.08] p-3 text-sm"><span className="text-violet-300">Next step: </span>{s.actions[0]}</div>
            <Link href={`/courses/?id=${s.course_id}`} className="mt-3 inline-block text-xs text-ink-300 hover:text-white">Why this score? →</Link>
          </Card>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <h2 className="mb-4 font-display text-lg font-semibold">Due soon</h2>
          {d.due_soon.length === 0 ? <Empty>Nothing due in the next week. Nice.</Empty> : d.due_soon.map((a) => <Row key={a.id} a={a} tone="text-sky-300" />)}
        </Card>
        <Card>
          <h2 className="mb-4 font-display text-lg font-semibold">Missing</h2>
          {d.missing.length === 0 ? <Empty>No missing work.</Empty> : d.missing.map((a) => <Row key={a.id} a={a} tone="text-rose-300" />)}
        </Card>
      </div>
    </div>
  );
}

function Row({ a, tone }: { a: Assignment; tone: string }) {
  return (
    <div className="flex items-center gap-3 border-b border-white/5 py-3 last:border-0">
      <div className="min-w-0 flex-1"><div className="truncate text-sm font-medium">{a.title}</div><div className="text-xs text-ink-300">{a.course} · {a.max_points ?? "–"} pts</div></div>
      <span className={`whitespace-nowrap text-xs ${tone}`}>{due(a.hours_left)}</span>
    </div>
  );
}
