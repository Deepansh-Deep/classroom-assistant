"use client";
// Tiny typed API client. The JWT lives in sessionStorage: it is cleared when the tab closes.

export type Role = "teacher" | "student";
export type User = { id: string; name: string; email: string; role: Role; is_demo: boolean; remind_hours: number[] };
export type Factors = { completion: number | null; timeliness: number | null; consistency: number | null; grades: number | null };
export type Score = {
  score: number | null; band: "on_track" | "needs_attention" | "at_risk" | "no_data"; factors: Factors;
  reasons: string[]; actions: string[]; counted: number; missing: string[]; late: string[];
};
export type Assignment = {
  id: string; course_id: string; course: string; title: string; description: string | null; max_points: number | null;
  due_at: string | null; hours_left: number | null; status: "done" | "late" | "missing" | "pending" | null; grade: number | null;
};

const KEY = "ca_token";
export const token = {
  get: () => (typeof window === "undefined" ? null : sessionStorage.getItem(KEY)),
  set: (t: string) => sessionStorage.setItem(KEY, t),
  clear: () => sessionStorage.removeItem(KEY),
};

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

export async function api<T = any>(path: string, init: RequestInit = {}): Promise<T> {
  const t = token.get();
  const res = await fetch(`/api${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(t ? { Authorization: `Bearer ${t}` } : {}), ...init.headers },
  });
  if (res.status === 401 && typeof window !== "undefined" && !path.startsWith("/auth")) {
    token.clear();
    window.location.href = "/";
  }
  if (!res.ok) {
    let msg = res.statusText;
    try { msg = (await res.json()).detail ?? msg; } catch {}
    throw new ApiError(res.status, typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  return res.headers.get("content-type")?.includes("json") ? res.json() : (res.text() as any);
}

export async function download(path: string, filename: string) {
  const res = await fetch(`/api${path}`, { headers: { Authorization: `Bearer ${token.get()}` } });
  const blob = await res.blob();
  const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(blob), download: filename });
  a.click();
  URL.revokeObjectURL(a.href);
}

export function due(hours: number | null): string {
  if (hours === null) return "No due date";
  const h = Math.abs(hours);
  const txt = h < 1 ? "under an hour" : h < 48 ? `${Math.round(h)}h` : `${Math.round(h / 24)} days`;
  return hours < 0 ? `${txt} overdue` : `in ${txt}`;
}

export const BAND = {
  on_track: { label: "On track", cls: "text-emerald-300 bg-emerald-400/10 ring-emerald-400/30", bar: "bg-emerald-400" },
  needs_attention: { label: "Needs attention", cls: "text-amber-300 bg-amber-400/10 ring-amber-400/30", bar: "bg-amber-400" },
  at_risk: { label: "At risk", cls: "text-rose-300 bg-rose-400/10 ring-rose-400/30", bar: "bg-rose-400" },
  no_data: { label: "No data yet", cls: "text-ink-300 bg-white/5 ring-white/10", bar: "bg-ink-500" },
} as const;
