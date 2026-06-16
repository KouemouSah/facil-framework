"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const OIDC_ENABLED = process.env.NEXT_PUBLIC_OIDC_ENABLED === "1";

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const next = params.get("next") || "/";
  const expired = params.has("next"); // arrived here from a 401 redirect

  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [totp, setTotp] = useState("");
  const [needTotp, setNeedTotp] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ identifier, password, totp_code: totp || undefined }),
      });
      const data = await res.json().catch(() => ({}));
      if (data.totp_required) {
        setNeedTotp(true);
        setError("");
      } else if (res.ok) {
        router.replace(next);
      } else if (res.status === 423) {
        setError("Account temporarily locked. Try again later.");
      } else {
        setError("Invalid credentials.");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
      <Card className="w-full max-w-sm">
        <CardHeader className="text-center">
          <span className="mx-auto grid h-10 w-10 place-items-center rounded-lg bg-primary text-primary-foreground">
            F
          </span>
          <CardTitle className="text-lg">Sign in to Facil</CardTitle>
          <CardDescription>Use your email or ID number</CardDescription>
        </CardHeader>
        <CardContent>
          {expired && (
            <p className="mb-4 rounded-md bg-muted px-3 py-2 text-xs text-muted-foreground">
              Your session expired — please sign in again.
            </p>
          )}
          <form onSubmit={submit} className="space-y-3">
            <div className="space-y-1.5">
              <Label htmlFor="identifier">Email or ID</Label>
              <Input id="identifier" autoComplete="username" required
                value={identifier} onChange={(e) => setIdentifier(e.target.value)}
                disabled={needTotp} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="password">Password</Label>
              <Input id="password" type="password" autoComplete="current-password" required
                value={password} onChange={(e) => setPassword(e.target.value)}
                disabled={needTotp} />
            </div>
            {needTotp && (
              <div className="space-y-1.5">
                <Label htmlFor="totp">Two-factor code</Label>
                <Input id="totp" inputMode="numeric" autoComplete="one-time-code" autoFocus
                  placeholder="123456 or backup code"
                  value={totp} onChange={(e) => setTotp(e.target.value)} />
              </div>
            )}
            {error && <p className="text-sm text-destructive">{error}</p>}
            <Button type="submit" className="w-full" disabled={busy}>
              {busy ? "Signing in…" : "Sign in"}
            </Button>
          </form>

          {OIDC_ENABLED && (
            <Button asChild variant="outline" className="mt-3 w-full">
              <a href="/api/auth/oidc/start">Sign in with your organization (SSO)</a>
            </Button>
          )}

          <div className="mt-4 flex justify-between text-xs text-muted-foreground">
            <Link href="/forgot-password" className="hover:text-foreground">Forgot password?</Link>
            <Link href="/verify-email" className="hover:text-foreground">Verify email</Link>
          </div>
        </CardContent>
      </Card>
  );
}

export default function LoginPage() {
  return (
    <main className="grid min-h-screen place-items-center bg-muted/40 p-4">
      <Suspense>
        <LoginForm />
      </Suspense>
    </main>
  );
}
