"use client";
import { useEffect, useRef, useState } from "react";
import useSWR from "swr";
import { toast } from "sonner";
import { siApple, siBluetooth, siDji, siDropbox, siGoogledrive, siIcloud, siNotion } from "simple-icons";
import { ChevronRight, Circle, Download, FolderOpen, HardDrive, Mic, Square, Upload, Watch } from "lucide-react";
import { API, api, fetcher, uploadFiles, type Settings, type Sources, type VoiceMemosStatus } from "@/lib/api";
import { fmtClock, fmtDate, fmtDur, fmtTime } from "@/lib/format";
import { useStatus } from "@/lib/use-status";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

/* ---------------------------------------------------------------- brand marks */
type Mark = { kind: "si"; path: string; hex: string } | { kind: "img"; src: string; fallback?: Mark } | { kind: "icon"; icon: React.ComponentType<{ className?: string; strokeWidth?: number }> };
const si = (i: { path: string; hex: string }): Mark => ({ kind: "si", path: i.path, hex: `#${i.hex}` });
const app = (key: string, fallback?: Mark): Mark => ({ kind: "img", src: `${API}/api/brand/${key}.png`, fallback });
const file = (name: string, fallback?: Mark): Mark => ({ kind: "img", src: `/brands/${name}`, fallback });

function BrandMark({ mark, size = 44 }: { mark: Mark; size?: number }) {
  const [failed, setFailed] = useState(false);
  if (mark.kind === "img" && !failed) {
    // eslint-disable-next-line @next/next/no-img-element
    return <img src={mark.src} alt="" width={size} height={size} className="rounded-[22%] object-contain" style={{ width: size, height: size }} onError={() => setFailed(true)} />;
  }
  if (mark.kind === "img" && mark.fallback) return <BrandMark mark={mark.fallback} size={size} />;
  if (mark.kind === "si") {
    return (
      <span className="grid place-items-center rounded-[22%] bg-surface-2" style={{ width: size, height: size }}>
        <svg viewBox="0 0 24 24" width={size * 0.55} height={size * 0.55} aria-hidden style={{ fill: mark.hex === "#000000" ? "var(--ink)" : mark.hex }}><path d={mark.path} /></svg>
      </span>
    );
  }
  if (mark.kind === "icon") {
    const Icon = mark.icon;
    return <span className="grid place-items-center rounded-[22%] bg-surface-2 text-ink" style={{ width: size, height: size }}><Icon className="size-5" strokeWidth={1.75} /></span>;
  }
  return null;
}

/* ---------------------------------------------------------------- catalogue */
type SourceId = "dji" | "usb" | "mic" | "voicememos" | "omi" | "granola" | "notion" | "icloud" | "dropbox" | "googledrive" | "folder" | "files";
type Tile = { id: SourceId; name: string; mark: Mark; blurb: string };

const DEVICES: Tile[] = [
  { id: "dji", name: "DJI Mic", mark: si(siDji), blurb: "Transmitters over USB. Verified, then cleared." },
  { id: "usb", name: "USB recorder or SD card", mark: { kind: "icon", icon: HardDrive }, blurb: "Zoom, Tascam, Sony, any drive with audio." },
  { id: "mic", name: "Microphone & Bluetooth", mark: si(siBluetooth), blurb: "Record from AirPods, a USB mic, or the Mac." },
  { id: "voicememos", name: "Apple Voice Memos", mark: app("voicememos", si(siApple)), blurb: "Mac, iPhone and Apple Watch memos via iCloud." },
  { id: "omi", name: "Omi", mark: file("omi.png", { kind: "icon", icon: Circle }), blurb: "Conversations from the Omi pendant." },
];
const INTEGRATIONS: Tile[] = [
  { id: "granola", name: "Granola", mark: app("granola", file("granola.svg")), blurb: "Meeting notes, transcripts and summaries." },
  { id: "notion", name: "Notion AI Meeting Notes", mark: app("notion", si(siNotion)), blurb: "Pages with Notion's meeting notes block." },
  { id: "icloud", name: "iCloud Drive", mark: si(siIcloud), blurb: "Watch a folder your phone recorder saves to." },
  { id: "dropbox", name: "Dropbox", mark: si(siDropbox), blurb: "Watch a synced folder." },
  { id: "googledrive", name: "Google Drive", mark: si(siGoogledrive), blurb: "Watch a synced folder." },
  { id: "folder", name: "Any folder", mark: { kind: "icon", icon: FolderOpen }, blurb: "Watch a folder on this Mac." },
  { id: "files", name: "Files & exports", mark: { kind: "icon", icon: Upload }, blurb: "Otter, Plaud, Pocket exports, or any audio file." },
];

type Tone = "good" | "warn" | "idle" | "live";
const Pill = ({ tone, children }: { tone: Tone; children: React.ReactNode }) => (
  <span className={cn("inline-flex items-center gap-1.5 rounded-full px-2 py-px text-[11px] font-medium", tone === "good" && "bg-good-soft text-good", tone === "warn" && "bg-warn-soft text-warn", tone === "idle" && "bg-surface-2 text-ink-2", tone === "live" && "bg-signal-soft text-signal")}>
    <span className={cn("size-1.5 rounded-full bg-current", tone === "live" && "blink")} />{children}
  </span>
);

/* ---------------------------------------------------------------- page */
export function SourcesView() {
  const { data: status, mutate: mutateStatus } = useStatus();
  const { data: src, mutate } = useSWR<Sources>("/api/sources", fetcher, { refreshInterval: 5000 });
  const { data: roots } = useSWR<{ key: string; label: string; path: string }[]>("/api/fs/roots", fetcher);
  const [open, setOpen] = useState<SourceId | null>(null);
  const [s, setS] = useState<Settings | null>(null);
  useEffect(() => { if (status) setS((cur) => cur ?? status.settings); }, [status]);
  const save = async (patch: Partial<Settings>, msg = "Saved") => {
    const p: Record<string, unknown> = { ...patch };
    for (const k of ["granola_api_key", "omi_api_key", "notion_token"]) if (p[k] === "•••") delete p[k];
    await api("/api/settings", { method: "PUT", json: { patch: p } });
    toast(msg); mutateStatus(); mutate();
    setS((cur) => (cur ? { ...cur, ...patch } : cur));
  };
  if (!status || !s || !src) return <div className="p-10 text-center text-[13px] text-ink-3">Loading…</div>;
  const c = src.counts;
  const rootOf = (key: string) => roots?.find((r) => r.key === key);
  const watching = (key: string) => { const r = rootOf(key); return r ? s.watched_folders.filter((f) => f.startsWith(r.path)) : []; };

  const state = (id: SourceId): { tone: Tone; text: string } => {
    switch (id) {
      case "dji": { const n = src.volumes.filter((v) => v.is_dji).length; return n ? { tone: "good", text: `${n} plugged in` } : { tone: "idle", text: `${c.dji ?? 0} recordings` }; }
      case "usb": { const on = src.volumes.filter((v) => !v.is_dji && v.enabled).length; const all = src.volumes.filter((v) => !v.is_dji).length; return on ? { tone: "good", text: `${on} importing` } : all ? { tone: "warn", text: `${all} plugged in` } : { tone: "idle", text: c.usb ? `${c.usb} recordings` : "Nothing plugged in" }; }
      case "mic": return src.recording ? { tone: "live", text: "Recording" } : { tone: "idle", text: `${src.microphones.length} input${src.microphones.length === 1 ? "" : "s"}` };
      case "voicememos": return src.voice_memos.available ? { tone: "good", text: s.auto_import_voice_memos ? "Auto-import on" : "Connected" } : { tone: "warn", text: "Needs access" };
      case "omi": case "granola": case "notion": { const k = src.connectors[id]; return !k.configured ? { tone: "idle", text: "Not connected" } : k.last_error ? { tone: "warn", text: "Error" } : { tone: "good", text: `${c[id] ?? 0} imported` }; }
      case "icloud": case "dropbox": case "googledrive": { const r = rootOf(id); const w = watching(id); return !r ? { tone: "idle", text: "Not on this Mac" } : w.length ? { tone: "good", text: `${w.length} folder${w.length === 1 ? "" : "s"}` } : { tone: "idle", text: "Available" }; }
      case "folder": { const other = s.watched_folders.filter((f) => !["icloud", "dropbox", "googledrive"].some((k) => rootOf(k) && f.startsWith(rootOf(k)!.path))); return other.length ? { tone: "good", text: `${other.length} watched` } : { tone: "idle", text: "None yet" }; }
      case "files": return { tone: "idle", text: c.file ? `${c.file} imported` : "Drop or choose" };
    }
  };

  const Grid = ({ tiles }: { tiles: Tile[] }) => (
    <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3 lg:grid-cols-4">
      {tiles.map((t) => {
        const st = state(t.id);
        return (
          <button key={t.id} type="button" onClick={() => setOpen(t.id)} className="group flex flex-col items-start gap-3 rounded-xl border border-hairline bg-surface p-3.5 text-left transition-[border-color,transform] duration-120 hover:border-ink-3 active:scale-[.99]">
            <div className="flex w-full items-start justify-between"><BrandMark mark={t.mark} /><ChevronRight className="size-4 text-ink-3 opacity-0 transition-opacity group-hover:opacity-100" /></div>
            <div className="min-w-0">
              <div className="truncate text-[14px] font-semibold leading-tight">{t.name}</div>
              <div className="mt-0.5 line-clamp-2 text-[12px] leading-snug text-ink-3">{t.blurb}</div>
            </div>
            <div className="mt-auto"><Pill tone={st.tone}>{st.text}</Pill></div>
          </button>
        );
      })}
    </div>
  );

  const tile = [...DEVICES, ...INTEGRATIONS].find((t) => t.id === open);
  return (
    <div className="h-full overflow-y-auto px-4 pb-10 pt-5 sm:px-8 sm:pt-7">
      <div className="mx-auto max-w-[1000px]">
        <h1 className="font-display text-[26px] font-semibold tracking-[-0.02em] sm:text-[30px]">Sources</h1>
        <p className="mt-1 max-w-[62ch] text-[13.5px] text-ink-2">Everything that can feed this library. Click a source to connect it.</p>
        <div className="eyebrow mt-7 mb-2.5">Devices</div>
        <Grid tiles={DEVICES} />
        <div className="eyebrow mt-8 mb-2.5">Integrations</div>
        <Grid tiles={INTEGRATIONS} />
      </div>

      <Dialog open={open != null} onOpenChange={(o) => !o && setOpen(null)}>
        <DialogContent className="max-h-[88vh] overflow-y-auto sm:max-w-[560px]">
          {tile && (
            <>
              <DialogHeader className="flex-row items-center gap-3.5 text-left">
                <BrandMark mark={tile.mark} size={48} />
                <div><DialogTitle className="text-[18px]">{tile.name}</DialogTitle><DialogDescription>{tile.blurb}</DialogDescription></div>
              </DialogHeader>
              <div className="text-[13.5px]">
                {open === "dji" && <DjiPanel src={src} count={c.dji ?? 0} />}
                {open === "usb" && <UsbPanel src={src} s={s} save={save} />}
                {open === "mic" && <MicPanel src={src} onChange={() => { mutate(); mutateStatus(); }} />}
                {open === "voicememos" && <VoiceMemosPanel vm={src.voice_memos} auto={s.auto_import_voice_memos} onAuto={(v) => save({ auto_import_voice_memos: v })} onChange={() => mutate()} onRecheck={() => mutate()} />}
                {(open === "omi" || open === "granola" || open === "notion") && <ConnectorPanel name={open} src={src} s={s} save={save} />}
                {(open === "icloud" || open === "dropbox" || open === "googledrive" || open === "folder") && <FolderPanel kind={open} root={open === "folder" ? undefined : rootOf(open)} s={s} save={save} />}
                {open === "files" && <FilesPanel />}
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}

/* ---------------------------------------------------------------- panels */
const Steps = ({ items }: { items: React.ReactNode[] }) => (
  <ol className="mt-3 grid gap-2">{items.map((it, i) => <li key={i} className="grid grid-cols-[22px_1fr] gap-2.5"><span className="tc grid size-[22px] place-items-center rounded-full bg-surface-2 text-[11px] font-semibold">{i + 1}</span><div className="pt-0.5">{it}</div></li>)}</ol>
);
const openSys = (target: string) => api("/api/system/open", { method: "POST", json: { target } }).catch((e) => toast((e as Error).message));

function DjiPanel({ src, count }: { src: Sources; count: number }) {
  const vols = src.volumes.filter((v) => v.is_dji);
  return (
    <div>
      {vols.length ? vols.map((v) => <div key={v.mount} className="mb-2 flex items-center gap-2 rounded-md border border-hairline px-3 py-2"><Pill tone="good">connected</Pill><span className="font-medium">{v.media || v.name}</span><span className="tc ml-auto text-[12px] text-ink-3">{v.files} file{v.files === 1 ? "" : "s"} waiting</span></div>) : <p className="text-ink-2">No transmitter is plugged in right now.</p>}
      <Steps items={[
        <>Plug a transmitter (or the charging case) into the Mac with USB-C. It shows up as a drive named <span className="tc">NO NAME</span>.</>,
        <>Every recording is copied, verified byte-for-byte, transcribed, and then deleted from the transmitter so it never fills up.</>,
        <>Unplug whenever the light in the sidebar is green. Nothing else to do.</>,
      ]} />
      <div className="mt-4 text-[12px] text-ink-3">{count} recordings so far. Deleting after import can be turned off in Settings.</div>
    </div>
  );
}

function UsbPanel({ src, s, save }: { src: Sources; s: Settings; save: (p: Partial<Settings>, m?: string) => Promise<void> }) {
  const vols = src.volumes.filter((v) => !v.is_dji);
  return (
    <div>
      {vols.length ? (
        <div className="divide-y divide-hairline rounded-md border border-hairline">
          {vols.map((v) => <div key={v.mount} className="flex items-center gap-3 px-3 py-2"><div className="min-w-0 flex-1"><div className="font-medium">{v.media || v.name}</div><div className="tc text-[12px] text-ink-3">{v.mount} · {v.files} audio file{v.files === 1 ? "" : "s"}</div></div><Switch checked={v.enabled} onCheckedChange={(on) => save({ usb_volumes: on ? [...new Set([...s.usb_volumes, v.name])] : s.usb_volumes.filter((n) => n !== v.name) }, on ? `Importing from ${v.name}` : `Stopped importing from ${v.name}`)} /></div>)}
        </div>
      ) : <p className="text-ink-2">Plug in a recorder, SD card or drive and it will appear here with a switch.</p>}
      <Steps items={[<>Plug the recorder or its card into the Mac.</>, <>Switch it on above. Audio is copied on every poll; the drive is never written to or cleared.</>, <>The switch is remembered by drive name, so the same card imports automatically next time.</>]} />
    </div>
  );
}

function MicPanel({ src, onChange }: { src: Sources; onChange: () => void }) {
  const [device, setDevice] = useState("");
  const [busy, setBusy] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const rec = src.recording;
  useEffect(() => { if (!device && src.microphones.length) setDevice(rec?.device ?? src.microphones.find((m) => /macbook|built-in/i.test(m)) ?? src.microphones[0]); }, [src.microphones, device, rec]);
  useEffect(() => { if (!rec) return; const t = setInterval(() => setElapsed(Date.now() / 1000 - rec.started_at), 500); return () => clearInterval(t); }, [rec]);
  const start = async () => { setBusy(true); try { await api("/api/record/start", { method: "POST", json: { device } }); toast(`Recording from ${device}`); onChange(); } catch (e) { toast(`Could not start: ${(e as Error).message}`); } setBusy(false); };
  const stop = async () => { setBusy(true); try { await api("/api/record/stop", { method: "POST" }); toast("Saved and queued for processing"); onChange(); } catch (e) { toast(`Stop failed: ${(e as Error).message}`); } setBusy(false); };
  return (
    <div>
      <div className="flex flex-wrap items-center gap-2">
        <Select value={device} onValueChange={(v) => setDevice(v ?? "")} disabled={!!rec}>
          <SelectTrigger className="min-w-[200px] flex-1 bg-surface"><SelectValue placeholder="Choose an input" /></SelectTrigger>
          <SelectContent>{src.microphones.map((m) => <SelectItem key={m} value={m}>{m}</SelectItem>)}</SelectContent>
        </Select>
        {rec ? <Button onClick={stop} disabled={busy} className="bg-signal text-white hover:bg-signal"><Square className="size-3.5 fill-current" />Stop · <span className="tc">{fmtTime(elapsed)}</span></Button>
             : <Button onClick={start} disabled={busy || !device}><Circle className="size-3.5 fill-signal text-signal" />Record</Button>}
      </div>
      {src.recording_error && !rec && <div className="mt-2 text-[12px] text-clip">{src.recording_error}</div>}
      <Steps items={[
        <>Pair AirPods or another Bluetooth mic in <button className="underline" onClick={() => openSys("bluetooth")}>Bluetooth settings</button>, or plug in a USB mic or DJI receiver. It appears in the list above within a few seconds.</>,
        <>Press <b>Record</b>. The first time, macOS asks for microphone access; if it didn't, <button className="underline" onClick={() => openSys("microphone")}>open Microphone privacy settings</button> and allow the app you launched this from.</>,
        <>Press <b>Stop</b>. The take is saved as 48 kHz WAV, transcribed and speaker-tagged like any other recording.</>,
      ]} />
      <div className="mt-4 text-[12px] text-ink-3">{src.counts.microphone ?? 0} recorded here so far.</div>
    </div>
  );
}

function VoiceMemosPanel({ vm, auto, onAuto, onChange, onRecheck }: { vm: Omit<VoiceMemosStatus, "memos">; auto: boolean; onAuto: (v: boolean) => void; onChange: () => void; onRecheck: () => void }) {
  const { data: full, mutate } = useSWR<VoiceMemosStatus>(vm.available ? "/api/voicememos" : null, fetcher, { refreshInterval: 20000 });
  const [busy, setBusy] = useState(false);
  if (!vm.available) {
    if (vm.reason !== "permission") return <p className="text-ink-2">{vm.message}</p>;
    return (
      <div>
        <p className="text-ink-2">Voice Memos keeps its recordings in a folder macOS protects. Grant access once and memos from this Mac, your iPhone and Apple Watch (via iCloud) import with their titles and dates. Voice Memos itself is never changed.</p>
        <Steps items={[
          <div className="flex flex-wrap items-center gap-2"><Button size="sm" onClick={() => openSys("fulldisk")}>Request access</Button><span className="text-ink-2">opens System Settings at Full Disk Access.</span></div>,
          <div className="flex flex-wrap items-center gap-2"><Button size="sm" variant="outline" onClick={() => openSys("reveal-python")}>Show the app to add</Button><span className="text-ink-2">reveals it in Finder. Drag it into the list, or use <b>+</b>, and switch it on. Adding Terminal instead also works if you start from there.</span></div>,
          <div className="flex flex-wrap items-center gap-2"><Button size="sm" variant="outline" onClick={onRecheck}>Check again</Button><span className="text-ink-2">after restarting the app.</span></div>,
        ]} />
        <div className="mt-4 text-[12px] text-ink-3">Meanwhile: drag any memo out of the Voice Memos window onto the Recordings list.</div>
      </div>
    );
  }
  const fresh = full?.memos.filter((m) => !m.imported) ?? [];
  return (
    <div>
      <div className="flex flex-wrap items-center gap-2">
        <Pill tone="good">connected</Pill>
        <span>{fresh.length ? <><b>{fresh.length}</b> new memo{fresh.length === 1 ? "" : "s"}</> : "Everything is in the library."}</span>
        {fresh.length > 0 && <Button size="sm" className="ml-auto" disabled={busy} onClick={async () => { setBusy(true); const r = await api<{ imported: number[] }>("/api/sources/voicememos/sync", { method: "POST" }); toast(`Imported ${r.imported.length}`); mutate(); onChange(); setBusy(false); }}>Import all new</Button>}
      </div>
      {fresh.length > 0 && <div className="mt-2 max-h-[220px] divide-y divide-hairline overflow-y-auto rounded-md border border-hairline">{fresh.slice(0, 60).map((m) => <div key={m.uid} className="flex items-center gap-3 px-3 py-1.5"><div className="min-w-0 flex-1 truncate">{m.title}</div><span className="text-[12px] text-ink-3">{m.recorded_at ? `${fmtDate(m.recorded_at)}, ${fmtClock(m.recorded_at)}` : ""}</span><span className="tc text-[12px] text-ink-3">{fmtDur(m.duration_sec)}</span></div>)}</div>}
      <label className="mt-4 flex items-center gap-2 text-[13px]"><Switch checked={auto} onCheckedChange={onAuto} />Import new memos automatically</label>
      <div className="mt-3 flex items-center gap-2 text-[12px] text-ink-3"><Watch className="size-3.5" />Apple Watch and iPhone memos arrive as soon as iCloud syncs them into Voice Memos on this Mac.</div>
    </div>
  );
}

const CONNECTORS = {
  omi: { key: "omi_api_key" as const, auto: "omi_auto" as const, placeholder: "omi_dev_…", steps: [<>In the Omi app open <b>Developer → API keys</b> and create a key with read access to conversations.</>, <>Paste it below and save. Conversations arrive with transcript, overview and action items.</>] },
  granola: { key: "granola_api_key" as const, auto: "granola_auto" as const, placeholder: "grn_…", steps: [<>In the Granola desktop app, create an API key (Business plan). It starts with <span className="tc">grn_</span>.</>, <>Paste it below and save. Notes come in with their transcript, and Granola's summary lands in the Summary tab.</>] },
  notion: { key: "notion_token" as const, auto: "notion_auto" as const, placeholder: "ntn_…", steps: [<>Create an internal integration at <span className="tc">notion.so/profile/integrations</span> and copy its token.</>, <>Share your meetings database with the integration (Share → invite the integration).</>, <>Paste the token below. Optionally add the database ID to scan only that database.</>] },
};

function ConnectorPanel({ name, src, s, save }: { name: "omi" | "granola" | "notion"; src: Sources; s: Settings; save: (p: Partial<Settings>, m?: string) => Promise<void> }) {
  const cfg = CONNECTORS[name];
  const c = src.connectors[name];
  const [key, setKey] = useState(s[cfg.key] ?? "");
  const [db, setDb] = useState(s.notion_database_id ?? "");
  const [busy, setBusy] = useState(false);
  useEffect(() => setKey(s[cfg.key] ?? ""), [s, cfg.key]);
  const sync = async () => { setBusy(true); try { const r = await api<{ imported: number[] }>(`/api/sources/${name}/sync`, { method: "POST" }); toast(r.imported.length ? `Imported ${r.imported.length}` : "Nothing new"); } catch (e) { toast((e as Error).message); } setBusy(false); };
  return (
    <div>
      <div className="flex items-center gap-2">{!c.configured ? <Pill tone="idle">not connected</Pill> : c.last_error ? <Pill tone="warn">error</Pill> : <Pill tone="good">connected</Pill>}<span className="text-[12px] text-ink-3">{src.counts[name] ?? 0} imported{c.last_sync ? ` · last sync ${fmtClock(c.last_sync)}` : ""}</span></div>
      <Steps items={cfg.steps} />
      <div className="mt-4 flex gap-2">
        <Input type="password" value={key} onChange={(e) => setKey(e.target.value)} placeholder={cfg.placeholder} className="h-9 flex-1 bg-surface" />
        <Button disabled={!key || key === "•••"} onClick={async () => { await save({ [cfg.key]: key } as Partial<Settings>, "Key saved"); setKey("•••"); }}>{c.configured ? "Replace key" : "Connect"}</Button>
      </div>
      {name === "notion" && <Input value={db} onChange={(e) => setDb(e.target.value)} onBlur={() => db !== s.notion_database_id && save({ notion_database_id: db })} placeholder="Database ID (optional)" className="tc mt-2 h-9 bg-surface text-[12.5px]" />}
      {c.configured && (
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-2 text-[13px]"><Switch checked={!!s[cfg.auto]} onCheckedChange={(v) => save({ [cfg.auto]: v } as Partial<Settings>)} />Sync every {Math.round(s.sync_interval_sec / 60)} min</label>
          <Button size="sm" variant="outline" className="ml-auto" disabled={busy} onClick={sync}>{busy ? "Syncing…" : "Sync now"}</Button>
          <Button size="sm" variant="ghost" className="text-clip" onClick={() => save({ [cfg.key]: "" } as Partial<Settings>, "Disconnected")}>Disconnect</Button>
        </div>
      )}
      {c.last_error && <div className="mt-2 text-[12px] text-clip">Last error: {c.last_error}</div>}
    </div>
  );
}

function FolderPanel({ kind, root, s, save }: { kind: string; root?: { key: string; label: string; path: string }; s: Settings; save: (p: Partial<Settings>, m?: string) => Promise<void> }) {
  const [path, setPath] = useState(root?.path ?? "");
  const { data: listing, error } = useSWR<{ path: string; parent: string | null; dirs: { name: string; path: string }[]; audio_files: number }>(path ? `/api/fs/list?path=${encodeURIComponent(path)}` : null, fetcher, { keepPreviousData: true });
  const watched = s.watched_folders;
  const isWatched = watched.includes(path);
  if (kind !== "folder" && !root) return <p className="text-ink-2">{kind === "icloud" ? "iCloud Drive" : kind === "dropbox" ? "Dropbox" : "Google Drive"} is not set up on this Mac, so there is no folder to watch. Once it is, it appears here automatically.</p>;
  return (
    <div>
      <p className="text-ink-2">Pick the folder your recordings land in. New audio in it is copied into the library on every poll; the folder itself is never touched.</p>
      <div className="mt-3 flex gap-2">
        <Input value={path} onChange={(e) => setPath(e.target.value)} placeholder="~/Recordings" className="tc h-9 flex-1 bg-surface text-[12.5px]" />
        <Button variant="outline" onClick={() => openSys(`reveal:${path}`)} disabled={!path}>Show in Finder</Button>
      </div>
      {listing && (
        <div className="mt-2 max-h-[220px] overflow-y-auto rounded-md border border-hairline">
          {listing.parent && <button type="button" className="block w-full px-3 py-1.5 text-left text-[12.5px] text-ink-3 hover:bg-surface-2" onClick={() => setPath(listing.parent!)}>‹ up</button>}
          {listing.dirs.map((d) => <button key={d.path} type="button" className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-[13px] hover:bg-surface-2" onClick={() => setPath(d.path)}><FolderOpen className="size-3.5 text-ink-3" />{d.name}{watched.includes(d.path) && <Pill tone="good">watched</Pill>}</button>)}
          {!listing.dirs.length && <div className="px-3 py-2 text-[12.5px] text-ink-3">No subfolders.</div>}
        </div>
      )}
      {error && <div className="mt-2 text-[12px] text-clip">{(error as Error).message}</div>}
      <div className="mt-3 flex flex-wrap items-center gap-2">
        {listing && <span className="text-[12px] text-ink-3">{listing.audio_files} audio file{listing.audio_files === 1 ? "" : "s"} here</span>}
        <Button className="ml-auto" disabled={!path} variant={isWatched ? "outline" : "default"} onClick={() => save({ watched_folders: isWatched ? watched.filter((f) => f !== path) : [...new Set([...watched, path])] }, isWatched ? "Stopped watching" : "Watching this folder")}>{isWatched ? "Stop watching" : "Watch this folder"}</Button>
      </div>
      {watched.length > 0 && <div className="mt-4"><div className="eyebrow mb-1.5">Watched folders</div><div className="divide-y divide-hairline rounded-md border border-hairline">{watched.map((f) => <div key={f} className="flex items-center gap-2 px-3 py-1.5"><span className="tc min-w-0 flex-1 truncate text-[12px]">{f}</span><Button size="sm" variant="ghost" className="text-clip" onClick={() => save({ watched_folders: watched.filter((x) => x !== f) }, "Stopped watching")}>Remove</Button></div>)}</div></div>}
    </div>
  );
}

function FilesPanel() {
  const ref = useRef<HTMLInputElement>(null);
  return (
    <div>
      <p className="text-ink-2">Any WAV, M4A, MP3, AAC or FLAC. Exports from Otter, Plaud, Pocket or any other recorder work this way. Files are copied, never moved.</p>
      <input ref={ref} type="file" accept="audio/*,.wav,.m4a,.mp3,.aac,.flac,.aif,.aiff" multiple className="hidden" onChange={async (e) => { const files = Array.from(e.target.files ?? []); e.target.value = ""; if (!files.length) return; toast(`Importing ${files.length}…`); try { const r = await uploadFiles(files); toast(r.imported.length ? `Imported ${r.imported.length}, queued` : "Nothing new: already in the library"); } catch (err) { toast(`Import failed: ${(err as Error).message}`); } }} />
      <div className="mt-4 flex flex-wrap gap-2">
        <Button onClick={() => ref.current?.click()}><Download className="size-4" />Choose files…</Button>
        <Button variant="outline" onClick={async () => { const p = prompt("Folder or file path to import once:"); if (!p) return; const r = await api<{ imported: number[] }>("/api/import/path", { method: "POST", json: { path: p } }); toast(`Imported ${r.imported.length} file(s)`); }}>Import a folder once…</Button>
      </div>
      <div className="mt-4 flex items-center gap-2 text-[12px] text-ink-3"><Mic className="size-3.5" />Tip: you can also drop files anywhere on the Recordings list.</div>
    </div>
  );
}
