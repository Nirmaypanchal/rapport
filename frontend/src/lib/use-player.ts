"use client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

export type Skip = [number, number];
type Listener = (t: number, playing: boolean) => void;

/**
 * Wraps one <audio> element. Time updates go to subscribers on requestAnimationFrame
 * (and on `timeupdate`, which also fires in background tabs) so the transcript and the
 * waveform can update imperatively without re-rendering React per frame.
 */
export function usePlayer(src: string | null, duration: number) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const listeners = useRef(new Set<Listener>());
  const skipsRef = useRef<Skip[]>([]);
  const skipOnRef = useRef(false);
  const raf = useRef<number | null>(null);
  const [playing, setPlaying] = useState(false);
  const [rate, setRateState] = useState(1);
  const [ready, setReady] = useState(false);

  const emit = useCallback(() => {
    const a = audioRef.current;
    if (!a) return;
    for (const l of listeners.current) l(a.currentTime, !a.paused);
  }, []);

  const applySkip = useCallback(() => {
    const a = audioRef.current;
    if (!a || a.paused || !skipOnRef.current || !skipsRef.current.length) return;
    const t = a.currentTime;
    for (const [from, to] of skipsRef.current) {
      if (t >= from && t < to) {
        if (to >= duration - 0.05) a.pause();
        else a.currentTime = to;
        return;
      }
      if (from > t) break;
    }
  }, [duration]);

  useEffect(() => {
    if (!src) return;
    const a = new Audio();
    a.preload = "metadata";
    a.src = src;
    audioRef.current = a;
    const loop = () => {
      applySkip();
      emit();
      if (!a.paused) raf.current = requestAnimationFrame(loop);
    };
    const onPlay = () => { setPlaying(true); loop(); };
    const onPause = () => { setPlaying(false); if (raf.current) cancelAnimationFrame(raf.current); emit(); };
    const onMeta = () => setReady(true);
    a.addEventListener("play", onPlay);
    a.addEventListener("pause", onPause);
    a.addEventListener("ended", onPause);
    a.addEventListener("seeked", emit);
    a.addEventListener("timeupdate", applySkip);
    a.addEventListener("loadedmetadata", onMeta);
    return () => {
      a.pause();
      a.removeEventListener("play", onPlay);
      a.removeEventListener("pause", onPause);
      a.removeEventListener("ended", onPause);
      a.removeEventListener("seeked", emit);
      a.removeEventListener("timeupdate", applySkip);
      a.removeEventListener("loadedmetadata", onMeta);
      if (raf.current) cancelAnimationFrame(raf.current);
      a.src = "";
      audioRef.current = null;
      setPlaying(false);
      setReady(false);
    };
  }, [src, applySkip, emit]);

  const subscribe = useCallback((l: Listener) => {
    listeners.current.add(l);
    return () => { listeners.current.delete(l); };
  }, []);

  const api = useMemo(
    () => ({
      subscribe,
      play: () => audioRef.current?.play().catch(() => {}),
      pause: () => audioRef.current?.pause(),
      toggle: () => { const a = audioRef.current; if (!a) return; if (a.paused) a.play().catch(() => {}); else a.pause(); },
      seek: (t: number, andPlay = false) => { const a = audioRef.current; if (!a) return; a.currentTime = Math.max(0, Math.min(duration, t)); if (andPlay) a.play().catch(() => {}); },
      nudge: (dt: number) => { const a = audioRef.current; if (a) a.currentTime = Math.max(0, Math.min(duration, a.currentTime + dt)); },
      setRate: (r: number) => { const a = audioRef.current; if (a) a.playbackRate = r; setRateState(r); },
      setSkips: (skips: Skip[], on: boolean) => { skipsRef.current = skips; skipOnRef.current = on; },
      get time() { return audioRef.current?.currentTime ?? 0; },
    }),
    [subscribe, duration],
  );

  return { ...api, playing, rate, ready };
}

export type Player = ReturnType<typeof usePlayer>;

/** Turn VAD speech regions into [from, to] jumps for pauses at least `minGap` long. */
export function skipsFromRegions(regions: [number, number][], duration: number, minGap: number, pad: number): Skip[] {
  const merged: [number, number][] = [];
  for (const [s, e] of regions) {
    const last = merged[merged.length - 1];
    if (last && s - last[1] < minGap) last[1] = Math.max(last[1], e);
    else merged.push([s, e]);
  }
  const skips: Skip[] = [];
  let prevEnd = 0;
  for (const [s, e] of merged) {
    if (s - prevEnd >= minGap) skips.push([prevEnd + (prevEnd ? pad : 0), s - pad]);
    prevEnd = e;
  }
  if (duration - prevEnd >= minGap) skips.push([prevEnd + pad, duration]);
  return skips.filter(([a, b]) => b > a);
}
