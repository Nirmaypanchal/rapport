"use client";
import { cn } from "@/lib/utils";

/** Thin Signal progress bar; indeterminate shimmer when the fraction is unknown. */
export function Progress({ value, className }: { value?: number | null; className?: string }) {
  const known = typeof value === "number" && value > 0;
  return (
    <div className={cn("h-1 w-full overflow-hidden rounded-full bg-surface-2", className)} role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={known ? Math.round(value * 100) : undefined}>
      <div className={cn("h-full rounded-full bg-signal transition-[width] duration-500 ease-out", !known && "w-1/3 animate-[shimmer_1.4s_ease-in-out_infinite]")} style={known ? { width: `${Math.min(100, Math.max(2, value * 100))}%` } : undefined} />
    </div>
  );
}
