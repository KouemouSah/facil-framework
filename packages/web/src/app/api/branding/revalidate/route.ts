import { revalidateTag } from "next/cache";
import { NextResponse } from "next/server";

// Invalidate the cached public branding (see lib/server/backend.getBranding) so
// the next render re-themes immediately after an admin saves branding. Called by
// the settings page on save; cheap and idempotent.
export async function POST() {
  revalidateTag("branding");
  return NextResponse.json({ revalidated: true });
}
