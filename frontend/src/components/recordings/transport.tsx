"use client";
import { useEffect, useRef, useState } from "react";
import useSWR from "swr";
import { Pause, Play, RotateCcw, RotateCw } from "lucide-react";
import { fetcher, type Recording } from "@/lib/api";
import { fmtTime } from "@/lib/format";
import { speakerStyle } from "@/lib/speakers";
import { skipsFromRegions, type Player } from "@/lib/use-player";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { cn } from "@/lib/utils";

const LS_SKIP = "skipSilence";
const LS_FOLLOW = "followPlayback";

function readLS(key: string, fallback: boolean) {
  try { const v = localStorage.getItem(key); return v == null ? fallback : v === "1"; } catch { return fallback; }
}

export function Transport({ r, player, minGap, pad, follow, onFollow }: { r: Recording; player: Player; minGap: number; pad: number; follow: boolean; onFollow: (v: boolean) => void }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const wrap = useRef<HTMLDivElement>(null);
  const timeEl = useRef<HTMLSpanElement>(null);
  const dur = r.duration_sec || 1;
  const [skip, setSkip] = useState(false);
  const [saved, setSaved] = useState<number | null>(null);
  const skipsRef = useRef<[number, number][]>([]);

  useEffect(() => { setSkip(readLS(LS_SKIP, false)); onFollow(readLS(LS_FOLLOW, true)); }, [onFollow]);

  const { data: speech } = useSWR<{ duration: number; regions: [number, number][] }>(skip ? `/api/recordings/${r.id}/speech` : null, fetcher);
  useEffect(() => {
    if (!speech) { skipsRef.current = []; player.setSkips([], false); setSaved(null); return; }
    const skips = skipsFromRegions(speech.regions, dur, minGap, pad);
    skipsRef.current = skips;
    player.setSkips(skips, skip);
    setSaved(skips.reduce((a, [f, t]) => a + Math.max(0, t - f), 0));
    draw(player.time);
  }, [speech, skip, minGap, pad, dur, player]);

  // Waveform. Bars in Wave grey, Ink behind the playhead, Signal for the head, dimmed where silence will be skipped.
  const draw = (t: number) => {
    const c = canvas.current, w = wrap.current;
    if (!c || !w) return;
    const dpr = window.devicePixelRatio || 1;
    const W = w.clientWidth, H = 56;
    if (c.width !== W * dpr || c.height !== H * dpr) { c.width = W * dpr; c.height = H * dpr; }
    const ctx = c.getContext("2d")!;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, W, H);
    const cs = getComputedStyle(document.documentElement);
    const peaks = r.peaks ?? [];
    const n = Math.min(peaks.length, Math.floor(W / 3));
    const pos = (t / dur) * W;
    const wave = cs.getPropertyValue("--wave"), played = cs.getPropertyValue("--wave-played");
    for (let i = 0; i < n; i++) {
      const p = peaks[Math.floor((i / n) * peaks.length)] ?? 0;
      const x = (i / n) * W;
      const ph = Math.max(2, p * (H - 6));
      ctx.fillStyle = x < pos ? played : wave;
      ctx.fillRect(x, (H - ph) / 2, Math.max(1.5, W / n - 1), ph);
    }
    if (skip && skipsRef.current.length) {
      ctx.fillStyle = cs.getPropertyValue("--ground"); ctx.globalAlpha = 0.72;
      for (const [f, to] of skipsRef.current) ctx.fillRect((f / dur) * W, 0, Math.max(1, ((to - f) / dur) * W), H);
      ctx.globalAlpha = 1;
    }
    ctx.fillStyle = cs.getPropertyValue("--signal");
    ctx.fillRect(pos - 1, 0, 2, H);
    ctx.beginPath(); ctx.arc(pos, 4, 4, 0, Math.PI * 2); ctx.fill();
  };

  useEffect(() => {
    const unsub = player.subscribe((t) => {
      draw(t);
      if (timeEl.current) timeEl.current.textContent = fmtTime(t);
    });
    draw(player.time);
    const ro = new ResizeObserver(() => draw(player.time));
    if (wrap.current) ro.observe(wrap.current);
    return () => { unsub(); ro.disconnect(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [player, r.peaks, skip]);

  const seekAt = (e: React.MouseEvent) => {
    const rect = wrap.current!.getBoundingClientRect();
    player.seek(((e.clientX - rect.left) / rect.width) * dur);
  };

  const segs = r.segments ?? [];
  return (
    <div className="glass border-t border-hairline px-3 pb-[max(10px,env(safe-area-inset-bottom))] pt-2.5 sm:px-4">
      <div ref={wrap} className="relative h-14 cursor-pointer" onClick={seekAt} role="slider" aria-label="Seek" aria-valuemin={0} aria-valuemax={dur} tabIndex={0}>
        <canvas ref={canvas} className="block h-14 w-full" />
      </div>
      {/* Speaker lane: who spoke when, as a thin map under the waveform */}
      <div className="relative mt-1 h-1.5 overflow-hidden rounded-full bg-surface-2">
        {segs.map((s) => {
          const sp = r.speakers.find((x) => x.label === s.speaker_label);
          return <span key={s.id} className="speaker absolute top-0 h-full" style={{ ...speakerStyle(sp?.person_color), left: `${(s.start / dur) * 100}%`, width: `${Math.max(0.2, ((s.end - s.start) / dur) * 100)}%`, background: "var(--c)", opacity: 0.85 }} />;
        })}
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-2">
        <button type="button" onClick={() => player.nudge(-5)} className="hidden size-8 place-items-center rounded-full text-ink-2 hover:bg-surface-2 sm:grid" title="Back 5 s"><RotateCcw className="size-4" /></button>
        <button type="button" onClick={player.toggle} className="grid size-9 place-items-center rounded-full bg-ink text-ground transition-opacity hover:opacity-85" title={player.playing ? "Pause (space)" : "Play (space)"}>
          {player.playing ? <Pause className="size-4 fill-current" /> : <Play className="ml-0.5 size-4 fill-current" />}
        </button>
        <button type="button" onClick={() => player.nudge(5)} className="hidden size-8 place-items-center rounded-full text-ink-2 hover:bg-surface-2 sm:grid" title="Forward 5 s"><RotateCw className="size-4" /></button>
        <span className="tc text-[12.5px] text-ink-2"><span ref={timeEl} className="font-medium text-ink">0:00</span> / {fmtTime(dur)}</span>
        <Select value={String(player.rate)} onValueChange={(v) => player.setRate(Number(v))}>
          <SelectTrigger size="sm" className="tc h-7 w-[72px] text-[12px]"><SelectValue>{(v: string) => `${v}×`}</SelectValue></SelectTrigger>
          <SelectContent>{[0.75, 1, 1.25, 1.5, 2].map((v) => <SelectItem key={v} value={String(v)}>{v}×</SelectItem>)}</SelectContent>
        </Select>
        <div className="ml-auto flex items-center gap-4">
          <label className="flex items-center gap-2 text-[12.5px] text-ink-2">
            <Switch checked={skip} onCheckedChange={(v) => { setSkip(v); try { localStorage.setItem(LS_SKIP, v ? "1" : "0"); } catch {} }} />
            <span className="whitespace-nowrap">Skip silences</span>
            {skip && saved != null && <span className={cn("tc text-[11px] text-ink-3", !saved && "hidden")}>−{fmtTime(saved)} · {Math.round((saved / dur) * 100)}%</span>}
          </label>
          <label className="hidden items-center gap-2 text-[12.5px] text-ink-2 sm:flex">
            <Switch checked={follow} onCheckedChange={(v) => { onFollow(v); try { localStorage.setItem(LS_FOLLOW, v ? "1" : "0"); } catch {} }} />
            Follow
          </label>
        </div>
      </div>
    </div>
  );
}
