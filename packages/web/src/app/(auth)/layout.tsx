// Shared shell for the unauthenticated auth screens (login, register, forgot /
// reset password, email verification). The route group `(auth)` does NOT change
// the URLs (`/login`, `/register`, …) — it only lets these pages share one
// centered layout instead of each repeating the wrapper (audit 21 DRY).
export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <main className="grid min-h-screen place-items-center bg-muted/40 p-4">
      {children}
    </main>
  );
}
