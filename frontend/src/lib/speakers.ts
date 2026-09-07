import type { CSSProperties } from "react";
import type { Speaker } from "./api";

export const PALETTE = ["sky", "blush", "sage", "orchid", "butter", "aqua", "periwinkle", "peach", "mint", "rose", "lime", "steel", "lilac", "apricot", "seafoam", "dusk"] as const;

/** CSS custom properties for a palette name, consumed by the `.speaker` class family. */
export function speakerStyle(color: string | null | undefined): CSSProperties {
  const name = color && (PALETTE as readonly string[]).includes(color) ? color : "none";
  return { "--c": `var(--spk-${name})`, "--wash": `var(--spk-${name}-wash)` } as CSSProperties;
}

export function speakerName(s: Pick<Speaker, "person_name" | "label"> & { display_name?: string | null }): string {
  return s.person_name || s.display_name || s.label;
}

/** Initial for a named person, number for an auto-named one: "still unnamed" reads at a glance. */
export function speakerGlyph(s: { person_name?: string | null; person_auto?: number | null; label?: string; name?: string; auto?: number | null; display_name?: string | null }): string {
  const name = s.person_name ?? s.name ?? s.display_name ?? "";
  const auto = s.person_auto ?? s.auto ?? 1;
  const m = name.match(/^Speaker (\d+)$/);
  if (m) return m[1];
  if (!auto && name) return name.trim()[0].toUpperCase();
  if (name) return name.trim()[0].toUpperCase();
  const l = (s.label ?? "").match(/(\d+)$/);
  return l ? String(Number(l[1]) + 1) : "?";
}
