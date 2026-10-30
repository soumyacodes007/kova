import { redirect } from "next/navigation";
import { Suspense } from "react";

// A run's record and its arena are the same page.
async function Go({ params }: { params: Promise<{ runId: string }> }) {
  const { runId } = await params;
  redirect(`/arena/${encodeURIComponent(runId)}`);
  return null;
}

export default function RunPage({ params }: { params: Promise<{ runId: string }> }) {
  return (
    <Suspense fallback={null}>
      <Go params={params} />
    </Suspense>
  );
}
