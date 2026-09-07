import { Suspense } from "react";
import { PeopleView } from "@/components/people-view";

export default function PeoplePage() {
  return (
    <Suspense fallback={<div className="p-10 text-center text-[13px] text-ink-3">Loading…</div>}>
      <PeopleView />
    </Suspense>
  );
}
