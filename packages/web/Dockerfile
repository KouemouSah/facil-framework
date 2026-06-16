# Facil web console (Next.js 15, standalone). Built by the `web` Compose profile
# (context: ./packages/web) and in CI -> GHCR. Multi-stage for a lean runtime
# image (only the traced deps ship). Prod build runs in CI, never manually.
FROM node:20-slim AS deps
WORKDIR /app
COPY package.json ./
RUN npm install --no-audit --no-fund

FROM node:20-slim AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# Public build-time config (compose passes these); the client uses the BFF
# (same-origin /api/*), so these are mostly informational.
ARG NEXT_PUBLIC_API_URL
ARG NEXT_PUBLIC_BUILD_VERSION
ARG NEXT_PUBLIC_ENVIRONMENT
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:20-slim AS runner
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
RUN groupadd -g 1001 nodejs && useradd -u 1001 -g nodejs -m nextjs
# Standalone server + static assets + public.
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
USER nextjs
EXPOSE 3000
CMD ["node", "server.js"]
