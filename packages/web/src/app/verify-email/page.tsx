"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

function Verify() {
  const token = useSearchParams().get("token") || "";
  const [state, setState] = useState<"idle" | "ok" | "error">("idle");

  useEffect(() => {
    if (!token) return;
    fetch("/api/bff/api/v1/auth/email-verification/confirm", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token }),
    })
      .then((r) => setState(r.ok ? "ok" : "error"))
      .catch(() => setState("error"));
  }, [token]);

  return (
    <Card className="w-full max-w-sm">
      <CardHeader>
        <CardTitle className="text-lg">Email verification</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        {!token && <p className="text-muted-foreground">Open the link from your verification email.</p>}
        {state === "ok" && <p className="text-foreground">Your email is verified. ✓</p>}
        {state === "error" && <p className="text-destructive">Invalid or expired verification link.</p>}
        {state === "idle" && token && <p className="text-muted-foreground">Verifying…</p>}
        <Link href="/login" className="block text-xs text-muted-foreground hover:text-foreground">
          Continue to sign in
        </Link>
      </CardContent>
    </Card>
  );
}

export default function VerifyEmailPage() {
  return (
    <main className="grid min-h-screen place-items-center bg-muted/40 p-4">
      <Suspense>
        <Verify />
      </Suspense>
    </main>
  );
}
