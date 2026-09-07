"use client";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api, type Person, type Recording, type Speaker } from "@/lib/api";
import { fmtDur } from "@/lib/format";
import { SpeakerChip } from "@/components/avatar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

export function SpeakerPopover({ r, s, onChange }: { r: Recording; s: Speaker; onChange: () => void }) {
  const [open, setOpen] = useState(false);
  const [people, setPeople] = useState<Person[]>([]);
  const [rename, setRename] = useState(s.person_name ?? "");
  const [pick, setPick] = useState(s.person_id ? String(s.person_id) : "");
  const [newName, setNewName] = useState("");
  useEffect(() => { if (open) { api<Person[]>("/api/people").then(setPeople); setRename(s.person_name ?? ""); } }, [open, s.person_name]);

  const done = (msg: string) => { setOpen(false); toast(msg); onChange(); };
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger render={<span />}>
        <SpeakerChip s={s} active={open} />
      </PopoverTrigger>
      <PopoverContent align="start" className="w-[300px] p-3.5">
        <div className="text-[13px] font-semibold">{s.label} <span className="tc ml-1 text-[11.5px] font-normal text-ink-3">{fmtDur(s.speaking_sec)} of speech</span></div>
        {s.person_id && (
          <>
            <div className="eyebrow mt-3 mb-1.5">Rename person (all recordings)</div>
            <div className="flex gap-2">
              <Input value={rename} onChange={(e) => setRename(e.target.value)} className="h-8 flex-1" autoFocus onKeyDown={async (e) => { if (e.key === "Enter" && rename.trim()) { await api(`/api/people/${s.person_id}`, { method: "PATCH", json: { name: rename } }); done("Renamed"); } }} />
              <Button size="sm" disabled={!rename.trim() || rename === s.person_name} onClick={async () => { await api(`/api/people/${s.person_id}`, { method: "PATCH", json: { name: rename } }); done("Renamed"); }}>Save</Button>
            </div>
          </>
        )}
        <div className="eyebrow mt-3 mb-1.5">Or: this voice is actually…</div>
        <div className="flex gap-2">
          <Select value={pick} onValueChange={(v) => setPick(v ?? "")}>
            <SelectTrigger size="sm" className="flex-1 text-[12.5px]"><SelectValue placeholder="Choose a person" /></SelectTrigger>
            <SelectContent>{people.map((p) => <SelectItem key={p.id} value={String(p.id)}>{p.name} · {p.appearances} rec.</SelectItem>)}</SelectContent>
          </Select>
          <Button size="sm" variant="outline" disabled={!pick || Number(pick) === s.person_id} onClick={async () => { await api(`/api/recordings/${r.id}/speakers/${s.label}/assign`, { method: "POST", json: { person_id: Number(pick) } }); done("Reassigned"); }}>Assign</Button>
        </div>
        <div className="eyebrow mt-3 mb-1.5">Or: a new person</div>
        <div className="flex gap-2">
          <Input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="e.g. Alice" className="h-8 flex-1" onKeyDown={async (e) => { if (e.key === "Enter" && newName.trim()) { await api(`/api/recordings/${r.id}/speakers/${s.label}/assign`, { method: "POST", json: { new_name: newName } }); done("Created"); } }} />
          <Button size="sm" variant="outline" disabled={!newName.trim()} onClick={async () => { await api(`/api/recordings/${r.id}/speakers/${s.label}/assign`, { method: "POST", json: { new_name: newName } }); done("Created"); }}>Create</Button>
        </div>
      </PopoverContent>
    </Popover>
  );
}
