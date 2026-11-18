const BACKEND_INTERNAL_URL = process.env.BACKEND_INTERNAL_URL || "http://backend:8000";
const EMBED_CSP =
  "frame-ancestors 'self' https://bentivegna-os.lovable.app https://preview--flow-canvas-automations.lovable.app";

module.exports = {
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${BACKEND_INTERNAL_URL}/api/:path*`,
      },
    ];
  },
  async headers() {
    return [
      {
        source: "/_next/static/:path*",
        headers: [
          {
            key: "Cache-Control",
            value: "public, max-age=31536000, immutable",
          },
        ],
      },
      {
        source: "/((?!_next/static|_next/image|favicon.ico).*)",
        headers: [
          {
            key: "Content-Security-Policy",
            value: EMBED_CSP,
          },
          {
            key: "Cache-Control",
            value: "no-cache, no-store, must-revalidate",
          },
        ],
      },
    ];
  },
};
