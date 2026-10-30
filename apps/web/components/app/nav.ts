export type TrackId = "a" | "b";

export const TRACKS: Record<TrackId, { id: TrackId; label: string; name: string; home: string; nav: { href: string; label: string }[] }> = {
  a: {
    id: "a",
    label: "Track A",
    name: "Live rounds",
    home: "/arena",
    nav: [
      { href: "/arena", label: "Arena" },
      { href: "/leaderboard", label: "Leaderboard" },
      { href: "/runs", label: "Runs" },
    ],
  },
  b: {
    id: "b",
    label: "Track B",
    name: "King of the hill",
    home: "/hill",
    nav: [
      { href: "/hill", label: "The hill" },
      { href: "/hill/leaderboard", label: "Leaderboard" },
      { href: "/hill/matches", label: "Matches" },
      { href: "/hill/submit", label: "Submit a model" },
    ],
  },
};

/** Pages both tracks share. */
export const SHARED_NAV = [
  { href: "/chain", label: "Chain" },
  { href: "/docs", label: "Docs" },
];

export const trackOf = (path: string): TrackId | null =>
  path.startsWith("/hill") ? "b" : ["/arena", "/leaderboard", "/runs"].some((p) => path === p || path.startsWith(`${p}/`)) ? "a" : null;
