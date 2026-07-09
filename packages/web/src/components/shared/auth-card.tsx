import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";

/**
 * Shared shell for the unauthenticated auth screens (login, register, forgot /
 * reset password, email verification) — audit 21 DRY. One branded, centered card
 * so every auth screen looks identical; pages supply only their title/description
 * and body. The centered `<main>` wrapper AND the white-label brand logo live in
 * `app/(auth)/layout.tsx` (Phase A1) — the card no longer hardcodes an "F" tile.
 */
export function AuthCard({
  title, description, children,
}: {
  title: React.ReactNode;
  description?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <Card className="w-full max-w-sm">
      <CardHeader className="text-center">
        <CardTitle className="text-lg">{title}</CardTitle>
        {description && <CardDescription>{description}</CardDescription>}
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}
