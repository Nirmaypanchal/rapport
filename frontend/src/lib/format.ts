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

/** Where a recording came from, in the words the app uses for it. A row written before the column existed is a DJI file.
 *
 * Takes a *place* (`source_place` on a recording, or a key from `/api/summary/templates`) — the Sources page's own
 * vocabulary, which is what a user picked from. The `source` column's mechanism names (`microphone`, `file`) are
 * still here so an older payload reads sensibly, and say the same thing.
 */
export function sourceLabel(src: string | null | undefined): string {
  return {
    dji: "DJI Mic", voicememos: "Apple Voice Memos", usb: "USB drive", granola: "Granola", omi: "Omi", notion: "Notion",
    mic: "microphone", files: "imported file", folder: "watched folder",
    icloud: "iCloud Drive", dropbox: "Dropbox", googledrive: "Google Drive", onedrive: "OneDrive", zoom: "Zoom",
    microphone: "microphone", file: "imported file",
  }[src ?? "dji"] ?? String(src);
}

/** The one- or two-syllable tag for a place, for the badge beside a title in the recordings list.
 *
 * Empty for the two places that are not worth a badge: a DJI file is the norm, and an imported file says nothing
 * a user did not already know. Anything unnamed here wears its own key rather than nothing at all.
 */
export function sourceTag(place: string | null | undefined): string {
  if (!place || place === "dji" || place === "files" || place === "file") return "";
  return { voicememos: "memo", microphone: "mic", googledrive: "drive", icloud: "iCloud" }[place] ?? place;
}

export function recordingTitle(r: { title?: string | null; recorded_at?: string | null; transmitter?: string | null; original_name: string }): string {
  if (r.title) return r.title;
  if (r.recorded_at) return `${fmtDate(r.recorded_at)}, ${fmtClock(r.recorded_at)}${r.transmitter ? ` · ${r.transmitter}` : ""}`;
  return r.original_name;
}
