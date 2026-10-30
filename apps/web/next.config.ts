import type { NextConfig } from "next";

// The read API (`make api`) serves 127.0.0.1:8000. The browser reaches it through /api/v1/* on this origin,
// so GLBs, drawings and the event stream need no CORS setup.
const API = process.env.CADRECOVER_API_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  async rewrites() {
    return [{ source: "/api/v1/:path*", destination: `${API}/v1/:path*` }];
  },
};

export default nextConfig;
