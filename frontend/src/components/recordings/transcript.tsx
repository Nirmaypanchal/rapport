"use client";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { api, type Person, type Recording, type Segment, type Speaker } from "@/lib/api";
import { fmtTime } from "@/lib/format";
import { speakerGlyph, speakerName, speakerStyle } from "@/lib/speakers";
import { SpeakerAvatar } from "@/components/avatar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import type { Player } from "@/lib/use-player";
import { cn } from "@/lib/utils";

type Payload = Pick<Recording, "speakers" | "segments">;

export function Transcript({ r, player, follow, onChange }: { r: Recording; player: Player; follow: boolean; onChange: (p: Payload) => void }) {
  const root = useRef<HTMLDivElement>(null);
  const [splitting, setSplitting] = useState<number | null>(null);
  const [editing, setEditing] = useState<number | null>(null);
  const segs = r.segments ?? [];
  const spk = (label: string) => r.speakers.find((s) => s.label === label);

  // Imperative highlight: runs per frame without touching React state.
  useEffect(() => {
    const el = root.current;
    if (!el) return;
    const turns = Array.from(el.querySelectorAll<HTMLElement>("[data-turn]"));
    const words = Array.from(el.querySelectorAll<HTMLElement>(".w"));
    const wStart = words.map((w) => Number(w.dataset.s));
    const wEnd = words.map((w) => Number(w.dataset.e));
    let activeTurn = -1, activeWord = -1;
    const unsub = player.subscribe((t, playing) => {
      let ti = -1;
      for (let i = 0; i < turns.length; i++) { const s = Number(turns[i].dataset.s), e = Number(turns[i].dataset.e); if (t >= s && t < e + 0.3) { ti = i; break; } }
      if (ti !== activeTurn) {
        if (activeTurn >= 0) turns[activeTurn].classList.remove("active");
        if (ti >= 0) { turns[ti].classList.add("active"); if (follow && playing) turns[ti].scrollIntoView({ block: "center", behavior: "smooth" }); }
        activeTurn = ti;
      }
      // binary search on start
      let lo = 0, hi = words.length - 1, wi = -1;
      while (lo <= hi) { const mid = (lo + hi) >> 1; if (wStart[mid] <= t) { wi = mid; lo = mid + 1; } else hi = mid - 1; }
      if (wi >= 0 && t >= wEnd[wi] + 0.05) wi = -1;
      if (!playing && t < 0.2) wi = -1;
      if (wi !== activeWord) {
        if (activeWord >= 0) words[activeWord].classList.remove("on");
        if (wi >= 0) words[wi].classList.add("on");
        // words already spoken in the active turn fade
        if (ti >= 0) {
          const turnWords = turns[ti].querySelectorAll<HTMLElement>(".w");
          turnWords.forEach((w) => w.classList.toggle("past", Number(w.dataset.e) <= t && Number(w.dataset.s) !== wStart[wi]));
        }
        activeWord = wi;
      }
    });
    return unsub;
  }, [player, segs, follow]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape" && splitting != null) { setSplitting(null); toast("Split cancelled"); } };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [splitting]);

  const split = async (seg: Segment, wordIndex: number) => {
    setSplitting(null);
    const payload = await api<Recording>(`/api/recordings/${r.id}/segments/${seg.id}/split`, { method: "POST", json: { word_index: wordIndex } });
    toast("Turn split. Now set the new turn's speaker.");
    onChange(payload);
  };

  if (!segs.length) return <div className="p-10 text-center text-[13px] text-ink-3">No speech detected.</div>;

  return (
    <div ref={root} className="mx-auto max-w-[720px]">
      {segs.map((seg, si) => {
        const s = spk(seg.speaker_label);
        return (
          <div
            key={seg.id}
            data-turn
            data-s={seg.start}
            data-e={seg.end}
            className={cn("turn speaker grid cursor-pointer gap-1 rounded-lg px-3 py-2.5 transition-colors duration-120 hover:bg-surface sm:grid-cols-[140px_1fr] sm:gap-4", splitting === seg.id && "splitting")}
            style={speakerStyle(s?.person_color)}
            onClick={() => { if (splitting == null && editing == null) player.seek(seg.start, true); }}
          >
            <div className="flex items-center gap-2 sm:block">
              <TurnPopover r={r} seg={seg} speaker={s} onChange={onChange} onSplit={() => { setSplitting(seg.id); toast("Click the word where the new turn should begin. Esc cancels."); }} onEdit={() => setEditing(seg.id)} hasPrev={si > 0} />
              <div className="tc text-[11.5px] text-ink-3 sm:mt-0.5">{fmtTime(seg.start)} – {fmtTime(seg.end)}</div>
            </div>
            {editing === seg.id ? (
              <EditText r={r} seg={seg} onDone={(p) => { setEditing(null); if (p) onChange(p); }} />
            ) : (
              <div className="text-[15.5px] leading-[1.6]">
                {seg.words.map((w, wi) => (
                  <span
                    key={wi}
                    className="w"
                    data-s={w[1]}
                    data-e={w[2]}
                    onClick={(e) => {
                      e.stopPropagation();
                      if (splitting === seg.id) { if (wi === 0) { toast("Pick a word after the first one."); return; } split(seg, wi); return; }
                      if (splitting == null) player.seek(w[1], true);
                    }}
                  >
                    {w[0]}{" "}
                  </span>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function EditText({ r, seg, onDone }: { r: Recording; seg: Segment; onDone: (p: Payload | null) => void }) {
  const [text, setText] = useState(seg.text);
  return (
    <div onClick={(e) => e.stopPropagation()} className="grid gap-2">
      <Textarea value={text} onChange={(e) => setText(e.target.value)} className="min-h-[72px] bg-surface text-[15px]" autoFocus />
      <div className="flex gap-2">
        <Button size="sm" onClick={async () => { const p = await api<Recording>(`/api/recordings/${r.id}/segments/${seg.id}`, { method: "PATCH", json: { text } }); toast("Text saved"); onDone(p); }}>Save</Button>
        <Button size="sm" variant="ghost" onClick={() => onDone(null)}>Cancel</Button>
      </div>
    </div>
  );
}

function TurnPopover({ r, seg, speaker, onChange, onSplit, onEdit, hasPrev }: { r: Recording; seg: Segment; speaker?: Speaker; onChange: (p: Payload) => void; onSplit: () => void; onEdit: () => void; hasPrev: boolean }) {
  const [open, setOpen] = useState(false);
  const [people, setPeople] = useState<Person[]>([]);
  const [pick, setPick] = useState("");
  const [newName, setNewName] = useState("");
  useEffect(() => { if (open) api<Person[]>("/api/people").then(setPeople); }, [open]);
  const patch = async (json: Record<string, unknown>, msg: string) => {
    const p = await api<Recording>(`/api/recordings/${r.id}/segments/${seg.id}`, { method: "PATCH", json });
    setOpen(false); toast(msg); onChange(p);
  };
  const inRec = new Set(r.speakers.map((s) => s.person_id));
  const others = people.filter((p) => !inRec.has(p.id));
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger
        onClick={(e) => e.stopPropagation()}
        className="group -ml-1 inline-flex max-w-full items-center gap-1.5 rounded-md px-1 py-0.5 text-[13.5px] font-semibold text-[var(--c)] hover:bg-surface-2"
        title="Change the speaker, split or edit this turn"
      >
        {speaker && <SpeakerAvatar color={speaker.person_color} glyph={speakerGlyph(speaker)} size={18} />}
        <span className="truncate">{speaker ? speakerName(speaker) : seg.speaker_label}</span>
        <span className="text-[11px] font-normal text-ink-3 opacity-0 transition-opacity group-hover:opacity-100">✎</span>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-[300px] p-3.5" onClick={(e) => e.stopPropagation()}>
        <div className="text-[13px] font-semibold">Turn <span className="tc ml-1 text-[11.5px] font-normal text-ink-3">{fmtTime(seg.start)} – {fmtTime(seg.end)}</span></div>
        <div className="eyebrow mt-3 mb-1.5">Who is speaking here?</div>
        <div className="flex flex-wrap gap-1.5">
          {r.speakers.map((s) => (
            <button key={s.label} type="button" onClick={() => patch({ speaker_label: s.label }, `Turn assigned to ${speakerName(s)}`)}
              className={cn("speaker inline-flex h-7 items-center gap-1.5 rounded-full border border-hairline bg-surface pl-1 pr-2.5 text-[12.5px] font-medium hover:border-[var(--c)] hover:bg-[var(--wash)]", s.label === seg.speaker_label && "border-[var(--c)] bg-[var(--wash)]")}
              style={speakerStyle(s.person_color)}>
              <SpeakerAvatar color={s.person_color} glyph={speakerGlyph(s)} size={18} />{speakerName(s)}
            </button>
          ))}
        </div>
        {others.length > 0 && (
          <div className="mt-2 flex gap-2">
            <Select value={pick} onValueChange={(v) => setPick(v ?? "")}>
              <SelectTrigger size="sm" className="flex-1 text-[12.5px]"><SelectValue placeholder="Someone not in this recording…" /></SelectTrigger>
              <SelectContent>{others.map((p) => <SelectItem key={p.id} value={String(p.id)}>{p.name}</SelectItem>)}</SelectContent>
            </Select>
            <Button size="sm" variant="outline" disabled={!pick} onClick={() => patch({ person_id: Number(pick) }, "Turn reassigned")}>Assign</Button>
          </div>
        )}
        <div className="mt-2 flex gap-2">
          <Input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="New person's name" className="h-8 flex-1 text-[12.5px]" onKeyDown={(e) => { if (e.key === "Enter" && newName.trim()) patch({ new_person: newName }, "Person created"); }} />
          <Button size="sm" variant="outline" disabled={!newName.trim()} onClick={() => patch({ new_person: newName }, "Person created")}>Create</Button>
        </div>
        <div className="eyebrow mt-3.5 mb-1.5">Fix the turn itself</div>
        <div className="flex flex-wrap gap-1.5">
          <Button size="sm" variant="outline" onClick={() => { setOpen(false); onSplit(); }}>Split at a word…</Button>
          {hasPrev && <Button size="sm" variant="outline" onClick={async () => { const p = await api<Recording>(`/api/recordings/${r.id}/segments/${seg.id}/merge_prev`, { method: "POST" }); setOpen(false); toast("Merged into previous turn"); onChange(p); }}>Merge with previous</Button>}
          <Button size="sm" variant="ghost" onClick={() => { setOpen(false); onEdit(); }}>Edit text</Button>
        </div>
      </PopoverContent>
    </Popover>
  );
}
