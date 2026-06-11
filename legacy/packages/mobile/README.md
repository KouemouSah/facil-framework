# Facil — Mobile App

Mobile client for **Facil**, the digital services platform. React Native + Expo SDK 54, consuming the FastAPI backend at `packages/backend/`.

> Part of the `taxasge` monorepo. See repository root `CLAUDE.md` for project-wide rules.

## Stack

| Concern | Choice |
|---------|--------|
| Runtime | React Native 0.81 (Hermes) on iOS + Android |
| Framework | Expo SDK 54 (managed workflow with custom dev clients) |
| Routing | Expo Router (file-based, `src/app/**`) |
| State | TanStack Query (server) + Zustand (client) + MMKV (persisted) |
| UI | React Native Paper (Material Design 3) |
| Forms | React Hook Form + Zod |
| i18n | i18next (es / fr / en) |
| HTTP | Axios with interceptors (`src/core/api/client.ts`) |
| Tokens | `expo-secure-store` (refresh) + MMKV (access) |
| Push | `expo-notifications` for permissions/token retrieval; backend talks **FCM/APNs directly** (not Expo Push Service) |

## Build & Deploy Pipelines

The mobile app uses **two independent pipelines** that work together:

### 1. EAS Build (artefact production — runs on expo.dev cloud)

All `npm run build:*` scripts dispatch to the Expo cloud build service (https://expo.dev). The local terminal only orchestrates and prints the build URL — actual compilation, signing, and artefact storage happen on Expo's infrastructure. Builds keep running even if you close the terminal.

Profiles live in `eas.json`. Per-platform and `:all` (Android + iOS in parallel) variants are exposed:

```bash
# Single platform (Android by default to match Play Store flow)
npm run build:dev          # development profile, Android APK + dev client
npm run build:preview      # preview profile, Android APK
npm run build:prod         # production profile, Android AAB

# iOS only
npm run build:dev:ios
npm run build:preview:ios
npm run build:prod:ios

# Both platforms in parallel — single command, two cloud jobs
npm run build:dev:all
npm run build:preview:all
npm run build:prod:all
```

`build:dev:ios` (and `:all` for development) builds an iOS Simulator binary by default — see `eas.json` `development.ios.simulator: true`. Switch to a real-device profile when going to TestFlight.

You can also run any of these directly: `eas build --profile <name> --platform <android|ios|all>`.

**Never** run `expo prebuild` and build natively unless debugging a native module locally — EAS handles iOS/Android toolchains in the cloud.

### 2. GitHub Actions (CI quality gates + EAS dispatch)

Two workflows ship in `.github/workflows/`:

| Workflow | Purpose |
|----------|---------|
| `mobile-build.yml` | Native Android build directly on the GitHub runner (Gradle). Faster feedback for Android-only iterations; produces `*.apk` + `*.aab` as workflow artefacts. |
| `mobile-eas-build.yml` | Dispatches an EAS Cloud build (Android + iOS in parallel). Use for cross-platform release candidates and store submissions. Requires the `EXPO_TOKEN` secret. |

CI quality gates (always-on):

- **Type check** — `npm run type-check` (must be 0 errors).
- **Lint** — `npm run lint` (max-warnings 100).
- **OpenAPI drift** — regenerate `openapi-types.ts` against staging and fail if it diverges from the committed file (planned).

`mobile-eas-build.yml` is triggered by:
- **Manual dispatch** (`workflow_dispatch`) with a profile + platform selector.
- **Tag push** (`v*.*.*`) → automatically builds both platforms with the `production` profile.

> **Rule** (CLAUDE.md): no manual cloud builds for the backend (`gcloud`). Mobile follows the same spirit — push to remote, let GitHub Actions + EAS run the pipeline. Local `eas build` invocations are reserved for ad-hoc preview builds.

## Local Development

```bash
# From repo root
npm install --legacy-peer-deps

# Then in this package
cd packages/mobile
npm start                  # Expo dev server (Metro)
npm run android            # Build & run on connected Android device
npm run ios                # Build & run on iOS simulator (macOS only)
```

## API & Backend Contract

Mobile consumes the FastAPI backend. The contract is enforced at three layers:

| Layer | File | Purpose |
|-------|------|---------|
| Paths | `src/core/api/endpoints.ts` | Single Source of Truth for every URL the app calls. Aligned with `packages/backend/app/main.py`. **Never hardcode paths in modules** — always import from `API_ENDPOINTS`. |
| Types (raw) | `src/core/api/openapi-types.ts` | Auto-generated from the backend's `/openapi.json`. **Do not edit by hand.** |
| Types (curated) | `src/core/api/api-types.ts` | Readable aliases over `openapi-types.ts` for the schemas mobile actually uses. |

### Regenerating types

```bash
npm run types:gen          # From staging (default — recommended for CI/PR work)
npm run types:gen-local    # From a local backend (uvicorn on :8000)
```

Both commands fetch `openapi.json` and overwrite `src/core/api/openapi-types.ts`. Commit the regenerated file alongside any backend schema change to keep the mobile contract in sync.

### Adding a new endpoint

1. Add the path to `endpoints.ts` under the matching backend module section, with a comment referencing the router file (e.g. `app/modules/auth/api/auth_routes.py`).
2. If the backend exposes a Pydantic response model, regenerate `openapi-types.ts` and add a curated alias in `api-types.ts`.
3. Use the path **only** via `API_ENDPOINTS.<module>.<key>` in the service file. No `/api/v1/...` literals in module code.

## Project Structure

```
packages/mobile/
├── eas.json                      # EAS Build profiles
├── app.json                      # Expo config (icons, splash, plugins)
├── src/
│   ├── app/                      # Expo Router file-based routing
│   ├── core/
│   │   ├── api/                  # client, endpoints, openapi-types, api-types
│   │   ├── auth/                 # auth provider, token storage
│   │   ├── i18n/                 # i18next setup + translations
│   │   └── ui/                   # theme, navigation primitives
│   ├── modules/                  # Feature modules (one per domain)
│   │   ├── auth/
│   │   ├── bundle-workflow/
│   │   ├── chatbot/
│   │   ├── dashboard/
│   │   ├── directory/
│   │   ├── fiscal-services/
│   │   ├── profile/
│   │   ├── service-requests/
│   │   └── wizard/
│   └── components/               # Cross-module shared UI
└── assets/                       # Fonts, images, lottie animations
```

Each module follows the convention `components/ + hooks/ + services/ + types/`.

## Quality Commands

```bash
npm run type-check    # tsc --noEmit (0 errors expected)
npm run lint          # expo lint
npm test              # When test suite is added
```

## Push Notifications (P1 architecture)

The app uses **native FCM (Android) and APNs (iOS) tokens**, not Expo Push Service:

- `expo-notifications` is used for **permissions UI** and to obtain the **native device token** via `getDevicePushTokenAsync()`.
- The token is registered via `POST /users/profile/device-token` and stored server-side.
- The backend (`packages/backend/`) calls FCM/APNs **directly** using `firebase-admin` and the APNs HTTP/2 API.
- This avoids the Expo Push proxy (one less external dependency) and supports data-only payloads for silent deep-link delivery.

## Documentation

- Repository root: [`CLAUDE.md`](../../CLAUDE.md) — project-wide rules and architecture.
- Phase plans: `.claude/plans/MOBILE_USER_PHASE_*.md`.
- Backend contract: regenerate via `npm run types:gen`, source = `app/main.py`.
