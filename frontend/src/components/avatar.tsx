"use client";
import { cn } from "@/lib/utils";
import { speakerGlyph, speakerName, speakerStyle } from "@/lib/speakers";
import { fmtDur } from "@/lib/format";
import type { Speaker } from "@/lib/api";

export function SpeakerAvatar({ color, glyph, size = 20, className }: { color: string | null | undefined; glyph: string; size?: number; className?: string }) {
  return (
    <span
      className={cn("speaker inline-grid shrink-0 place-items-center rounded-full font-bold", className)}
      style={{ ...speakerStyle(color), width: size, height: size, fontSize: Math.round(size * 0.5), background: "var(--wash)", color: "var(--c)", boxShadow: "inset 0 0 0 1px color-mix(in oklab, var(--c) 25%, transparent)" }}
      aria-hidden
    >
      {glyph}
    </span>
  );
}

export function SpeakerDot({ color, className }: { color: string | null | undefined; className?: string }) {
  return <span className={cn("speaker inline-block size-2 shrink-0 rounded-full", className)} style={{ ...speakerStyle(color), background: "var(--wash)", boxShadow: "inset 0 0 0 1.5px var(--c)" }} aria-hidden />;
}

export function SpeakerChip({ s, onClick, active, showTime = true }: { s: Speaker; onClick?: (e: React.MouseEvent<HTMLButtonElement>) => void; active?: boolean; showTime?: boolean }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "speaker inline-flex h-7 items-center gap-1.5 rounded-full border border-hairline bg-surface pl-1 pr-2.5 text-[13px] font-medium transition-colors duration-120 hover:border-[var(--c)] hover:bg-[var(--wash)]",
        active && "border-[var(--c)] bg-[var(--wash)]",
      )}
      style={speakerStyle(s.person_color)}
    >
      <SpeakerAvatar color={s.person_color} glyph={speakerGlyph(s)} size={20} />
      <span className="max-w-[16ch] truncate">{speakerName(s)}</span>
      {showTime && <span className="tc text-[11px] text-ink-3">{fmtDur(s.speaking_sec)}</span>}
      {showTime && s.similarity != null && <span className="tc border-l border-hairline pl-1.5 text-[10.5px] text-ink-3" title="voice match confidence">{Math.round(s.similarity * 100)}%</span>}
    </button>
  );
}
