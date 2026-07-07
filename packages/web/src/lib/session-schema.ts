import { z } from "zod";

/**
 * Runtime schema for the BFF `/session` payload (audit 9). The hook parses the
 * response through this at the trust boundary and fails SAFE to an
 * unauthenticated session on any mismatch — a hostile or malformed body can
 * never yield a truthy `authenticated` or crash a consumer that assumes shape.
 * Unknown keys are stripped (forward-compatible with backend additions).
 */
export const AccountRoleSchema = z.object({
  role_id: z.string(),
  organization_id: z.string().nullable(),
  org_unit_id: z.string().nullable(),
  site_id: z.string().nullable(),
});

export const SessionSchema = z.object({
  authenticated: z.boolean(),
  break_glass: z.boolean().optional(),
  account: z
    .object({
      id: z.string(),
      email: z.string().optional(),
      display_name: z.string().optional(),
      account_number: z.string().optional(),
      email_verified: z.boolean().optional(),
    })
    .optional(),
  roles: z.array(AccountRoleSchema).optional(),
  idp: z.string().nullable().optional(),
});

export type AccountRole = z.infer<typeof AccountRoleSchema>;
export type Session = z.infer<typeof SessionSchema>;

export function parseSession(raw: unknown): Session {
  const r = SessionSchema.safeParse(raw);
  return r.success ? r.data : { authenticated: false };
}

/**
 * Whether to nudge the signed-in user to verify their email (P7 in-app banner).
 * True only for a real authenticated account that HAS an email and is explicitly
 * unverified. Fail-safe: break-glass, NIU-only accounts (no email), and an
 * unknown/absent `email_verified` never trigger the nag.
 */
export function needsEmailVerification(s: Session): boolean {
  return !!s.authenticated && !s.break_glass
    && !!s.account?.email && s.account?.email_verified === false;
}
