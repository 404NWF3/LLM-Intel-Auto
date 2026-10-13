import type { NextConfig } from "next";

// eslint-disable-next-line @typescript-eslint/no-require-imports
const withBundleAnalyzer = require("@next/bundle-analyzer")({
  enabled: process.env.ANALYZE === "true",
});

const CSP = [
  "default-src 'self'",
  // Next.js needs unsafe-eval in dev; tighten to nonce in production
  "script-src 'self' 'unsafe-eval' 'unsafe-inline'",
  "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
  "font-src 'self' https://fonts.gstatic.com",
  "img-src 'self' data: blob:",
  // /api/* for SWR + SSE; ws: for HMR in dev
  "connect-src 'self' ws:",
  "frame-ancestors 'none'",
]
  .join("; ")
  .trim();

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        // 将所有 /api/* 请求代理到 FastAPI 后端（开发模式）
        source: "/api/:path*",
        destination: "http://localhost:8000/api/:path*",
      },
    ];
  },
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Content-Security-Policy", value: CSP },
        ],
      },
    ];
  },
};

export default withBundleAnalyzer(nextConfig);
