/** Running mean of challenger vs champion, task by task, with the line the challenger must clear. Pure SVG. */
export function RaceChart({
  challenger,
  champion,
  total,
  margin,
}: {
  challenger: (number | null)[];
  champion: (number | null)[];
  total: number;
  margin: number;
}) {
  const W = 640;
  const H = 220;
  const pad = { l: 36, r: 16, t: 14, b: 26 };
  const x = (i: number) => pad.l + (i / Math.max(1, total - 1)) * (W - pad.l - pad.r);
  const y = (v: number) => pad.t + (1 - v / 100) * (H - pad.t - pad.b);

  const running = (xs: (number | null)[]) => {
    const out: number[] = [];
    let sum = 0;
    xs.forEach((v, i) => {
      if (v == null) return;
      sum += v;
      out.push(sum / (i + 1));
    });
    return out;
  };
  const ch = running(challenger);
  const cp = running(champion);
  const path = (pts: number[]) => pts.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  const bar = cp.length ? cp.map((v) => Math.min(100, v + margin)) : [];

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full" role="img" aria-label="Running mean score: challenger vs champion">
      {[0, 25, 50, 75, 100].map((g) => (
        <g key={g}>
          <line x1={pad.l} x2={W - pad.r} y1={y(g)} y2={y(g)} stroke="currentColor" strokeOpacity={0.08} />
          <text x={pad.l - 8} y={y(g) + 4} textAnchor="end" className="fill-ink-soft font-mono text-[11px]">
            {g}
          </text>
        </g>
      ))}
      {Array.from({ length: total }, (_, i) => (
        <text key={i} x={x(i)} y={H - 6} textAnchor="middle" className="fill-ink-soft font-mono text-[11px]">
          {i + 1}
        </text>
      ))}
      {bar.length > 1 && <path d={path(bar)} fill="none" stroke="#ff5e1f" strokeWidth={1} strokeDasharray="4 4" />}
      {cp.length > 0 && <path d={path(cp)} fill="none" stroke="#262626" strokeWidth={2} />}
      {ch.length > 0 && <path d={path(ch)} fill="none" stroke="#ff5e1f" strokeWidth={2.5} />}
      {ch.length > 0 && <circle cx={x(ch.length - 1)} cy={y(ch[ch.length - 1])} r={4} fill="#ff5e1f" />}
      {cp.length > 0 && <circle cx={x(cp.length - 1)} cy={y(cp[cp.length - 1])} r={3.5} fill="#262626" />}
    </svg>
  );
}

export function Stamp({ verdict, block }: { verdict: "crowned" | "defended"; block: number | null }) {
  const crowned = verdict === "crowned";
  return (
    <div
      className={`inline-flex -rotate-3 flex-col items-center rounded-sm border-[2.5px] px-4 py-2 font-mono ${
        crowned ? "border-accent text-accent" : "border-ink text-ink"
      }`}
    >
      <span className="text-[19px] font-semibold tracking-[0.06em]">{crowned ? "TOP SPOT TAKEN" : "DEFENDED"}</span>
      {block != null && <span className="text-[11.5px] tracking-[0.04em]">block {block.toLocaleString("en-US")}</span>}
    </div>
  );
}
