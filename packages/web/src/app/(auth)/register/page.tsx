import { redirect } from "next/navigation";
import { getBranding } from "@/lib/server/backend";
import { RegisterForm } from "./register-form";

// Server gate: self-registration is opt-in per tenant (default off). When the
// backend flag is false, the route redirects to /login — the form is never
// reachable, mirroring the backend's 403 on POST /auth/register (defence in depth).
export default async function RegisterPage() {
  const { self_registration_enabled } = await getBranding();
  if (!self_registration_enabled) redirect("/login");
  return <RegisterForm />;
}
