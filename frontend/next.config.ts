import type { NextConfig } from "next";

// Static export: `npm run build` writes ./out, which the Python server serves.
// In development the app talks to the API directly (see .env.development).
const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
  reactStrictMode: true,
};

export default nextConfig;
