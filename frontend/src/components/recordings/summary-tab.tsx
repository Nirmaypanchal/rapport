"use client";
import Link from "next/link";
import useSWR from "swr";
import { toast } from "sonner";
import { Sparkles } from "lucide-react";
import { api, fetcher, type Recording } from "@/lib/api";
import { fmtClock, fmtDate } from "@/lib/format";
import { Button } from "@/components/ui/button";

type Providers = { ollama: string[]; mlx_default: string; active: { provider: string; model: string } | null };

/** Renders the small Markdown subset the summarizer is asked for: ## headings, bullets, paragraphs, **bold**. */
function Markdown({ text }: { text: string }) {
  const blocks: React.ReactNode[] = [];
  let list: string[] = [];
  const flush = () => { if (list.length) { blocks.push(<ul key={`l${blocks.length}`} className="my-2 list-disc space-y-1 pl-5">{list.map((l, i) => <li key={i}><Inline text={l} /></li>)}</ul>); list = []; } };
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim();
    if (!line) { flush(); continue; }
    if (/^#{1,3}\s/.test(line)) { flush(); blocks.push(<div key={`h${blocks.length}`} className="eyebrow mt-5 mb-1.5 first:mt-0">{line.replace(/^#+\s/, "")}</div>); continue; }
    if (/^[-*•]\s/.test(line)) { list.push(line.replace(/^[-*•]\s/, "")); continue; }
    if (/^\d+[.)]\s/.test(line)) { list.push(line.replace(/^\d+[.)]\s/, "")); continue; }
    flush(); blocks.push(<p key={`p${blocks.length}`} className="my-1.5">{<Inline text={line} />}</p>);
  }
  flush();
  return <div className="text-[15px] leading-[1.6]">{blocks}</div>;
}

function Inline({ text }: { text: string }) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return <>{parts.map((p, i) => (p.startsWith("**") && p.endsWith("**") ? <b key={i}>{p.slice(2, -2)}</b> : <span key={i}>{p}</span>))}</>;
}

export function SummaryTab({ r, onChange }: { r: Recording; onChange: () => void }) {
  const { data: providers } = useSWR<Providers>("/api/summary/providers", fetcher, { refreshInterval: 30000 });
  const busy = r.summary_status === "queued" || r.summary_status === "running";
  const generate = async () => {
    try { await api(`/api/recordings/${r.id}/summarize`, { method: "POST" }); toast("Summarizing…"); onChange(); }
    catch (e) { toast(`Cannot summarize: ${(e as Error).message}`); }
  };
  const active = providers?.active;

  return (
    <div className="mx-auto max-w-[720px]">
      {r.summary ? (
        <div className="rounded-lg border border-hairline bg-surface px-5 py-4">
          <Markdown text={r.summary} />
        </div>
      ) : busy ? (
        <div className="flex items-center gap-3 rounded-lg border border-hairline bg-surface px-5 py-6 text-[13.5px] text-ink-2">
          <span className="blink size-2 rounded-full bg-signal" />{r.summary_status === "running" ? `Summarizing with ${active?.model ?? "a local model"}…` : "Waiting for the model…"}
        </div>
      ) : r.summary_status === "error" ? (
        <div className="rounded-lg border border-hairline bg-surface px-5 py-5 text-[13.5px]"><b className="text-clip">Summary failed.</b> <span className="tc text-ink-2">{r.summary_error}</span></div>
      ) : (
        <div className="rounded-lg border border-dashed border-hairline px-5 py-8 text-center text-[13.5px] text-ink-2">
          {active ? <>No summary yet. It will be written by <span className="tc">{active.model}</span>, running on this Mac.</> : <>No local model is available. Start Ollama, or pick the MLX model in <Link href="/settings/" className="underline">Settings</Link> to have one downloaded.</>}
        </div>
      )}
      <div className="mt-3 flex flex-wrap items-center gap-2 text-[12px] text-ink-3">
        <Button size="sm" variant={r.summary ? "outline" : "default"} disabled={busy || !active} onClick={generate}><Sparkles className="size-3.5" />{busy ? "Working…" : r.summary ? "Regenerate" : "Summarize"}</Button>
        {r.summary_at && <span>Written {fmtDate(r.summary_at)}, {fmtClock(r.summary_at)} by <span className="tc">{r.summary_model}</span></span>}
        {busy && r.summary && <span className="flex items-center gap-1.5"><span className="blink size-1.5 rounded-full bg-signal" />Rewriting…</span>}
      </div>
    </div>
  );
}
