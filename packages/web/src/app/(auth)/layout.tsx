import { getBranding } from "@/lib/server/backend";
import { BrandLogo } from "@/components/shared";

// Shared shell for the unauthenticated auth screens (login, register, forgot /
// reset password, email verification). The route group `(auth)` does NOT change
// the URLs (`/login`, `/register`, …) — it only lets these pages share one
// centered layout instead of each repeating the wrapper (audit 21 DRY).
//
// White-label (Config-UI-first, Phase A1): a deployment brands these screens via
// the Branding editor — `login_background_url` paints the backdrop (previously a
// PHANTOM field: editable but never rendered), and the logo sits above the card
// so every auth screen is consistently branded (was a hardcoded "F" tile in
// AuthCard). Branding is fetched server-side (cached, fail-safe defaults).
export default async function AuthLayout({ children }: { children: React.ReactNode }) {
  const b = await getBranding();
  const appName = b.app_name || "Facil";
  const hasBg = Boolean(b.login_background_url);

  return (
    <main
      className={`relative grid min-h-screen place-items-center p-4 ${hasBg ? "bg-cover bg-center" : "bg-muted/40"}`}
      style={hasBg ? { backgroundImage: `url("${b.login_background_url}")` } : undefined}
    >
      {/* Legibility scrim over a custom background so the card + logo stay readable
          regardless of the uploaded image (and theme-aware via bg-background). */}
      {hasBg && <div aria-hidden className="absolute inset-0 bg-background/70 backdrop-blur-sm" />}

      <div className="relative flex flex-col items-center gap-6">
        <BrandLogo
          light={b.logo_url}
          dark={b.logo_dark_url}
          fallback="/brand-logo.png"
          alt={appName}
          width={160}
          height={44}
          priority
          className="h-11 w-auto object-contain"
        />
        {children}
      </div>
    </main>
  );
}
