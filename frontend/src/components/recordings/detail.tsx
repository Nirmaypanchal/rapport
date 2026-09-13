"use client";
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import useSWR from "swr";
import { toast } from "sonner";
import { ArrowLeft, Download, FileText, RefreshCw, Scissors, Trash2 } from "lucide-react";
import { api, exportRecording, fetcher, urls, type Recording } from "@/lib/api";
import { useConfirm } from "@/components/confirm";
import { fmtClock, fmtDate, fmtDur, fmtTime, recordingTitle } from "@/lib/format";
import { usePlayer } from "@/lib/use-player";
import { useStatus } from "@/lib/use-status";
import { Transport } from "./transport";
import { Transcript } from "./transcript";
import { SpeakerPopover } from "./speaker-popover";
import { SummaryTab } from "./summary-tab";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";
import { Progress } from "@/components/progress";

const TABS = ["transcript", "summary", "details", "actions", "notes"] as const;
type Tab = (typeof TABS)[number];
const LS_TAB = "recordingTab";

export function RecordingDetail({ id, seekTo, openTab, onListChanged }: { id: number; seekTo?: number; openTab?: string; onListChanged: () => void }) {
  const router = useRouter();
  const { confirm } = useConfirm();
  const { data: status } = useStatus();
  const { data: r, mutate } = useSWR<Recording>(`/api/recordings/${id}`, fetcher, {
    refreshInterval: (d) => (d && ((d.status !== "done" && d.status !== "error") || d.summary_status === "queued" || d.summary_status === "running") ? 2000 : 0),
  });
  const done = r?.status === "done";
  const hasAudio = !!(r && r.has_audio !== 0);
  const player = usePlayer(done && hasAudio ? urls.audio(id) : null, r?.duration_sec || 1);
  const [follow, setFollow] = useState(true);
  const [title, setTitle] = useState("");
  const [notes, setNotes] = useState("");
  const [tab, setTab] = useState<Tab>("transcript");
  useEffect(() => { try { const t = localStorage.getItem(LS_TAB) as Tab | null; if (t && TABS.includes(t)) setTab(t); } catch {} }, []);
  // A link that asks for a tab (a cited summary, say) wins over whichever one was left open last.
  useEffect(() => { if (openTab && TABS.includes(openTab as Tab)) setTab(openTab as Tab); }, [openTab, id]);
  useEffect(() => { if (r) { setTitle(r.title ?? ""); setNotes(r.notes ?? ""); } }, [r?.id, r?.title, r?.notes]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!player.ready || !seekTo) return;
    player.seek(seekTo, true);
    setTab("transcript");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [player.ready, seekTo, id]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement)?.matches?.("input,textarea,select,[contenteditable]")) return;
      if (e.code === "Space") { e.preventDefault(); player.toggle(); }
      if (e.key === "ArrowLeft") player.nudge(-5);
      if (e.key === "ArrowRight") player.nudge(5);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [player]);

  const applyPayload = useCallback((p: Pick<Recording, "speakers" | "segments">) => {
    mutate((cur) => (cur ? { ...cur, speakers: p.speakers, segments: p.segments } : cur), { revalidate: false });
    onListChanged();
  }, [mutate, onListChanged]);

  if (!r) return <div className="p-10 text-center text-[13px] text-ink-3">Loading…</div>;
  const minGap = status?.settings.skip_silence_min_gap ?? 0.7;
  const pad = status?.settings.skip_silence_pad ?? 0.15;
  const pick = (t: string) => { const v = t as Tab; setTab(v); try { localStorage.setItem(LS_TAB, v); } catch {} };
  const doExport = async (kind: "transcript" | "original" | "condensed") => {
    toast(kind === "condensed" ? "Exporting… (cutting pauses)" : "Exporting…");
    try { const res = await exportRecording(id, kind); toast(`Saved to ${res.path.replace(/^\/Users\/[^/]+/, "~")}`); }
    catch (e) { toast(`Export failed: ${(e as Error).message}`); }
  };

  return (
    <div className="grid h-full grid-rows-[1fr_auto]">
      <div className="min-h-0 overflow-y-auto px-4 pb-8 pt-4 sm:px-8 sm:pt-6 @container" id="detail-scroll">
        <Button variant="ghost" size="sm" className="-ml-2 mb-2 lg:hidden" onClick={() => router.push("/")}><ArrowLeft className="size-4" />Recordings</Button>
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          onBlur={async () => { if (title !== (r.title ?? "")) { await api(`/api/recordings/${id}`, { method: "PATCH", json: { title } }); mutate(); onListChanged(); toast("Title saved"); } }}
          placeholder={recordingTitle(r)}
          className="w-full border-b border-transparent bg-transparent font-display text-[22px] font-semibold leading-tight tracking-[-0.02em] outline-none placeholder:text-ink hover:border-hairline focus:border-hairline sm:text-[30px]"
          aria-label="Title"
        />
        <div className="mt-1 text-[12.5px] text-ink-3">{fmtDate(r.recorded_at)} · {fmtClock(r.recorded_at)} · <span className="tc">{fmtDur(r.duration_sec)}</span>{!hasAudio && <> · text only, from {sourceLabel(r.source)}</>}</div>

        {r.status !== "done" && (
          <div className={cn("mt-5 rounded-lg border border-hairline bg-surface px-4 py-4 text-[13.5px]", r.status === "error" ? "text-clip" : "text-ink-2")}>
            <div className="flex items-center gap-3">
              {r.status === "error" ? <span>⚠︎</span> : <span className="blink size-2 rounded-full bg-signal" />}
              <span className="flex-1">{r.status === "error" ? `Processing failed: ${r.error}` : r.status === "processing" ? `${r.stage || "Starting"}` : "Waiting in queue…"}</span>
              {r.status === "processing" && typeof r.progress === "number" && <span className="tc text-[12.5px] text-ink-3">{Math.round(r.progress * 100)}%</span>}
              {r.status === "error" && <Button size="sm" variant="outline" onClick={() => reprocess(r, mutate, onListChanged, confirm, true)}>Retry</Button>}
            </div>
            {r.status === "processing" && <Progress value={r.progress} className="mt-3" />}
          </div>
        )}

        {done && (
          <Tabs value={tab} onValueChange={pick} className="mt-4">
            <TabsList variant="line" className="glass sticky top-0 z-10 -mx-4 w-[calc(100%+2rem)] flex-wrap justify-start overflow-visible px-4 sm:-mx-8 sm:w-[calc(100%+4rem)] sm:px-8">
              <TabsTrigger value="transcript">Transcript</TabsTrigger>
              <TabsTrigger value="summary" className="gap-1.5">Summary{(r.summary_status === "queued" || r.summary_status === "running") && <span className="blink size-1.5 rounded-full bg-signal" />}</TabsTrigger>
              <TabsTrigger value="details">Details</TabsTrigger>
              <TabsTrigger value="actions">Actions</TabsTrigger>
              <TabsTrigger value="notes" className="gap-1.5">Notes{r.notes?.trim() && <span className="size-1.5 rounded-full bg-ink-3" />}</TabsTrigger>
            </TabsList>

            <TabsContent value="transcript" keepMounted className="mt-4">
              <div className="flex flex-wrap gap-2">
                {r.speakers.map((s) => <SpeakerPopover key={s.label} r={r} s={s} onChange={() => { mutate(); onListChanged(); }} />)}
                <span className="hidden self-center text-[12px] text-ink-3 md:inline">Click a speaker name in the transcript to correct it.</span>
              </div>
              <div className="mt-5">
                <Transcript r={r} player={player} follow={follow} onChange={applyPayload} />
              </div>
            </TabsContent>

            <TabsContent value="summary" keepMounted className="mt-4">
              <SummaryTab r={r} onChange={() => mutate()} />
            </TabsContent>

            <TabsContent value="details" keepMounted className="mt-4">
              <Details r={r} />
            </TabsContent>

            <TabsContent value="actions" keepMounted className="mt-4">
              <div className="mx-auto grid max-w-[720px] gap-2">
                <Action icon={<FileText className="size-4" />} title="Export transcript" desc="Plain text with timecodes and speaker names, saved to Downloads/Rapport." onClick={() => doExport("transcript")} />
                {hasAudio && <Action icon={<Download className="size-4" />} title="Export original audio" desc={`A copy of the untouched file (${r.original_name}), saved to Downloads/Rapport.`} onClick={() => doExport("original")} />}
                {hasAudio && <Action icon={<Scissors className="size-4" />} title="Export condensed audio" desc={`An .m4a with pauses longer than ${minGap}s cut out, saved to Downloads/Rapport.`} onClick={() => doExport("condensed")} />}
                {hasAudio && <Action icon={<RefreshCw className="size-4" />} title="Re-process" desc="Run transcription and speaker detection again. Manual corrections to turns are replaced." onClick={() => reprocess(r, mutate, onListChanged, confirm)} />}
                <Action icon={<Trash2 className="size-4" />} title="Remove from library" desc="Deletes the transcript, speakers and summary. The original audio stays on disk." danger onClick={async () => {
                  if (!(await confirm({ title: `Remove "${recordingTitle(r)}"?`, description: "The transcript, speakers and summary are deleted. The original audio file stays in the library folder.", confirmLabel: "Remove", destructive: true }))) return;
                  await api(`/api/recordings/${id}`, { method: "DELETE" }); toast("Removed"); onListChanged(); router.push("/");
                }} />
              </div>
            </TabsContent>

            <TabsContent value="notes" keepMounted className="mt-4">
              <div className="mx-auto max-w-[720px]">
                <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Add notes about this recording…" className="min-h-[200px] bg-surface text-[15px] leading-relaxed"
                  onBlur={async () => { if (notes !== (r.notes ?? "")) { await api(`/api/recordings/${id}`, { method: "PATCH", json: { notes } }); mutate(); toast("Notes saved"); } }} />
                <div className="mt-2 text-[12px] text-ink-3">Saved when you click away.</div>
              </div>
            </TabsContent>
          </Tabs>
        )}
      </div>
      {done && hasAudio && <Transport r={r} player={player} minGap={minGap} pad={pad} follow={follow} onFollow={setFollow} />}
    </div>
  );
}

export function sourceLabel(src: Recording["source"]): string {
  return { dji: "DJI Mic", voicememos: "Apple Voice Memos", file: "imported file", usb: "USB drive", folder: "watched folder", microphone: "microphone", granola: "Granola", omi: "Omi", notion: "Notion" }[src ?? "dji"] ?? String(src);
}

function Details({ r }: { r: Recording }) {
  const rows: [string, React.ReactNode][] = [
    ["Recorded", r.recorded_at ? `${fmtDate(r.recorded_at)}, ${fmtClock(r.recorded_at)}` : "Unknown"],
    ["Duration", <span key="d" className="tc">{fmtTime(r.duration_sec)} ({fmtDur(r.duration_sec)})</span>],
    ["Source", r.source === "dji" || !r.source ? `DJI Mic${r.transmitter ? `, transmitter ${r.transmitter}` : ""}` : sourceLabel(r.source)],
    ["File", <span key="f" className="tc break-all">{r.original_name}</span>],
    ["Audio", r.sample_rate ? <span key="a" className="tc">{(r.sample_rate / 1000).toFixed(r.sample_rate % 1000 ? 1 : 0)} kHz</span> : "—"],
    ["Language", r.language ? r.language : "—"],
    ["Transcription", r.whisper_model ? <span key="w" className="tc">{r.whisper_model.split("/").pop()}</span> : "—"],
    ["Speaker detection", r.diarizer === "pyannote" ? "pyannote diarization pipeline" : r.diarizer === "builtin" ? "Built-in (Silero VAD + WeSpeaker embeddings)" : r.diarizer ?? "—"],
    ["Summary model", r.summary_model ? <span key="s" className="tc">{r.summary_model}</span> : "—"],
    ["Summary template", r.summary_template ? <span key="st" className="tc">{r.summary_template}</span> : "—"],
    ["Processed", r.processed_at ? `${fmtDate(r.processed_at)}, ${fmtClock(r.processed_at)}` : "—"],
    ["Imported", r.imported_at ? `${fmtDate(r.imported_at)}, ${fmtClock(r.imported_at)}${r.deleted_from_device ? " · removed from the mic after verification" : ""}` : "—"],
    ["Speakers", `${r.speakers.length}`],
    ["Turns", `${r.segments?.length ?? 0}`],
    ["Words", `${(r.segments ?? []).reduce((a, s) => a + s.words.length, 0)}`],
  ];
  return (
    <div className="mx-auto max-w-[720px] rounded-lg border border-hairline bg-surface">
      {rows.map(([k, v]) => (
        <div key={k} className="grid grid-cols-[130px_1fr] gap-3 border-t border-hairline px-4 py-2.5 text-[13.5px] first:border-t-0 sm:grid-cols-[170px_1fr]">
          <span className="text-ink-3">{k}</span><span className="min-w-0">{v}</span>
        </div>
      ))}
    </div>
  );
}

function Action({ icon, title, desc, href, newTab, onClick, danger }: { icon: React.ReactNode; title: string; desc: string; href?: string; newTab?: boolean; onClick?: () => void; danger?: boolean }) {
  const cls = cn("grid grid-cols-[auto_1fr] items-center gap-3.5 rounded-lg border border-hairline bg-surface px-4 py-3 text-left transition-colors hover:border-ink-3", danger && "hover:border-clip");
  const body = (
    <>
      <span className={cn("grid size-9 place-items-center rounded-full bg-surface-2", danger ? "text-clip" : "text-ink")}>{icon}</span>
      <span className="min-w-0"><span className={cn("block text-[14px] font-semibold", danger && "text-clip")}>{title}</span><span className="block text-[12.5px] text-ink-2">{desc}</span></span>
    </>
  );
  return href ? <a href={href} target={newTab ? "_blank" : undefined} rel={newTab ? "noreferrer" : undefined} className={cls}>{body}</a> : <button type="button" onClick={onClick} className={cn(cls, "w-full")}>{body}</button>;
}

async function reprocess(r: Recording, mutate: () => void, onListChanged: () => void, confirm: (o: { title: string; description?: string; confirmLabel?: string; destructive?: boolean }) => Promise<boolean>, silent = false) {
  if (!silent && r.status === "done" && !(await confirm({ title: "Re-process this recording?", description: "Transcription and speaker detection run again from the audio. Manual corrections to turns (speakers, splits, text edits) are replaced.", confirmLabel: "Re-process" }))) return;
  await api(`/api/recordings/${r.id}/reprocess`, { method: "POST" });
  toast("Queued for processing");
  mutate();
  onListChanged();
}
