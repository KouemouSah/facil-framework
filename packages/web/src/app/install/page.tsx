"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const PROFILES = ["empty", "private-services-company", "gov-emergent-country", "saas-multitenant", "banking"];

export default function InstallPage() {
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const [adminToken, setAdminToken] = useState("");
  const [profile, setProfile] = useState("empty");
  const [appName, setAppName] = useState("Facil");
  const [primaryColor, setPrimaryColor] = useState("#2563eb");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  // If already installed, the installer is closed.
  useEffect(() => {
    fetch("/api/bff/api/v1/system/install-status")
      .then((r) => r.json())
      .then((s) => { if (s.installed) router.replace("/login"); })
      .catch(() => undefined);
  }, [router]);

  async function finish() {
    setBusy(true);
    setError("");
    const res = await fetch("/api/install", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ adminToken, profile, appName, primaryColor, email, password }),
    });
    setBusy(false);
    if (res.ok) router.replace("/login");
    else {
      const d = await res.json().catch(() => ({}));
      setError(
        d.error === "invalid_admin_token" ? "Invalid admin (break-glass) token."
        : d.error === "register_failed" || typeof d.error === "string" ? `Could not create admin: ${d.error}`
        : "Install failed.",
      );
      if (d.error === "invalid_admin_token") setStep(1);
    }
  }

  return (
    <main className="grid min-h-screen place-items-center bg-muted/40 p-4">
      <Card className="w-full max-w-lg">
        <CardHeader>
          <CardTitle className="text-lg">Set up Facil</CardTitle>
          <CardDescription>First-run installation · step {step} of 3</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {step === 1 && (
            <div className="space-y-3">
              <p className="text-sm text-muted-foreground">
                Paste the bootstrap admin token (from your deployment secrets) to authorize setup.
              </p>
              <div className="space-y-1.5">
                <Label htmlFor="tok">Admin (break-glass) token</Label>
                <Input id="tok" type="password" value={adminToken}
                  onChange={(e) => setAdminToken(e.target.value)} />
              </div>
              <div className="flex justify-end">
                <Button disabled={!adminToken} onClick={() => setStep(2)}>Continue</Button>
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="space-y-3">
              <div className="space-y-1.5">
                <Label htmlFor="profile">Profile</Label>
                <select id="profile" value={profile} onChange={(e) => setProfile(e.target.value)}
                  className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm">
                  {PROFILES.map((p) => <option key={p} value={p}>{p}</option>)}
                </select>
              </div>
              <div className="grid grid-cols-[1fr_auto] gap-3">
                <div className="space-y-1.5">
                  <Label htmlFor="appName">App name</Label>
                  <Input id="appName" value={appName} onChange={(e) => setAppName(e.target.value)} />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="color">Accent</Label>
                  <input id="color" type="color" value={primaryColor}
                    onChange={(e) => setPrimaryColor(e.target.value)}
                    className="h-9 w-12 rounded-md border border-input bg-background" />
                </div>
              </div>
              <div className="flex justify-between">
                <Button variant="ghost" onClick={() => setStep(1)}>Back</Button>
                <Button onClick={() => setStep(3)}>Continue</Button>
              </div>
            </div>
          )}

          {step === 3 && (
            <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); finish(); }}>
              <p className="text-sm text-muted-foreground">Create the first administrator.</p>
              <div className="space-y-1.5">
                <Label htmlFor="email">Admin email</Label>
                <Input id="email" type="email" required value={email}
                  onChange={(e) => setEmail(e.target.value)} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="pw">Admin password</Label>
                <Input id="pw" type="password" autoComplete="new-password" required value={password}
                  onChange={(e) => setPassword(e.target.value)} />
              </div>
              {error && <p className="text-sm text-destructive">{error}</p>}
              <div className="flex justify-between">
                <Button type="button" variant="ghost" onClick={() => setStep(2)}>Back</Button>
                <Button type="submit" disabled={busy}>{busy ? "Installing…" : "Finish setup"}</Button>
              </div>
            </form>
          )}
        </CardContent>
      </Card>
    </main>
  );
}
