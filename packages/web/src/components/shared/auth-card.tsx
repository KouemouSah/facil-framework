import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";

/**
 * Shared shell for the unauthenticated auth screens (login, register, forgot /
 * reset password, email verification) — audit 21 DRY. One branded, centered card
 * so every auth screen looks identical; pages supply only their title/description
 * and body. The centered `<main>` wrapper lives in `app/(auth)/layout.tsx`.
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
        <span className="mx-auto grid size-10 place-items-center rounded-lg bg-primary text-primary-foreground">
          F
        </span>
        <CardTitle className="text-lg">{title}</CardTitle>
        {description && <CardDescription>{description}</CardDescription>}
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}
