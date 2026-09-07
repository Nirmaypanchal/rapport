"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import useSWR from "swr";
import { toast } from "sonner";
import { api, fetcher, type LogLine, type Settings } from "@/lib/api";

type Providers = { ollama: string[]; mlx_default: string; active: { provider: string; model: string } | null };
import { useStatus } from "@/lib/use-status";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { cn } from "@/lib/utils";

const WHISPER = [
  ["mlx-community/whisper-large-v3-turbo", "large-v3-turbo (recommended)"],
  ["mlx-community/whisper-large-v3-mlx", "large-v3 (slower, slightly better)"],
  ["mlx-community/whisper-medium-mlx", "medium"],
  ["mlx-community/whisper-small-mlx", "small (fast)"],
  ["mlx-community/whisper-base-mlx", "base (fastest)"],
];

function Row({ label, help, children }: { label: string; help?: string; children: React.ReactNode }) {
  return (
    <div className="grid gap-1.5 border-t border-hairline py-3.5 first:border-t-0 sm:grid-cols-[220px_1fr] sm:gap-4">
      <div className="text-[13px] text-ink-2">{label}</div>
      <div className="grid gap-1">{children}{help && <div className="text-[12px] text-ink-3">{help}</div>}</div>
    </div>
  );
}

export function SettingsView() {
  const { data: status, mutate } = useStatus();
  const { data: log, mutate: mutateLog } = useSWR<LogLine[]>("/api/log?limit=150", fetcher, { refreshInterval: 5000 });
  const { data: prov } = useSWR<Providers>("/api/summary/providers", fetcher, { refreshInterval: 30000 });
  const [s, setS] = useState<Settings | null>(null);
  useEffect(() => { if (status && !s) setS(status.settings); }, [status, s]);
  if (!status || !s) return <div className="p-10 text-center text-[13px] text-ink-3">Loading…</div>;
  const set = <K extends keyof Settings>(k: K, v: Settings[K]) => setS({ ...s, [k]: v });
  const vols = status.importer.volumes;
  const m = status.worker.models;
  const num = (k: keyof Settings, step = 0.05) => <Input type="number" step={step} value={String(s[k] ?? "")} onChange={(e) => set(k, Number(e.target.value) as never)} className="h-8 max-w-[160px] bg-surface" />;

  const save = async () => {
    const patch: Record<string, unknown> = { ...s };
    if (patch.hf_token === "•••") delete patch.hf_token;
    if (patch.language === "") patch.language = null;
    await api("/api/settings", { method: "PUT", json: { patch } });
    toast("Settings saved"); mutate();
  };

  return (
    <div className="h-full overflow-y-auto px-4 pb-10 pt-5 sm:px-8 sm:pt-7">
      <div className="mx-auto max-w-[900px]">
        <h1 className="font-display text-[26px] font-semibold tracking-[-0.02em] sm:text-[30px]">Activity &amp; Settings</h1>

        <div className="eyebrow mt-6 mb-2">Mic</div>
        <div className="rounded-lg border border-hairline bg-surface px-4 py-3.5 text-[13.5px]">
          {vols.length ? vols.map((v) => <div key={v.mount} className="flex items-center gap-2"><span className="size-1.5 rounded-full bg-good" />{v.media || v.name} at <span className="tc text-ink-2">{v.mount}</span> · {v.files} file{v.files === 1 ? "" : "s"} waiting</div>) : <div className="text-ink-2">No DJI transmitter detected. Plug a transmitter or the charging case into the Mac; it appears as a drive and import starts on its own.</div>}
          <div className="mt-3 flex flex-wrap gap-1.5">
            <Button size="sm" variant="outline" onClick={async () => { await api("/api/import/scan", { method: "POST" }); toast("Scanning…"); }}>Scan now</Button>
          </div>
        </div>

        <div className="mt-6 rounded-lg border border-dashed border-hairline px-4 py-3 text-[13px] text-ink-2">Devices, Voice Memos, watched folders and integrations moved to <Link href="/sources/" className="underline">Sources</Link>.</div>

        <div className="eyebrow mt-6 mb-2">Speaker engine</div>
        <div className={cn("rounded-lg border-l-2 bg-surface px-4 py-3 text-[13px]", m.pyannote_loaded ? "border-good" : "border-warn")}>
          {m.pyannote_loaded ? "Using pyannote's diarization pipeline (best quality)." : m.pyannote_error ? (
            <div>
              <b>Using the built-in speaker engine.</b> pyannote's better diarizer is gated on Hugging Face. To unlock it, sign in at huggingface.co, accept the terms on <a className="underline" href="https://huggingface.co/pyannote/speaker-diarization-community-1" target="_blank" rel="noreferrer">speaker-diarization-community-1</a> and <a className="underline" href="https://huggingface.co/pyannote/segmentation-3.0" target="_blank" rel="noreferrer">segmentation-3.0</a>, then paste a read token below.
              <div className="tc mt-1 text-[11.5px] text-ink-3">Last error: {m.pyannote_error}</div>
            </div>
          ) : "The speaker engine loads with the first recording."}
        </div>

        <div className="eyebrow mt-6 mb-2">Settings</div>
        <div className="rounded-lg border border-hairline bg-surface px-4 py-1">
          <Row label="Auto-import from mic"><Switch checked={s.auto_import} onCheckedChange={(v) => set("auto_import", v)} /></Row>
          <Row label="Clear the mic after import" help="Off by default: recordings are copied and the transmitter is left alone. When on, a file is deleted only after its copy is verified byte-for-byte."><Switch checked={s.delete_from_device_after_import} onCheckedChange={(v) => set("delete_from_device_after_import", v)} /></Row>
          <Row label="Whisper model" help="Downloaded once from Hugging Face; everything runs on this Mac.">
            <Select value={s.whisper_model} onValueChange={(v) => v && set("whisper_model", v)}><SelectTrigger className="max-w-[360px] bg-surface"><SelectValue /></SelectTrigger><SelectContent>{WHISPER.map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}</SelectContent></Select>
          </Row>
          <Row label="Language" help="Leave empty to auto-detect, or a code like en, hi, es."><Input value={s.language ?? ""} onChange={(e) => set("language", e.target.value)} className="h-8 max-w-[160px] bg-surface" /></Row>
          <Row label="Speaker engine">
            <Select value={s.diarizer} onValueChange={(v) => v && set("diarizer", v)}><SelectTrigger className="max-w-[360px] bg-surface"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="auto">Auto (pyannote if available, else built-in)</SelectItem><SelectItem value="pyannote">pyannote only</SelectItem><SelectItem value="builtin">Built-in only</SelectItem></SelectContent></Select>
          </Row>
          <Row label="Hugging Face token" help={status.hf_token_present && !s.hf_token ? "Using the token from ~/.cache/huggingface/token." : "Optional. Needed only for pyannote's gated models."}><Input type="password" value={s.hf_token ?? ""} onChange={(e) => set("hf_token", e.target.value)} className="h-8 max-w-[360px] bg-surface" /></Row>
          <Row label="Voice match threshold" help="Similarity (0–1) needed to say a voice is a known person. Lower finds more matches; higher is stricter. 0.5–0.65 is sensible.">{num("person_match_threshold")}</Row>
          <Row label="Built-in engine: split sensitivity" help="Distance (0–1) at which two voices in one file count as different people. Lower finds more speakers.">{num("cluster_distance_threshold")}</Row>
          <Row label="Minimum speaker duration (s)" help="Speakers with less speech are merged into the nearest voice.">{num("min_speaker_seconds", 0.5)}</Row>
          <Row label="Summaries" help={prov?.active ? `Right now: ${prov.active.model} via ${prov.active.provider === "ollama" ? "Ollama" : "MLX"}. Everything runs on this Mac.` : "No local model available. Start Ollama, or choose MLX to download a small model."}>
            <Select value={s.summary_provider} onValueChange={(v) => v && set("summary_provider", v as Settings["summary_provider"])}><SelectTrigger className="max-w-[360px] bg-surface"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="auto">Auto (Ollama if running, else MLX)</SelectItem><SelectItem value="ollama">Ollama only</SelectItem><SelectItem value="mlx">MLX only</SelectItem><SelectItem value="off">Off</SelectItem></SelectContent></Select>
          </Row>
          <Row label="Summary model" help={`Leave empty for the default: the first Ollama model${prov?.ollama.length ? ` (${prov.ollama[0]})` : ""}, or ${prov?.mlx_default ?? "the MLX default"}.`}>
            {prov?.ollama.length ? (
              <Select value={s.summary_model || "__default"} onValueChange={(v) => set("summary_model", v === "__default" ? "" : (v ?? ""))}><SelectTrigger className="max-w-[360px] bg-surface"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="__default">Default</SelectItem>{prov.ollama.map((m) => <SelectItem key={m} value={m}>{m} (Ollama)</SelectItem>)}<SelectItem value={prov.mlx_default}>{prov.mlx_default.split("/").pop()} (MLX)</SelectItem></SelectContent></Select>
            ) : (
              <Input value={s.summary_model ?? ""} onChange={(e) => set("summary_model", e.target.value)} placeholder="mlx-community/… or an Ollama model name" className="h-8 max-w-[360px] bg-surface" />
            )}
          </Row>
          <Row label="Summarize automatically" help="Write a summary as soon as a recording is processed."><Switch checked={!!s.auto_summarize} onCheckedChange={(v) => set("auto_summarize", v)} /></Row>
          <Row label="Skip silences: minimum pause (s)" help="Pauses shorter than this are kept.">{num("skip_silence_min_gap")}</Row>
          <Row label="Skip silences: padding (s)" help="Audio kept on each side of a skipped pause.">{num("skip_silence_pad")}</Row>
          <Row label="Mic poll interval (s)">{num("poll_interval_sec", 1)}</Row>
          <Row label="Open browser on launch"><Switch checked={s.open_browser} onCheckedChange={(v) => set("open_browser", v)} /></Row>
          <div className="border-t border-hairline py-3"><Button onClick={save}>Save settings</Button></div>
        </div>
        <div className="mt-3 grid gap-1 text-[12.5px] text-ink-2 sm:grid-cols-[220px_1fr]">
          <span className="text-ink-3">Library folder</span><span className="tc break-all">{status.library}</span>
          <span className="text-ink-3">Backup</span><span>Back up that one folder: it holds the original WAVs, transcripts, speakers and settings.</span>
        </div>

        <div className="eyebrow mt-6 mb-2">Activity</div>
        <div className="tc max-h-[360px] overflow-auto rounded-lg border border-hairline bg-surface px-4 py-2 text-[12px]">
          {log?.map((l) => <div key={l.id} className={cn("grid grid-cols-[150px_1fr] gap-3 border-b border-dashed border-hairline py-1 last:border-b-0", l.level === "warn" && "text-warn", l.level === "error" && "text-clip")}><span className="text-ink-3">{l.ts.replace("T", " ").slice(0, 19)}</span><span className="font-sans">{l.message}</span></div>)}
          {!log?.length && <div className="py-2 text-ink-3">Nothing yet.</div>}
        </div>
        <div className="mt-2"><Button size="sm" variant="ghost" onClick={() => mutateLog()}>Refresh</Button></div>
      </div>
    </div>
  );
}


