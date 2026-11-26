"use client";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { ArrowLeft, Download, RefreshCw, X } from "lucide-react";
import { Badge, Card, Empty, FactorBars, Ring, Shell, useMe } from "../../components/ui";
import { api, BAND, download, due, type Assignment, type Score, type User } from "../../lib/api";

type Course = { id: string; name: string; section: string; description: string; role: string; assignments: number; students: number; synced_at: string };
type Row = Score & { id: string; name: string; email: string };
type Detail = Score & { student: User; course: string; assignments: Assignment[] };

export default function Page() {
  return <Shell><Suspense fallback={<Empty>Loading…</Empty>}><Courses /></Suspense></Shell>;
}

function Courses() {
  const params = useSearchParams();
  const id = params.get("id");
  const [courses, setCourses] = useState<Course[] | null>(null);
  const [syncing, setSyncing] = useState(false);
  useEffect(() => { api<Course[]>("/courses").then(setCourses); }, []);
  if (!courses) return <Empty>Loading…</Empty>;
  const course = courses.find((c) => c.id === id);
  if (course) return <CourseView course={course} initialStudent={params.get("student")} />;

  async function sync() {
    setSyncing(true);
    try { await api("/sync", { method: "POST" }); setCourses(await api("/courses")); } finally { setSyncing(false); }
  }
  return (
    <>
      <div className="mb-6 flex items-end justify-between">
        <div><h1 className="font-display text-3xl font-bold">Courses</h1><p className="text-ink-300">Synced from Google Classroom.</p></div>
        <button onClick={sync} className="flex items-center gap-2 rounded-full border border-white/10 px-4 py-2 text-sm hover:bg-white/5">
          <RefreshCw className={`h-4 w-4 ${syncing ? "animate-spin" : ""}`} /> Sync now
        </button>
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        {courses.map((c, i) => (
          <Link key={c.id} href={`/courses/?id=${c.id}`}>
            <Card className="h-full transition hover:-translate-y-1 hover:border-violet-400/30" style={{ animationDelay: `${i * 60}ms` }}>
              <div className="mb-3 h-1.5 w-12 rounded-full bg-gradient-to-r from-violet-400 to-sky-400" />
              <h3 className="font-display text-lg font-semibold">{c.name}</h3>
              <p className="text-xs text-ink-300">{c.section}</p>
              <p className="mt-3 text-sm text-ink-300">{c.description}</p>
              <p className="mt-4 text-xs text-ink-500">{c.assignments} assignments{c.role === "teacher" ? ` · ${c.students} students` : ""}</p>
            </Card>
          </Link>
        ))}
      </div>
    </>
  );
}

function CourseView({ course, initialStudent }: { course: Course; initialStudent: string | null }) {
  const me = useMe();
  const router = useRouter();
  const [rows, setRows] = useState<Row[] | null>(null);
  const [open, setOpen] = useState<string | null>(initialStudent);
  const teacher = course.role === "teacher";

  useEffect(() => { if (teacher) api<Row[]>(`/courses/${course.id}/students`).then(setRows); }, [course.id, teacher]);
  if (!me) return null;

  return (
    <>
      <button onClick={() => router.push("/courses/")} className="mb-4 flex items-center gap-1 text-sm text-ink-300 hover:text-white"><ArrowLeft className="h-4 w-4" /> All courses</button>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div><h1 className="font-display text-3xl font-bold">{course.name}</h1><p className="text-ink-300">{course.section}</p></div>
        {teacher && (
          <button onClick={() => download(`/reports/${course.id}.csv`, `${course.name}-progress.csv`)}
            className="flex items-center gap-2 rounded-full bg-white px-4 py-2 text-sm font-medium text-ink-950 hover:opacity-90">
            <Download className="h-4 w-4" /> Export CSV report
          </button>
        )}
      </div>

      {teacher ? (
        !rows ? <Empty>Calculating scores…</Empty> : (
          <Card className="overflow-x-auto p-0">
            <table className="w-full text-sm">
              <thead className="text-left text-xs uppercase tracking-wider text-ink-500">
                <tr className="border-b border-white/5">
                  <th className="p-4">Student</th><th className="p-4">Score</th><th className="p-4">Status</th>
                  <th className="p-4">Submitted</th><th className="p-4">On time</th><th className="p-4">Grades</th><th className="p-4">Missing</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id} onClick={() => setOpen(r.id)} className="cursor-pointer border-b border-white/5 transition last:border-0 hover:bg-white/[.03]">
                    <td className="p-4 font-medium">{r.name}</td>
                    <td className="p-4">
                      <div className="flex items-center gap-2">
                        <div className="h-1.5 w-20 overflow-hidden rounded-full bg-white/5"><div className={`h-full ${BAND[r.band].bar}`} style={{ width: `${r.score ?? 0}%` }} /></div>
                        <span className="font-display">{r.score == null ? "–" : Math.round(r.score)}</span>
                      </div>
                    </td>
                    <td className="p-4"><Badge band={r.band} /></td>
                    <td className="p-4 text-ink-300">{pct(r.factors.completion)}</td>
                    <td className="p-4 text-ink-300">{pct(r.factors.timeliness)}</td>
                    <td className="p-4 text-ink-300">{pct(r.factors.grades)}</td>
                    <td className="p-4">{r.missing.length ? <span className="text-rose-300">{r.missing.length}</span> : <span className="text-ink-500">0</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        )
      ) : <StudentDetail courseId={course.id} studentId={me.id} />}

      {teacher && open && (
        <div className="fixed inset-0 z-30 flex justify-end bg-black/50 backdrop-blur-sm" onClick={() => setOpen(null)}>
          <div className="h-full w-full max-w-lg overflow-y-auto border-l border-white/10 bg-ink-900 p-6 shadow-2xl" style={{ animation: "rise .35s both" }} onClick={(e) => e.stopPropagation()}>
            <button onClick={() => setOpen(null)} className="float-right rounded-full p-1 text-ink-300 hover:bg-white/5"><X className="h-5 w-5" /></button>
            <StudentDetail courseId={course.id} studentId={open} compact />
          </div>
        </div>
      )}
    </>
  );
}

const pct = (v: number | null) => (v == null ? "–" : `${Math.round(v)}%`);
const STATUS: Record<string, string> = { done: "text-emerald-300", late: "text-amber-300", missing: "text-rose-300", pending: "text-sky-300" };

function StudentDetail({ courseId, studentId, compact = false }: { courseId: string; studentId: string; compact?: boolean }) {
  const [d, setD] = useState<Detail | null>(null);
  useEffect(() => { setD(null); api<Detail>(`/courses/${courseId}/students/${studentId}`).then(setD); }, [courseId, studentId]);
  if (!d) return <Empty>Loading…</Empty>;
  return (
    <div className="space-y-5">
      <div className="flex items-center gap-4">
        <Ring value={d.score} size={76} />
        <div><h2 className="font-display text-xl font-semibold">{d.student.name}</h2><p className="text-xs text-ink-300">{d.course} · {d.counted} assignments past deadline</p><div className="mt-1"><Badge band={d.band} /></div></div>
      </div>
      <div className={`grid gap-5 ${compact ? "" : "md:grid-cols-2"}`}>
        <Card><h3 className="mb-3 text-sm font-semibold">Breakdown</h3><FactorBars factors={d.factors} /></Card>
        <Card>
          <h3 className="mb-2 text-sm font-semibold">Why</h3>
          <ul className="list-disc space-y-1 pl-4 text-sm text-ink-300">{d.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
          <h3 className="mb-2 mt-4 text-sm font-semibold">What would help</h3>
          <ul className="list-disc space-y-1 pl-4 text-sm text-violet-200">{d.actions.map((r) => <li key={r}>{r}</li>)}</ul>
        </Card>
      </div>
      <Card className="p-0">
        {d.assignments.map((a) => (
          <div key={a.id} className="flex items-center gap-3 border-b border-white/5 px-5 py-3 last:border-0">
            <div className="min-w-0 flex-1"><div className="truncate text-sm">{a.title}</div><div className="text-xs text-ink-500">{a.due_at ? new Date(a.due_at).toLocaleDateString(undefined, { day: "numeric", month: "short" }) : "No due date"}</div></div>
            {a.grade != null && <span className="text-xs text-ink-300">{a.grade}/{a.max_points}</span>}
            <span className={`w-24 text-right text-xs capitalize ${STATUS[a.status ?? "pending"]}`}>{a.status === "pending" ? due(a.hours_left) : a.status}</span>
          </div>
        ))}
      </Card>
    </div>
  );
}
