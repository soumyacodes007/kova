"use client";

import dynamic from "next/dynamic";

import type { PartLayer } from "./part-viewer";

// three.js is large and needs WebGL: load it on the client only, after the page shell.
const Viewer = dynamic(() => import("./part-viewer"), {
  ssr: false,
  loading: () => <div className="h-full w-full animate-pulse bg-surface" />,
});

export type { PartLayer };

export function PartViewer({ layers, label }: { layers: PartLayer[]; label: string }) {
  return <Viewer layers={layers} label={label} />;
}
