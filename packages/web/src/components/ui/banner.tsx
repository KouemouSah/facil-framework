import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { AlertCircle, CheckCircle2, Info, TriangleAlert, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

// In-page alert/banner (a11y: role=alert for errors so screen readers announce,
// role=status otherwise). Themeable tokens, optional dismiss. Used for the
// email-verify banner, optimistic-concurrency reloads, page-level errors.
const bannerVariants = cva(
  "flex items-start gap-3 rounded-lg border px-4 py-3 text-sm",
  {
    variants: {
      variant: {
        info: "border-primary/20 bg-primary/5 text-foreground",
        success: "border-emerald-500/30 bg-emerald-500/8 text-foreground",
        warning: "border-amber-500/30 bg-amber-500/10 text-foreground",
        error: "border-destructive/30 bg-destructive/8 text-foreground",
      },
    },
    defaultVariants: { variant: "info" },
  },
);

const ICONS = {
  info: Info,
  success: CheckCircle2,
  warning: TriangleAlert,
  error: AlertCircle,
} as const;

export interface BannerProps
  extends Omit<React.HTMLAttributes<HTMLDivElement>, "title">,
    VariantProps<typeof bannerVariants> {
  title?: React.ReactNode;
  onDismiss?: () => void;
  /** Accessible label for the dismiss button — pass a translated string (i18n). */
  dismissLabel?: string;
  /** Action node rendered on the trailing edge (e.g. a "Resend" button). */
  action?: React.ReactNode;
}

function Banner({ className, variant = "info", title, onDismiss, dismissLabel = "Dismiss", action, children, ...props }: BannerProps) {
  const Icon = ICONS[variant ?? "info"];
  return (
    <div
      role={variant === "error" ? "alert" : "status"}
      className={cn(bannerVariants({ variant }), className)}
      {...props}
    >
      <Icon className="mt-0.5 size-4 shrink-0" aria-hidden />
      <div className="min-w-0 flex-1">
        {title && <p className="font-medium">{title}</p>}
        {children && <div className="text-muted-foreground">{children}</div>}
      </div>
      {action && <div className="shrink-0">{action}</div>}
      {onDismiss && (
        <Button variant="ghost" size="icon" className="-mr-2 -mt-1 size-7 shrink-0" onClick={onDismiss} aria-label={dismissLabel}>
          <X className="size-4" />
        </Button>
      )}
    </div>
  );
}

export { Banner, bannerVariants };
