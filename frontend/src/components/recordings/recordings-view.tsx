"use client";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Upload } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import useSWR from "swr";
import { fetcher, uploadFiles, type Recording } from "@/lib/api";
import { useStatus } from "@/lib/use-status";
import { RecordingList } from "./list";
import { RecordingDetail } from "./detail";
import { cn } from "@/lib/utils";

export function RecordingsView() {
  const params = useSearchParams();
  const router = useRouter();
  const id = params.get("id") ? Number(params.get("id")) : null;
  const t = params.get("t") ? Number(params.get("t")) : undefined;
  const openTab = params.get("tab") || undefined;   // a cited summary links straight to the Summary tab
  const { data: status } = useStatus();
  const busy = !!(status?.worker.current || status?.importer.importing);
  const { data: recordings, mutate } = useSWR<Recording[]>("/api/recordings", fetcher, { refreshInterval: busy ? 3000 : 15000 });

  // Desktop: open the newest recording by default. Phone: stay on the list.
  useEffect(() => {
    if (id == null && recordings?.length && window.matchMedia("(min-width: 1024px)").matches) router.replace(`/?id=${recordings[0].id}`);
  }, [id, recordings, router]);

  const [dragging, setDragging] = useState(0);
  const onDrop = useCallback(async (e: React.DragEvent) => {
    e.preventDefault(); setDragging(0);
    const files = Array.from(e.dataTransfer.files).filter((f) => /\.(wav|m4a|mp3|aac|flac|aif|aiff)$/i.test(f.name));
    if (!files.length) { toast("Drop audio files (WAV, M4A, MP3, FLAC…)"); return; }
    toast(`Importing ${files.length} file${files.length === 1 ? "" : "s"}…`);
    try {
      const res = await uploadFiles(files);
      toast(res.imported.length ? `Imported ${res.imported.length}, queued for processing` : "Nothing new: already in the library");
      mutate();
    } catch (err) { toast(`Import failed: ${(err as Error).message}`); }
  }, [mutate]);

  return (
    <div
      className="relative grid h-full lg:grid-cols-[340px_1fr]"
      onDragEnter={(e) => { if (e.dataTransfer.types.includes("Files")) setDragging((d) => d + 1); }}
      onDragLeave={() => setDragging((d) => Math.max(0, d - 1))}
      onDragOver={(e) => { if (e.dataTransfer.types.includes("Files")) e.preventDefault(); }}
      onDrop={onDrop}
    >
      {dragging > 0 && (
        <div className="pointer-events-none absolute inset-0 z-40 grid place-items-center bg-signal-soft/80 backdrop-blur-sm">
          <div className="flex items-center gap-3 rounded-xl border-2 border-dashed border-signal bg-surface px-6 py-4 text-[15px] font-semibold"><Upload className="size-5 text-signal" />Drop audio to import it</div>
        </div>
      )}
      <aside className={cn("min-h-0 overflow-y-auto border-r border-hairline bg-surface", id != null && "hidden lg:block")}>
        <RecordingList recordings={recordings ?? []} activeId={id} />
      </aside>
      <section className={cn("min-h-0", id == null && "hidden lg:block")}>
        {id != null ? <RecordingDetail id={id} seekTo={t} openTab={openTab} onListChanged={() => mutate()} /> :<div className="hidden h-full place-items-center text-[13px] text-ink-3 lg:grid">Select a recording.</div>}
      </section>
    </div>
  );
}
