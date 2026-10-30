import { redirect } from "next/navigation";
import { Suspense } from "react";

import { Empty, Offline, Page, Skeleton } from "@/components/app/page-parts";
import { api, type Status } from "@/lib/api";

async function Latest() {
  const res = await api<Status>("/v1/status");
  if (!res.ok) return <Offline error={res.error} />;
  if (!res.data.latest_run) return <Empty title="No rounds yet">Start one with `make demo` and it opens here.</Empty>;
  redirect(`/arena/${res.data.latest_run.run_id}`);
}

export default function ArenaIndex() {
  return (
    <Page>
      <Suspense fallback={<Skeleton rows={6} />}>
        <Latest />
      </Suspense>
    </Page>
  );
}
