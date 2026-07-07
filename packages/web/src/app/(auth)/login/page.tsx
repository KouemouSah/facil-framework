import { Suspense } from "react";
import { getBranding } from "@/lib/server/backend";
import { LoginForm } from "./login-form";

// Server wrapper: reads the public `self_registration_enabled` flag once (SSR,
// cached) so the client form can conditionally offer a "Create account" link
// without a client round-trip or flash.
export default async function LoginPage() {
  const { self_registration_enabled } = await getBranding();
  return (
    <Suspense>
      <LoginForm selfRegistration={self_registration_enabled} />
    </Suspense>
  );
}
