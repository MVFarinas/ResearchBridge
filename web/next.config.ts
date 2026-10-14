/**
 * Next.js configuration for the ResearchBridge reader.
 *
 * The backend API is reached server-side only (`RB_API_URL`), so browsers never
 * talk to it directly and no CORS configuration is needed.
 */
import type { NextConfig } from "next";

/** Security headers sent with every page. */
const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
];

/** The Next.js configuration. */
const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  // Do not let `next dev` write an AGENTS.md into the app; CLAUDE.md at the root covers agents.
  agentRules: false,
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

export default nextConfig;
