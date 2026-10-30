import type { Metadata } from "next";
import { Suspense } from "react";

import { ArenaView } from "@/components/arena/arena-view";
import { Empty, Offline, Page, Skeleton } from "@/components/app/page-parts";
import { api, type RunDetail } from "@/lib/api";

export const metadata: Metadata = { title: "Arena | CADRecover" };

async function Arena({ params }: { params: Promise<{ runId: string }> }) {
  const { runId } = await params;
  const res = await api<RunDetail>(`/v1/runs/${encodeURIComponent(runId)}`);
  if (!res.ok && res.error === "not found") return <Empty title="No such round">{runId} is not in the validator&apos;s database.</Empty>;
  if (!res.ok) return <Offline error={res.error} />;
  return <ArenaView key={runId} initial={res.data} />;
}

export default function ArenaPage({ params }: { params: Promise<{ runId: string }> }) {
  return (
    <Page>
      <Suspense fallback={<Skeleton rows={6} />}>
        <Arena params={params} />
      </Suspense>
    </Page>
  );
}
