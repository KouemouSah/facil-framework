import createNextIntlPlugin from 'next-intl/plugin';

// Use i18n.ts at project root for Docker build compatibility
const withNextIntl = createNextIntlPlugin('./i18n.ts');

// Sentry's withSentryConfig is loaded dynamically below so a failed import
// (e.g. workspace hoisting of @sentry/nextjs that loses sight of next/constants
// — observed on CI run #25246274191, 2026-05-02) doesn't break the build.
// Runtime Sentry stays wired via sentry.client/server/edge.config.ts which
// load the SDK from packages/web/node_modules/@sentry/nextjs directly.
let withSentryConfig = null;
try {
  ({ withSentryConfig } = await import('@sentry/nextjs'));
} catch (err) {
  console.warn(
    '[next.config] @sentry/nextjs build wrapper unavailable - skipping sourcemap upload.',
    err && err.message,
  );
}

/** @type {import('next').NextConfig} */
const nextConfig = {
  // SSR/ISR for Cloud Run deployment (static export removed)
  output: 'standalone', // Enable standalone output for Docker

  images: {
    unoptimized: false, // Enable image optimization
    remotePatterns: [
      {
        protocol: 'https',
        hostname: '**.run.app', // Cloud Run domains
      },
      {
        protocol: 'https',
        hostname: 'storage.googleapis.com',
      },
      {
        protocol: 'https',
        hostname: 'firebasestorage.googleapis.com',
      },
      {
        protocol: 'https',
        hostname: 'taxasge-dev.firebasestorage.app',
        pathname: '/application-attachments/**',
      },
      {
        protocol: 'https',
        hostname: '**.supabase.co',
      },
    ],
    formats: ['image/avif', 'image/webp'],
  },

  // SEO & Performance
  compress: true,
  poweredByHeader: false,

  // Headers for security and performance
  async headers() {
    return [
      {
        source: '/(.*)',
        headers: [
          {
            key: 'X-Frame-Options',
            value: 'SAMEORIGIN',
          },
          {
            key: 'X-Content-Type-Options',
            value: 'nosniff',
          },
          {
            key: 'Referrer-Policy',
            value: 'strict-origin-when-cross-origin',
          },
          {
            key: 'Permissions-Policy',
            value: 'geolocation=(), microphone=(), camera=()',
          },
          {
            key: 'Content-Security-Policy',
            // Note: this header is overridden per-request by src/middleware.ts.
            // Keep this fallback in sync with the middleware so a crashed
            // middleware (or static asset path bypassing it) still gets a
            // workable CSP — LogRocket allowlist included.
            value: [
              "default-src 'self'",
              "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.lr-in.com https://cdn.logr-in.com",
              "style-src 'self' 'unsafe-inline'",
              "img-src 'self' data: blob: https://storage.googleapis.com https://firebasestorage.googleapis.com https://*.supabase.co",
              "font-src 'self' data:",
              "connect-src 'self' https://*.run.app https://*.supabase.co https://storage.googleapis.com https://firebasestorage.googleapis.com https://*.lr-in.com https://*.logr-in.com https://*.lr-ingest.io https://*.logrocket.io https://*.logrocket.com",
              "worker-src 'self' blob:",
              "frame-src 'self' https://storage.googleapis.com https://firebasestorage.googleapis.com https://*.grafana.net https://lookerstudio.google.com",
              "object-src 'none'",
              "base-uri 'self'",
            ].join('; '),
          },
        ],
      },
      {
        source: '/api/(.*)',
        headers: [
          {
            key: 'Cache-Control',
            value: 'public, max-age=300, stale-while-revalidate=60',
          },
        ],
      },
      {
        source: '/_next/static/(.*)',
        headers: [
          {
            key: 'Cache-Control',
            value: 'public, max-age=31536000, immutable',
          },
        ],
      },
    ];
  },

  // Redirects
  async redirects() {
    return [
      {
        source: '/home',
        destination: '/',
        permanent: true,
      },
    ];
  },

  // Webpack configuration (optional optimizations for Cloud Run)
  webpack: (config, { isServer }) => {
    // Optimize bundle splitting for better performance
    if (!isServer) {
      config.optimization.splitChunks = {
        chunks: 'all',
        cacheGroups: {
          default: false,
          vendors: false,
          // Separate vendor bundle for better caching
          vendor: {
            name: 'vendor',
            chunks: 'all',
            test: /node_modules/,
            priority: 20,
          },
          // Common code shared between pages
          common: {
            name: 'common',
            minChunks: 2,
            chunks: 'all',
            priority: 10,
            reuseExistingChunk: true,
            enforce: true,
          },
        },
      };
    }

    return config;
  },

  // Environment variables (public, prefixed with NEXT_PUBLIC_)
  // Note: NEXT_PUBLIC_API_URL is the canonical var set by GitHub Actions
  env: {
    NEXT_PUBLIC_API_URL:
      process.env.NEXT_PUBLIC_API_URL || process.env.NEXT_PUBLIC_API_BASE_URL || 'https://taxasge-backend-dev.run.app',
    NEXT_PUBLIC_SITE_URL:
      process.env.NEXT_PUBLIC_SITE_URL || 'https://taxasge-frontend-dev.run.app',
    NEXT_PUBLIC_ENVIRONMENT: process.env.NEXT_PUBLIC_ENVIRONMENT || 'development',
  },

  // Experimental features
  experimental: {
    optimizePackageImports: ['@radix-ui/react-icons', 'lucide-react', 'date-fns', 'lodash'],
    serverActions: {
      bodySizeLimit: '2mb',
    },
  },

  // TypeScript configuration
  typescript: {
    ignoreBuildErrors: false,
  },

  // ESLint configuration
  eslint: {
    ignoreDuringBuilds: false,
  },
};

// Sentry wrapper — uploads sourcemaps + tunnels SDK requests to bypass
// adblockers. The wrapper no-ops when SENTRY_AUTH_TOKEN / org / project
// are missing (e.g. local dev, contributor without secrets) AND when
// the @sentry/nextjs build module itself failed to load (see top of file).
//
// Org/project values match the live Sentry projects under taxasge.sentry.io
// (see .claude/plans/OBSERVABILITY_DASHBOARDS_AND_SENTRY_BACKEND.md §3).
const finalConfig = withSentryConfig
  ? withSentryConfig(withNextIntl(nextConfig), {
      org: 'taxasge',
      project: 'javascript-nextjs',
      silent: !process.env.CI,
      // Only upload sourcemaps when the auth token is present (CI build).
      // Without this guard, local `next build` would error.
      authToken: process.env.SENTRY_AUTH_TOKEN,
      // Hide sourcemap files from the public bundle once uploaded.
      hideSourceMaps: true,
      // Disable Sentry's CLI logger spam in CI logs.
      disableLogger: true,
      // Tunnel SDK requests through /monitoring to bypass adblockers (saves
      // ~5-15% of would-be-dropped events on browsers with uBlock Origin).
      tunnelRoute: '/monitoring',
    })
  : withNextIntl(nextConfig);

export default finalConfig;
// deploy trigger 1771369122
