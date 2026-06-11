# =============================================================================
# TaxasGE Frontend - Production Dockerfile for Cloud Run
# =============================================================================
# Multi-stage build for optimized Next.js SSR deployment
# Base: Node.js 20 Alpine (matches engines requirement in package.json)
# =============================================================================

FROM node:20-alpine AS base

# Install dependencies only when needed
FROM base AS deps
WORKDIR /app

# Install dependencies based on package manager
# Note: Using npm install instead of npm ci because this package is part of a
# monorepo with npm workspaces, which keeps package-lock.json at the root level
COPY package.json ./
RUN npm install --legacy-peer-deps

# =============================================================================
# Build stage
# =============================================================================
FROM base AS builder
WORKDIR /app

# Accept build-time arguments for Next.js public env vars
# These MUST be set at build time for client-side JavaScript
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}

# LogRocket — empty value disables init at runtime (safe default for forks)
ARG NEXT_PUBLIC_LOGROCKET_APP_ID=
ENV NEXT_PUBLIC_LOGROCKET_APP_ID=${NEXT_PUBLIC_LOGROCKET_APP_ID}

# Build version stamp surfaced to LogRocket + Sentry as `release`
ARG NEXT_PUBLIC_BUILD_VERSION=dev
ENV NEXT_PUBLIC_BUILD_VERSION=${NEXT_PUBLIC_BUILD_VERSION}

# Sentry — empty DSN disables init at runtime (safe default for forks).
# The DSN itself is public (visible in client bundle network requests),
# kept centralised for parity with LogRocket app id.
ARG NEXT_PUBLIC_SENTRY_DSN=
ENV NEXT_PUBLIC_SENTRY_DSN=${NEXT_PUBLIC_SENTRY_DSN}

# Sentry environment label (staging | production) — surfaced via
# Sentry.environment to filter events in the UI. Default 'production'.
ARG NEXT_PUBLIC_ENVIRONMENT=production
ENV NEXT_PUBLIC_ENVIRONMENT=${NEXT_PUBLIC_ENVIRONMENT}

# Sentry CLI auth token — used by withSentryConfig at build time to
# upload sourcemaps. Build-time only (not baked into the image runtime).
ARG SENTRY_AUTH_TOKEN=
ENV SENTRY_AUTH_TOKEN=${SENTRY_AUTH_TOKEN}

# Copy dependencies
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Set build-time environment variables
ENV NEXT_TELEMETRY_DISABLED=1
ENV NODE_ENV=production

# Log the API URL being baked into the build
RUN echo "Building with NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}"

# Build Next.js application with increased memory for large codebase
ENV NODE_OPTIONS="--max-old-space-size=4096"
RUN npm run build

# =============================================================================
# Production stage
# =============================================================================
FROM base AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

# Create non-root user for security
RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

# Copy public assets
COPY --from=builder /app/public ./public

# Create .next directory with correct permissions
RUN mkdir .next
RUN chown nextjs:nodejs .next

# Copy built application
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

# Copy next-intl configuration and messages (required at runtime)
COPY --from=builder --chown=nextjs:nodejs /app/src/i18n ./src/i18n
COPY --from=builder --chown=nextjs:nodejs /app/messages ./messages

# Switch to non-root user
USER nextjs

# Expose port 3000 (Cloud Run will map to 8080)
EXPOSE 3000

# Set port environment variable
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD node -e "require('http').get('http://localhost:3000/api/health', (r) => {process.exit(r.statusCode === 200 ? 0 : 1)})"

# Start Next.js server
CMD ["node", "server.js"]
