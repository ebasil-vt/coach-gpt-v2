const COACHGPT_API =
  process.env.COACHGPT_API_PROXY ?? "http://localhost:8080";

const isProduction = process.env.NODE_ENV === "production";

/** @type {import('next').NextConfig} */
const nextConfig = isProduction
  ? {
      // In prod, Next is built as a static bundle and served by FastAPI
      // alongside the API. No rewrites — same-origin already.
      output: "export",
      images: { unoptimized: true },
      trailingSlash: true,
    }
  : {
      // In dev, two services run on different ports — proxy /api and /auth/*
      // through Next so cookies stay same-origin in the browser.
      async rewrites() {
        return [
          { source: "/auth/login", destination: `${COACHGPT_API}/login` },
          { source: "/auth/logout", destination: `${COACHGPT_API}/logout` },
          { source: "/api/:path*", destination: `${COACHGPT_API}/api/:path*` },
        ];
      },
    };

export default nextConfig;
