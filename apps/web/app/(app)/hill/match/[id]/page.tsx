import type { Metadata } from "next";
import { Suspense } from "react";

import { Empty, Page, Skeleton } from "@/components/app/page-parts";
import { MatchView } from "@/components/hill/match-view";
import { BackendPending, SampleBanner } from "@/components/hill/ui";
import { getMatch, isSample } from "@/lib/hill";

export const metadata: Metadata = { title: "Match | CADRecover" };

type Props = { params: Promise<{ id: string }>; searchParams: Promise<Record<string, string | string[] | undefined>> };

async function Body({ params, searchParams }: Props) {
  const [{ id }, sp] = await Promise.all([params, searchParams]);
  const sample = isSample(sp);
  const res = await getMatch(id, { sample });
  if (!res.ok && res.error === "not found") return <Empty title={sample ? "No such sample match" : "No such match"}>{id} is not on the hill.</Empty>;
  if (!res.ok) return <BackendPending error={res.error} samplePath="/hill/match/m_sample_live?sample=1" />;
  return (
    <>
      {sample && <SampleBanner live={`/hill/match/${id}`} />}
      <MatchView key={id} detail={res.data} poll={!sample} />
    </>
  );
}

export default function MatchPage(props: Props) {
  return (
    <Page>
      <Suspense fallback={<Skeleton rows={6} />}>
        <Body {...props} />
      </Suspense>
    </Page>
  );
}
