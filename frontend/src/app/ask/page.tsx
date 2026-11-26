"use client";
import { useEffect, useRef, useState } from "react";
import { FileText, Megaphone, NotebookPen, Send } from "lucide-react";
import { Shell } from "../../components/ui";
import { api } from "../../lib/api";

type Source = { n: number; course: string; kind: string; title: string; text: string; relevance: number };
type Msg = { who: "me" | "bot"; text: string; sources?: Source[]; mode?: string };
const ICON: Record<string, any> = { assignment: NotebookPen, announcement: Megaphone, material: FileText };
const SUGGEST = ["When is the ML mid-term exam?", "What's the late submission policy?", "How many people per capstone group?", "What are the DBMS lab rules?"];

export default function Ask() {
  return <Shell><Chat /></Shell>;
}

function Chat() {
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [courses, setCourses] = useState<{ id: string; name: string }[]>([]);
  const [course, setCourse] = useState("");
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => { api("/courses").then(setCourses); }, []);
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs, busy]);

  async function ask(question: string) {
    if (!question.trim() || busy) return;
    setMsgs((m) => [...m, { who: "me", text: question }]);
    setQ(""); setBusy(true);
    try {
      const r = await api("/ask", { method: "POST", body: JSON.stringify({ question, course_id: course || null }) });
      setMsgs((m) => [...m, { who: "bot", text: r.answer, sources: r.sources, mode: r.mode }]);
    } catch (e: any) {
      setMsgs((m) => [...m, { who: "bot", text: e.message }]);
    } finally { setBusy(false); }
  }

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="font-display text-3xl font-bold">Ask your courses</h1>
      <p className="mb-6 text-ink-300">Answers come only from assignments, announcements and materials, and every one shows its source.</p>

      <div className="min-h-[45vh] space-y-4 pb-4">
        {msgs.length === 0 && (
          <div className="flex flex-wrap gap-2">
            {SUGGEST.map((s) => <button key={s} onClick={() => ask(s)} className="rounded-full border border-white/10 bg-white/[.03] px-4 py-2 text-sm text-ink-300 transition hover:border-violet-400/40 hover:text-white">{s}</button>)}
          </div>
        )}
        {msgs.map((m, i) => m.who === "me" ? (
          <div key={i} className="ml-auto w-fit max-w-[80%] rounded-2xl rounded-br-md bg-white px-4 py-2.5 text-ink-950 animate-rise">{m.text}</div>
        ) : (
          <div key={i} className="max-w-[90%] rounded-2xl rounded-bl-md border border-white/[.07] bg-white/[.04] px-4 py-3 animate-rise">
            <p className="whitespace-pre-wrap text-sm leading-relaxed">{m.text.replace(/\[(\d+)\]/g, "⁽$1⁾")}</p>
            {!!m.sources?.length && (
              <div className="mt-3 space-y-2">
                {m.sources.map((s) => {
                  const Icon = ICON[s.kind] ?? FileText;
                  return (
                    <details key={s.n} className="group rounded-xl bg-black/20 px-3 py-2 text-xs">
                      <summary className="flex cursor-pointer list-none items-center gap-2 text-ink-300">
                        <Icon className="h-3.5 w-3.5 text-violet-300" /> <span className="text-violet-300">[{s.n}]</span> {s.course} · {s.title}
                        <span className="ml-auto h-1 w-10 overflow-hidden rounded bg-white/10"><span className="block h-full bg-violet-400" style={{ width: `${s.relevance * 100}%` }} /></span>
                      </summary>
                      <p className="mt-2 text-ink-300">{s.text}</p>
                    </details>
                  );
                })}
              </div>
            )}
            {m.mode === "extractive" && <p className="mt-2 text-[11px] text-ink-500">Showing the best matching course text directly (AI phrasing is off).</p>}
          </div>
        ))}
        {busy && <div className="w-fit rounded-2xl bg-white/[.04] px-4 py-3 text-sm text-ink-300">Searching your courses…</div>}
        <div ref={end} />
      </div>

      <form onSubmit={(e) => { e.preventDefault(); ask(q); }} className="sticky bottom-4 flex items-center gap-2 rounded-full border border-white/10 bg-ink-900/90 p-2 backdrop-blur-xl">
        <select value={course} onChange={(e) => setCourse(e.target.value)} className="max-w-[10rem] truncate rounded-full bg-transparent px-3 text-sm text-ink-300 outline-none">
          <option value="">All courses</option>
          {courses.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Ask about deadlines, exams, rules…" className="flex-1 bg-transparent px-2 py-2 text-sm outline-none placeholder:text-ink-500" />
        <button disabled={busy} className="grid h-10 w-10 place-items-center rounded-full bg-violet-500 text-white transition hover:bg-violet-400 disabled:opacity-50"><Send className="h-4 w-4" /></button>
      </form>
    </div>
  );
}
