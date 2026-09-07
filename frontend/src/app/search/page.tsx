import { Suspense } from "react";
import { SearchView } from "@/components/search-view";

export default function SearchPage() {
  return (
    <Suspense fallback={<div className="p-10 text-center text-[13px] text-ink-3">Loading…</div>}>
      <SearchView />
    </Suspense>
  );
}
