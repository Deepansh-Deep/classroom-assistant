"use client";
import { useEffect, useState } from "react";
import { BellRing, Check } from "lucide-react";
import { Card, Empty, Shell } from "@/components/ui";
import { api } from "@/lib/api";

type Rem = { title: string; course: string; kind: string; due_at: string; hours_left: number };
const OPTIONS = [72, 48, 24, 12, 6, 2, 1];

export default function Reminders() {
  return <Shell><Inner /></Shell>;
}

function Inner() {
  const [data, setData] = useState<{ due: Rem[]; sent: any[]; remind_hours: number[] } | null>(null);
  const [hours, setHours] = useState<number[]>([]);
  const [saved, setSaved] = useState(false);
  useEffect(() => { api("/reminders").then((d) => { setData(d); setHours(d.remind_hours); }); }, []);
  if (!data) return <Empty>Loading…</Empty>;

  const toggle = (h: number) => { setSaved(false); setHours((x) => (x.includes(h) ? x.filter((y) => y !== h) : [...x, h])); };
  async function save() {
    const u = await api("/me/reminders", { method: "PUT", body: JSON.stringify({ remind_hours: hours }) });
    setHours(u.remind_hours); setSaved(true);
    setData(await api("/reminders"));
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div><h1 className="font-display text-3xl font-bold">Reminders</h1><p className="text-ink-300">Nudges for work you haven't submitted. Each fires once; submitting cancels the rest.</p></div>

      <Card>
        <h2 className="mb-1 font-display text-lg font-semibold">When should we remind you?</h2>
        <p className="mb-4 text-sm text-ink-300">Hours before each deadline.</p>
        <div className="flex flex-wrap gap-2">
          {OPTIONS.map((h) => (
            <button key={h} onClick={() => toggle(h)} className={`rounded-full px-4 py-2 text-sm ring-1 transition ${hours.includes(h) ? "bg-violet-500/20 text-violet-200 ring-violet-400/50" : "text-ink-300 ring-white/10 hover:ring-white/30"}`}>{h}h</button>
          ))}
        </div>
        <button onClick={save} disabled={!hours.length} className="mt-5 flex items-center gap-2 rounded-full bg-white px-5 py-2 text-sm font-medium text-ink-950 disabled:opacity-40">
          {saved ? <><Check className="h-4 w-4" /> Saved</> : "Save"}
        </button>
      </Card>

      <Card>
        <h2 className="mb-4 font-display text-lg font-semibold">Due to send now</h2>
        {data.due.length === 0 ? <Empty>No reminders pending.</Empty> : data.due.map((r) => (
          <div key={r.title + r.kind} className="flex items-center gap-3 border-b border-white/5 py-3 last:border-0">
            <BellRing className={`h-4 w-4 ${r.kind === "overdue" ? "text-rose-300" : "text-amber-300"}`} />
            <div className="flex-1"><div className="text-sm">{r.title}</div><div className="text-xs text-ink-300">{r.course}</div></div>
            <span className="rounded-full bg-white/5 px-2 py-0.5 text-xs text-ink-300">{r.kind === "overdue" ? "overdue" : `${r.kind} before`}</span>
          </div>
        ))}
      </Card>
    </div>
  );
}
