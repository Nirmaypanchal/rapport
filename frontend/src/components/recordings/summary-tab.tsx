"use client";
import Link from "next/link";
import { useState } from "react";
import useSWR from "swr";
import { toast } from "sonner";
import { Sparkles } from "lucide-react";
import { api, fetcher, type Recording, type SummaryTemplates } from "@/lib/api";
import { fmtClock, fmtDate } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Markdown } from "@/components/markdown";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

type Providers = { ollama: string[]; mlx_default: string; active: { provider: string; model: string } | null };

export function SummaryTab({ r, onChange }: { r: Recording; onChange: () => void }) {
  const { data: providers } = useSWR<Providers>("/api/summary/providers", fetcher, { refreshInterval: 30000 });
  const { data: tpl } = useSWR<SummaryTemplates>("/api/summary/templates", fetcher);
  const [picked, setPicked] = useState<string | null>(null);
  const busy = r.summary_status === "queued" || r.summary_status === "running";
  // What the button will use: the pick made here, else this recording's own template, else the default from Settings.
  const template = picked ?? r.summary_template ?? tpl?.default ?? "";
  const chosen = tpl?.templates.find((t) => t.id === template);
  // A summary written with a different template is the reason to press Regenerate again.
  const stale = !!r.summary && !!r.summary_template && template !== r.summary_template;
  const generate = async () => {
    // Before the template list has loaded there is nothing to choose; the backend then keeps the existing one.
    try { await api(`/api/recordings/${r.id}/summarize`, { method: "POST", json: template ? { template } : {} }); toast("Summarizing…"); onChange(); }
    catch (e) { toast(`Cannot summarize: ${(e as Error).message}`); }
  };
  const active = providers?.active;

  return (
    <div className="mx-auto max-w-[720px]">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <span className="eyebrow">Template</span>
        <Select value={template} onValueChange={(v) => v && setPicked(v)}>
          <SelectTrigger className="h-8 w-[220px] bg-surface text-[13px]" aria-label="Summary template"><SelectValue /></SelectTrigger>
          <SelectContent>{tpl?.templates.map((t) => <SelectItem key={t.id} value={t.id}>{t.name}</SelectItem>)}</SelectContent>
        </Select>
        <Button size="sm" variant={r.summary && !stale ? "outline" : "default"} disabled={busy || !active} onClick={generate}>
          <Sparkles className="size-3.5" />{busy ? "Working…" : r.summary ? "Regenerate" : "Summarize"}
        </Button>
        {chosen?.description && <span className="w-full text-[12px] text-ink-3 sm:w-auto">{chosen.description}</span>}
      </div>
      {stale && !busy && (
        <div className="mb-3 rounded-lg border border-dashed border-hairline px-4 py-2.5 text-[12.5px] text-ink-2">
          The summary below was written as <span className="tc">{r.summary_template}</span>. Regenerate to rewrite it as {chosen?.name ?? template}.
        </div>
      )}
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
        {r.summary_at && <span>Written {fmtDate(r.summary_at)}, {fmtClock(r.summary_at)} by <span className="tc">{r.summary_model}</span></span>}
        {busy && r.summary && <span className="flex items-center gap-1.5"><span className="blink size-1.5 rounded-full bg-signal" />Rewriting…</span>}
      </div>
    </div>
  );
}
