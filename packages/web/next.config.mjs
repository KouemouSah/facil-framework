import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  // Lean container image (only traced deps) for the `web` Compose profile / k8s.
  output: "standalone",
  // SSR -> backend over the internal network; browser -> public origin.
  // `/api` is proxied to the backend so the SPA is single-origin (no CORS) and
  // the BFF route handlers can set httpOnly cookies on the same site.
  async rewrites() {
    const internal = process.env.INTERNAL_API_URL || "http://localhost:8080";
    return [{ source: "/backend/:path*", destination: `${internal}/:path*` }];
  },
  // Lean, secure defaults; full CSP is enforced at the edge (Caddy) + here.
  async headers() {
    return [{
      source: "/:path*",
      headers: [
        { key: "X-Content-Type-Options", value: "nosniff" },
        { key: "X-Frame-Options", value: "DENY" },
        { key: "Referrer-Policy", value: "no-referrer" },
      ],
    }];
  },
};

export default withNextIntl(nextConfig);
