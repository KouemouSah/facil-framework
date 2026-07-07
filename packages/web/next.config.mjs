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
    return [
      { source: "/backend/:path*", destination: `${internal}/:path*` },
      // Public binary asset serving (Phase 3a): a rewrite streams bytes natively
      // (unlike the JSON BFF's res.text(), which corrupts binary). The backend's
      // GET /api/v1/assets/<id> is public + prefix-locked, so its returned url
      // works verbatim same-origin in <img src> — no mapping, no CORS.
      { source: "/api/v1/assets/:path*", destination: `${internal}/api/v1/assets/:path*` },
    ];
  },
  // Defence-in-depth security headers (audit E2); the edge (Caddy) may add more.
  // The CSP allows 'unsafe-inline' scripts/styles because Next's hydration and
  // Tailwind inject inline content without a nonce — but it still locks default-,
  // connect-, frame-ancestors, object-, base-uri and form-action, which block
  // off-origin exfiltration, clickjacking, base-tag hijack and plugin injection.
  async headers() {
    const dev = process.env.NODE_ENV !== "production";
    const csp = [
      "default-src 'self'",
      `script-src 'self' 'unsafe-inline'${dev ? " 'unsafe-eval'" : ""}`,
      "style-src 'self' 'unsafe-inline'",
      // https: allows admin-configured EXTERNAL branding images (logo/favicon/
      // login background can be off-origin URLs); same-origin uploads are covered
      // by 'self'. http: stays disallowed (mixed content). Images can't execute.
      "img-src 'self' data: https:",
      "font-src 'self' data:",
      "connect-src 'self'",
      "frame-ancestors 'none'",
      "base-uri 'self'",
      "form-action 'self'",
      "object-src 'none'",
    ].join("; ");
    return [{
      source: "/:path*",
      headers: [
        { key: "X-Content-Type-Options", value: "nosniff" },
        { key: "X-Frame-Options", value: "DENY" },
        { key: "Referrer-Policy", value: "no-referrer" },
        { key: "Content-Security-Policy", value: csp },
        { key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains" },
        { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), interest-cohort=()" },
      ],
    }];
  },
};

export default withNextIntl(nextConfig);
