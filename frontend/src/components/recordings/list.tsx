"use client";
import Link from "next/link";
import { useMemo, useState } from "react";
import { cn } from "@/lib/utils";
import type { Recording, Speaker } from "@/lib/api";
import { fmtClock, fmtDay, fmtTime, dayKey, recordingTitle } from "@/lib/format";
import { speakerGlyph, speakerName } from "@/lib/speakers";
import { SpeakerAvatar } from "@/components/avatar";
import { Input } from "@/components/ui/input";

/** Up to three overlapping pastel discs: the people in the recording, at a glance. */
function AvatarStack({ speakers }: { speakers: Speaker[] }) {
  const shown = speakers.slice(0, 3);
  if (!shown.length) return <span className="size-7 rounded-full border border-dashed border-hairline" aria-hidden />;
  return (
    <div className="flex items-center justify-end" style={{ width: 28 + (shown.length - 1) * 18 }} aria-hidden>
      {shown.map((s, i) => (
        <span key={s.label} className={cn("flex rounded-full ring-2 ring-surface", i > 0 && "-ml-[10px]")} style={{ zIndex: shown.length - i }}>
          <SpeakerAvatar color={s.person_color} glyph={speakerGlyph(s)} size={28} />
        </span>
      ))}
    </div>
  );
}

function speakerLine(r: Recording): string {
  const names = r.speakers.map(speakerName);
  if (!names.length) return "";
  const shown = names.slice(0, 2).join(", ");
  return names.length > 2 ? `${shown} +${names.length - 2}` : shown;
}

export function RecordingList({ recordings, activeId }: { recordings: Recording[]; activeId: number | null }) {
  const [q, setQ] = useState("");
  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return recordings;
    return recordings.filter((r) => recordingTitle(r).toLowerCase().includes(needle) || r.original_name.toLowerCase().includes(needle) || r.speakers.some((s) => speakerName(s).toLowerCase().includes(needle)));
  }, [q, recordings]);

  let lastDay: string | null = null;
  return (
    <div className="flex h-full flex-col">
      <div className="sticky top-0 z-10 border-b border-hairline bg-surface p-3">
        <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filter by title or speaker…" className="h-9 bg-surface-2" />
      </div>
      {!filtered.length && <div className="p-10 text-center text-[13px] text-ink-3">{recordings.length ? "No matches." : "Plug in a DJI transmitter, or import a folder from Settings."}</div>}
      <div className="pb-4">
        {filtered.map((r) => {
          const d = dayKey(r.recorded_at);
          const header = d !== lastDay ? <div className="eyebrow px-5 pb-1.5 pt-5">{fmtDay(r.recorded_at)}</div> : null;
          lastDay = d;
          const active = r.id === activeId;
          const who = speakerLine(r);
          const status = r.status !== "done" ? (r.status === "processing" ? r.stage || "processing" : r.status) : null;
          return (
            <div key={r.id}>
              {header}
              <Link
                href={`/?id=${r.id}`}
                className={cn("mx-2 grid grid-cols-[1fr_auto_auto] items-center gap-3 rounded-lg px-3 py-2.5 transition-colors duration-120 hover:bg-surface-2", active && "bg-surface-2")}
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-1.5 text-[14px] font-semibold leading-5">
                    <span className="truncate">{r.title || fmtClock(r.recorded_at) || r.original_name}</span>
                    {r.source && r.source !== "dji" && r.source !== "file" && <span className="tc shrink-0 rounded-[3px] bg-surface-2 px-1 text-[10px] font-medium text-ink-3">{{ voicememos: "memo", usb: "usb", folder: "folder", microphone: "mic", granola: "granola", omi: "omi", notion: "notion" }[r.source]}</span>}
                  </div>
                  <div className="mt-px truncate text-[12.5px] leading-4 text-ink-2">
                    {status ? (
                      <span className={cn("rounded-full px-1.5 py-px text-[11px] font-medium", r.status === "error" ? "bg-clip-soft text-clip" : r.status === "processing" ? "bg-signal-soft text-signal" : "bg-surface-2 text-ink-2")}>{status}</span>
                    ) : (
                      <span className={cn(!who && "text-ink-3")}>{who || "No speech"}{r.title && r.recorded_at ? ` · ${fmtClock(r.recorded_at)}` : ""}</span>
                    )}
                  </div>
                </div>
                <AvatarStack speakers={r.speakers} />
                <div className="tc w-9 text-right text-[12px] text-ink-3">{fmtTime(r.duration_sec)}</div>
              </Link>
            </div>
          );
        })}
      </div>
    </div>
  );
}
