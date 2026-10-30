export const shortHash = (h: string | null | undefined, n = 6) => {
  if (!h) return "none";
  const hex = h.replace(/^sha256:/, "");
  return hex.length <= n * 2 ? hex : `${hex.slice(0, n)}…${hex.slice(-4)}`;
};

export const shortKey = (k: string) => `${k.slice(0, 6)}…${k.slice(-4)}`;

export const q = (v: number | null | undefined, digits = 1) => (v == null ? "n/a" : v.toFixed(digits));

export const pct = (v: number | null | undefined) => (v == null ? "n/a" : `${Math.round(v * 100)}%`);

export function when(iso: string) {
  const d = new Date(iso);
  return d.toLocaleString("en-GB", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "UTC",
  }) + " UTC";
}

export const minerName = (uid: number, label: string | null | undefined) => label ?? `uid ${uid}`;
