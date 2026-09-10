"use client";

/** A full-text-search snippet, where SQLite marked the matching words with `[[…]]`. */
export function Snippet({ s }: { s: string }) {
  const parts = s.split(/(\[\[.*?\]\])/g);
  return <>{parts.map((p, i) => (p.startsWith("[[") ? <mark key={i} className="rounded-[3px] bg-signal-soft px-0.5 text-ink shadow-[inset_0_-2px_0_var(--signal)]">{p.slice(2, -2)}</mark> : <span key={i}>{p}</span>))}</>;
}
