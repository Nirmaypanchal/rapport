"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Disc3, Plug, Search, Settings2, Users } from "lucide-react";
import { cn } from "@/lib/utils";
import { useStatus } from "@/lib/use-status";
import { Progress } from "@/components/progress";

const NAV = [
  { href: "/", label: "Recordings", icon: Disc3, key: "1" },
  { href: "/people/", label: "People", icon: Users, key: "2" },
  { href: "/sources/", label: "Sources", icon: Plug, key: "3" },
  { href: "/search/", label: "Search", icon: Search, key: "/" },
  { href: "/settings/", label: "Settings", icon: Settings2, key: "," },
] as const;

function isActive(pathname: string, href: string) {
  if (href === "/") return pathname === "/" || pathname === "";
  return pathname.startsWith(href.replace(/\/$/, ""));
}

export function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { data: status } = useStatus();
  const vols = status?.importer.volumes ?? [];
  const files = vols.reduce((a, v) => a + v.files, 0);
  const busy = status?.recording ? { title: "Recording", detail: status.recording.device } : status?.importer.importing ? { title: "Importing", detail: status.importer.importing } : status?.worker.current ? { title: `Processing${typeof status.worker.current.progress === "number" ? ` · ${Math.round(status.worker.current.progress * 100)}%` : ""}${status.stats.queued > 1 ? ` · ${status.stats.queued - 1} more queued` : ""}`, detail: `${status.worker.current.name}\n${status.worker.current.stage || "starting"}` } : null;

  return (
    <div className="grid h-full grid-rows-[1fr_auto] md:grid-cols-[64px_1fr] md:grid-rows-1 xl:grid-cols-[220px_1fr]">
      {/* Sidebar (desktop) / rail (tablet) */}
      <nav className="hidden flex-col gap-1 border-r border-hairline bg-surface p-3 md:flex md:items-center xl:items-stretch">
        <Link href="/" className="mb-3 flex items-center gap-2 px-2 py-1 font-display text-[15px] font-semibold">
          <span className={cn("size-2 shrink-0 rounded-full", status?.recording ? "bg-signal blink" : vols.length ? "bg-good" : "bg-ink-3")} aria-hidden />
          <span className="hidden xl:inline">Rapport</span>
        </Link>
        {NAV.map(({ href, label, icon: Icon, key }) => (
          <Link
            key={href}
            href={href}
            title={label}
            className={cn(
              "flex items-center gap-2.5 rounded-md px-2.5 py-2 text-[13.5px] font-medium text-ink-2 transition-colors duration-120 hover:bg-surface-2 hover:text-ink md:justify-center xl:justify-start",
              isActive(pathname, href) && "bg-ink text-ground hover:bg-ink hover:text-ground",
            )}
          >
            <Icon className="size-4 shrink-0" strokeWidth={1.75} />
            <span className="hidden xl:inline">{label}</span>
            <kbd className="ml-auto hidden font-mono text-[10.5px] opacity-60 xl:inline">{key}</kbd>
          </Link>
        ))}
        <div className="mt-auto hidden flex-col gap-2 xl:flex">
          {busy && (
            <Link href={status?.recording ? "/sources/" : "/"} className="rounded-md bg-signal-soft px-2.5 py-2 text-[12px] text-ink">
              <div className="flex items-center gap-1.5 font-medium"><span className="blink size-1.5 rounded-full bg-signal" />{busy.title}</div>
              <div className="mt-0.5 whitespace-pre-line text-ink-2">{busy.detail}</div>
              {status?.worker.current && <Progress value={status.worker.current.progress} className="mt-2" />}
            </Link>
          )}
          <div className={cn("flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[12px] font-medium", vols.length ? "bg-good-soft text-good" : "bg-surface-2 text-ink-3")}>
            <span className="size-1.5 rounded-full bg-current" />
            {vols.length ? `${vols.length} mic${vols.length > 1 ? "s" : ""} connected · ${files} file${files === 1 ? "" : "s"}` : "No mic connected"}
          </div>
          {status && (
            <div className="px-2.5 text-[12px] leading-relaxed text-ink-3">
              {status.stats.recordings} recordings · {status.stats.hours.toFixed(1)} h<br />
              {status.stats.people} people
            </div>
          )}
        </div>
      </nav>

      <main className="min-h-0 min-w-0">{children}</main>

      {/* Bottom tab bar (phone) */}
      <nav className="glass sticky bottom-0 z-30 flex h-14 items-stretch border-t border-hairline pb-[env(safe-area-inset-bottom)] md:hidden">
        {NAV.map(({ href, label, icon: Icon }) => (
          <Link key={href} href={href} className={cn("flex flex-1 flex-col items-center justify-center gap-0.5 text-[10.5px] font-medium text-ink-3", isActive(pathname, href) && "text-ink")}>
            <Icon className="size-5" strokeWidth={isActive(pathname, href) ? 2 : 1.6} />
            {label}
          </Link>
        ))}
      </nav>
    </div>
  );
}
