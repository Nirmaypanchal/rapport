"use client";
import Link from "next/link";
import { FileText } from "lucide-react";
import { fmtClock, fmtDate } from "@/lib/format";
import { Snippet } from "@/components/snippet";

/** One block of a written summary, as a card: the `FileText` badge, the block's heading, which recording it
 *  belongs to, and the matching words. It carries no timestamp because a summary block has none — which is
 *  also why it opens the recording's Summary tab rather than the player at a second.
 *
 *  Both lists that can contain one use this: Ask passes `badge` (the number its answer cites) and dims the
 *  blocks the answer did not use; Search passes neither. One component, so a summary hit cannot come to look
 *  like two different things depending on which page found it.
 */
export function SummaryHitCard({ id, recordingId, heading, title, recordedAt, snippet, badge, dim }: {
  id?: string;
  recordingId: number;
  heading: string | null;
  title: string | null;
  recordedAt: string | null;
  snippet: string;
  badge?: React.ReactNode;
  dim?: boolean;
}) {
  const when = recordedAt ? (title ? `, ${fmtDate(recordedAt)}` : `${fmtDate(recordedAt)}, ${fmtClock(recordedAt)}`) : "";
  return (
    <Link
      id={id}
      href={`/?id=${recordingId}&tab=summary`}
      className={`speaker rounded-lg border border-hairline bg-surface px-4 py-3 transition-colors hover:border-[var(--c)] ${dim ? "opacity-65" : ""}`}
    >
      <div className="flex flex-wrap items-center gap-x-3 text-[12px] text-ink-2">
        {badge}
        <span className="inline-flex items-center gap-1.5 font-semibold text-ink-2"><FileText className="size-3.5" />Summary{heading ? ` · ${heading}` : ""}</span>
        <span>{title}{when}</span>
      </div>
      <div className="mt-1 text-[15px]"><Snippet s={snippet} /></div>
    </Link>
  );
}
