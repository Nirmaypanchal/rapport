"use client";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { Sparkles } from "lucide-react";
import { api, type AskAnswer, type AskSource } from "@/lib/api";
import { fmtDate, fmtTime } from "@/lib/format";
import { speakerStyle } from "@/lib/speakers";
import { SpeakerDot } from "@/components/avatar";
import { Markdown } from "@/components/markdown";
import { Snippet } from "@/components/snippet";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const EXAMPLES = ["What did we decide about pricing?", "What am I supposed to do before Friday?", "What has Maya said about the launch?"];

function Note({ children }: { children: React.ReactNode }) {
  return <div className="rounded-lg border border-dashed border-hairline px-5 py-4 text-[13.5px] text-ink-2">{children}</div>;
}

/** `active` is the Ask tab being the visible one: the panel stays mounted so an answer survives a trip to Search. */
export function AskPanel({ active }: { active: boolean }) {
  const [q, setQ] = useState("");
  const [asked, setAsked] = useState<AskAnswer | null>(null);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState<string | null>(null);
  const field = useRef<HTMLInputElement>(null);
  useEffect(() => { if (active) field.current?.focus(); }, [active]);

  const ask = async (question: string) => {
    const text = question.trim();
    if (!text || busy) return;
    setBusy(true);
    setFailed(null);
    try { setAsked(await api<AskAnswer>("/api/ask", { method: "POST", json: { q: text } })); }
    catch (e) { setFailed((e as Error).message); setAsked(null); }
    finally { setBusy(false); }
  };

  const jump = (n: number) => document.getElementById(`ask-source-${n}`)?.scrollIntoView({ behavior: "smooth", block: "center" });

  return (
    <div>
      <form onSubmit={(e) => { e.preventDefault(); ask(q); }} className="mt-4 flex items-center gap-2">
        <Input ref={field} value={q} onChange={(e) => setQ(e.target.value)} placeholder="Ask your recordings a question…" className="h-12 flex-1 bg-surface text-[16px]" aria-label="Ask your library" />
        <Button type="submit" size="lg" className="h-12" disabled={busy || !q.trim()}><Sparkles className="size-4" />{busy ? "Reading…" : "Ask"}</Button>
      </form>

      {!asked && !busy && !failed && (
        <div className="mt-4">
          <div className="eyebrow mb-2">For example</div>
          <div className="flex flex-wrap gap-2">
            {EXAMPLES.map((x) => (
              <button key={x} type="button" onClick={() => { setQ(x); ask(x); }} className="rounded-full border border-hairline bg-surface px-3 py-1.5 text-[13px] text-ink-2 transition-colors hover:border-signal hover:text-ink">{x}</button>
            ))}
          </div>
          <p className="mt-4 text-[12.5px] text-ink-3">Answers are written on this Mac by the same local model that writes your summaries, from your transcripts only. Every claim is linked to the moment it came from.</p>
        </div>
      )}

      {busy && (
        <div className="mt-4 flex items-center gap-3 rounded-lg border border-hairline bg-surface px-5 py-6 text-[13.5px] text-ink-2">
          <span className="blink size-2 rounded-full bg-signal" />Reading your transcripts…
        </div>
      )}

      {failed && !busy && <div className="mt-4 rounded-lg border border-hairline bg-surface px-5 py-4 text-[13.5px]"><b className="text-clip">That question could not be answered.</b> <span className="tc text-ink-2">{failed}</span></div>}

      {asked && !busy && (
        <div className="mt-4 grid gap-3">
          {asked.answer && (
            <div className="rounded-lg border border-hairline bg-surface px-5 py-4">
              <Markdown text={asked.answer} cite={(n) => (
                <button type="button" onClick={() => jump(n)} className="mx-0.5 rounded-[4px] bg-signal-soft px-1 align-[1px] text-[11px] font-semibold text-signal transition-opacity hover:opacity-70" aria-label={`Excerpt ${n}`}>{n}</button>
              )} />
            </div>
          )}

          {asked.reason === "no_matches" && <Note>Nothing in your transcripts matches that. Try the words you would actually have said out loud.</Note>}
          {asked.reason === "no_model" && <Note>No local model is available, so here are the moments themselves. Start Ollama, or pick the MLX model in <Link href="/settings/" className="underline">Settings</Link>, and the answer will be written for you.</Note>}
          {asked.reason === "model_error" && <Note><b className="text-clip">The model could not answer.</b> <span className="tc">{asked.error}</span> The matching moments are below.</Note>}
          {asked.reason === "empty_answer" && <Note>The model returned nothing. Here are the moments it was given.</Note>}

          {!!asked.sources.length && <div className="eyebrow mt-2">{asked.answer ? "Sources" : "Moments that match"}</div>}
          {asked.sources.map((s) => <Source key={s.n} s={s} dim={!!asked.answer && !s.cited} />)}

          {asked.model && <p className="mt-1 text-[12px] text-ink-3">Written by <span className="tc">{asked.model.model}</span>, running on this Mac.</p>}
        </div>
      )}
    </div>
  );
}

/** One excerpt, numbered the way the answer cites it. Clicking opens the recording a second before the turn. */
function Source({ s, dim }: { s: AskSource; dim: boolean }) {
  return (
    <Link
      id={`ask-source-${s.n}`}
      href={`/?id=${s.recording_id}&t=${Math.max(0, s.start - 1).toFixed(1)}`}
      style={speakerStyle(s.person_color)}
      className={`speaker rounded-lg border border-hairline bg-surface px-4 py-3 transition-colors hover:border-[var(--c)] ${dim ? "opacity-65" : ""}`}
    >
      <div className="flex flex-wrap items-center gap-x-3 text-[12px] text-ink-2">
        <span className={`tc grid size-5 shrink-0 place-items-center rounded-[5px] text-[11px] font-semibold ${dim ? "bg-surface-2 text-ink-3" : "bg-signal-soft text-signal"}`}>{s.n}</span>
        <span className="inline-flex items-center gap-1.5 font-semibold text-[var(--c)]"><SpeakerDot color={s.person_color} />{s.speaker}</span>
        <span>{s.title}{s.recorded_at ? `, ${fmtDate(s.recorded_at)}` : ""}</span>
        <span className="tc">{fmtTime(s.start)}</span>
      </div>
      <div className="mt-1 text-[15px]"><Snippet s={s.snippet} /></div>
    </Link>
  );
}
