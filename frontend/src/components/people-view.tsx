"use client";
import Link from "next/link";
import { useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import useSWR from "swr";
import { toast } from "sonner";
import { api, fetcher, type Appearance, type Person } from "@/lib/api";

type PersonDetail = Omit<Person, "appearances"> & { appearances: Appearance[] };
import { fmtClock, fmtDate, fmtDur } from "@/lib/format";
import { speakerGlyph } from "@/lib/speakers";
import { SpeakerAvatar } from "@/components/avatar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { cn } from "@/lib/utils";

export function PeopleView() {
  const params = useSearchParams();
  const selected = params.get("id") ? Number(params.get("id")) : null;
  const { data: people, mutate } = useSWR<Person[]>("/api/people", fetcher, { refreshInterval: 10000 });
  const { data: person } = useSWR<PersonDetail>(selected ? `/api/people/${selected}` : null, fetcher);
  const [q, setQ] = useState("");
  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return (people ?? []).filter((p) => !needle || p.name.toLowerCase().includes(needle) || (p.note ?? "").toLowerCase().includes(needle));
  }, [people, q]);

  return (
    <div className="h-full overflow-y-auto px-4 pb-10 pt-5 sm:px-8 sm:pt-7">
      <div className="mx-auto max-w-[1000px]">
        <h1 className="font-display text-[26px] font-semibold tracking-[-0.02em] sm:text-[30px]">People</h1>
        <p className="mt-1 max-w-[62ch] text-[13.5px] text-ink-2">Everyone whose voice has been heard. Auto-named people like “Speaker 3” are matched by voice across recordings; rename them once and the name follows the voice.</p>

        {people && people.length > 0 && (
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder={`Search ${people.length} people…`} className="mt-5 h-10 max-w-[420px] bg-surface" />
        )}
        {!people?.length ? (
          <div className="mt-10 text-center text-[13px] text-ink-3">No one yet. Process a recording first.</div>
        ) : !filtered.length ? (
          <div className="mt-8 text-[13px] text-ink-3">No one matches “{q}”.</div>
        ) : (
          <div className="mt-4 overflow-x-auto rounded-lg border border-hairline bg-surface">
            <table className="w-full min-w-[560px] text-[14px]">
              <thead><tr className="eyebrow text-left"><th className="px-4 py-2.5 font-medium">Name</th><th className="px-3 py-2.5 font-medium">Recordings</th><th className="px-3 py-2.5 font-medium">Speaking</th><th className="px-3 py-2.5 font-medium">Last heard</th><th className="px-3 py-2.5" /></tr></thead>
              <tbody>
                {filtered.map((p) => <PersonRow key={p.id} p={p} people={people} selected={p.id === selected} onChange={() => mutate()} />)}
              </tbody>
            </table>
          </div>
        )}

        {person && (
          <div className="mt-8">
            <div className="eyebrow mb-2">{person.name} · appearances</div>
            <div className="grid gap-2">
              {person.appearances.map((a) => (
                <Link key={`${a.recording_id}-${a.label}`} href={`/?id=${a.recording_id}`} className="rounded-lg border border-hairline bg-surface px-4 py-3 transition-colors hover:border-ink-3">
                  <div className="text-[14px] font-semibold">{a.title || `${fmtDate(a.recorded_at)}, ${fmtClock(a.recorded_at)}`}</div>
                  <div className="mt-0.5 flex flex-wrap gap-x-3 text-[12px] text-ink-2"><span className="tc">{a.original_name}</span><span>spoke {fmtDur(a.speaking_sec)} of {fmtDur(a.duration_sec)}</span><span>{a.similarity != null ? `voice match ${Math.round(a.similarity * 100)}%` : "first seen or assigned by hand"}</span></div>
                </Link>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function PersonRow({ p, people, selected, onChange }: { p: Person; people: Person[]; selected: boolean; onChange: () => void }) {
  const [name, setName] = useState(p.name);
  const others = people.filter((x) => x.id !== p.id);
  return (
    <tr className={cn("border-t border-hairline", selected && "bg-surface-2")}>
      <td className="px-4 py-2.5">
        <div className="flex items-center gap-2.5">
          <SpeakerAvatar color={p.color} glyph={speakerGlyph(p)} size={28} />
          <div className="min-w-0">
            <input value={name} onChange={(e) => setName(e.target.value)} onBlur={async () => { if (name.trim() && name !== p.name) { await api(`/api/people/${p.id}`, { method: "PATCH", json: { name } }); toast("Renamed"); onChange(); } }}
              className="w-full rounded-md bg-transparent px-1 py-0.5 text-[14px] font-semibold outline-none hover:bg-surface-2 focus:bg-surface-2" aria-label="Name" />
            {p.auto ? <div className="px-1 text-[11.5px] text-ink-3">auto-named · click to rename</div> : null}
          </div>
        </div>
      </td>
      <td className="px-3 py-2.5"><Link href={`/people/?id=${p.id}`} className="tc underline-offset-2 hover:underline">{p.appearances}</Link></td>
      <td className="tc px-3 py-2.5">{fmtDur(p.speaking_sec)}</td>
      <td className="px-3 py-2.5 text-[12.5px] text-ink-2">{p.last_heard ? fmtDate(p.last_heard) : "—"}</td>
      <td className="px-3 py-2.5 text-right">
        <div className="flex items-center justify-end gap-1.5">
          <Select value="" onValueChange={async (v) => { if (!v) return; const keep = Number(v); const target = others.find((o) => o.id === keep)!; if (!confirm(`Merge “${p.name}” into “${target.name}”?\n\nAll of ${p.name}'s appearances will belong to ${target.name}.`)) return; await api(`/api/people/${keep}/merge/${p.id}`, { method: "POST" }); toast("Merged"); onChange(); }}>
            <SelectTrigger size="sm" className="h-7 text-[12px]"><SelectValue placeholder="Merge into…" /></SelectTrigger>
            <SelectContent>{others.map((o) => <SelectItem key={o.id} value={String(o.id)}>{o.name}</SelectItem>)}</SelectContent>
          </Select>
          {p.appearances === 0 && <Button size="sm" variant="ghost" className="text-clip" onClick={async () => { await api(`/api/people/${p.id}`, { method: "DELETE" }); onChange(); }}>Delete</Button>}
        </div>
      </td>
    </tr>
  );
}
