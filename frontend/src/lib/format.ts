/* One formatter per unit. Timecode: m:ss under an hour, h:mm:ss above. Durations in prose: 2m 29s. */
export function fmtTime(s: number | null | undefined): string {
  const t = Math.max(0, Math.floor(s ?? 0));
  const h = Math.floor(t / 3600);
  const m = Math.floor((t % 3600) / 60);
  const sec = t % 60;
  return h ? `${h}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}` : `${m}:${String(sec).padStart(2, "0")}`;
}

export function fmtDur(s: number | null | undefined): string {
  const t = Math.round(s ?? 0);
  if (t < 60) return `${t}s`;
  const m = Math.floor(t / 60);
  if (m < 60) return `${m}m ${t % 60}s`;
  return `${Math.floor(m / 60)}h ${m % 60}m`;
}

export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short", year: "numeric" });
}

export function fmtDay(iso: string | null | undefined): string {
  if (!iso) return "Unknown date";
  const d = new Date(iso);
  const today = new Date();
  const yesterday = new Date();
  yesterday.setDate(today.getDate() - 1);
  const same = (a: Date, b: Date) => a.toDateString() === b.toDateString();
  if (same(d, today)) return "Today";
  if (same(d, yesterday)) return "Yesterday";
  return d.toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short", year: d.getFullYear() === today.getFullYear() ? undefined : "numeric" });
}

export function fmtClock(iso: string | null | undefined): string {
  if (!iso) return "";
  return new Date(iso).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
}

export function dayKey(iso: string | null | undefined): string {
  return iso ? iso.slice(0, 10) : "unknown";
}

export function recordingTitle(r: { title?: string | null; recorded_at?: string | null; transmitter?: string | null; original_name: string }): string {
  if (r.title) return r.title;
  if (r.recorded_at) return `${fmtDate(r.recorded_at)}, ${fmtClock(r.recorded_at)}${r.transmitter ? ` · ${r.transmitter}` : ""}`;
  return r.original_name;
}
