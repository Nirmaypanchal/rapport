"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import useSWR from "swr";
import { fetcher, type SearchHit } from "@/lib/api";
import { fmtClock, fmtDate, fmtTime } from "@/lib/format";
import { speakerStyle } from "@/lib/speakers";
import { SpeakerDot } from "@/components/avatar";
import { Input } from "@/components/ui/input";

function Snippet({ s }: { s: string }) {
  const parts = s.split(/(\[\[.*?\]\])/g);
  return <>{parts.map((p, i) => (p.startsWith("[[") ? <mark key={i} className="rounded-[3px] bg-signal-soft px-0.5 text-ink shadow-[inset_0_-2px_0_var(--signal)]">{p.slice(2, -2)}</mark> : <span key={i}>{p}</span>))}</>;
}

export function SearchView() {
  const params = useSearchParams();
  const [q, setQ] = useState(params.get("q") ?? "");
  const [debounced, setDebounced] = useState(q);
  useEffect(() => { const t = setTimeout(() => setDebounced(q), 200); return () => clearTimeout(t); }, [q]);
  useEffect(() => { history.replaceState(null, "", debounced ? `/search/?q=${encodeURIComponent(debounced)}` : "/search/"); }, [debounced]);
  const { data: hits } = useSWR<SearchHit[] | { error: string }>(debounced.trim() ? `/api/search?q=${encodeURIComponent(debounced)}` : null, fetcher, { keepPreviousData: true });
  const list = Array.isArray(hits) ? hits : null;

  return (
    <div className="h-full overflow-y-auto px-4 pb-10 pt-5 sm:px-8 sm:pt-7">
      <div className="mx-auto max-w-[760px]">
        <h1 className="font-display text-[26px] font-semibold tracking-[-0.02em] sm:text-[30px]">Search</h1>
        <Input autoFocus value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search every transcript…" className="mt-4 h-12 bg-surface text-[16px]" />
        <div className="mt-4 grid gap-2">
          {hits && !Array.isArray(hits) && <div className="text-[13px] text-clip">{hits.error}</div>}
          {list && !list.length && <div className="p-8 text-center text-[13px] text-ink-3">Nothing found.</div>}
          {list?.map((x) => (
            <Link key={x.id} href={`/?id=${x.recording_id}&t=${Math.max(0, x.start - 1).toFixed(1)}`} className="speaker rounded-lg border border-hairline bg-surface px-4 py-3 transition-colors hover:border-[var(--c)]" style={speakerStyle(x.person_color)}>
              <div className="flex flex-wrap items-center gap-x-3 text-[12px] text-ink-2">
                <span className="inline-flex items-center gap-1.5 font-semibold text-[var(--c)]"><SpeakerDot color={x.person_color} />{x.person_name || x.speaker_label}</span>
                <span>{x.title || `${fmtDate(x.recorded_at)}, ${fmtClock(x.recorded_at)}`}</span>
                <span className="tc">{fmtTime(x.start)}</span>
              </div>
              <div className="mt-1 text-[15px]"><Snippet s={x.snippet} /></div>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
