import * as React from "react";
import { cn } from "@/lib/utils";

/**
 * Native <select> styled to match Input — accessible by default (keyboard,
 * screen readers) and zero-JS. Replaces the copy-pasted select classNames across
 * admin pages (a Radix combobox can come later if typeahead is needed).
 */
const Select = React.forwardRef<HTMLSelectElement, React.SelectHTMLAttributes<HTMLSelectElement>>(
  ({ className, children, ...props }, ref) => (
    <select
      ref={ref}
      className={cn(
        "flex h-9 w-full rounded-md border border-input bg-background px-3 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      {...props}
    >
      {children}
    </select>
  ),
);
Select.displayName = "Select";

export { Select };
