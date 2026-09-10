"use client";
import type { ReactNode } from "react";

/**
 * The small Markdown subset the local models are asked for: ## headings, bullets, paragraphs, **bold**.
 * Anything fancier is left as text — a summary is meant to be read, not to be a document format.
 *
 * `cite` renders a bare `[3]` however the caller wants; Ask links each one to the excerpt it came from.
 */
export function Markdown({ text, cite }: { text: string; cite?: (n: number) => ReactNode }) {
  const blocks: ReactNode[] = [];
  let list: string[] = [];
  const flush = () => { if (list.length) { blocks.push(<ul key={`l${blocks.length}`} className="my-2 list-disc space-y-1 pl-5">{list.map((l, i) => <li key={i}><Inline text={l} cite={cite} /></li>)}</ul>); list = []; } };
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim();
    if (!line) { flush(); continue; }
    if (/^#{1,3}\s/.test(line)) { flush(); blocks.push(<div key={`h${blocks.length}`} className="eyebrow mt-5 mb-1.5 first:mt-0">{line.replace(/^#+\s/, "")}</div>); continue; }
    if (/^[-*•]\s/.test(line)) { list.push(line.replace(/^[-*•]\s/, "")); continue; }
    if (/^\d+[.)]\s/.test(line)) { list.push(line.replace(/^\d+[.)]\s/, "")); continue; }
    flush(); blocks.push(<p key={`p${blocks.length}`} className="my-1.5">{<Inline text={line} cite={cite} />}</p>);
  }
  flush();
  return <div className="text-[15px] leading-[1.6]">{blocks}</div>;
}

function Inline({ text, cite }: { text: string; cite?: (n: number) => ReactNode }) {
  const parts = text.split(cite ? /(\*\*[^*]+\*\*|\[\d{1,2}\])/g : /(\*\*[^*]+\*\*)/g);
  return <>{parts.map((p, i) => {
    if (p.startsWith("**") && p.endsWith("**")) return <b key={i}>{p.slice(2, -2)}</b>;
    if (cite && /^\[\d{1,2}\]$/.test(p)) return <span key={i}>{cite(Number(p.slice(1, -1)))}</span>;
    return <span key={i}>{p}</span>;
  })}</>;
}
