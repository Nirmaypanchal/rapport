import { Suspense } from "react";
import { RecordingsView } from "@/components/recordings/recordings-view";

export default function RecordingsPage() {
  return (
    <Suspense fallback={<div className="p-10 text-center text-[13px] text-ink-3">Loading…</div>}>
      <RecordingsView />
    </Suspense>
  );
}
